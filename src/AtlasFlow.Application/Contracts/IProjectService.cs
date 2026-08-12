using AtlasFlow.Domain;
using AtlasFlow.Domain.Projects;

namespace AtlasFlow.Application.Contracts;

/// <summary>Opening a project, reading it, and adapting it.</summary>
/// <remarks>
/// Opening is not running. Every method here is safe against an arbitrary
/// directory: nothing executes a command in the project, and
/// <see cref="ApplyAdaptationAsync"/> is the only one that writes.
/// </remarks>
public interface IProjectService
{
    /// <summary>
    /// Inspects a directory and reports what Atlas Flow may do with it.
    /// </summary>
    /// <remarks>
    /// This is the first call the workspace makes. Everything the shell enables
    /// or blocks comes from <see cref="ProjectInspection.Capabilities"/> and
    /// the reason attached to it.
    /// </remarks>
    Task<ProjectInspection> InspectAsync(string root, CancellationToken cancellationToken = default);

    /// <summary>The currently open project, or <c>null</c> if none is.</summary>
    Task<ProjectInspection?> GetCurrentAsync(CancellationToken cancellationToken = default);

    /// <summary>Every file the explorer should offer.</summary>
    Task<IReadOnlyList<ProjectFile>> ListFilesAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Reads one project file.
    /// </summary>
    /// <exception cref="ProjectPathException">
    /// The path escapes the open project. Rejected rather than resolved.
    /// </exception>
    Task<ProjectFileContent> ReadFileAsync(ProjectPath path, CancellationToken cancellationToken = default);

    /// <summary>What adapting this project would write, without writing it.</summary>
    Task<AdaptationPreview> PreviewAdaptationAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Writes the adaptation, limited to the paths the caller authorized.
    /// </summary>
    /// <param name="paths">
    /// The subset of <see cref="AdaptationPreview.Files"/> the user approved.
    /// A path not in the preview is refused: this method never writes
    /// something the user did not see first.
    /// </param>
    /// <param name="cancellationToken">Cancels before the next file is written.</param>
    Task<AdaptationResult> ApplyAdaptationAsync(
        IReadOnlyList<ProjectPath> paths,
        CancellationToken cancellationToken = default);
}

/// <summary>A path was outside the open project, or otherwise unusable.</summary>
public sealed class ProjectPathException : Exception
{
    public ProjectPathException() { }

    public ProjectPathException(string message) : base(message) { }

    public ProjectPathException(string message, Exception innerException)
        : base(message, innerException) { }
}
