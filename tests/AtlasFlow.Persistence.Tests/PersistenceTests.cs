using System.Runtime.CompilerServices;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Planning;
using AtlasFlow.Domain.Verification;
using AtlasFlow.Persistence;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence.Tests;

/// <summary>
/// Operational state, against a real SQLite file.
/// </summary>
/// <remarks>
/// A temporary file rather than <c>:memory:</c>. Durability is the reason this
/// layer exists — run state has to survive a crash — and an in-memory database
/// cannot fail the way a file can.
/// </remarks>
public sealed class PersistenceTests : IAsyncLifetime
{
    private readonly string _databasePath =
        Path.Combine(Path.GetTempPath(), $"atlas-test-{Guid.NewGuid():N}", "state.db");

    private AtlasFlowDatabase _database = null!;
    private EventStore _events = null!;
    private RunRepository _runs = null!;
    private PlanRepository _plans = null!;
    private EvidenceRepository _evidence = null!;

    public async Task InitializeAsync()
    {
        _database = new AtlasFlowDatabase(_databasePath);
        await _database.InitializeAsync();
        _events = new EventStore(_database);
        _runs = new RunRepository(_database, _events);
        _plans = new PlanRepository(_database);
        _evidence = new EvidenceRepository(_database);
    }

    public async Task DisposeAsync()
    {
        await _database.DisposeAsync();
        string? directory = Path.GetDirectoryName(_databasePath);
        if (directory is not null && Directory.Exists(directory))
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    // --- fixtures ---------------------------------------------------------

    private static Run NewRun(RunState state = RunState.Created) => new()
    {
        Id = new RunId("run-1"),
        ProjectId = "proj-1",
        GoalId = new GoalId("P01-G01"),
        GoalRevision = "abc123",
        State = state,
        Autonomy = AutonomyLevel.Agentic,
        CreatedAt = DateTimeOffset.UtcNow,
    };

    private static DomainEvent NewEvent(EventType type = EventType.StateChange) => new()
    {
        Id = $"evt-{Guid.NewGuid():N}"[..16],
        Timestamp = DateTimeOffset.UtcNow,
        ProjectId = "proj-1",
        RunId = new RunId("run-1"),
        Type = type,
    };

    /// <summary>
    /// A fixed moment, so that two calls produce byte-identical plans.
    /// </summary>
    /// <remarks>
    /// <c>UtcNow</c> here made the immutability tests non-deterministic: two
    /// "identical" plans differed by microseconds and every comparison found a
    /// change.
    /// </remarks>
    private static readonly DateTimeOffset _fixedMoment =
        new(2026, 8, 11, 12, 0, 0, TimeSpan.Zero);

    private static Plan NewPlan(PlanState state = PlanState.Draft) => new()
    {
        Id = new PlanId("plan-1"),
        ProjectId = "proj-1",
        GoalId = new GoalId("P01-G01"),
        GoalRevision = "abc123",
        State = state,
        Autonomy = AutonomyLevel.Agentic,
        Runner = "dummy",
        IntegrationTarget = "main",
        CreatedAt = _fixedMoment,
        Context = new ContextPlan
        {
            Profile = ContextProfile.Medium,
            Strategy = ContextStrategy.ContextPack,
            Mode = ContextMode.Legacy,
            Budget = new ContextBudget
            {
                ContextTargetTokens = 8000,
                ContextHardTokens = 16000,
                OutputTargetTokens = 1500,
                OutputHardTokens = 3000,
                MaxExpansionRounds = 2,
                MaxDelegationDepth = 1,
            },
            Reasons = ["legacy-project", "default"],
            Source = "legacy-default",
        },
        Tasks =
        [
            new PlanTask
            {
                Id = new TaskId("task-1"),
                Objective = "port the thing",
                Risk = RiskLevel.Medium,
                IsParallelizable = true,
                WriteScope = [new ProjectPath("src/")],
                Gates = [GateKind.Build, GateKind.Tests],
                Capabilities = ["csharp"],
            },
        ],
    };

    // --- round trips ------------------------------------------------------

    [Fact]
    public async Task ARunSurvivesARoundTrip()
    {
        Run run = NewRun();
        await _runs.SaveAsync(run);

        Run? loaded = await _runs.FindAsync(run.Id);

        Assert.NotNull(loaded);
        Assert.Equal(run.GoalId, loaded.GoalId);
        Assert.Equal(RunState.Created, loaded.State);
        Assert.Equal(AutonomyLevel.Agentic, loaded.Autonomy);
    }

    [Fact]
    public async Task ATaskKeepsItsScopeAndDependencies()
    {
        await _runs.SaveAsync(NewRun());
        RunTask task = new()
        {
            Id = new TaskId("task-1"),
            RunId = new RunId("run-1"),
            Objective = "do the thing",
            State = TaskState.Planned,
            Risk = RiskLevel.High,
            CreatedAt = DateTimeOffset.UtcNow,
            WriteScope = [new ProjectPath("src/a.cs"), new ProjectPath("src/b.cs")],
            Dependencies = [new TaskId("task-0")],
        };

        await _runs.SaveAsync(task);
        List<RunTask> loaded = await _runs.ListTasksAsync(new RunId("run-1"));

        Assert.Single(loaded);
        Assert.Equal(["src/a.cs", "src/b.cs"], loaded[0].WriteScope.Select(p => p.Value));
        Assert.Equal([new TaskId("task-0")], loaded[0].Dependencies);
        Assert.Equal(RiskLevel.High, loaded[0].Risk);
    }

    [Fact]
    public async Task APlanKeepsItsTaskGraph()
    {
        await _plans.SaveAsync(NewPlan());

        Plan? loaded = await _plans.FindAsync(new PlanId("plan-1"));

        Assert.NotNull(loaded);
        Assert.Single(loaded.Tasks);
        Assert.Equal("port the thing", loaded.Tasks[0].Objective);
        Assert.True(loaded.Tasks[0].IsParallelizable);
        Assert.Equal([GateKind.Build, GateKind.Tests], loaded.Tasks[0].Gates);
    }

    [Fact]
    public async Task APlanKeepsItsBoundedContextDecision()
    {
        Plan plan = NewPlan();
        await _plans.SaveAsync(plan);

        Plan? loaded = await _plans.FindAsync(plan.Id);

        Assert.NotNull(loaded?.Context);
        Assert.Equal(ContextProfile.Medium, loaded.Context.Profile);
        Assert.Equal(ContextStrategy.ContextPack, loaded.Context.Strategy);
        Assert.Equal(16000, loaded.Context.Budget.ContextHardTokens);
        Assert.Equal(["legacy-project", "default"], loaded.Context.Reasons);
    }

    [Fact]
    public async Task AVersionThreeDatabaseReceivesTheNullableContextColumn()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"atlas-migration-{Guid.NewGuid():N}");
        string path = Path.Combine(directory, "state.db");
        Directory.CreateDirectory(directory);

        try
        {
            await using (SqliteConnection legacy = new($"Data Source={path}"))
            {
                await legacy.OpenAsync();
                await using SqliteCommand command = legacy.CreateCommand();
                command.CommandText = """
                    CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
                    INSERT INTO schema_version (version) VALUES (3);
                    CREATE TABLE plans (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        goal_id TEXT NOT NULL,
                        goal_revision TEXT NOT NULL,
                        state TEXT NOT NULL,
                        autonomy TEXT NOT NULL,
                        runner TEXT NOT NULL,
                        integration_target TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        tasks TEXT NOT NULL DEFAULT '[]'
                    );
                    """;
                await command.ExecuteNonQueryAsync();
            }

            await using AtlasFlowDatabase upgraded = new(path);
            await upgraded.InitializeAsync();
            PlanRepository repository = new(upgraded);
            Plan plan = NewPlan();

            await repository.SaveAsync(plan);

            Plan? loaded = await repository.FindAsync(plan.Id);
            Assert.Equal(ContextProfile.Medium, loaded?.Context?.Profile);
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }

    // --- the state machine ------------------------------------------------

    [Fact]
    public async Task ALegalTransitionMovesTheRunAndRecordsWhy()
    {
        Run run = NewRun();
        await _runs.SaveAsync(run);

        Run moved = await _runs.TransitionAsync(run, RunState.Planning, NewEvent());

        Assert.Equal(RunState.Planning, moved.State);
        Assert.Equal(RunState.Planning, (await _runs.FindAsync(run.Id))!.State);
        Assert.Single(await _events.ListForRunAsync(run.Id));
    }

    [Fact]
    public async Task AnIllegalTransitionIsRefused()
    {
        Run run = NewRun();
        await _runs.SaveAsync(run);

        // Created -> Completed skips the entire lifecycle.
        await Assert.ThrowsAsync<InvalidTransitionException>(
            () => _runs.TransitionAsync(run, RunState.Completed, NewEvent()));
    }

    [Fact]
    public async Task ARefusedTransitionWritesNothing()
    {
        Run run = NewRun();
        await _runs.SaveAsync(run);

        await Assert.ThrowsAsync<InvalidTransitionException>(
            () => _runs.TransitionAsync(run, RunState.Completed, NewEvent()));

        Assert.Equal(RunState.Created, (await _runs.FindAsync(run.Id))!.State);
        Assert.Empty(await _events.ListForRunAsync(run.Id));
    }

    [Fact]
    public async Task ATaskCanBeCancelledWhileStillPlanned()
    {
        // The defect this covers: Planned could not be cancelled, so a run
        // stopped before its tasks started had to mark them Ready first — a lie
        // the state machine forced.
        Assert.True(StateMachine.CanTransition(TaskState.Planned, TaskState.Cancelled));
        Assert.True(StateMachine.CanTransition(TaskState.Blocked, TaskState.Ready));
        await Task.CompletedTask;
    }

    // --- plan immutability -------------------------------------------------

    [Fact]
    public async Task ALockedPlanCannotBeRewritten()
    {
        await _plans.SaveAsync(NewPlan(PlanState.Locked));

        Plan tampered = NewPlan(PlanState.Locked) with { Runner = "something-else" };

        await Assert.ThrowsAsync<PersistenceException>(() => _plans.SaveAsync(tampered));
    }

    [Fact]
    public async Task ALockedPlanMayStillBeConsumed()
    {
        await _plans.SaveAsync(NewPlan(PlanState.Locked));

        await _plans.SaveAsync(NewPlan(PlanState.Consumed));

        Plan? loaded = await _plans.FindAsync(new PlanId("plan-1"));
        Assert.Equal(PlanState.Consumed, loaded!.State);
    }

    [Fact]
    public async Task RewritingALockedPlanWithIdenticalContentIsANoOp()
    {
        await _plans.SaveAsync(NewPlan(PlanState.Locked));

        await _plans.SaveAsync(NewPlan(PlanState.Locked));

        Assert.Equal(PlanState.Locked, (await _plans.FindAsync(new PlanId("plan-1")))!.State);
    }

    // --- evidence -----------------------------------------------------------

    [Fact]
    public async Task FailingEvidenceIsStoredRatherThanDiscarded()
    {
        // Dropping it would hide the failure instead of recording it, and the
        // verification engine needs to see a failed verdict to refuse the gate.
        Evidence failed = new()
        {
            Id = new EvidenceId("ev-1"),
            Gate = GateKind.Review,
            Kind = "review",
            Verdict = Verdict.Failed,
            Uri = "docs/review.md",
            AttachedAt = DateTimeOffset.UtcNow,
        };

        await _evidence.SaveAsync(failed, new GoalId("P01-G01"));
        List<Evidence> loaded = await _evidence.ListForGoalAsync(new GoalId("P01-G01"));

        Assert.Single(loaded);
        Assert.Equal(Verdict.Failed, loaded[0].Verdict);
    }

    // --- the event fan-out ---------------------------------------------------

    [Fact]
    public async Task SubscribersSeeAnEventAfterItIsCommitted()
    {
        List<DomainEvent> seen = [];
        using IDisposable subscription = _events.Subscribe((e, _) =>
        {
            seen.Add(e);
            return Task.CompletedTask;
        });

        await _events.AppendAsync(NewEvent(EventType.RunStarted));

        Assert.Single(seen);
        Assert.Equal(EventType.RunStarted, seen[0].Type);
    }

    [Fact]
    public async Task AThrowingSubscriberDoesNotBreakTheWrite()
    {
        using IDisposable bad = _events.Subscribe((_, _) => throw new InvalidOperationException("boom"));

        await _events.AppendAsync(NewEvent());

        // The run is the thing that matters; a subscriber must not be able to
        // fail it.
        Assert.Single(await _events.ListForRunAsync(new RunId("run-1")));
    }

    [Fact]
    public async Task UnsubscribingStopsDelivery()
    {
        int count = 0;
        IDisposable subscription = _events.Subscribe((_, _) =>
        {
            count++;
            return Task.CompletedTask;
        });

        await _events.AppendAsync(NewEvent());
        subscription.Dispose();
        await _events.AppendAsync(NewEvent());

        Assert.Equal(1, count);
    }

    // --- durability ----------------------------------------------------------

    [Fact]
    public async Task StateOutlivesTheProcessThatWroteIt()
    {
        await _runs.SaveAsync(NewRun());
        await _database.DisposeAsync();

        AtlasFlowDatabase reopened = new(_databasePath);
        await using (reopened.ConfigureAwait(false))
        {
            await reopened.InitializeAsync();
            RunRepository runs = new(reopened, new EventStore(reopened));

            Run? loaded = await runs.FindAsync(new RunId("run-1"));

            Assert.NotNull(loaded);
            Assert.Equal("P01-G01", loaded.GoalId.Value);
        }

        // Re-open for the disposal in DisposeAsync.
        _database = new AtlasFlowDatabase(_databasePath);
        await _database.InitializeAsync();
    }

    [Fact]
    public async Task AnUninitializedDatabaseSaysSoRatherThanNullReferencing()
    {
        AtlasFlowDatabase fresh = new(AtlasFlowDatabase.SharedMemory);
        await using ConfiguredAsyncDisposable _ = fresh.ConfigureAwait(false);

        Assert.False(fresh.IsDurable);
        await Assert.ThrowsAsync<PersistenceException>(() => fresh.ExecuteAsync("SELECT 1"));
    }
}
