namespace AtlasFlow.Domain.Execution;

/// <summary>How much the runtime may do without asking.</summary>
public enum AutonomyLevel
{
    /// <summary>Every step is confirmed.</summary>
    Supervised,

    /// <summary>The agent works the plan; the human reviews the result.</summary>
    Agentic,
}

/// <summary>How much damage a task can do if it goes wrong.</summary>
public enum RiskLevel
{
    Low,
    Medium,
    High,
}

/// <summary>Where a run is in its lifecycle.</summary>
public enum RunState
{
    Created,
    Planning,
    Ready,
    Running,
    Verifying,
    Reviewing,
    Completed,
    Blocked,
    Cancelled,
    Failed,
}

/// <summary>Where one task of a run is.</summary>
public enum TaskState
{
    Planned,
    Ready,
    Running,
    Succeeded,
    Blocked,
    Failed,
    Cancelled,

    /// <summary>Replaced by a later task before it ran.</summary>
    Superseded,
}

/// <summary>Where one attempt at a task is.</summary>
public enum AttemptState
{
    Created,
    Starting,
    Running,
    Completed,
    Failed,
    Cancelled,
}

/// <summary>One execution of one locked plan.</summary>
public sealed record Run
{
    public required RunId Id { get; init; }

    public required GoalId GoalId { get; init; }

    /// <summary>
    /// The Goal's content hash when the run started.
    /// </summary>
    /// <remarks>
    /// A run is evidence about a specific version of a Goal. Without this, a
    /// Goal edited mid-run would silently inherit evidence for text that no
    /// longer exists.
    /// </remarks>
    public required string GoalRevision { get; init; }

    public required RunState State { get; init; }

    public required AutonomyLevel Autonomy { get; init; }

    public required DateTimeOffset CreatedAt { get; init; }

    public int TaskCount { get; init; }
}

/// <summary>One node of a run's task graph.</summary>
public sealed record RunTask
{
    public required TaskId Id { get; init; }

    public required string Objective { get; init; }

    public required TaskState State { get; init; }

    public required RiskLevel Risk { get; init; }

    /// <summary>The abstract role resolved for this task, if one was.</summary>
    public string? Role { get; init; }

    /// <summary>The paths this task is permitted to write.</summary>
    public IReadOnlyList<ProjectPath> WriteScope { get; init; } = [];

    public IReadOnlyList<TaskId> Dependencies { get; init; } = [];
}

/// <summary>One try at one task.</summary>
public sealed record Attempt
{
    public required AttemptId Id { get; init; }

    public required TaskId TaskId { get; init; }

    public required AttemptState State { get; init; }

    public string? Runner { get; init; }

    public string? ModelId { get; init; }

    public DateTimeOffset? StartedAt { get; init; }

    public DateTimeOffset? CompletedAt { get; init; }

    /// <summary>Why it failed, when it did.</summary>
    public string? Error { get; init; }
}
