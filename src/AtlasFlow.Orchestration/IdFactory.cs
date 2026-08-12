using AtlasFlow.Domain;

namespace AtlasFlow.Orchestration;

/// <summary>Generates the runtime's identifiers.</summary>
/// <remarks>
/// Prefixed and short, matching the previous implementation, because these
/// appear in logs and in the interface. <c>run-3f2a91c04b7e</c> tells a reader
/// what it is; a bare GUID tells them nothing and takes twice the width.
/// </remarks>
public static class IdFactory
{
    public static RunId NewRun() => new(Next("run"));

    public static PlanId NewPlan() => new(Next("plan"));

    public static TaskId NewTask() => new(Next("task"));

    public static AttemptId NewAttempt() => new(Next("att"));

    public static DiscussionId NewDiscussion() => new(Next("disc"));

    public static DecisionId NewDecision() => new(Next("dec"));

    public static string NewMessageId() => Next("msg");

    public static EvidenceId NewEvidence() => new(Next("ev"));

    public static string NewEventId() => Next("evt");

    private static string Next(string prefix) => $"{prefix}-{Guid.NewGuid():N}"[..(prefix.Length + 13)];
}
