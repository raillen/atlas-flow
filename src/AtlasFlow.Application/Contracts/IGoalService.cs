using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Verification;

namespace AtlasFlow.Application.Contracts;

/// <summary>Reading the Goals in Git and checking whether they may close.</summary>
/// <remarks>
/// Git is canonical (ADR-009). Nothing here writes a Goal state: a Goal moves
/// because a run produced evidence, not because the UI asked.
/// </remarks>
public interface IGoalService
{
    /// <summary>Every Goal in the open project, in phase order.</summary>
    Task<IReadOnlyList<Goal>> ListAsync(CancellationToken cancellationToken = default);

    /// <summary>One Goal, or <c>null</c> if the project has no such Goal.</summary>
    Task<Goal?> FindAsync(GoalId id, CancellationToken cancellationToken = default);

    /// <summary>
    /// Whether a Goal may be declared done, and what is stopping it.
    /// </summary>
    /// <remarks>
    /// This is the check that refuses to round up. A Goal declaring a gate
    /// required needs evidence for that gate whose verdict passed; evidence
    /// that opens with a failing verdict does not cover it.
    /// </remarks>
    Task<GoalVerification> GetVerificationAsync(GoalId id, CancellationToken cancellationToken = default);
}
