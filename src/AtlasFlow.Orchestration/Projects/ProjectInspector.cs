using AtlasFlow.Domain.Projects;


namespace AtlasFlow.Orchestration.Projects;

/// <summary>
/// Classifies a directory without running anything inside it.
/// </summary>
/// <remarks>
/// <para>
/// Opening a project must be safe against an arbitrary directory. Nothing here
/// executes a command, a build script or project code — it reads files and
/// reports what it found. That is the property that lets the workspace open
/// something a user has not vetted.
/// </para>
/// <para>
/// The Python original was one function of a hundred-odd lines with five
/// return points, each calling a fourteen-argument constructor. The
/// classification is the same, in the same order; it is expressed as a chain of
/// named checks so that a reader can see the order without holding it in their
/// head.
/// </para>
/// </remarks>
public static class ProjectInspector
{
    private const string SupportedFramework = "project-atlas-framework";

    private static readonly string[] _legacyRequiredManifests =
    [
        "PROJECT_MANIFEST.yaml",
        "ENTRYPOINT.md",
        "PROJECT_STATE.md",
        "docs/ATLAS.md",
        ".ai/context/project-profile.yaml",
        ".ai/agents/manifest.yaml",
        ".ai/skills/manifest.yaml",
        ".ai/recipes/manifest.yaml",
        ".ai/orchestration/model-policy.yaml",
        ".ai/orchestration/autonomy-policy.yaml",
        ".ai/orchestration/orchestrator.yaml",
        ".ai/orchestration/fallbacks.yaml",
    ];

    private static readonly string[] _v2RequiredManifests =
    [
        "atlas.json",
        "ENTRYPOINT.md",
        "PROJECT_STATE.md",
        "docs/ATLAS.md",
        ".ai/agents/manifest.json",
        ".ai/skills/manifest.json",
        ".ai/recipes/manifest.json",
        ".ai/orchestration/model-policy.json",
        ".ai/orchestration/orchestrator.json",
        ".ai/orchestration/fallbacks.json",
        ".atlas/history/project-intelligence.json",
    ];

    private static readonly string[] _requiredDirectories = [".ai/goals"];

    /// <summary>Files whose presence names a project's technology.</summary>
    private static readonly (string File, string Type)[] _typeSignals =
    [
        ("pyproject.toml", "python"),
        ("package.json", "javascript/typescript"),
        ("Cargo.toml", "rust"),
        ("go.mod", "go"),
        ("pom.xml", "java"),
        ("composer.json", "php"),
        ("AtlasFlow.slnx", "csharp"),
    ];

    public static ProjectInspection Inspect(string root)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);

        string resolved = Path.GetFullPath(root);
        Context context = new(resolved, Directory.Exists(Path.Combine(resolved, ".git")));

        return NoManifest(context)
            ?? UnreadableManifest(context)
            ?? WrongFramework(context)
            ?? UnsupportedVersion(context)
            ?? IncompleteManifests(context)
            ?? Ready(context);
    }

    // --- the checks, in the order they run ---------------------------------

    private static ProjectInspection? NoManifest(Context context)
    {
        if (File.Exists(context.ManifestPath))
        {
            return null;
        }

        return context.Build(
            ProjectMode.External,
            reason: "This directory does not declare Project Atlas manifests.",
            recommendation: "Inspect the project, then preview an adaptation to Project Atlas.",
            missing: context.RequiredManifests);
    }

    private static ProjectInspection? UnreadableManifest(Context context) =>
        context.Manifest.Error is { } error
            ? context.Build(
                ProjectMode.AtlasNeedsAdaptation,
                reason: error,
                recommendation: "Repair or replace the invalid Project Atlas manifest after reviewing a preview.",
                invalid: [context.ManifestRelativePath])
            : null;

    private static ProjectInspection? WrongFramework(Context context) =>
        context.FrameworkName == SupportedFramework
            ? null
            : context.Build(
                ProjectMode.AtlasIncompatible,
                reason: $"This project declares {context.FrameworkName ?? "no framework"}, not {SupportedFramework}.",
                recommendation: "Review the compatibility report and adapt deliberately; automatic conversion is disabled.",
                invalid: [context.ManifestRelativePath]);

    private static ProjectInspection? UnsupportedVersion(Context context) =>
        IsSupported(context.FrameworkVersion, context.IsV2)
            ? null
            : context.Build(
                ProjectMode.AtlasIncompatible,
                reason: $"Framework version {context.FrameworkVersion ?? "unknown"} is not supported; "
                        + $"Atlas Flow currently supports {(context.IsV2 ? "0.2.x" : "0.1.x")}.",
                recommendation: "Inspect and review an explicit framework migration before execution.",
                invalid: [context.ManifestRelativePath],
                frameworkSupported: false);

    private static ProjectInspection? IncompleteManifests(Context context)
    {
        List<string> missing =
        [
            .. context.RequiredManifests.Where(relative => !File.Exists(Path.Combine(context.Root, relative))),
            .. _requiredDirectories.Where(relative => !Directory.Exists(Path.Combine(context.Root, relative))),
        ];

        List<string> invalid =
        [
            .. context.RequiredManifests
                .Where(relative => !missing.Contains(relative))
                .Where(relative => IsUnusable(Path.Combine(context.Root, relative))),
        ];

        if (missing.Count == 0 && invalid.Count == 0)
        {
            return null;
        }

        return context.Build(
            ProjectMode.AtlasNeedsAdaptation,
            reason: "Project Atlas is declared but required manifests need attention.",
            recommendation: "Review the missing or invalid manifests, then preview an authorized adaptation.",
            missing: missing,
            invalid: invalid,
            frameworkSupported: true);
    }

    private static ProjectInspection Ready(Context context) =>
        context.Build(
            ProjectMode.AtlasReady,
            reason: "Project Atlas manifests are valid and the supported framework is available.",
            recommendation: "Project is ready for Goal planning and execution.",
            frameworkSupported: true);

    // --- predicates ---------------------------------------------------------

    /// <summary>Whether a required manifest is present but useless.</summary>
    /// <remarks>
    /// A structured manifest has to parse as a mapping; anything else has to be non-empty.
    /// An empty <c>ENTRYPOINT.md</c> satisfies "the file exists" and satisfies
    /// nothing else.
    /// </remarks>
    private static bool IsUnusable(string path)
    {
        string extension = Path.GetExtension(path);
        if (extension is ".yaml" or ".yml" or ".json")
        {
            return !Manifest.Read(path).IsValid;
        }

        try
        {
            return string.IsNullOrWhiteSpace(File.ReadAllText(path));
        }
        catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
        {
            return true;
        }
    }

    private static bool IsSupported(string? version, bool isV2)
    {
        if (version is null)
        {
            return false;
        }

        string[] parts = version.Split('.');
        int expectedMinor = isV2 ? 2 : 1;
        return parts.Length >= 2
            && int.TryParse(parts[0], out int major)
            && int.TryParse(parts[1], out int minor)
            && (major, minor) == (0, expectedMinor);
    }

    private static IReadOnlyList<string> DetectTypes(string root) =>
        [.. _typeSignals.Where(signal => File.Exists(Path.Combine(root, signal.File))).Select(signal => signal.Type)];

    /// <summary>
    /// What every check already knows, so no check re-reads the manifest.
    /// </summary>
    private sealed class Context(string root, bool isGitPresent)
    {
        internal string Root { get; } = root;

        internal bool IsGitPresent { get; } = isGitPresent;

        internal bool IsV2 { get; } = File.Exists(Path.Combine(root, "atlas.json"));

        internal string ManifestRelativePath => IsV2 ? "atlas.json" : "PROJECT_MANIFEST.yaml";

        internal string ManifestPath => Path.Combine(Root, ManifestRelativePath);

        internal IReadOnlyList<string> RequiredManifests => IsV2 ? _v2RequiredManifests : _legacyRequiredManifests;

        private Manifest? _manifest;

        internal Manifest Manifest => _manifest ??= Manifest.Read(ManifestPath);

        internal string? FrameworkName => Manifest.Section("framework")?.Text("name");

        internal string? FrameworkVersion => Manifest.Section("framework")?.Text("version");

        private string FallbackId =>
            new DirectoryInfo(Root).Name is { Length: > 0 } name ? name : "unknown-project";

        internal ProjectInspection Build(
            ProjectMode mode,
            string reason,
            string recommendation,
            IReadOnlyList<string>? missing = null,
            IReadOnlyList<string>? invalid = null,
            bool frameworkSupported = false)
        {
            Manifest? project = Manifest.Section("project");
            string id = project?.Text("id") ?? FallbackId;
            IReadOnlyList<string> types = project?.Strings("type") is { Count: > 0 } declared
                ? declared
                : DetectTypes(Root);

            bool isReady = mode == ProjectMode.AtlasReady;

            // A ready project without Git can be planned but not run: execution
            // isolates through worktrees, and there is nothing to branch from.
            // Saying so here is better than blocking Run with no explanation.
            if (isReady && !IsGitPresent)
            {
                reason = "Project Atlas manifests are valid, but Git is required for isolated execution.";
                recommendation = "Initialize or open a Git repository before running a Goal.";
            }

            return new ProjectInspection
            {
                Root = Root,
                Mode = mode,
                ProjectId = id,
                ProjectName = project?.Text("name") ?? id,
                Types = types,
                FrameworkName = FrameworkName,
                FrameworkVersion = FrameworkVersion,
                IsFrameworkSupported = frameworkSupported,
                IsGitPresent = IsGitPresent,
                MissingManifests = missing ?? [],
                InvalidManifests = invalid ?? [],
                Reason = reason,
                Recommendation = recommendation,
                Capabilities = new ProjectCapabilities
                {
                    CanExplore = true,
                    CanDiscuss = true,
                    CanAdapt = mode is ProjectMode.External or ProjectMode.AtlasNeedsAdaptation,
                    CanPlan = isReady,
                    CanRun = isReady && IsGitPresent,
                    CanReview = isReady,
                },
            };
        }
    }
}
