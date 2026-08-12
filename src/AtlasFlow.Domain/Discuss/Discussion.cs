namespace AtlasFlow.Domain.Discuss;

/// <summary>Who or what produced a turn, and what kind of turn it is.</summary>
public enum TurnType
{
    Message,
    Question,
    Answer,
    Summary,
}

/// <summary>What a message points at in the open project.</summary>
public enum ReferenceKind
{
    File,
    Image,
}

/// <summary>Where a proposed decision stands.</summary>
public enum DecisionState
{
    Proposed,
    Accepted,
    Rejected,
    Superseded,
}

/// <summary>How much of the project draft a discussion has settled.</summary>
public enum Completeness
{
    Unknown,
    Partial,
    Sufficient,
    Locked,
}

/// <summary>
/// A link from a message to something in the project.
/// </summary>
/// <remarks>
/// A reference is a link to canonical context, never an implicit upload. The
/// content is not sent to any provider by attaching it; the boundary validates
/// that the path is inside the open project and rejects traversal.
/// </remarks>
public sealed record MessageReference
{
    public required ProjectPath Path { get; init; }

    public required ReferenceKind Kind { get; init; }

    public required string Label { get; init; }

    public string? MimeType { get; init; }
}

/// <summary>One turn in a discussion.</summary>
public sealed record DiscussionMessage
{
    public required string Id { get; init; }

    public required string Author { get; init; }

    public required TurnType TurnType { get; init; }

    public required string Content { get; init; }

    public required DateTimeOffset CreatedAt { get; init; }

    public IReadOnlyList<MessageReference> References { get; init; } = [];
}

/// <summary>
/// A decision the discussion produced, bound for the ledger.
/// </summary>
/// <remarks>
/// Decisions are what a discussion is for. Chat history is not durable memory:
/// Git is (ADR-009), and a decision reaches Git through the ledger.
/// </remarks>
public sealed record Decision
{
    public required DecisionId Id { get; init; }

    public required string Title { get; init; }

    public required string Statement { get; init; }

    public required string Rationale { get; init; }

    public required DecisionState State { get; init; }

    public IReadOnlyList<string> AffectedDomains { get; init; } = [];

    /// <summary>Whether this decision is architectural enough to need an ADR.</summary>
    public bool RequiresAdr { get; init; }

    public required DateTimeOffset CreatedAt { get; init; }
}

/// <summary>One conversation about what to build.</summary>
public sealed record Discussion
{
    public required DiscussionId Id { get; init; }

    public required Completeness Completeness { get; init; }

    public required DateTimeOffset CreatedAt { get; init; }

    public IReadOnlyList<DiscussionMessage> Messages { get; init; } = [];

    public IReadOnlyList<Decision> Decisions { get; init; } = [];
}

/// <summary>What finalizing a discussion wrote.</summary>
public sealed record DiscussionOutcome
{
    public required DiscussionId DiscussionId { get; init; }

    /// <summary>The decisions that reached the ledger.</summary>
    public IReadOnlyList<DecisionId> Recorded { get; init; } = [];

    /// <summary>The files written, so the caller can show the diff.</summary>
    public IReadOnlyList<ProjectPath> Written { get; init; } = [];
}
