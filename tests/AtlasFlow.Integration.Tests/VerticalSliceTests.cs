using AtlasFlow.Application;
using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Projects;
using AtlasFlow.Persistence;

using Microsoft.Extensions.DependencyInjection;

namespace AtlasFlow.Integration.Tests;

/// <summary>
/// The first vertical slice, end to end: container, real services, real repo.
/// </summary>
/// <remarks>
/// <para>
/// This resolves services out of <c>AddAtlasFlow</c> exactly as the desktop
/// app does and points them at this repository, which is itself a Project
/// Atlas project. Nothing is substituted.
/// </para>
/// <para>
/// It exists because a contract nobody has called is a guess. The interfaces
/// were derived from the previous REST API, which was shaped by a webview —
/// this is the test that says the shape survives contact with a real caller.
/// </para>
/// </remarks>
public sealed class VerticalSliceTests
{
    /// <summary>
    /// Walks up from the test assembly until it finds the repository.
    /// </summary>
    /// <remarks>
    /// Not a hard-coded path: the test binary lives several directories deep
    /// under <c>bin/</c>, and that depth changes with configuration and runtime
    /// identifier.
    /// </remarks>
    private static string RepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);

        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "PROJECT_MANIFEST.yaml")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new InvalidOperationException("Could not find the repository root from the test assembly");
    }

    private static ServiceProvider Open(string root)
    {
        ServiceCollection services = new();
        services.AddAtlasFlow(root);
        return services.BuildServiceProvider();
    }

    [Fact]
    public async Task TheContainerResolvesTheServicesThatArePorted()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());

        Assert.NotNull(provider.GetService<IProjectService>());
        Assert.NotNull(provider.GetService<IGoalService>());
        Assert.NotNull(provider.GetService<IContextService>());
        Assert.NotNull(provider.GetService<IProjectIntelligenceService>());
        Assert.NotNull(provider.GetService<IDiscussionService>());
    }

    [Fact]
    public async Task TheContextContractReturnsABoundedLegacyPlanForThisRepository()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IContextService context = provider.GetRequiredService<IContextService>();

        ContextPlan plan = await context.PlanAsync(new ContextPlanRequest
        {
            Task = "inspect the current orchestration boundary",
        }, CancellationToken.None);

        Assert.Equal(ContextMode.Legacy, plan.Mode);
        Assert.True(plan.Budget.ContextHardTokens >= plan.Budget.ContextTargetTokens);
        Assert.True(plan.Budget.OutputHardTokens >= plan.Budget.OutputTargetTokens);
        Assert.False(plan.DeepRecursionEnabled);
    }

    [Fact]
    public async Task AProjectUsingAtlasJsonGetsTheV2RuntimeDatabaseLocation()
    {
        string root = Path.Combine(Path.GetTempPath(), $"atlas-v2-runtime-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            await File.WriteAllTextAsync(
                Path.Combine(root, "atlas.json"),
                "{\"version\": 2, \"framework\": {\"name\": \"project-atlas-framework\", \"version\": \"0.2.0\"}}");

            await using ServiceProvider provider = Open(root);
            AtlasFlowDatabase database = provider.GetRequiredService<AtlasFlowDatabase>();

            Assert.EndsWith(
                Path.Combine(".atlas", "runtime", "atlas.db"),
                database.DatabasePath,
                StringComparison.Ordinal);
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Fact]
    public async Task ResolvingAnUnportedServiceFailsInsteadOfReturningAStub()
    {
        // The registration comment says this is deliberate. A stub that
        // answered plausibly would be believed.
        await using ServiceProvider provider = Open(RepositoryRoot());

        Assert.Null(provider.GetService<IRoutingService>());
        Assert.Null(provider.GetService<ISettingsService>());
        Assert.Null(provider.GetService<IDocumentationService>());
    }

    [Fact]
    public async Task AtlasFlowRecognisesItsOwnRepositoryAsReady()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IProjectService projects = provider.GetRequiredService<IProjectService>();

        ProjectInspection? inspection = await projects.GetCurrentAsync(CancellationToken.None);

        Assert.NotNull(inspection);
        Assert.Equal(ProjectMode.AtlasReady, inspection.Mode);
        Assert.True(inspection.IsGitPresent);
        Assert.True(inspection.Capabilities.CanRun);
    }

    [Fact]
    public async Task TheGoalsInGitAreReadBackWithTheirGates()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IGoalService goals = provider.GetRequiredService<IGoalService>();

        IReadOnlyList<Goal> loaded = await goals.ListAsync(CancellationToken.None);

        // Thirteen phases live under .ai/goals in this repository.
        Assert.Equal(13, loaded.Count);
        Assert.All(loaded, goal => Assert.False(string.IsNullOrWhiteSpace(goal.Title)));
        Assert.All(loaded, goal => Assert.NotEmpty(goal.Gates.Required()));
    }

    [Fact]
    public async Task GoalsComeBackInPhaseOrder()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IGoalService goals = provider.GetRequiredService<IGoalService>();

        IReadOnlyList<Goal> loaded = await goals.ListAsync(CancellationToken.None);

        Assert.Equal(
            loaded.Select(goal => goal.Phase).Order(StringComparer.Ordinal),
            loaded.Select(goal => goal.Phase));
    }

    [Fact]
    public async Task EveryGoalOnThisBranchIsActive()
    {
        // The port moved all thirteen from DONE to ACTIVE: their build and
        // tests evidence was produced on a runtime this branch deletes.
        await using ServiceProvider provider = Open(RepositoryRoot());
        IGoalService goals = provider.GetRequiredService<IGoalService>();

        IReadOnlyList<Goal> loaded = await goals.ListAsync(CancellationToken.None);

        Assert.All(loaded, goal => Assert.Equal(GoalState.Active, goal.State));
    }

    [Fact]
    public async Task FindingAGoalByIdReturnsTheSameGoalTheListDid()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IGoalService goals = provider.GetRequiredService<IGoalService>();

        IReadOnlyList<Goal> all = await goals.ListAsync(CancellationToken.None);
        Goal? found = await goals.FindAsync(all[0].Id, CancellationToken.None);

        Assert.Equal(all[0], found);
    }

    [Fact]
    public async Task AGoalThatDoesNotExistIsNullRatherThanAnError()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IGoalService goals = provider.GetRequiredService<IGoalService>();

        Assert.Null(await goals.FindAsync(new GoalId("P99-G99"), CancellationToken.None));
    }

    // --- the explorer ------------------------------------------------------

    [Fact]
    public async Task TheFileListSkipsTheDirectoriesNobodyWantsToSee()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IProjectService projects = provider.GetRequiredService<IProjectService>();

        IReadOnlyList<ProjectFile> files = await projects.ListFilesAsync(CancellationToken.None);

        Assert.NotEmpty(files);
        Assert.DoesNotContain(files, file => file.Path.Value.Contains("/obj/", StringComparison.Ordinal));
        Assert.DoesNotContain(files, file => file.Path.Value.StartsWith(".git/", StringComparison.Ordinal));
        Assert.Contains(files, file => file.Path.Value == "PROJECT_MANIFEST.yaml");
    }

    [Fact]
    public async Task ReadingAFileReturnsItsContents()
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IProjectService projects = provider.GetRequiredService<IProjectService>();

        ProjectFileContent content = await projects.ReadFileAsync(
            new ProjectPath("PROJECT_MANIFEST.yaml"),
            CancellationToken.None);

        Assert.Contains("project-atlas-framework", content.Content, StringComparison.Ordinal);
        Assert.False(content.IsTruncated);
    }

    [Theory]
    [InlineData("../../../etc/passwd")]
    [InlineData("/etc/passwd")]
    [InlineData("docs/../../outside.txt")]
    public async Task APathThatEscapesTheProjectIsRefused(string escape)
    {
        await using ServiceProvider provider = Open(RepositoryRoot());
        IProjectService projects = provider.GetRequiredService<IProjectService>();

        await Assert.ThrowsAsync<ProjectPathException>(
            () => projects.ReadFileAsync(new ProjectPath(escape), CancellationToken.None));
    }

    // --- an ordinary directory ------------------------------------------------

    [Fact]
    public async Task AnExternalDirectoryIsReportedRatherThanFailing()
    {
        string external = Path.Combine(Path.GetTempPath(), $"atlas-external-{Guid.NewGuid():N}");
        Directory.CreateDirectory(external);
        try
        {
            await using ServiceProvider provider = Open(external);
            IProjectService projects = provider.GetRequiredService<IProjectService>();

            ProjectInspection? inspection = await projects.GetCurrentAsync(CancellationToken.None);

            Assert.NotNull(inspection);
            Assert.Equal(ProjectMode.External, inspection.Mode);
            Assert.False(inspection.Capabilities.CanPlan);
            Assert.True(inspection.Capabilities.CanExplore);
        }
        finally
        {
            Directory.Delete(external, recursive: true);
        }
    }
}
