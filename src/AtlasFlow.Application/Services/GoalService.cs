using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Verification;
using AtlasFlow.Orchestration.Goals;

namespace AtlasFlow.Application.Services;

/// <summary>The Goals a project declares in Git.</summary>
/// <remarks>
/// Read only, and that is a property rather than an omission. A Goal moves
/// because a run produced evidence for its gates; nothing the UI does moves
/// one directly.
/// </remarks>
public sealed class GoalService(AtlasFlowOptions options, GoalLoader loader) : IGoalService
{
    private readonly string _root = options.ProjectRoot;
    private readonly GoalLoader _loader = loader;

    public Task<IReadOnlyList<Goal>> ListAsync(CancellationToken cancellationToken = default) =>
        Task.Run(() => _loader.Load(_root), cancellationToken);

    public async Task<Goal?> FindAsync(GoalId id, CancellationToken cancellationToken = default)
    {
        IReadOnlyList<Goal> goals = await ListAsync(cancellationToken).ConfigureAwait(false);
        return goals.FirstOrDefault(goal => goal.Id == id);
    }

    public Task<GoalVerification> GetVerificationAsync(
        GoalId id,
        CancellationToken cancellationToken = default) =>
        throw new NotSupportedException(
            "Verification is not ported yet. See reference/python-backend/atlas_flow/verification/.");
}
