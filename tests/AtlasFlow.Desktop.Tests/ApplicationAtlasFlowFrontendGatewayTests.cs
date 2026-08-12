using AtlasFlow.Application.Contracts;
using AtlasFlow.Desktop.Integration;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Projects;
using NSubstitute;

namespace AtlasFlow.Desktop.Tests;

public sealed class ApplicationAtlasFlowFrontendGatewayTests
{
    [Fact]
    public async Task Load_aggregates_the_public_application_contracts()
    {
        CancellationToken cancellationToken = TestContext.Current.CancellationToken;
        ProjectInspection project = CreateInspection();
        IReadOnlyList<Goal> goals = [CreateGoal()];
        IProjectService projectService = Substitute.For<IProjectService>();
        IGoalService goalService = Substitute.For<IGoalService>();
        projectService.GetCurrentAsync(cancellationToken).Returns(project);
        goalService.ListAsync(cancellationToken).Returns(goals);
        ApplicationAtlasFlowFrontendGateway gateway = new(projectService, goalService);

        WorkspaceSnapshot snapshot = await gateway.LoadWorkspaceAsync(cancellationToken);

        Assert.Same(project, snapshot.Project);
        Assert.Same(goals, snapshot.Goals);
        Assert.Contains("Núcleo conectado", snapshot.ConnectionDescription, StringComparison.Ordinal);
    }

    [Fact]
    public async Task Load_does_not_query_goals_without_an_open_project()
    {
        CancellationToken cancellationToken = TestContext.Current.CancellationToken;
        IProjectService projectService = Substitute.For<IProjectService>();
        IGoalService goalService = Substitute.For<IGoalService>();
        projectService.GetCurrentAsync(cancellationToken).Returns((ProjectInspection?)null);
        ApplicationAtlasFlowFrontendGateway gateway = new(projectService, goalService);

        WorkspaceSnapshot snapshot = await gateway.LoadWorkspaceAsync(cancellationToken);

        Assert.Null(snapshot.Project);
        Assert.Empty(snapshot.Goals);
        _ = goalService.DidNotReceive().ListAsync(Arg.Any<CancellationToken>());
    }

    private static ProjectInspection CreateInspection()
    {
        return new ProjectInspection
        {
            Root = "/workspace/atlas-flow",
            Mode = ProjectMode.AtlasReady,
            ProjectId = "atlas-flow",
            ProjectName = "Atlas Flow",
            Capabilities = ProjectCapabilities.ExploreOnly with
            {
                CanPlan = true,
                CanRun = true,
                CanReview = true,
            },
            Reason = "Project Atlas válido.",
            Recommendation = "Continue.",
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
            Title = "Frontend",
            State = GoalState.Active,
            Objective = "Entregar o shell.",
            Gates = new GoalGates
            {
                Build = GateRequirement.Required,
                Tests = GateRequirement.Required,
                Review = GateRequirement.Required,
                Documentation = GateRequirement.Required,
            },
        };
    }
}
