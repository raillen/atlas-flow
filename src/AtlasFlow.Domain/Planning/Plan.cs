using AtlasFlow.Domain;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Execution;

namespace AtlasFlow.Domain.Planning;

/// <summary>
/// Whether a plan can still change, and whether it has been spent.
/// </summary>
/// <remarks>
/// A run from the UI always starts from a <see cref="Locked"/> plan. Locking
/// freezes it; scheduling marks it <see cref="Consumed"/>. That is what stops
/// the same reviewed plan being executed twice and producing two sets of
/// evidence that both claim to be about it.
/// </remarks>
public enum PlanState
{
    Draft,
    Locked,
    Consumed,
}

/// <summary>One node of a proposed task graph, before any run exists.</summary>
public sealed record PlanTask
{
    public required TaskId Id { get; init; }

    public required string Objective { get; init; }

    public required RiskLevel Risk { get; init; }

    /// <summary>Whether this task may run alongside its siblings.</summary>
    public required bool IsParallelizable { get; init; }

    public IReadOnlyList<TaskId> Dependencies { get; init; } = [];

    /// <summary>The paths this task would be permitted to write.</summary>
    public IReadOnlyList<ProjectPath> WriteScope { get; init; } = [];

    /// <summary>The gates this task's output must satisfy.</summary>
    public IReadOnlyList<Goals.GateKind> Gates { get; init; } = [];

    /// <summary>What an agent must be able to do to take this task.</summary>
    public IReadOnlyList<string> Capabilities { get; init; } = [];
}

/// <summary>A reviewable snapshot of how a Goal would be executed.</summary>
public sealed record Plan
{
    public required PlanId Id { get; init; }

    public required string ProjectId { get; init; }

    public required GoalId GoalId { get; init; }

    /// <summary>The Goal's content hash when the plan was drawn.</summary>
    public required string GoalRevision { get; init; }

    public required PlanState State { get; init; }

    public required AutonomyLevel Autonomy { get; init; }

    public required string Runner { get; init; }

    /// <summary>The branch a completed run integrates into.</summary>
    public required string IntegrationTarget { get; init; }

    public required DateTimeOffset CreatedAt { get; init; }

    /// <summary>
    /// The bounded context decision captured when this plan was drawn.
    /// </summary>
    /// <remarks>
    /// Optional for plans created by the v1 runtime. Keeping the field nullable
    /// lets old SQLite snapshots remain readable while new plans carry the
    /// exact LPC/PCA policy reviewed alongside their task graph.
    /// </remarks>
    public ContextPlan? Context { get; init; }

    public IReadOnlyList<PlanTask> Tasks { get; init; } = [];
}
