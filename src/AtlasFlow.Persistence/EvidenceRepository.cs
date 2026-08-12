using AtlasFlow.Domain;
using AtlasFlow.Domain.Verification;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence;

/// <summary>Evidence attached to a Goal's gates.</summary>
/// <remarks>
/// Rows here are claims, not conclusions. Whether a Goal may close is decided
/// by the verification engine reading these, and a row whose verdict is
/// <see cref="Verdict.Failed"/> is stored exactly like one that passed —
/// discarding it would hide the failure rather than record it.
/// </remarks>
public sealed class EvidenceRepository(AtlasFlowDatabase database)
{
    private const string Upsert = """
        INSERT OR REPLACE INTO evidence
            (id, goal_id, run_id, task_id, gate, kind, uri, digest, verdict, attached_at)
        VALUES ($id, $goalId, $runId, $taskId, $gate, $kind, $uri, $digest, $verdict, $attachedAt)
        """;

    private readonly AtlasFlowDatabase _database = database;

    public Task SaveAsync(
        Evidence evidence,
        GoalId goalId,
        RunId? runId = null,
        string digest = "",
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(evidence);

        return _database.ExecuteAsync(
            Upsert,
            new Dictionary<string, object?>
            {
                ["$id"] = evidence.Id.Value,
                ["$goalId"] = goalId.Value,
                ["$runId"] = runId?.Value,
                ["$taskId"] = evidence.TaskId?.Value,
                ["$gate"] = SqlValues.Text(evidence.Gate),
                ["$kind"] = evidence.Kind,
                ["$uri"] = evidence.Uri,
                ["$digest"] = digest,
                ["$verdict"] = SqlValues.Text(evidence.Verdict),
                ["$attachedAt"] = SqlValues.Text(evidence.AttachedAt),
            },
            cancellationToken);
    }

    public Task<List<Evidence>> ListForGoalAsync(GoalId goalId, CancellationToken cancellationToken = default) =>
        _database.QueryAsync(
            "SELECT * FROM evidence WHERE goal_id = $goalId ORDER BY attached_at",
            Read,
            new Dictionary<string, object?> { ["$goalId"] = goalId.Value },
            cancellationToken);

    private static Evidence Read(SqliteDataReader reader)
    {
        string? taskId = reader.NullableString("task_id");
        return new Evidence
        {
            Id = new EvidenceId(reader.String("id")),
            Gate = SqlValues.GateOf(reader.String("gate")),
            Kind = reader.String("kind"),
            Uri = reader.String("uri"),
            Verdict = SqlValues.VerdictOf(reader.String("verdict")),
            TaskId = taskId is null ? null : new TaskId(taskId),
            AttachedAt = reader.Moment("attached_at"),
        };
    }
}
