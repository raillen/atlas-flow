namespace AtlasFlow.Domain.Goals;

/// <summary>Where a Goal is in its lifecycle.</summary>
/// <remarks>
/// This was <c>state: str</c> with the valid set written in a trailing comment.
/// A comment does not stop <c>state == "Done"</c> from being false forever.
/// </remarks>
public enum GoalState
{
    Draft,
    Planned,
    Locked,
    Executing,
    Verifying,
    Reviewing,
    Ready,
    Active,
    Blocked,
    Done,
    Cancelled,
}

/// <summary>Whether a gate must pass before a Goal may be declared done.</summary>
public enum GateRequirement
{
    Optional,
    Required,
}

/// <summary>The gates a Goal may declare.</summary>
public enum GateKind
{
    Build,
    Tests,
    Review,
    Documentation,
    ProjectIntelligence,
}

/// <summary>What each of a Goal's gates requires.</summary>
public sealed record GoalGates
{
    public required GateRequirement Build { get; init; }

    public required GateRequirement Tests { get; init; }

    public required GateRequirement Review { get; init; }

    public required GateRequirement Documentation { get; init; }

    /// <summary>
    /// Whether the Goal's task report must be recorded in Project Intelligence.
    /// </summary>
    /// <remarks>
    /// This is optional by default so v0.1 Goals retain their existing
    /// semantics while the v0.2 contract is read during the migration period.
    /// </remarks>
    public GateRequirement ProjectIntelligence { get; init; } = GateRequirement.Optional;

    public GateRequirement For(GateKind gate) => gate switch
    {
        GateKind.Build => Build,
        GateKind.Tests => Tests,
        GateKind.Review => Review,
        GateKind.Documentation => Documentation,
        GateKind.ProjectIntelligence => ProjectIntelligence,
        _ => throw new ArgumentOutOfRangeException(nameof(gate)),
    };

    /// <summary>Every gate this Goal declares required, in gate order.</summary>
    public IEnumerable<GateKind> Required() =>
        Enum.GetValues<GateKind>().Where(gate => For(gate) == GateRequirement.Required);
}

/// <summary>A locked unit of intent, as it lives in Git under <c>.ai/goals/</c>.</summary>
/// <remarks>
/// Git is canonical (ADR-009). This is a read of what is on disk, not a row.
/// </remarks>
public sealed record Goal
{
    public required GoalId Id { get; init; }

    public required string Phase { get; init; }

    public required string Title { get; init; }

    public required GoalState State { get; init; }

    public required string Objective { get; init; }

    public required GoalGates Gates { get; init; }

    public IReadOnlyList<string> Constraints { get; init; } = [];

    public IReadOnlyList<string> NonGoals { get; init; } = [];

    public IReadOnlyList<GoalId> Dependencies { get; init; } = [];

    public IReadOnlyList<string> Acceptance { get; init; } = [];

    public IReadOnlyList<string> History { get; init; } = [];

    /// <summary>
    /// How many evidence entries the Goal file carries.
    /// </summary>
    /// <remarks>
    /// A count rather than the entries themselves: the Goal list renders this,
    /// and reading every evidence body to show a number is work nobody asked
    /// for. <c>IGoalService.GetVerificationAsync</c> returns the entries.
    /// </remarks>
    public int EvidenceCount { get; init; }
}
