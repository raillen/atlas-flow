using AtlasFlow.Application.Contracts;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Planning;

using NSubstitute;

namespace AtlasFlow.Desktop.Tests;

public sealed class RunViewModelTests
{
    [Fact]
    public async Task Loading_a_terminal_run_replays_detail_without_opening_a_live_stream()
    {
        Run run = CreateRun("run-1", RunState.Verifying);
        RunDetail detail = CreateDetail(run);
        IRunService service = Substitute.For<IRunService>();
        service.ListAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Run>>([run]));
        service.FindAsync(run.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<RunDetail?>(detail));

        RunViewModel viewModel = new(service, new PlanViewModel(Substitute.For<IPlanService>()));

        await viewModel.LoadAsync(TestContext.Current.CancellationToken);

        Assert.Same(run, viewModel.SelectedRun);
        Assert.Single(viewModel.Tasks);
        Assert.Single(viewModel.Events);
        Assert.Equal("1/1 tasks encerradas", viewModel.TaskProgress);
        Assert.False(viewModel.IsWatching);
    }

    [Fact]
    public async Task Starting_uses_the_selected_locked_plan_and_applies_streamed_state()
    {
        Goal goal = CreateGoal();
        Plan locked = CreatePlan(PlanState.Locked);
        Plan consumed = locked with { State = PlanState.Consumed };
        IPlanService planService = Substitute.For<IPlanService>();
        planService.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(
                Task.FromResult<IReadOnlyList<Plan>>([locked]),
                Task.FromResult<IReadOnlyList<Plan>>([consumed]));
        PlanViewModel plans = new(planService);
        await plans.LoadAsync(goal, TestContext.Current.CancellationToken);

        Run created = CreateRun("run-created", RunState.Created);
        Run final = CreateRun("run-created", RunState.Verifying);
        RunDetail detail = CreateDetail(final);
        DomainEvent started = CreateEvent(created.Id, EventType.RunStarted);
        IRunService service = Substitute.For<IRunService>();
        service.StartAsync(Arg.Any<StartRunRequest>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(created));
        service.FindAsync(created.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<RunDetail?>(detail));
        service.WatchAsync(created.Id, Arg.Any<CancellationToken>())
            .Returns(Stream(started));

        RunViewModel viewModel = new(service, plans);

        Assert.True(viewModel.CanStartRun);
        await viewModel.StartSelectedPlanAsync(TestContext.Current.CancellationToken);

        Assert.Equal(RunState.Verifying, viewModel.SelectedRun!.State);
        Assert.Single(viewModel.Events);
        Assert.Equal(PlanState.Consumed, plans.SelectedPlan!.State);
        await service.Received(1).StartAsync(
            Arg.Is<StartRunRequest>(request =>
                request.GoalId == goal.Id
                && request.PlanId == locked.Id
                && request.Runner == locked.Runner
                && request.IntegrationTarget == locked.IntegrationTarget),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task A_draft_plan_cannot_start_a_run()
    {
        Goal goal = CreateGoal();
        Plan draft = CreatePlan(PlanState.Draft);
        IPlanService planService = Substitute.For<IPlanService>();
        planService.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Plan>>([draft]));
        PlanViewModel plans = new(planService);
        await plans.LoadAsync(goal, TestContext.Current.CancellationToken);

        IRunService service = Substitute.For<IRunService>();
        RunViewModel viewModel = new(service, plans);

        Assert.False(viewModel.CanStartRun);
        await viewModel.StartSelectedPlanAsync(TestContext.Current.CancellationToken);

        await service.DidNotReceive().StartAsync(
            Arg.Any<StartRunRequest>(),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Cancelling_an_active_run_delegates_to_the_application_contract()
    {
        Run active = CreateRun("run-active", RunState.Running);
        IRunService service = Substitute.For<IRunService>();
        RunViewModel viewModel = new(service, new PlanViewModel(Substitute.For<IPlanService>()));
        viewModel.SelectedRun = active;

        await viewModel.CancelSelectedRunAsync(TestContext.Current.CancellationToken);

        await service.Received(1).CancelAsync(active.Id, Arg.Any<CancellationToken>());
        Assert.False(viewModel.HasError);
    }

    private static Goal CreateGoal() => new()
    {
        Id = new GoalId("P12-G01"),
        Phase = "P12",
        Title = "Construir a experiência",
        State = GoalState.Active,
        Objective = "Entregar o command center.",
        Gates = new GoalGates
        {
            Build = GateRequirement.Required,
            Tests = GateRequirement.Required,
            Review = GateRequirement.Optional,
            Documentation = GateRequirement.Optional,
        },
    };

    private static Plan CreatePlan(PlanState state) => new()
    {
        Id = new PlanId("plan-run"),
        ProjectId = "atlas-flow",
        GoalId = new GoalId("P12-G01"),
        GoalRevision = "revision",
        State = state,
        Autonomy = AutonomyLevel.Agentic,
        Runner = "dummy",
        IntegrationTarget = "main",
        CreatedAt = DateTimeOffset.UtcNow,
        Tasks =
        [
            new PlanTask
            {
                Id = new TaskId("task-run"),
                Objective = "Executar a tarefa.",
                Risk = RiskLevel.Low,
                IsParallelizable = false,
                Gates = [GateKind.Build],
            },
        ],
    };

    private static Run CreateRun(string id, RunState state) => new()
    {
        Id = new RunId(id),
        GoalId = new GoalId("P12-G01"),
        GoalRevision = "revision",
        State = state,
        Autonomy = AutonomyLevel.Agentic,
        ProjectId = "atlas-flow",
        CreatedAt = DateTimeOffset.UtcNow,
        TaskCount = 1,
    };

    private static RunDetail CreateDetail(Run run) => new()
    {
        Run = run,
        Tasks =
        [
            new RunTask
            {
                Id = new TaskId("run-task"),
                RunId = run.Id,
                Objective = "Executar a tarefa.",
                State = TaskState.Succeeded,
                Risk = RiskLevel.Low,
                CreatedAt = DateTimeOffset.UtcNow,
            },
        ],
        Events = [CreateEvent(run.Id, EventType.TaskSucceeded)],
    };

    private static DomainEvent CreateEvent(RunId runId, EventType type) => new()
    {
        Id = $"event-{type}",
        Timestamp = DateTimeOffset.UtcNow,
        Type = type,
        ProjectId = "atlas-flow",
        RunId = runId,
    };

    private static async IAsyncEnumerable<DomainEvent> Stream(DomainEvent domainEvent)
    {
        await Task.CompletedTask;
        yield return domainEvent;
    }
}
