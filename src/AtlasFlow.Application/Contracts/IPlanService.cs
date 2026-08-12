using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Planning;

namespace AtlasFlow.Application.Contracts;

/// <summary>How a Goal would be executed, drawn before anything runs.</summary>
public interface IPlanService
{
    /// <summary>Every plan drawn for a Goal, newest first.</summary>
    Task<IReadOnlyList<Plan>> ListForGoalAsync(GoalId goalId, CancellationToken cancellationToken = default);

    /// <summary>One plan, or <c>null</c>.</summary>
    Task<Plan?> FindAsync(PlanId id, CancellationToken cancellationToken = default);

    /// <summary>Draws a new draft plan for a Goal.</summary>
    Task<Plan> CreateAsync(CreatePlanRequest request, CancellationToken cancellationToken = default);

    /// <summary>
    /// Freezes a plan so it can be run.
    /// </summary>
    /// <remarks>
    /// A run from the UI always starts from a locked plan, and locking is what
    /// makes the reviewed graph and the executed graph the same graph.
    /// </remarks>
    /// <exception cref="PlanStateException">
    /// The plan is already locked or has been consumed.
    /// </exception>
    Task<Plan> LockAsync(PlanId id, CancellationToken cancellationToken = default);
}

/// <summary>
/// What to plan, and how.
/// </summary>
/// <remarks>
/// An options record rather than four positional parameters. Three of them
/// were strings in the previous implementation, which is three chances to pass
/// the runner where the branch belongs.
/// </remarks>
public sealed record CreatePlanRequest
{
    public required GoalId GoalId { get; init; }

    public AutonomyLevel Autonomy { get; init; } = AutonomyLevel.Agentic;

    /// <summary>Which runner executes the tasks.</summary>
    public string Runner { get; init; } = "dummy";

    /// <summary>The branch a completed run integrates into.</summary>
    public string IntegrationTarget { get; init; } = "main";
}

/// <summary>A plan was asked to do something its state forbids.</summary>
public sealed class PlanStateException : Exception
{
    public PlanStateException() { }

    public PlanStateException(string message) : base(message) { }

    public PlanStateException(string message, Exception innerException)
        : base(message, innerException) { }
}
