namespace AtlasFlow.Domain.Projects;

/// <summary>What Atlas Flow found when it opened a directory.</summary>
public enum ProjectMode
{
    /// <summary>Valid manifests on a supported framework version.</summary>
    AtlasReady,

    /// <summary>An Atlas project with manifests missing or invalid.</summary>
    AtlasNeedsAdaptation,

    /// <summary>An Atlas framework or version this runtime does not support.</summary>
    AtlasIncompatible,

    /// <summary>No <c>PROJECT_MANIFEST.yaml</c>. An ordinary directory.</summary>
    External,
}

/// <summary>
/// Which workspace stages the open project actually permits.
/// </summary>
/// <remarks>
/// Opening is not running. Plan, Run and Review stay visible in the interface
/// and are blocked with a reason, rather than hidden — a control that vanishes
/// when unavailable cannot explain why it is unavailable.
/// </remarks>
public sealed record ProjectCapabilities
{
    public required bool CanExplore { get; init; }

    public required bool CanDiscuss { get; init; }

    public required bool CanAdapt { get; init; }

    public required bool CanPlan { get; init; }

    public required bool CanRun { get; init; }

    public required bool CanReview { get; init; }

    /// <summary>Nothing but reading. The state an unadapted directory is in.</summary>
    public static ProjectCapabilities ExploreOnly => new()
    {
        CanExplore = true,
        CanDiscuss = true,
        CanAdapt = false,
        CanPlan = false,
        CanRun = false,
        CanReview = false,
    };
}

/// <summary>The result of inspecting a directory, without running anything in it.</summary>
public sealed record ProjectInspection
{
    public required string Root { get; init; }

    public required ProjectMode Mode { get; init; }

    public required string ProjectId { get; init; }

    public required string ProjectName { get; init; }

    public required ProjectCapabilities Capabilities { get; init; }

    /// <summary>Why the project is in this mode, in words a person can act on.</summary>
    public required string Reason { get; init; }

    /// <summary>What to do about it.</summary>
    public required string Recommendation { get; init; }

    public IReadOnlyList<string> Types { get; init; } = [];

    public string? FrameworkName { get; init; }

    public string? FrameworkVersion { get; init; }

    public bool IsFrameworkSupported { get; init; }

    /// <summary>
    /// Whether the directory is a Git repository.
    /// </summary>
    /// <remarks>
    /// Execution isolates through worktrees, so a project without Git can be
    /// explored and adapted but never run.
    /// </remarks>
    public bool IsGitPresent { get; init; }

    public IReadOnlyList<string> MissingManifests { get; init; } = [];

    public IReadOnlyList<string> InvalidManifests { get; init; } = [];
}

/// <summary>What a project file is, for the explorer tree.</summary>
public enum ProjectFileKind
{
    Directory,
    Document,
    Source,
    Manifest,
    Other,
}

/// <summary>One entry in the project explorer.</summary>
public sealed record ProjectFile
{
    public required ProjectPath Path { get; init; }

    public required ProjectFileKind Kind { get; init; }

    public required long SizeInBytes { get; init; }
}

/// <summary>The contents of one project file.</summary>
public sealed record ProjectFileContent
{
    public required ProjectPath Path { get; init; }

    public required string Content { get; init; }

    /// <summary>
    /// Whether the reader stopped early.
    /// </summary>
    /// <remarks>
    /// Silently returning a prefix is how a viewer shows half a file and calls
    /// it the file.
    /// </remarks>
    public bool IsTruncated { get; init; }
}

/// <summary>What an adaptation would do to one path.</summary>
public enum AdaptationAction
{
    Create,
    Skip,
    Conflict,
}

/// <summary>One file an adaptation proposes to write.</summary>
public sealed record AdaptationFile
{
    public required ProjectPath Path { get; init; }

    public required AdaptationAction Action { get; init; }

    public required string Reason { get; init; }
}

/// <summary>
/// What adapting this project would do, before anything is written.
/// </summary>
/// <remarks>
/// Adaptation is non-destructive by contract: it creates only authorized
/// paths, runs no commands, overwrites nothing, and never produces a Goal that
/// is already <c>LOCKED</c> or <c>DONE</c>.
/// </remarks>
public sealed record AdaptationPreview
{
    public required bool IsReady { get; init; }

    public IReadOnlyList<AdaptationFile> Files { get; init; } = [];

    public IReadOnlyList<string> Conflicts { get; init; } = [];

    public IReadOnlyList<string> Limitations { get; init; } = [];
}

/// <summary>What an applied adaptation actually wrote.</summary>
public sealed record AdaptationResult
{
    public IReadOnlyList<ProjectPath> Written { get; init; } = [];

    /// <summary>The project re-inspected afterwards, never the state assumed.</summary>
    public required ProjectInspection Inspection { get; init; }
}
