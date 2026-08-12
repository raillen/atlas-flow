using AtlasFlow.Domain;

namespace AtlasFlow.Application.Contracts;

/// <summary>Reading the project's canonical documentation.</summary>
/// <remarks>
/// The Knowledge stage of the workspace. Read only: documentation is written
/// by the work, not by the browser that displays it.
/// </remarks>
public interface IDocumentationService
{
    /// <summary>Every canonical document, grouped by its section.</summary>
    Task<IReadOnlyList<DocumentEntry>> ListAsync(CancellationToken cancellationToken = default);

    /// <summary>One document's contents.</summary>
    /// <exception cref="ProjectPathException">
    /// The path is not a canonical document of the open project.
    /// </exception>
    Task<DocumentContent> ReadAsync(ProjectPath path, CancellationToken cancellationToken = default);
}

/// <summary>One document in the atlas.</summary>
public sealed record DocumentEntry
{
    public required ProjectPath Path { get; init; }

    public required string Title { get; init; }

    /// <summary>The numbered section it lives under, such as <c>01-architecture</c>.</summary>
    public required string Section { get; init; }
}

/// <summary>One document's text.</summary>
public sealed record DocumentContent
{
    public required ProjectPath Path { get; init; }

    public required string Content { get; init; }
}
