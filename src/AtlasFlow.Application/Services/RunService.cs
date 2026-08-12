using System.Collections.Concurrent;
using System.Runtime.CompilerServices;
using System.Text.Json.Nodes;
using System.Threading.Channels;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Planning;
using AtlasFlow.Orchestration;
using AtlasFlow.Orchestration.Execution;
using AtlasFlow.Persistence;

namespace AtlasFlow.Application.Services;

/// <summary>Starting runs, following them, and stopping them.</summary>
public sealed class RunService : IRunService, IDisposable
{
    private readonly AtlasFlowOptions _options;
    private readonly RunRepository _runs;
    private readonly PlanRepository _plans;
    private readonly EventStore _events;
    private readonly ITaskRunner _runner;

    /// <summary>One token per run in flight, so <c>CancelAsync</c> has something to pull.</summary>
    private readonly ConcurrentDictionary<RunId, CancellationTokenSource> _inFlight = new();

    public RunService(
        AtlasFlowOptions options,
        RunRepository runs,
        PlanRepository plans,
        EventStore events,
        ITaskRunner runner)
    {
        _options = options;
        _runs = runs;
        _plans = plans;
        _events = events;
        _runner = runner;
    }

    private string ProjectId => new DirectoryInfo(_options.ProjectRoot).Name;

    public async Task<IReadOnlyList<Run>> ListAsync(CancellationToken cancellationToken = default) =>
        await _runs.ListAsync(ProjectId, cancellationToken).ConfigureAwait(false);

    public async Task<RunDetail?> FindAsync(RunId id, CancellationToken cancellationToken = default)
    {
        Run? run = await _runs.FindAsync(id, cancellationToken).ConfigureAwait(false);
        if (run is null)
        {
            return null;
        }

        return new RunDetail
        {
            Run = run,
            Tasks = await _runs.ListTasksAsync(id, cancellationToken).ConfigureAwait(false),
            Attempts = await _runs.ListAttemptsAsync(id, cancellationToken).ConfigureAwait(false),
            Events = await _events.ListForRunAsync(id, cancellationToken).ConfigureAwait(false),
        };
    }

    public async Task<Run> StartAsync(StartRunRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        Plan plan = await LockedPlanFor(request, cancellationToken).ConfigureAwait(false);

        Run run = new()
        {
            Id = IdFactory.NewRun(),
            ProjectId = ProjectId,
            GoalId = plan.GoalId,
            GoalRevision = plan.GoalRevision,
            State = RunState.Created,
            Autonomy = plan.Autonomy,
            CreatedAt = DateTimeOffset.UtcNow,
        };

        await _runs.SaveAsync(run, cancellationToken).ConfigureAwait(false);

        // The plan is spent the moment it is scheduled, not when the run ends.
        // That is what stops one reviewed plan producing two runs.
        await _plans.SaveAsync(plan with { State = PlanState.Consumed }, cancellationToken).ConfigureAwait(false);

        StartInBackground(run, plan);
        return run;
    }

    /// <remarks>
    /// The engine is not awaited, and the token deliberately does not come
    /// from the caller. <c>StartAsync</c> returns as soon as the run exists;
    /// tying the run's lifetime to the request that started it would cancel it
    /// the moment a view navigated away.
    /// </remarks>
    private void StartInBackground(Run run, Plan plan)
    {
        CancellationTokenSource source = new();
        _inFlight[run.Id] = source;

        RunEngine engine = new(_runs, new Scheduler(_runs, ProjectId), _runner);

        _ = Task.Run(
            async () =>
            {
                try
                {
                    await engine.ExecuteAsync(run, plan, source.Token).ConfigureAwait(false);
                }
#pragma warning disable CA1031 // Nothing is awaiting this. An escaping
                // exception would be an unobserved task and a run frozen in
                // RUNNING with no explanation anywhere.
                catch (Exception)
#pragma warning restore CA1031
                {
                    // The engine already records a failure as a task or run
                    // state. Reaching here means it could not, and there is
                    // nowhere better to put it than the run's own final state.
                }
                finally
                {
                    _inFlight.TryRemove(run.Id, out _);
                    source.Dispose();
                }
            },
            CancellationToken.None);
    }

    public async Task CancelAsync(RunId id, CancellationToken cancellationToken = default)
    {
        if (_inFlight.TryGetValue(id, out CancellationTokenSource? source))
        {
            await source.CancelAsync().ConfigureAwait(false);
            return;
        }

        // Not in flight in this process. It may be a run left RUNNING by a
        // crash, and refusing to close it would leave it looking active
        // forever.
        Run? run = await _runs.FindAsync(id, cancellationToken).ConfigureAwait(false);
        if (run is not null && !run.State.IsTerminal())
        {
            Scheduler scheduler = new(_runs, ProjectId);
            await scheduler.CancelRunAsync(run, "cancelled by request", cancellationToken).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// Recorded events first, then live ones, with nothing lost in between.
    /// </summary>
    /// <remarks>
    /// <para>
    /// The subscription is opened <em>before</em> the recorded events are read.
    /// The obvious order — read the log, then subscribe — drops every event
    /// that arrives during the read, and the window is exactly when a run is
    /// busiest. Subscribing first can only produce duplicates, which are
    /// cheap to remove; the other order loses events, which is not
    /// recoverable.
    /// </para>
    /// <para>
    /// The stream completes when the run reaches a terminal state, so a caller
    /// can <c>await foreach</c> to the end rather than deciding for itself when
    /// to stop watching.
    /// </para>
    /// </remarks>
    public async IAsyncEnumerable<DomainEvent> WatchAsync(
        RunId id,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        Channel<DomainEvent> live = Channel.CreateUnbounded<DomainEvent>(
            new UnboundedChannelOptions { SingleReader = true });

        using IDisposable subscription = _events.Subscribe((domainEvent, _) =>
        {
            if (domainEvent.RunId == id)
            {
                live.Writer.TryWrite(domainEvent);
            }

            return Task.CompletedTask;
        });

        HashSet<string> delivered = new(StringComparer.Ordinal);

        foreach (DomainEvent recorded in await _events.ListForRunAsync(id, cancellationToken).ConfigureAwait(false))
        {
            delivered.Add(recorded.Id);
            yield return recorded;

            if (StopsStream(recorded))
            {
                yield break;
            }
        }

        await foreach (DomainEvent domainEvent in live.Reader.ReadAllAsync(cancellationToken).ConfigureAwait(false))
        {
            if (!delivered.Add(domainEvent.Id))
            {
                continue;
            }

            yield return domainEvent;

            if (StopsStream(domainEvent))
            {
                yield break;
            }
        }
    }

    /// <inheritdoc />
    public async IAsyncEnumerable<DomainEvent> WatchAllAsync(
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        Channel<DomainEvent> live = Channel.CreateUnbounded<DomainEvent>(
            new UnboundedChannelOptions { SingleReader = true });

        using IDisposable subscription = _events.Subscribe((domainEvent, _) =>
        {
            live.Writer.TryWrite(domainEvent);
            return Task.CompletedTask;
        });

        await foreach (DomainEvent domainEvent in live.Reader.ReadAllAsync(cancellationToken).ConfigureAwait(false))
        {
            yield return domainEvent;
        }
    }

    /// <summary>
    /// Whether the run has reached a state the engine will not move it out of.
    /// </summary>
    /// <remarks>
    /// <para>
    /// Read from the run's actual state rather than guessed from an event
    /// payload. Matching on a serialized state name inside a payload was the
    /// first attempt and it was wrong twice over: it duplicated the state
    /// machine in a string comparison, and it missed the state the engine
    /// actually stops in.
    /// </para>
    /// <para>
    /// <see cref="RunState.Verifying"/> counts as a stopping point <em>only
    /// because verification is not ported</em>. A run legitimately reaches it
    /// and then waits for a gate evaluation that no code performs yet. When
    /// verification lands, Verifying stops being an endpoint and this method
    /// must lose that case — otherwise every run will appear to end one step
    /// before it does.
    /// </para>
    /// </remarks>
    private static bool IsWhereTheEngineStops(RunState state) =>
        state.IsTerminal() || state is RunState.Verifying or RunState.Blocked;

    private static bool StopsStream(DomainEvent domainEvent)
    {
        if (domainEvent.Payload["next"] is not JsonValue value
            || !value.TryGetValue<string>(out string? nextState)
            || !Enum.TryParse(nextState, ignoreCase: true, out RunState state))
        {
            return false;
        }

        return IsWhereTheEngineStops(state);
    }

    private async Task<Plan> LockedPlanFor(StartRunRequest request, CancellationToken cancellationToken)
    {
        if (request.PlanId is { } planId)
        {
            Plan plan = await _plans.FindAsync(planId, cancellationToken).ConfigureAwait(false)
                ?? throw new PlanStateException($"No plan '{planId}'");

            // A run from the UI always starts from a plan a person reviewed.
            // Accepting a draft would make locking decorative.
            return plan.State == PlanState.Locked
                ? plan
                : throw new PlanStateException($"Plan {planId} is {plan.State}, not LOCKED");
        }

        throw new PlanStateException(
            "A run must name a locked plan. Planning and running in one step is a CLI affordance "
            + "that is not ported yet.");
    }

    public void Dispose()
    {
        foreach (CancellationTokenSource source in _inFlight.Values)
        {
            source.Dispose();
        }

        _inFlight.Clear();
    }
}
