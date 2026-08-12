using AtlasFlow.Application;
using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Planning;

using Microsoft.Extensions.DependencyInjection;

namespace AtlasFlow.Integration.Tests;

/// <summary>
/// The second vertical slice: plan a Goal, lock it, run it, watch the events.
/// </summary>
/// <remarks>
/// <para>
/// This exists for <see cref="IRunService.WatchAsync"/>. Streaming is the
/// largest integration risk in the product — ordering, cancellation, replay,
/// what a late subscriber sees — and it is the one part of the contract that
/// cannot be faked convincingly. Everything else here is scaffolding to give
/// it something real to stream.
/// </para>
/// <para>
/// Each test builds a throwaway Atlas project with one Goal, so the run is
/// real without depending on this repository's own Goals.
/// </para>
/// </remarks>
public sealed class RunSliceTests : IAsyncLifetime
{
    private readonly string _root =
        Path.Combine(Path.GetTempPath(), $"atlas-run-{Guid.NewGuid():N}");

    private ServiceProvider _provider = null!;

    public async Task InitializeAsync()
    {
        WriteProject();
        ServiceCollection services = new();
        services.AddAtlasFlow(_root);
        _provider = services.BuildServiceProvider();
        await _provider.InitializeAtlasFlowAsync();
    }

    public async Task DisposeAsync()
    {
        await _provider.DisposeAsync();
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    private void Write(string relative, string content)
    {
        string path = Path.Combine(_root, relative);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    /// <summary>A minimal but genuinely valid Atlas project with one Goal.</summary>
    private void WriteProject()
    {
        Write("PROJECT_MANIFEST.yaml", """
            framework:
              name: project-atlas-framework
              version: "0.1.0"
            project:
              id: run-slice
              name: Run Slice
            """);
        Write("ENTRYPOINT.md", "# Entry");
        Write("PROJECT_STATE.md", "# State");
        Write("docs/ATLAS.md", "# Atlas");
        Write(".ai/context/project-profile.yaml", "id: run-slice");
        Write(".ai/agents/manifest.yaml", "agents: []");
        Write(".ai/skills/manifest.yaml", "skills: []");
        Write(".ai/recipes/manifest.yaml", "recipes: []");
        Write(".ai/orchestration/model-policy.yaml", "version: 1");
        Write(".ai/orchestration/autonomy-policy.yaml", "default: agentic");
        Write(".ai/orchestration/orchestrator.yaml", "version: 1");
        Write(".ai/orchestration/fallbacks.yaml", "version: 1");
        Write(".ai/goals/P01/P01-G01.yaml", """
            id: P01-G01
            phase: P01
            title: Do the thing
            state: ACTIVE
            objective: Prove the event stream carries a real run
            acceptance:
              - The first criterion holds
              - The second criterion holds
              - The third criterion holds
            gates:
              build: required
              tests: required
              review: optional
              documentation: optional
            """);
        Directory.CreateDirectory(Path.Combine(_root, ".git"));
    }

    private IPlanService Plans => _provider.GetRequiredService<IPlanService>();

    private IRunService Runs => _provider.GetRequiredService<IRunService>();

    private static readonly GoalId TheGoal = new("P01-G01");

    private async Task<Plan> LockedPlanAsync()
    {
        Plan draft = await Plans.CreateAsync(
            new CreatePlanRequest { GoalId = TheGoal },
            CancellationToken.None);

        return await Plans.LockAsync(draft.Id, CancellationToken.None);
    }

    // --- planning -------------------------------------------------------------

    [Fact]
    public async Task EveryAcceptanceCriterionBecomesATask()
    {
        // The contract that keeps a plan answerable to its Goal. A planner
        // that drops a criterion produces a run that can succeed while the
        // Goal remains unmet.
        Plan plan = await Plans.CreateAsync(new CreatePlanRequest { GoalId = TheGoal }, CancellationToken.None);

        Assert.Equal(3, plan.Tasks.Count);
        Assert.Contains(plan.Tasks, task => task.Objective == "The second criterion holds");
    }

    [Fact]
    public async Task ATaskCarriesTheGoalsRequiredGates()
    {
        Plan plan = await Plans.CreateAsync(new CreatePlanRequest { GoalId = TheGoal }, CancellationToken.None);

        // review and documentation are declared optional in the fixture.
        Assert.Equal([GateKind.Build, GateKind.Tests], plan.Tasks[0].Gates);
    }

    [Fact]
    public async Task PlanningAnUnknownGoalIsRefused() =>
        await Assert.ThrowsAsync<PlanStateException>(
            () => Plans.CreateAsync(new CreatePlanRequest { GoalId = new GoalId("P99-G99") }, CancellationToken.None));

    [Fact]
    public async Task ADraftBecomesLockedOnce()
    {
        Plan locked = await LockedPlanAsync();

        Assert.Equal(PlanState.Locked, locked.State);
        await Assert.ThrowsAsync<PlanStateException>(() => Plans.LockAsync(locked.Id, CancellationToken.None));
    }

    // --- running ---------------------------------------------------------------

    [Fact]
    public async Task ARunMustNameALockedPlan()
    {
        Plan draft = await Plans.CreateAsync(new CreatePlanRequest { GoalId = TheGoal }, CancellationToken.None);

        // Accepting a draft would make locking decorative.
        await Assert.ThrowsAsync<PlanStateException>(
            () => Runs.StartAsync(
                new StartRunRequest { GoalId = TheGoal, PlanId = draft.Id },
                CancellationToken.None));
    }

    [Fact]
    public async Task ALockedPlanIsConsumedWhenItIsScheduled()
    {
        Plan locked = await LockedPlanAsync();
        await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        Plan? after = await Plans.FindAsync(locked.Id, CancellationToken.None);

        // One reviewed plan must not produce two runs and two sets of evidence
        // that each claim to be about it.
        Assert.Equal(PlanState.Consumed, after!.State);
    }

    [Fact]
    public async Task ARunReachesATerminalStateAndItsTasksSucceed()
    {
        Plan locked = await LockedPlanAsync();
        Run started = await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        await DrainAsync(started.Id);

        RunDetail? detail = await Runs.FindAsync(started.Id, CancellationToken.None);

        Assert.NotNull(detail);
        Assert.Equal(3, detail.Tasks.Count);
        Assert.All(detail.Tasks, task => Assert.Equal(TaskState.Succeeded, task.State));
        Assert.Equal(RunState.Verifying, detail.Run.State);
    }

    // --- the event stream --------------------------------------------------------

    [Fact]
    public async Task WatchingDeliversTheWholeRunAndThenCompletes()
    {
        Plan locked = await LockedPlanAsync();
        Run started = await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        List<DomainEvent> seen = await DrainAsync(started.Id);

        // The loop above ended on its own. A stream that never completes makes
        // every caller invent its own stopping rule.
        Assert.NotEmpty(seen);
        Assert.Contains(seen, e => e.Type == EventType.RunStarted);
        Assert.Equal(3, seen.Count(e => e.Type == EventType.TaskSucceeded));
    }

    [Fact]
    public async Task NoEventIsDeliveredTwice()
    {
        Plan locked = await LockedPlanAsync();
        Run started = await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        List<DomainEvent> seen = await DrainAsync(started.Id);

        // Subscribing before the replay can only produce duplicates. That is
        // the correct trade — the other order loses events — but the
        // duplicates have to be removed.
        Assert.Equal(seen.Select(e => e.Id).Distinct().Count(), seen.Count);
    }

    [Fact]
    public async Task EventsArriveInTheOrderTheyHappened()
    {
        Plan locked = await LockedPlanAsync();
        Run started = await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        List<DomainEvent> seen = await DrainAsync(started.Id);

        Assert.Equal(EventType.RunStarted, seen[0].Type);
        int firstSuccess = seen.FindIndex(e => e.Type == EventType.TaskSucceeded);
        int firstReady = seen.FindIndex(e => e.Type == EventType.TaskReady);
        Assert.True(
            firstReady >= 0 && firstReady < firstSuccess,
            $"firstReady={firstReady}, firstSuccess={firstSuccess}; "
            + string.Join(", ", seen.Select(domainEvent => domainEvent.Type)));
    }

    [Fact]
    public async Task ALateWatcherStillSeesTheWholeHistory()
    {
        // The replay half. A view opened after a run finished must render the
        // same thing as one that watched it live.
        Plan locked = await LockedPlanAsync();
        Run started = await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        await DrainAsync(started.Id);
        List<DomainEvent> replayed = await DrainAsync(started.Id);

        Assert.Contains(replayed, e => e.Type == EventType.RunStarted);
        Assert.Equal(3, replayed.Count(e => e.Type == EventType.TaskSucceeded));
    }

    [Fact]
    public async Task WatchingCanBeAbandonedWithoutAffectingTheRun()
    {
        Plan locked = await LockedPlanAsync();
        Run started = await Runs.StartAsync(
            new StartRunRequest { GoalId = TheGoal, PlanId = locked.Id },
            CancellationToken.None);

        using (CancellationTokenSource giveUp = new())
        {
            await giveUp.CancelAsync();
            await Assert.ThrowsAnyAsync<OperationCanceledException>(async () =>
            {
                await foreach (DomainEvent _ in Runs.WatchAsync(started.Id, giveUp.Token))
                {
                    // Cancelled before the first read.
                }
            });
        }

        // The run is not the watcher's. Walking away from a stream must not
        // stop the work.
        List<DomainEvent> seen = await DrainAsync(started.Id);
        Assert.Contains(seen, e => e.Type == EventType.TaskSucceeded);
    }

    /// <summary>Reads a run's stream to completion, with a ceiling.</summary>
    /// <remarks>
    /// The timeout is the test's own safety net. If the stream fails to
    /// complete this fails on time rather than hanging the suite, and a
    /// hanging suite is how a streaming bug gets ignored.
    /// </remarks>
    private async Task<List<DomainEvent>> DrainAsync(RunId id)
    {
        using CancellationTokenSource timeout = new(TimeSpan.FromSeconds(20));
        List<DomainEvent> seen = [];

        await foreach (DomainEvent domainEvent in Runs.WatchAsync(id, timeout.Token))
        {
            seen.Add(domainEvent);
        }

        return seen;
    }
}
