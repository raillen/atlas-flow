using AtlasFlow.Domain;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Intelligence;
using AtlasFlow.Domain.Planning;

namespace AtlasFlow.Application.Services;

/// <summary>
/// Creates the compact report for the plan lifecycle.
/// </summary>
/// <remarks>
/// This is deliberately one report per reviewed plan, not one report per raw
/// event or runner trace. Project Intelligence keeps the current lifecycle
/// summary; SQLite remains the source for detailed operational events.
/// </remarks>
internal static class ProjectIntelligenceReportFactory
{
    public static TaskReport Planned(Plan plan) => Create(plan, TaskReportStatus.Planned);

    public static TaskReport Running(Plan plan) => Create(plan, TaskReportStatus.Running);

    public static TaskReport Failed(Plan plan) => Create(plan, TaskReportStatus.Failed);

    public static TaskReport FromRun(Plan plan, Run run) =>
        Create(plan, StatusFor(run.State), run.StartedAt, run.CompletedAt);

    private static TaskReport Create(
        Plan plan,
        TaskReportStatus status,
        DateTimeOffset? startedAt = null,
        DateTimeOffset? finishedAt = null)
    {
        ArgumentNullException.ThrowIfNull(plan);

        ContextPlan? context = plan.Context;
        return new TaskReport
        {
            Id = ReportId(plan.Id),
            Status = status,
            Type = "orchestration-plan",
            Components = ComponentsOf(plan),
            Risk = HighestRiskOf(plan),
            Complexity = context is null ? "unknown" : ProfileText(context.Profile),
            Strategy = context is null ? "unknown" : StrategyText(context.Strategy),
            ChangedFiles = [.. plan.Tasks
                .SelectMany(task => task.WriteScope)
                .Select(path => path.Value)
                .Distinct(StringComparer.Ordinal)
                .Order(StringComparer.Ordinal)],
            StartedAt = startedAt,
            FinishedAt = finishedAt,
        };
    }

    public static string ReportId(PlanId planId) => $"plan:{planId.Value}";

    private static string[] ComponentsOf(Plan plan)
    {
        string[] components = [.. plan.Tasks
            .SelectMany(task => task.Capabilities)
            .Where(capability => !string.IsNullOrWhiteSpace(capability))
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)];

        return components.Length > 0 ? components : ["orchestration"];
    }

    private static RiskLevel? HighestRiskOf(Plan plan) =>
        plan.Tasks.Count == 0 ? null : plan.Tasks.Max(task => task.Risk);

    private static TaskReportStatus StatusFor(RunState state) => state switch
    {
        RunState.Completed or RunState.Verifying => TaskReportStatus.Success,
        RunState.Failed => TaskReportStatus.Failed,
        RunState.Blocked => TaskReportStatus.Blocked,
        RunState.Cancelled => TaskReportStatus.Cancelled,
        _ => TaskReportStatus.Running,
    };

    private static string ProfileText(ContextProfile profile) => profile switch
    {
        ContextProfile.Small => "small",
        ContextProfile.Medium => "medium",
        ContextProfile.Large => "large",
        _ => "unknown",
    };

    private static string StrategyText(ContextStrategy strategy) => strategy switch
    {
        ContextStrategy.Direct => "direct",
        ContextStrategy.StructuralRetrieval => "structural-retrieval",
        ContextStrategy.ContextPack => "context-pack",
        ContextStrategy.ProgressiveRetrieval => "progressive-retrieval",
        _ => "unknown",
    };
}
