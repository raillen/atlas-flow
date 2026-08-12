using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;

namespace AtlasFlow.Application.Contracts;

/// <summary>Turning a conversation into decisions the ledger can hold.</summary>
/// <remarks>
/// Chat history is not durable memory. A discussion matters to the rest of the
/// runtime only through the decisions it produces and what
/// <see cref="FinalizeAsync"/> writes to Git.
/// </remarks>
public interface IDiscussionService
{
    Task<IReadOnlyList<DiscussionId>> ListAsync(CancellationToken cancellationToken = default);

    Task<Discussion?> FindAsync(DiscussionId id, CancellationToken cancellationToken = default);

    Task<Discussion> StartAsync(CancellationToken cancellationToken = default);

    /// <summary>Appends a turn.</summary>
    /// <exception cref="ProjectPathException">
    /// A reference points outside the open project.
    /// </exception>
    Task<DiscussionMessage> AppendMessageAsync(
        AppendMessageRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>Proposes a decision. It is not in the ledger until accepted.</summary>
    Task<Decision> ProposeDecisionAsync(
        ProposeDecisionRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>Accepts a proposed decision.</summary>
    Task<Decision> AcceptDecisionAsync(
        DiscussionId discussionId,
        DecisionId decisionId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Writes the accepted decisions to the ledger in Git.
    /// </summary>
    /// <remarks>
    /// The one method here with a side effect outside the database. It writes
    /// files and nothing else — it creates no Goal, and certainly no Goal that
    /// is already locked or done.
    /// </remarks>
    Task<DiscussionOutcome> FinalizeAsync(DiscussionId id, CancellationToken cancellationToken = default);
}

/// <summary>One turn to append.</summary>
public sealed record AppendMessageRequest
{
    public required DiscussionId DiscussionId { get; init; }

    public required string Content { get; init; }

    public TurnType TurnType { get; init; } = TurnType.Message;

    public IReadOnlyList<MessageReference> References { get; init; } = [];
}

/// <summary>One decision to propose.</summary>
public sealed record ProposeDecisionRequest
{
    public required DiscussionId DiscussionId { get; init; }

    public required string Title { get; init; }

    public required string Statement { get; init; }

    public required string Rationale { get; init; }

    public IReadOnlyList<string> AffectedDomains { get; init; } = [];

    public bool RequiresAdr { get; init; }
}

/// <summary>A discussion transition was requested from an invalid state.</summary>
public sealed class DiscussionStateException : Exception
{
    public DiscussionStateException() { }

    public DiscussionStateException(string message) : base(message) { }

    public DiscussionStateException(string message, Exception innerException)
        : base(message, innerException) { }
}
