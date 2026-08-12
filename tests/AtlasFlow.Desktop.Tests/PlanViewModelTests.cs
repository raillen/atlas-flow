using AtlasFlow.Application.Contracts;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Intelligence;
using AtlasFlow.Domain.Planning;

using NSubstitute;

namespace AtlasFlow.Desktop.Tests;

public sealed class PlanViewModelTests
{
    [Fact]
    public async Task Loading_history_selects_the_newest_snapshot_and_exposes_its_tasks()
    {
        Goal goal = CreateGoal();
        Plan draft = CreatePlan("plan-draft", PlanState.Draft);
        IPlanService service = Substitute.For<IPlanService>();
        service.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Plan>>([draft]));

        PlanViewModel viewModel = new(service);

        await viewModel.LoadAsync(goal, TestContext.Current.CancellationToken);

        Assert.Same(goal, viewModel.Goal);
        Assert.Same(draft, viewModel.SelectedPlan);
        Assert.True(viewModel.HasPlans);
        Assert.True(viewModel.CanLockPlan);
        Assert.Equal("1 tarefa(s) · dummy · integra em main", viewModel.SelectedPlanSummary);
    }

    [Fact]
    public async Task Creating_a_draft_adds_it_to_history_and_selects_it()
    {
        Goal goal = CreateGoal();
        Plan created = CreatePlan("plan-created", PlanState.Draft);
        IPlanService service = Substitute.For<IPlanService>();
        service.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Plan>>([]));
        service.CreateAsync(Arg.Any<CreatePlanRequest>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(created));

        PlanViewModel viewModel = new(service);
        await viewModel.LoadAsync(goal, TestContext.Current.CancellationToken);
        await viewModel.CreateDraftAsync(TestContext.Current.CancellationToken);

        Assert.Single(viewModel.Plans);
        Assert.Same(created, viewModel.SelectedPlan);
        await service.Received(1).CreateAsync(
            Arg.Is<CreatePlanRequest>(request => request.GoalId == goal.Id),
            Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Loading_exposes_the_bounded_context_decision_without_payload_details()
    {
        Goal goal = CreateGoal();
        Plan plan = CreatePlan("plan-context", PlanState.Draft) with
        {
            Context = new ContextPlan
            {
                Profile = ContextProfile.Medium,
                Strategy = ContextStrategy.StructuralRetrieval,
                Mode = ContextMode.Progressive,
                Budget = new ContextBudget
                {
                    ContextTargetTokens = 8000,
                    ContextHardTokens = 12000,
                    OutputTargetTokens = 2000,
                    OutputHardTokens = 4000,
                    MaxExpansionRounds = 2,
                    MaxDelegationDepth = 1,
                },
                Reasons = ["dependências estruturais"],
                Source = "lpc-policy",
            },
        };
        IPlanService service = Substitute.For<IPlanService>();
        service.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Plan>>([plan]));

        PlanViewModel viewModel = new(service);

        await viewModel.LoadAsync(goal, TestContext.Current.CancellationToken);

        Assert.Equal("Medium · Structural retrieval · Progressive", viewModel.SelectedContextState);
        Assert.Equal(
            "Entrada: 8000/12000 tokens · saída: 2000/4000 · expansão: 2 · delegação: 1",
            viewModel.SelectedContextSummary);
        Assert.Contains("dependências estruturais", viewModel.SelectedContextReasons);
        Assert.DoesNotContain("payload", viewModel.SelectedContextSummary, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Loading_reads_the_project_intelligence_summary()
    {
        Goal goal = CreateGoal();
        IPlanService planService = Substitute.For<IPlanService>();
        planService.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Plan>>([CreatePlan("plan-intelligence", PlanState.Draft)]));
        IProjectIntelligenceService intelligenceService = Substitute.For<IProjectIntelligenceService>();
        intelligenceService.GetAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(new ProjectIntelligenceSnapshot
            {
                Version = 1,
                UpdatedAt = DateTimeOffset.UtcNow,
                Summary = new ProjectIntelligenceSummary
                {
                    Tasks = 2,
                    InputTokens = 100,
                    OutputTokens = 50,
                    CachedTokens = 0,
                    IntermediateOutputTokens = 10,
                    DirectCost = 0,
                },
            }));

        PlanViewModel viewModel = new(planService, intelligenceService);

        await viewModel.LoadAsync(goal, TestContext.Current.CancellationToken);

        Assert.Equal("Snapshot carregado · 2 relatório(s)", viewModel.IntelligenceStatusLabel);
        Assert.Equal("100 tokens de entrada · 50 de saída · 10 intermediários", viewModel.IntelligenceSummaryLabel);
        Assert.Equal("Custo direto: não observado", viewModel.IntelligenceCostLabel);
        await intelligenceService.Received(1).GetAsync(Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Locking_replaces_the_selected_draft_with_the_locked_snapshot()
    {
        Goal goal = CreateGoal();
        Plan draft = CreatePlan("plan-draft", PlanState.Draft);
        Plan locked = draft with { State = PlanState.Locked };
        IPlanService service = Substitute.For<IPlanService>();
        service.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<Plan>>([draft]));
        service.LockAsync(draft.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(locked));

        PlanViewModel viewModel = new(service);
        await viewModel.LoadAsync(goal, TestContext.Current.CancellationToken);
        await viewModel.LockSelectedAsync(TestContext.Current.CancellationToken);

        Assert.Equal(PlanState.Locked, viewModel.SelectedPlan!.State);
        Assert.False(viewModel.CanLockPlan);
        await service.Received(1).LockAsync(draft.Id, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task A_service_failure_remains_visible_without_losing_the_shell_state()
    {
        Goal goal = CreateGoal();
        IPlanService service = Substitute.For<IPlanService>();
        service.ListForGoalAsync(goal.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromException<IReadOnlyList<Plan>>(new PlanStateException("plan unavailable")));

        PlanViewModel viewModel = new(service);
        await viewModel.LoadAsync(goal, TestContext.Current.CancellationToken);

        Assert.True(viewModel.HasError);
        Assert.Equal("plan unavailable", viewModel.ErrorMessage);
        Assert.Equal("P12-G01", viewModel.Goal!.Id.Value);
    }

    private static Goal CreateGoal() => new()
    {
        Id = new GoalId("P12-G01"),
        Phase = "P12",
        Title = "Portar o fluxo principal",
        State = GoalState.Active,
        Objective = "Entregar o workspace.",
        Gates = new GoalGates
        {
            Build = GateRequirement.Required,
            Tests = GateRequirement.Required,
            Review = GateRequirement.Required,
            Documentation = GateRequirement.Required,
        },
    };

    private static Plan CreatePlan(string id, PlanState state) => new()
    {
        Id = new PlanId(id),
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
                Id = new TaskId($"{id}-task"),
                Objective = "Entregar o workspace.",
                Risk = RiskLevel.Medium,
                IsParallelizable = true,
                Gates = [GateKind.Build, GateKind.Tests],
            },
        ],
    };
}
