using System.Globalization;
using System.Text.Json.Nodes;

using AtlasFlow.Domain.Discuss;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Planning;
using AtlasFlow.Domain.Verification;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence;

/// <summary>
/// The mapping between domain values and their stored text.
/// </summary>
/// <remarks>
/// <para>
/// Kept in one file, and only here. The stored spellings are the ones the
/// Python implementation wrote (<c>SUCCEEDED</c>, <c>atlas.run.started</c>,
/// <c>atlas-ready</c>), so an existing database opens without a migration.
/// C# naming does not reach the disk and the disk does not reach C# naming.
/// </para>
/// <para>
/// Parsing is strict. An unrecognised value throws rather than falling back to
/// a default: a run silently read back as <c>Created</c> because its state was
/// spelled in a way nobody expected is a corruption that looks like a feature.
/// </para>
/// </remarks>
internal static class SqlValues
{
    // --- states ----------------------------------------------------------

    internal static string Text(RunState state) => state switch
    {
        RunState.Created => "CREATED",
        RunState.Planning => "PLANNING",
        RunState.Ready => "READY",
        RunState.Running => "RUNNING",
        RunState.Verifying => "VERIFYING",
        RunState.Reviewing => "REVIEWING",
        RunState.Completed => "COMPLETED",
        RunState.Blocked => "BLOCKED",
        RunState.Cancelled => "CANCELLED",
        RunState.Failed => "FAILED",
        _ => throw Unmapped(state),
    };

    internal static RunState RunStateOf(string text) => text switch
    {
        "CREATED" => RunState.Created,
        "PLANNING" => RunState.Planning,
        "READY" => RunState.Ready,
        "RUNNING" => RunState.Running,
        "VERIFYING" => RunState.Verifying,
        "REVIEWING" => RunState.Reviewing,
        "COMPLETED" => RunState.Completed,
        "BLOCKED" => RunState.Blocked,
        "CANCELLED" => RunState.Cancelled,
        "FAILED" => RunState.Failed,
        _ => throw Unreadable(nameof(RunState), text),
    };

    internal static string Text(TaskState state) => state switch
    {
        TaskState.Planned => "PLANNED",
        TaskState.Ready => "READY",
        TaskState.Running => "RUNNING",
        TaskState.Succeeded => "SUCCEEDED",
        TaskState.Blocked => "BLOCKED",
        TaskState.Failed => "FAILED",
        TaskState.Cancelled => "CANCELLED",
        TaskState.Superseded => "SUPERSEDED",
        _ => throw Unmapped(state),
    };

    internal static TaskState TaskStateOf(string text) => text switch
    {
        "PLANNED" => TaskState.Planned,
        "READY" => TaskState.Ready,
        "RUNNING" => TaskState.Running,
        "SUCCEEDED" => TaskState.Succeeded,
        "BLOCKED" => TaskState.Blocked,
        "FAILED" => TaskState.Failed,
        "CANCELLED" => TaskState.Cancelled,
        "SUPERSEDED" => TaskState.Superseded,
        _ => throw Unreadable(nameof(TaskState), text),
    };

    internal static string Text(AttemptState state) => state switch
    {
        AttemptState.Created => "CREATED",
        AttemptState.Starting => "STARTING",
        AttemptState.Running => "RUNNING",
        AttemptState.Completed => "COMPLETED",
        AttemptState.Failed => "FAILED",
        AttemptState.Cancelled => "CANCELLED",
        _ => throw Unmapped(state),
    };

    internal static AttemptState AttemptStateOf(string text) => text switch
    {
        "CREATED" => AttemptState.Created,
        "STARTING" => AttemptState.Starting,
        "RUNNING" => AttemptState.Running,
        "COMPLETED" => AttemptState.Completed,
        "FAILED" => AttemptState.Failed,
        "CANCELLED" => AttemptState.Cancelled,
        _ => throw Unreadable(nameof(AttemptState), text),
    };

    internal static string Text(PlanState state) => state switch
    {
        PlanState.Draft => "DRAFT",
        PlanState.Locked => "LOCKED",
        PlanState.Consumed => "CONSUMED",
        _ => throw Unmapped(state),
    };

    internal static PlanState PlanStateOf(string text) => text switch
    {
        "DRAFT" => PlanState.Draft,
        "LOCKED" => PlanState.Locked,
        "CONSUMED" => PlanState.Consumed,
        _ => throw Unreadable(nameof(PlanState), text),
    };

    internal static string Text(TurnType type) => type switch
    {
        TurnType.Message => "message",
        TurnType.Question => "question",
        TurnType.Answer => "answer",
        TurnType.Summary => "summary",
        _ => throw Unmapped(type),
    };

    internal static TurnType TurnTypeOf(string text) => text switch
    {
        "message" => TurnType.Message,
        "question" => TurnType.Question,
        "answer" => TurnType.Answer,
        "summary" => TurnType.Summary,
        _ => throw Unreadable(nameof(TurnType), text),
    };

    internal static string Text(ReferenceKind kind) => kind switch
    {
        ReferenceKind.File => "file",
        ReferenceKind.Image => "image",
        _ => throw Unmapped(kind),
    };

    internal static ReferenceKind ReferenceKindOf(string text) => text switch
    {
        "file" => ReferenceKind.File,
        "image" => ReferenceKind.Image,
        _ => throw Unreadable(nameof(ReferenceKind), text),
    };

    internal static string Text(DecisionState state) => state switch
    {
        DecisionState.Proposed => "proposed",
        DecisionState.Accepted => "accepted",
        DecisionState.Rejected => "rejected",
        DecisionState.Superseded => "superseded",
        _ => throw Unmapped(state),
    };

    internal static DecisionState DecisionStateOf(string text) => text switch
    {
        "proposed" => DecisionState.Proposed,
        "accepted" => DecisionState.Accepted,
        "rejected" => DecisionState.Rejected,
        "superseded" => DecisionState.Superseded,
        _ => throw Unreadable(nameof(DecisionState), text),
    };

    internal static string Text(Completeness completeness) => completeness switch
    {
        Completeness.Unknown => "unknown",
        Completeness.Partial => "partial",
        Completeness.Sufficient => "sufficient",
        Completeness.Locked => "locked",
        _ => throw Unmapped(completeness),
    };

    internal static Completeness CompletenessOf(string text) => text switch
    {
        "unknown" => Completeness.Unknown,
        "partial" => Completeness.Partial,
        "sufficient" => Completeness.Sufficient,
        "locked" => Completeness.Locked,
        _ => throw Unreadable(nameof(Completeness), text),
    };

    // --- value objects ---------------------------------------------------

    internal static string Text(EventType type) => type switch
    {
        EventType.RunStarted => "atlas.run.started",
        EventType.RunCompleted => "atlas.run.completed",
        EventType.RunFailed => "atlas.run.failed",
        EventType.TaskReady => "atlas.task.ready",
        EventType.TaskSucceeded => "atlas.task.succeeded",
        EventType.TaskFailed => "atlas.task.failed",
        EventType.AttemptStarted => "atlas.attempt.started",
        EventType.AttemptCompleted => "atlas.attempt.completed",
        EventType.AttemptFailed => "atlas.attempt.failed",
        EventType.GatePassed => "atlas.gate.passed",
        EventType.GateFailed => "atlas.gate.failed",
        EventType.StateChange => "atlas.state.change",
        _ => throw Unmapped(type),
    };

    internal static EventType EventTypeOf(string text) => text switch
    {
        "atlas.run.started" => EventType.RunStarted,
        "atlas.run.completed" => EventType.RunCompleted,
        "atlas.run.failed" => EventType.RunFailed,
        "atlas.task.ready" => EventType.TaskReady,
        "atlas.task.succeeded" => EventType.TaskSucceeded,
        "atlas.task.failed" => EventType.TaskFailed,
        "atlas.attempt.started" => EventType.AttemptStarted,
        "atlas.attempt.completed" => EventType.AttemptCompleted,
        "atlas.attempt.failed" => EventType.AttemptFailed,
        "atlas.gate.passed" => EventType.GatePassed,
        "atlas.gate.failed" => EventType.GateFailed,
        "atlas.state.change" => EventType.StateChange,
        _ => throw Unreadable(nameof(EventType), text),
    };

    internal static string Text(RiskLevel risk) => risk switch
    {
        RiskLevel.Low => "low",
        RiskLevel.Medium => "medium",
        RiskLevel.High => "high",
        _ => throw Unmapped(risk),
    };

    internal static RiskLevel RiskOf(string text) => text switch
    {
        "low" => RiskLevel.Low,
        "medium" => RiskLevel.Medium,
        "high" => RiskLevel.High,
        _ => throw Unreadable(nameof(RiskLevel), text),
    };

    internal static string Text(AutonomyLevel autonomy) => autonomy switch
    {
        AutonomyLevel.Supervised => "supervised",
        AutonomyLevel.Agentic => "agentic",
        _ => throw Unmapped(autonomy),
    };

    internal static AutonomyLevel AutonomyOf(string text) => text switch
    {
        "supervised" => AutonomyLevel.Supervised,
        "agentic" => AutonomyLevel.Agentic,
        _ => throw Unreadable(nameof(AutonomyLevel), text),
    };

    internal static string Text(GateKind gate) => gate switch
    {
        GateKind.Build => "build",
        GateKind.Tests => "tests",
        GateKind.Review => "review",
        GateKind.Documentation => "documentation",
        GateKind.ProjectIntelligence => "project_intelligence",
        _ => throw Unmapped(gate),
    };

    internal static GateKind GateOf(string text) => text switch
    {
        "build" => GateKind.Build,
        "tests" => GateKind.Tests,
        "review" => GateKind.Review,
        "documentation" => GateKind.Documentation,
        "documentation_impact" => GateKind.Documentation,
        "project_intelligence" => GateKind.ProjectIntelligence,
        _ => throw Unreadable(nameof(GateKind), text),
    };

    internal static string Text(Verdict verdict) => verdict switch
    {
        Verdict.Passed => "PASSED",
        Verdict.Failed => "FAILED",
        Verdict.Pending => "PENDING",
        _ => throw Unmapped(verdict),
    };

    internal static Verdict VerdictOf(string text) => text switch
    {
        "PASSED" => Verdict.Passed,
        "FAILED" => Verdict.Failed,
        "PENDING" => Verdict.Pending,
        _ => throw Unreadable(nameof(Verdict), text),
    };

    // --- scalars ---------------------------------------------------------

    /// <summary>ISO-8601 with an offset, which is what the previous store wrote.</summary>
    internal static string Text(DateTimeOffset moment) =>
        moment.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);

    internal static string? Text(DateTimeOffset? moment) =>
        moment is null ? null : Text(moment.Value);

    internal static DateTimeOffset MomentOf(string text) =>
        DateTimeOffset.Parse(text, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind);

    internal static string Json(IEnumerable<string> values)
    {
        JsonArray array = [];
        foreach (string value in values)
        {
            array.Add(value);
        }

        return array.ToJsonString();
    }

    internal static List<string> StringsOf(string json) =>
        JsonNode.Parse(json) is JsonArray array
            ? [.. array.Select(node => node?.GetValue<string>() ?? string.Empty)]
            : [];

    // --- reader helpers ---------------------------------------------------

    internal static string String(this SqliteDataReader reader, string column) =>
        reader.GetString(reader.GetOrdinal(column));

    internal static string? NullableString(this SqliteDataReader reader, string column)
    {
        int ordinal = reader.GetOrdinal(column);
        return reader.IsDBNull(ordinal) ? null : reader.GetString(ordinal);
    }

    internal static DateTimeOffset Moment(this SqliteDataReader reader, string column) =>
        MomentOf(reader.String(column));

    internal static DateTimeOffset? NullableMoment(this SqliteDataReader reader, string column)
    {
        string? text = reader.NullableString(column);
        return text is null ? null : MomentOf(text);
    }

    private static InvalidOperationException Unmapped(object value) =>
        new($"No stored spelling for {value.GetType().Name}.{value}");

    private static PersistenceException Unreadable(string type, string text) =>
        new($"Stored value '{text}' is not a known {type}");
}
