using AtlasFlow.Domain;

namespace AtlasFlow.Orchestration.Projects;

/// <summary>Resolving a project-relative path, and refusing one that escapes.</summary>
/// <remarks>
/// Every path the UI sends arrives as text the user or an agent influenced.
/// Resolution happens here and only here, so there is one place to read when
/// asking whether traversal is possible.
/// </remarks>
public static class ProjectPaths
{
    /// <summary>
    /// Turns a project-relative path into an absolute one inside the project.
    /// </summary>
    /// <remarks>
    /// The check compares fully resolved paths rather than scanning the input
    /// for <c>..</c>. Scanning for the pattern misses symlinks, misses
    /// <c>%2e%2e</c> once anything decodes, and misses absolute paths
    /// altogether — <c>/etc/passwd</c> contains no dots to find.
    /// </remarks>
    /// <exception cref="ProjectPathEscapeException">
    /// The path resolves outside the project root.
    /// </exception>
    public static string Resolve(string projectRoot, ProjectPath relative)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);

        string root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(projectRoot));
        string candidate = Path.GetFullPath(Path.Combine(root, relative.Value));

        bool isInside =
            candidate.Equals(root, StringComparison.Ordinal)
            || candidate.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.Ordinal);

        if (!isInside)
        {
            throw new ProjectPathEscapeException(
                $"'{relative.Value}' resolves outside the open project");
        }

        return candidate;
    }

    /// <summary>The project-relative form of an absolute path inside the project.</summary>
    public static ProjectPath Relative(string projectRoot, string absolute)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(absolute);

        string relative = Path.GetRelativePath(Path.GetFullPath(projectRoot), absolute);
        return new ProjectPath(relative.Replace(Path.DirectorySeparatorChar, '/'));
    }
}

/// <summary>A path pointed outside the open project.</summary>
public sealed class ProjectPathEscapeException : Exception
{
    public ProjectPathEscapeException() { }

    public ProjectPathEscapeException(string message) : base(message) { }

    public ProjectPathEscapeException(string message, Exception innerException)
        : base(message, innerException) { }
}
