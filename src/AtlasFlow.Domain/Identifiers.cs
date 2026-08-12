namespace AtlasFlow.Domain;

/// <summary>
/// The identifiers the runtime passes around, each one its own type.
/// </summary>
/// <remarks>
/// Every one of these was a bare <c>str</c> in the implementation this is
/// ported from, and several methods took two or three of them in a row.
/// <c>CreateRun(goalId, planId, projectId)</c> compiles just as happily with
/// the arguments in the wrong order, and the failure surfaces as a run against
/// the wrong Goal rather than as an error.
/// <para>
/// These are <c>readonly record struct</c>: no allocation, structural equality,
/// and the compiler refuses the swap. That is the whole reason they exist —
/// they are not wrapped for the sake of wrapping, and anything without a
/// mix-up risk stays a plain string.
/// </para>
/// </remarks>
public readonly record struct GoalId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(GoalId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct PlanId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(PlanId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct RunId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(RunId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct TaskId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(TaskId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct AttemptId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(AttemptId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct DiscussionId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(DiscussionId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct DecisionId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(DecisionId id) => id.Value;
}

/// <inheritdoc cref="GoalId"/>
public readonly record struct EvidenceId(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(EvidenceId id) => id.Value;
}

/// <summary>
/// A path relative to the open project root.
/// </summary>
/// <remarks>
/// Distinct from an absolute filesystem path on purpose. Everything the UI
/// asks for is project-relative, and the boundary that resolves one to the
/// other is the same boundary that rejects traversal. A method taking a
/// <see cref="ProjectPath"/> is stating that it will do that resolution.
/// </remarks>
public readonly record struct ProjectPath(string Value)
{
    public override string ToString() => Value;

    public static implicit operator string(ProjectPath path) => path.Value;
}
