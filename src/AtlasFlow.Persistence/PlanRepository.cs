using System.Text.Json.Nodes;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Planning;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence;

/// <summary>Plans, and the rule that a reviewed one cannot change.</summary>
public sealed class PlanRepository(AtlasFlowDatabase database)
{
    private const string Upsert = """
        INSERT OR REPLACE INTO plans
            (id, project_id, goal_id, goal_revision, state, autonomy, runner,
             integration_target, created_at, context, tasks)
        VALUES ($id, $projectId, $goalId, $goalRevision, $state, $autonomy, $runner,
                $integrationTarget, $createdAt, $context, $tasks)
        """;

    private readonly AtlasFlowDatabase _database = database;

    /// <summary>
    /// Writes a plan, refusing to rewrite one that has been locked.
    /// </summary>
    /// <remarks>
    /// Locking is what makes the graph a person reviewed and the graph that
    /// executes the same graph. The single change a locked plan may undergo is
    /// to <see cref="PlanState.Consumed"/>, once it has been scheduled — that
    /// is what stops one reviewed plan producing two runs and two sets of
    /// evidence that each claim to be about it.
    /// </remarks>
    /// <exception cref="PersistenceException">The plan is locked and the write would change it.</exception>
    public async Task SaveAsync(Plan plan, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(plan);

        Plan? existing = await FindAsync(plan.Id, cancellationToken).ConfigureAwait(false);
        if (existing is not null && existing.State != PlanState.Draft)
        {
            bool isBeingConsumed =
                existing.State == PlanState.Locked && plan.State == PlanState.Consumed;

            if (!isBeingConsumed)
            {
                if (WouldChange(existing, plan))
                {
                    throw new PersistenceException(
                        $"Plan {plan.Id} is immutable after {existing.State}");
                }

                return;
            }
        }

        await _database.ExecuteAsync(Upsert, ParametersFor(plan), cancellationToken).ConfigureAwait(false);
    }

    public Task<Plan?> FindAsync(PlanId id, CancellationToken cancellationToken = default) =>
        _database.QuerySingleAsync(
            "SELECT * FROM plans WHERE id = $id",
            Read,
            new Dictionary<string, object?> { ["$id"] = id.Value },
            cancellationToken);

    public Task<List<Plan>> ListAsync(GoalId? goalId = null, CancellationToken cancellationToken = default) =>
        goalId is null
            ? _database.QueryAsync("SELECT * FROM plans ORDER BY created_at DESC", Read, null, cancellationToken)
            : _database.QueryAsync(
                "SELECT * FROM plans WHERE goal_id = $goalId ORDER BY created_at DESC",
                Read,
                new Dictionary<string, object?> { ["$goalId"] = goalId.Value.Value },
                cancellationToken);

    /// <summary>Whether writing <paramref name="incoming"/> would alter what is stored.</summary>
    /// <remarks>
    /// Compares the persisted form, not the records. <c>Plan</c> is a record,
    /// but its <c>Tasks</c> is an <see cref="IReadOnlyList{T}"/>, and record
    /// equality compares a list by reference — so <c>existing != incoming</c>
    /// was true for two plans with identical content, and re-saving an
    /// unchanged locked plan threw. Asking whether the row would change is
    /// both the correct question and the one the previous implementation asked,
    /// by comparing serialized forms.
    /// </remarks>
    private static bool WouldChange(Plan existing, Plan incoming)
    {
        Dictionary<string, object?> before = ParametersFor(existing);
        Dictionary<string, object?> after = ParametersFor(incoming);

        return before.Any(entry => !Equals(entry.Value, after[entry.Key]));
    }

    private static Dictionary<string, object?> ParametersFor(Plan plan) => new()
    {
        ["$id"] = plan.Id.Value,
        ["$projectId"] = plan.ProjectId,
        ["$goalId"] = plan.GoalId.Value,
        ["$goalRevision"] = plan.GoalRevision,
        ["$state"] = SqlValues.Text(plan.State),
        ["$autonomy"] = SqlValues.Text(plan.Autonomy),
        ["$runner"] = plan.Runner,
        ["$integrationTarget"] = plan.IntegrationTarget,
        ["$createdAt"] = SqlValues.Text(plan.CreatedAt),
        ["$context"] = SerializeContext(plan.Context),
        ["$tasks"] = SerializeTasks(plan.Tasks),
    };

    private static string? SerializeContext(ContextPlan? context)
    {
        if (context is null)
        {
            return null;
        }

        JsonObject document = new()
        {
            ["profile"] = ProfileText(context.Profile),
            ["strategy"] = StrategyText(context.Strategy),
            ["mode"] = ModeText(context.Mode),
            ["deep_recursion_enabled"] = context.DeepRecursionEnabled,
            ["source"] = context.Source,
            ["reasons"] = ArrayOf(context.Reasons),
            ["budget"] = new JsonObject
            {
                ["context_target_tokens"] = context.Budget.ContextTargetTokens,
                ["context_hard_tokens"] = context.Budget.ContextHardTokens,
                ["output_target_tokens"] = context.Budget.OutputTargetTokens,
                ["output_hard_tokens"] = context.Budget.OutputHardTokens,
                ["max_expansion_rounds"] = context.Budget.MaxExpansionRounds,
                ["max_delegation_depth"] = context.Budget.MaxDelegationDepth,
            },
        };

        return document.ToJsonString();
    }

    private static string SerializeTasks(IReadOnlyList<PlanTask> tasks)
    {
        JsonArray array = [];
        foreach (PlanTask task in tasks)
        {
            array.Add(new JsonObject
            {
                ["id"] = task.Id.Value,
                ["objective"] = task.Objective,
                ["risk"] = SqlValues.Text(task.Risk),
                ["parallelizable"] = task.IsParallelizable,
                ["dependencies"] = ArrayOf(task.Dependencies.Select(d => d.Value)),
                ["write_scope"] = ArrayOf(task.WriteScope.Select(p => p.Value)),
                ["gates"] = ArrayOf(task.Gates.Select(SqlValues.Text)),
                ["capabilities"] = ArrayOf(task.Capabilities),
            });
        }

        return array.ToJsonString();
    }

    private static JsonArray ArrayOf(IEnumerable<string> values)
    {
        JsonArray array = [];
        foreach (string value in values)
        {
            array.Add(value);
        }

        return array;
    }

    private static List<PlanTask> DeserializeTasks(string json)
    {
        if (JsonNode.Parse(json) is not JsonArray array)
        {
            return [];
        }

        List<PlanTask> tasks = [];
        foreach (JsonObject node in array.OfType<JsonObject>())
        {
            tasks.Add(new PlanTask
            {
                Id = new TaskId(Text(node, "id")),
                Objective = Text(node, "objective"),
                Risk = SqlValues.RiskOf(Text(node, "risk")),
                IsParallelizable = node["parallelizable"]?.GetValue<bool>() ?? false,
                Dependencies = [.. Strings(node, "dependencies").Select(d => new TaskId(d))],
                WriteScope = [.. Strings(node, "write_scope").Select(p => new ProjectPath(p))],
                Gates = [.. Strings(node, "gates").Select(SqlValues.GateOf)],
                Capabilities = Strings(node, "capabilities"),
            });
        }

        return tasks;
    }

    private static string Text(JsonObject node, string key) =>
        node[key]?.GetValue<string>() ?? string.Empty;

    private static List<string> Strings(JsonObject node, string key) =>
        node[key] is JsonArray array
            ? [.. array.Select(item => item?.GetValue<string>() ?? string.Empty)]
            : [];

    private static Plan Read(SqliteDataReader reader) => new()
    {
        Id = new PlanId(reader.String("id")),
        ProjectId = reader.String("project_id"),
        GoalId = new GoalId(reader.String("goal_id")),
        GoalRevision = reader.String("goal_revision"),
        State = SqlValues.PlanStateOf(reader.String("state")),
        Autonomy = SqlValues.AutonomyOf(reader.String("autonomy")),
        Runner = reader.String("runner"),
        IntegrationTarget = reader.String("integration_target"),
        CreatedAt = reader.Moment("created_at"),
        Context = DeserializeContext(reader.NullableString("context")),
        Tasks = DeserializeTasks(reader.String("tasks")),
    };

    private static ContextPlan? DeserializeContext(string? json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return null;
        }

        JsonObject document = JsonNode.Parse(json) as JsonObject
            ?? throw new PersistenceException("The stored plan context is not an object");
        JsonObject budget = document["budget"] as JsonObject
            ?? throw new PersistenceException("The stored plan context has no budget");

        return new ContextPlan
        {
            Profile = ParseProfile(Text(document, "profile")),
            Strategy = ParseStrategy(Text(document, "strategy")),
            Mode = ParseMode(Text(document, "mode")),
            DeepRecursionEnabled = document["deep_recursion_enabled"]?.GetValue<bool>() ?? false,
            Source = Text(document, "source"),
            Reasons = Strings(document, "reasons"),
            Budget = new ContextBudget
            {
                ContextTargetTokens = Number(budget, "context_target_tokens"),
                ContextHardTokens = Number(budget, "context_hard_tokens"),
                OutputTargetTokens = Number(budget, "output_target_tokens"),
                OutputHardTokens = Number(budget, "output_hard_tokens"),
                MaxExpansionRounds = Number(budget, "max_expansion_rounds"),
                MaxDelegationDepth = Number(budget, "max_delegation_depth"),
            },
        };
    }

    private static string ProfileText(ContextProfile profile) => profile switch
    {
        ContextProfile.Small => "small",
        ContextProfile.Medium => "medium",
        ContextProfile.Large => "large",
        _ => throw new PersistenceException($"Unknown context profile '{profile}'"),
    };

    private static string StrategyText(ContextStrategy strategy) => strategy switch
    {
        ContextStrategy.Direct => "direct",
        ContextStrategy.StructuralRetrieval => "structural-retrieval",
        ContextStrategy.ContextPack => "context-pack",
        ContextStrategy.ProgressiveRetrieval => "progressive-retrieval",
        _ => throw new PersistenceException($"Unknown context strategy '{strategy}'"),
    };

    private static string ModeText(ContextMode mode) => mode switch
    {
        ContextMode.Legacy => "legacy",
        ContextMode.Progressive => "progressive",
        _ => throw new PersistenceException($"Unknown context mode '{mode}'"),
    };

    private static ContextProfile ParseProfile(string value) => value switch
    {
        "small" => ContextProfile.Small,
        "medium" => ContextProfile.Medium,
        "large" => ContextProfile.Large,
        _ => throw new PersistenceException($"Stored value '{value}' is not a known context profile"),
    };

    private static ContextStrategy ParseStrategy(string value) => value switch
    {
        "direct" => ContextStrategy.Direct,
        "structural-retrieval" => ContextStrategy.StructuralRetrieval,
        "context-pack" => ContextStrategy.ContextPack,
        "progressive-retrieval" => ContextStrategy.ProgressiveRetrieval,
        _ => throw new PersistenceException($"Stored value '{value}' is not a known context strategy"),
    };

    private static ContextMode ParseMode(string value) => value switch
    {
        "legacy" => ContextMode.Legacy,
        "progressive" => ContextMode.Progressive,
        _ => throw new PersistenceException($"Stored value '{value}' is not a known context mode"),
    };

    private static int Number(JsonObject node, string key) =>
        node[key] is JsonValue value
        && value.TryGetValue<int>(out int number)
        && number >= 0
            ? number
            : throw new PersistenceException($"Stored context budget field '{key}' is invalid");
}
