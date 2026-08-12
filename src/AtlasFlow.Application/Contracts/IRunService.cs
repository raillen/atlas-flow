using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;

namespace AtlasFlow.Application.Contracts;

/// <summary>Starting runs, following them, and stopping them.</summary>
public interface IRunService
{
    /// <summary>Every run in the open project, newest first.</summary>
    Task<IReadOnlyList<Run>> ListAsync(CancellationToken cancellationToken = default);

    /// <summary>One run with its graph, attempts and recorded events.</summary>
    Task<RunDetail?> FindAsync(RunId id, CancellationToken cancellationToken = default);

    /// <summary>Schedules a run and returns immediately.</summary>
    /// <remarks>
    /// The returned run is in <see cref="RunState.Created"/>. Progress arrives
    /// through <see cref="WatchAsync"/>, not by polling
    /// <see cref="FindAsync"/> — polling is how a UI shows a run that finished
    /// four seconds ago as still running.
    /// </remarks>
    Task<Run> StartAsync(StartRunRequest request, CancellationToken cancellationToken = default);

    /// <summary>
    /// Asks a run to stop.
    /// </summary>
    /// <remarks>
    /// Cooperative and asynchronous. The run reaches
    /// <see cref="RunState.Cancelled"/> when its in-flight attempts have been
    /// torn down and their worktrees released; this method returning is not
    /// that moment. Watch for the state change.
    /// </remarks>
    Task CancelAsync(RunId id, CancellationToken cancellationToken = default);

    /// <summary>
    /// The live event stream for one run.
    /// </summary>
    /// <remarks>
    /// <para>
    /// This is AG-UI. It replaces the server-sent-events endpoint the webview
    /// subscribed to; the event model did not change, only the transport, and
    /// the transport existed to cross a process boundary that is gone.
    /// </para>
    /// <para>
    /// The stream replays everything already recorded for the run before it
    /// begins yielding live events, so a UI that attaches late still renders a
    /// complete history. It completes when the run reaches a terminal state.
    /// </para>
    /// </remarks>
    IAsyncEnumerable<DomainEvent> WatchAsync(RunId id, CancellationToken cancellationToken = default);

    /// <summary>
    /// Every event in the project, across runs.
    /// </summary>
    /// <remarks>
    /// What the workspace status bar watches so it can show work in flight
    /// without the user having opened a run first.
    /// </remarks>
    IAsyncEnumerable<DomainEvent> WatchAllAsync(CancellationToken cancellationToken = default);
}

/// <summary>What to run.</summary>
public sealed record StartRunRequest
{
    public required GoalId GoalId { get; init; }

    /// <summary>
    /// The locked plan to execute.
    /// </summary>
    /// <remarks>
    /// Optional only for the CLI, which may plan and run in one step. A run
    /// started from the UI always names a plan the user reviewed and locked.
    /// </remarks>
    public PlanId? PlanId { get; init; }

    public string Runner { get; init; } = "dummy";

    public string IntegrationTarget { get; init; } = "main";
}

/// <summary>A run and everything recorded about it.</summary>
public sealed record RunDetail
{
    public required Run Run { get; init; }

    public IReadOnlyList<RunTask> Tasks { get; init; } = [];

    public IReadOnlyList<Attempt> Attempts { get; init; } = [];

    public IReadOnlyList<DomainEvent> Events { get; init; } = [];
}
