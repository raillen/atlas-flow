using AtlasFlow.Domain.Projects;
using AtlasFlow.Orchestration.Projects;

namespace AtlasFlow.Orchestration.Tests;

/// <summary>
/// Classifying a directory, against directories that actually exist.
/// </summary>
/// <remarks>
/// Every case builds a real tree in a temporary directory. Inspection is
/// entirely about what is on disk, and a mocked filesystem would be asserting
/// that the mock agrees with itself.
/// </remarks>
public sealed class ProjectInspectorTests : IDisposable
{
    private readonly string _root =
        Path.Combine(Path.GetTempPath(), $"atlas-inspect-{Guid.NewGuid():N}");

    public ProjectInspectorTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    // --- builders ----------------------------------------------------------

    private void Write(string relative, string content)
    {
        string path = Path.Combine(_root, relative);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    private void MakeDirectory(string relative) =>
        Directory.CreateDirectory(Path.Combine(_root, relative));

    private void WriteManifest(string framework = "project-atlas-framework", string version = "0.1.0") =>
        Write("PROJECT_MANIFEST.yaml", $"""
            framework:
              name: {framework}
              version: "{version}"
            project:
              id: demo-project
              name: Demo Project
              type:
                - csharp
            """);

    private void WriteV2Manifest(string version = "0.2.0") =>
        Write("atlas.json", $$"""
            {
              "version": 2,
              "framework": {
                "name": "project-atlas-framework",
                "version": "{{version}}"
              },
              "project": {
                "id": "demo-project-v2",
                "name": "Demo Project v2",
                "type": ["csharp", "desktop"]
              }
            }
            """);

    /// <summary>Everything a ready project must have, none of it meaningful.</summary>
    private void WriteCompleteAtlas()
    {
        WriteManifest();
        Write("ENTRYPOINT.md", "# Entry");
        Write("PROJECT_STATE.md", "# State");
        Write("docs/ATLAS.md", "# Atlas");
        Write(".ai/context/project-profile.yaml", "id: demo-project");
        Write(".ai/agents/manifest.yaml", "agents: []");
        Write(".ai/skills/manifest.yaml", "skills: []");
        Write(".ai/recipes/manifest.yaml", "recipes: []");
        Write(".ai/orchestration/model-policy.yaml", "version: 1");
        Write(".ai/orchestration/autonomy-policy.yaml", "default: agentic");
        Write(".ai/orchestration/orchestrator.yaml", "version: 1");
        Write(".ai/orchestration/fallbacks.yaml", "version: 1");
        MakeDirectory(".ai/goals");
    }

    private void WriteCompleteAtlasV2()
    {
        WriteV2Manifest();
        Write("ENTRYPOINT.md", "# Entry");
        Write("PROJECT_STATE.md", "# State");
        Write("docs/ATLAS.md", "# Atlas");
        Write(".ai/agents/manifest.json", "{\"agents\": []}");
        Write(".ai/skills/manifest.json", "{\"skills\": []}");
        Write(".ai/recipes/manifest.json", "{\"recipes\": []}");
        Write(".ai/orchestration/model-policy.json", "{\"version\": 2}");
        Write(".ai/orchestration/orchestrator.json", "{\"version\": 2}");
        Write(".ai/orchestration/fallbacks.json", "{\"version\": 2}");
        Write(".atlas/history/project-intelligence.json", "{\"tasks\": []}");
        MakeDirectory(".ai/goals");
    }

    // --- classification ------------------------------------------------------

    [Fact]
    public void ADirectoryWithNoManifestIsExternal()
    {
        Write("README.md", "just a folder");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.External, inspection.Mode);
        Assert.False(inspection.Capabilities.CanPlan);
        Assert.True(inspection.Capabilities.CanAdapt);
        Assert.Contains("does not declare", inspection.Reason, StringComparison.Ordinal);
    }

    [Fact]
    public void AnUnparseableManifestNeedsAdaptationRatherThanCrashing()
    {
        Write("PROJECT_MANIFEST.yaml", "framework: [unclosed");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasNeedsAdaptation, inspection.Mode);
        Assert.Contains("PROJECT_MANIFEST.yaml", inspection.InvalidManifests);
    }

    [Fact]
    public void AManifestThatIsNotAMappingIsReportedAsSuch()
    {
        Write("PROJECT_MANIFEST.yaml", "- just\n- a\n- list");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasNeedsAdaptation, inspection.Mode);
        Assert.Contains("mapping", inspection.Reason, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void AnotherFrameworkIsIncompatibleAndNotAdaptable()
    {
        WriteManifest(framework: "some-other-framework");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasIncompatible, inspection.Mode);

        // Automatic conversion is deliberately unavailable here: guessing at
        // another framework's layout is how a tool destroys a project.
        Assert.False(inspection.Capabilities.CanAdapt);
        Assert.True(inspection.Capabilities.CanExplore);
    }

    [Fact]
    public void AnUnsupportedVersionIsIncompatible()
    {
        WriteManifest(version: "2.0.0");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasIncompatible, inspection.Mode);
        Assert.False(inspection.IsFrameworkSupported);
        Assert.Contains("0.1.x", inspection.Reason, StringComparison.Ordinal);
    }

    [Fact]
    public void ACompleteV2ProjectWithJsonManifestsIsReady()
    {
        WriteCompleteAtlasV2();
        MakeDirectory(".git");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasReady, inspection.Mode);
        Assert.Equal("0.2.0", inspection.FrameworkVersion);
        Assert.True(inspection.IsFrameworkSupported);
        Assert.True(inspection.Capabilities.CanRun);
        Assert.Equal("demo-project-v2", inspection.ProjectId);
        Assert.Equal(["csharp", "desktop"], inspection.Types);
    }

    [Fact]
    public void AnInvalidV2ManifestIsReportedWithoutFallingBackToLegacyYaml()
    {
        Write("atlas.json", "{\"framework\": [}");
        Write("PROJECT_MANIFEST.yaml", "framework:\n  name: project-atlas-framework\n  version: 0.1.0");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasNeedsAdaptation, inspection.Mode);
        Assert.Contains("atlas.json", inspection.InvalidManifests);
        Assert.DoesNotContain("PROJECT_MANIFEST.yaml", inspection.InvalidManifests);
    }

    [Fact]
    public void AVersionMismatchInV2NamesTheV2SupportWindow()
    {
        WriteV2Manifest(version: "0.3.0");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasIncompatible, inspection.Mode);
        Assert.False(inspection.IsFrameworkSupported);
        Assert.Contains("0.2.x", inspection.Reason, StringComparison.Ordinal);
    }

    [Fact]
    public void AMissingManifestIsNamedRatherThanCounted()
    {
        WriteCompleteAtlas();
        File.Delete(Path.Combine(_root, "docs/ATLAS.md"));

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasNeedsAdaptation, inspection.Mode);
        Assert.Contains("docs/ATLAS.md", inspection.MissingManifests);
    }

    [Fact]
    public void AnEmptyRequiredDocumentCountsAsInvalid()
    {
        // "The file exists" is not the same as "the file is usable".
        WriteCompleteAtlas();
        Write("ENTRYPOINT.md", "   \n  ");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasNeedsAdaptation, inspection.Mode);
        Assert.Contains("ENTRYPOINT.md", inspection.InvalidManifests);
    }

    [Fact]
    public void AMissingGoalsDirectoryIsNoticed()
    {
        WriteCompleteAtlas();
        Directory.Delete(Path.Combine(_root, ".ai/goals"));

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasNeedsAdaptation, inspection.Mode);
        Assert.Contains(".ai/goals", inspection.MissingManifests);
    }

    [Fact]
    public void ACompleteProjectWithGitIsReady()
    {
        WriteCompleteAtlas();
        MakeDirectory(".git");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasReady, inspection.Mode);
        Assert.True(inspection.IsFrameworkSupported);
        Assert.True(inspection.Capabilities.CanPlan);
        Assert.True(inspection.Capabilities.CanRun);
        Assert.True(inspection.Capabilities.CanReview);
        Assert.Equal("demo-project", inspection.ProjectId);
        Assert.Equal("Demo Project", inspection.ProjectName);
    }

    [Fact]
    public void ACompleteProjectWithoutGitCanPlanButNotRun()
    {
        // Execution isolates through worktrees. Without Git there is nothing to
        // branch from, and the reason has to say so rather than Run being
        // blocked with no explanation.
        WriteCompleteAtlas();

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(ProjectMode.AtlasReady, inspection.Mode);
        Assert.True(inspection.Capabilities.CanPlan);
        Assert.False(inspection.Capabilities.CanRun);
        Assert.Contains("Git is required", inspection.Reason, StringComparison.Ordinal);
    }

    // --- details ---------------------------------------------------------------

    [Fact]
    public void EveryModeStillPermitsExploringAndDiscussing()
    {
        Write("README.md", "nothing else");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.True(inspection.Capabilities.CanExplore);
        Assert.True(inspection.Capabilities.CanDiscuss);
    }

    [Fact]
    public void TypesAreDetectedFromTheDirectoryWhenTheManifestIsSilent()
    {
        Write("Cargo.toml", "[package]");
        Write("go.mod", "module x");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Contains("rust", inspection.Types);
        Assert.Contains("go", inspection.Types);
    }

    [Fact]
    public void TheManifestWinsOverDetectionWhenItDeclaresTypes()
    {
        WriteCompleteAtlas();
        Write("Cargo.toml", "[package]");

        ProjectInspection inspection = ProjectInspector.Inspect(_root);

        Assert.Equal(["csharp"], inspection.Types);
    }

    [Fact]
    public void InspectionRunsNothingInTheProject()
    {
        // The guarantee that lets the workspace open an unvetted directory. A
        // build script that would run is left as a tripwire: if inspection ever
        // executes one, this file appears.
        Write("build.sh", "#!/bin/sh\ntouch executed.marker\n");
        Write("Makefile", "all:\n\ttouch executed.marker\n");
        Write("package.json", """{"scripts":{"postinstall":"touch executed.marker"}}""");

        ProjectInspector.Inspect(_root);

        Assert.False(File.Exists(Path.Combine(_root, "executed.marker")));
    }
}
