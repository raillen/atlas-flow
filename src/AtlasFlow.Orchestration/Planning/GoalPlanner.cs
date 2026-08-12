using System.Globalization;
using System.Security.Cryptography;
using System.Text;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Planning;

namespace AtlasFlow.Orchestration.Planning;

/// <summary>Turns a Goal into a reviewable task graph.</summary>
public static class GoalPlanner
{
    /// <summary>
    /// Derives one task per acceptance criterion.
    /// </summary>
    /// <remarks>
    /// The deterministic baseline decomposition: one verifiable task per thing
    /// the Goal says must be true. A model-driven planner can replace it, but
    /// the contract it establishes — every acceptance criterion is owned by
    /// exactly one task — is what keeps a plan answerable to its Goal. A
    /// planner that drops a criterion produces a run that can succeed while
    /// the Goal remains unmet.
    /// </remarks>
    public static Plan Draw(
        Goal goal,
        string projectId,
        AutonomyLevel autonomy,
        string runner,
        string integrationTarget)
    {
        ArgumentNullException.ThrowIfNull(goal);

        IReadOnlyList<GateKind> gates = [.. goal.Gates.Required()];

        List<PlanTask> tasks = [];
        for (int index = 0; index < goal.Acceptance.Count; index++)
        {
            tasks.Add(new PlanTask
            {
                Id = new TaskId(string.Create(
                    CultureInfo.InvariantCulture,
                    $"{goal.Id.Value}-t{index + 1}")),
                Objective = goal.Acceptance[index],
                Risk = RiskLevel.Medium,
                IsParallelizable = true,
                Gates = gates,
            });
        }

        return new Plan
        {
            Id = IdFactory.NewPlan(),
            ProjectId = projectId,
            GoalId = goal.Id,
            GoalRevision = RevisionOf(goal),
            State = PlanState.Draft,
            Autonomy = autonomy,
            Runner = runner,
            IntegrationTarget = integrationTarget,
            CreatedAt = DateTimeOffset.UtcNow,
            Tasks = tasks,
        };
    }

    /// <summary>
    /// A content hash of the parts of a Goal a plan is answerable to.
    /// </summary>
    /// <remarks>
    /// A run is evidence about a specific version of a Goal. Without this, a
    /// Goal edited mid-run silently inherits evidence produced for text that no
    /// longer exists. Only the fields a plan depends on are hashed: retitling a
    /// Goal does not invalidate work done against its acceptance criteria.
    /// </remarks>
    public static string RevisionOf(Goal goal)
    {
        ArgumentNullException.ThrowIfNull(goal);

        StringBuilder material = new();
        material.Append(goal.Id.Value).Append('\n');
        material.Append(goal.Objective).Append('\n');

        foreach (string criterion in goal.Acceptance)
        {
            material.Append(criterion).Append('\n');
        }

        foreach (GateKind gate in goal.Gates.Required())
        {
            material.Append(gate).Append('\n');
        }

        byte[] digest = SHA256.HashData(Encoding.UTF8.GetBytes(material.ToString()));
        return Convert.ToHexStringLower(digest)[..12];
    }
}
