using AtlasFlow.Domain.Goals;

namespace AtlasFlow.Domain.Verification;

/// <summary>What a gate check concluded.</summary>
public enum Verdict
{
    Pending,
    Passed,
    Failed,
}

/// <summary>One artefact offered as proof that a gate passed.</summary>
public sealed record Evidence
{
    public required EvidenceId Id { get; init; }

    public required GateKind Gate { get; init; }

    /// <summary>What sort of artefact this is — a log, a report, a review.</summary>
    public required string Kind { get; init; }

    public required Verdict Verdict { get; init; }

    /// <summary>Where the artefact lives.</summary>
    public required string Uri { get; init; }

    public TaskId? TaskId { get; init; }

    public required DateTimeOffset AttachedAt { get; init; }
}

/// <summary>Where one gate of one Goal stands.</summary>
public sealed record GateOutcome
{
    public required GateKind Gate { get; init; }

    public required GateRequirement Requirement { get; init; }

    public required Verdict Verdict { get; init; }

    public IReadOnlyList<EvidenceId> Evidence { get; init; } = [];

    /// <summary>Why the verdict is what it is.</summary>
    public string Details { get; init; } = string.Empty;
}

/// <summary>
/// Whether a Goal may be declared done, and what is stopping it.
/// </summary>
/// <remarks>
/// The rule this type exists to enforce: a gate is not passed by writing that
/// it is. A Goal that declares a gate required needs evidence for it whose
/// verdict is <see cref="Verdict.Passed"/> — evidence that opens with a failing
/// verdict does not cover its gate, which was a real defect found on
/// 2026-08-11 and is the reason <see cref="GateOutcome.Verdict"/> is separate
/// from the presence of evidence.
/// </remarks>
public sealed record GoalVerification
{
    public required GoalId GoalId { get; init; }

    public required bool IsCompletable { get; init; }

    /// <summary>The single reason completion is refused, or empty if it is not.</summary>
    public string Blocking { get; init; } = string.Empty;

    public IReadOnlyList<GateOutcome> Gates { get; init; } = [];

    public IReadOnlyList<Evidence> Evidence { get; init; } = [];
}
