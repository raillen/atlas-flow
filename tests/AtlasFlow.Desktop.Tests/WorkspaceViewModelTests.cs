using AtlasFlow.Desktop.Integration;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Projects;

namespace AtlasFlow.Desktop.Tests;

public sealed class WorkspaceViewModelTests
{
    [Fact]
    public async Task Initialize_projects_backend_snapshot_without_leaking_backend_types()
    {
        ProjectCapabilities capabilities = CreateCapabilities(canRun: true, canReview: false);
        WorkspaceSnapshot snapshot = new(
            CreateInspection(capabilities),
            [CreateGoal()],
            "Adapter conectado");
        WorkspaceViewModel viewModel = CreateViewModel(_ => Task.FromResult(snapshot));

        await viewModel.InitializeAsync(TestContext.Current.CancellationToken);

        Assert.Equal("Atlas Flow", viewModel.ProjectName);
        Assert.Equal("Project Atlas pronto", viewModel.ProjectModeLabel);
        Assert.Equal("1 Goal(s) no projeto", viewModel.GoalSummaryLabel);
        Assert.True(Stage(viewModel, "run").IsEnabled);
        Assert.False(Stage(viewModel, "review").IsEnabled);
        Assert.False(viewModel.HasError);
    }

    [Fact]
    public void Disabled_stage_cannot_replace_the_current_stage()
    {
        WorkspaceViewModel viewModel = CreateViewModel(_ => Task.FromResult(WorkspaceSnapshot.BackendUnavailable));

        viewModel.SelectStage("plan");

        Assert.Equal("attention", viewModel.SelectedStage.Key);
    }

    [Fact]
    public void Panel_commands_preserve_the_design_system_dimensions()
    {
        WorkspaceViewModel viewModel = CreateViewModel(_ => Task.FromResult(WorkspaceSnapshot.BackendUnavailable));

        viewModel.ToggleNavigationCommand.Execute(null);
        viewModel.ToggleContextCommand.Execute(null);

        Assert.False(viewModel.IsNavigationExpanded);
        Assert.Equal(WorkspaceViewModel.CompactNavigationWidth, viewModel.NavigationPanelWidth);
        Assert.False(viewModel.IsContextVisible);
        Assert.Equal(0, viewModel.ContextPanelWidth);
    }

    [Fact]
    public void Theme_command_updates_the_visible_mode_label()
    {
        WorkspaceViewModel viewModel = CreateViewModel(_ => Task.FromResult(WorkspaceSnapshot.BackendUnavailable));

        viewModel.ToggleThemeCommand.Execute(null);

        Assert.Equal("Claro", viewModel.ThemeModeLabel);
    }

    [Fact]
    public async Task Gateway_failure_keeps_the_shell_available_and_exposes_an_error()
    {
        WorkspaceViewModel viewModel = CreateViewModel(
            _ => Task.FromException<WorkspaceSnapshot>(new InvalidOperationException("adapter offline")));

        await viewModel.InitializeAsync(TestContext.Current.CancellationToken);

        Assert.True(viewModel.HasError);
        Assert.DoesNotContain("adapter offline", viewModel.ErrorMessage, StringComparison.Ordinal);
        Assert.Contains("Verifique a integração", viewModel.ErrorMessage, StringComparison.Ordinal);
        Assert.Equal("Frontend disponível · integração indisponível", viewModel.ConnectionDescription);
        Assert.False(viewModel.IsBusy);
    }

    private static WorkspaceViewModel CreateViewModel(
        Func<CancellationToken, Task<WorkspaceSnapshot>> loadWorkspace)
    {
        return new WorkspaceViewModel(
            new StubGateway(loadWorkspace),
            new StubThemeController());
    }

    private static WorkspaceStageViewModel Stage(WorkspaceViewModel viewModel, string key)
    {
        return Assert.Single(
            viewModel.Stages,
            stage => string.Equals(stage.Key, key, StringComparison.Ordinal));
    }

    private static ProjectCapabilities CreateCapabilities(bool canRun, bool canReview)
    {
        return new ProjectCapabilities
        {
            CanExplore = true,
            CanDiscuss = true,
            CanAdapt = false,
            CanPlan = true,
            CanRun = canRun,
            CanReview = canReview,
        };
    }

    private static ProjectInspection CreateInspection(ProjectCapabilities capabilities)
    {
        return new ProjectInspection
        {
            Root = "/workspace/atlas-flow",
            Mode = ProjectMode.AtlasReady,
            ProjectId = "atlas-flow",
            ProjectName = "Atlas Flow",
            Capabilities = capabilities,
            Reason = "Manifesto e atlas válidos.",
            Recommendation = "Continue o trabalho.",
            IsFrameworkSupported = true,
            IsGitPresent = true,
        };
    }

    private static Goal CreateGoal()
    {
        return new Goal
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
    }

    private sealed class StubGateway(
        Func<CancellationToken, Task<WorkspaceSnapshot>> loadWorkspace) : IAtlasFlowFrontendGateway
    {
        public Task<WorkspaceSnapshot> LoadWorkspaceAsync(CancellationToken cancellationToken) =>
            loadWorkspace(cancellationToken);
    }

    private sealed class StubThemeController : IThemeController
    {
        public string CurrentMode { get; private set; } = "Escuro";

        public string Toggle()
        {
            CurrentMode = string.Equals(CurrentMode, "Escuro", StringComparison.Ordinal)
                ? "Claro"
                : "Escuro";

            return CurrentMode;
        }
    }
}
