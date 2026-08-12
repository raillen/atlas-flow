using System.Text.Json;
using System.Text.Json.Nodes;

using AtlasFlow.Domain.Context;

namespace AtlasFlow.Orchestration.Context;

/// <summary>A project context policy could not be interpreted safely.</summary>
public sealed class ContextPlanningException : Exception
{
    public ContextPlanningException(string message) : base(message) { }

    public ContextPlanningException(string message, Exception innerException)
        : base(message, innerException) { }
}

/// <summary>Chooses a bounded LPC/PCA plan without retrieving project content.</summary>
/// <remarks>
/// This is deliberately a planner rather than a context engine. It classifies
/// the task and reads the project's budget profiles; a later retrieval engine
/// may expand the plan only within those limits.
/// </remarks>
public sealed class ContextPlanner
{
    private const string AtlasManifest = "atlas.json";

    private static readonly ContextBudget _legacyDefaultBudget = new()
    {
        ContextTargetTokens = 8000,
        ContextHardTokens = 16000,
        OutputTargetTokens = 1500,
        OutputHardTokens = 3000,
        MaxExpansionRounds = 2,
        MaxDelegationDepth = 1,
    };

    private readonly string _projectRoot;

    public ContextPlanner(string projectRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);
        _projectRoot = Path.GetFullPath(projectRoot);
    }

    /// <summary>Plans context from the task wording and the project policy.</summary>
    public async Task<ContextPlan> PlanAsync(
        string task,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(task);

        string path = Path.Combine(_projectRoot, AtlasManifest);
        if (!File.Exists(path))
        {
            return LegacyPlan(task);
        }

        string text;
        try
        {
            text = await File.ReadAllTextAsync(path, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            throw new ContextPlanningException($"Could not read {AtlasManifest}: {exception.Message}", exception);
        }

        JsonObject atlas = ParseObject(text, AtlasManifest);
        JsonObject context = RequiredObject(atlas, "context", AtlasManifest);
        ContextMode mode = ParseMode(ReadRequiredString(context, "mode", AtlasManifest));
        (ContextProfile profile, ContextStrategy strategy, IReadOnlyList<string> reasons) = Select(task);
        JsonObject profiles = RequiredObject(context, "profiles", AtlasManifest);
        JsonObject budgetObject = RequiredObject(profiles, ProfileName(profile), AtlasManifest);

        return new ContextPlan
        {
            Profile = profile,
            Strategy = strategy,
            Mode = mode,
            Budget = ReadBudget(budgetObject, AtlasManifest),
            Reasons = reasons,
            DeepRecursionEnabled = ReadDeepRecursion(context, AtlasManifest),
            Source = AtlasManifest,
        };
    }

    private static ContextPlan LegacyPlan(string task)
    {
        (_, ContextStrategy strategy, IReadOnlyList<string> reasons) = Select(task);
        return new ContextPlan
        {
            Profile = ContextProfile.Medium,
            Strategy = strategy,
            Mode = ContextMode.Legacy,
            Budget = _legacyDefaultBudget,
            Reasons = ["legacy-project", .. reasons],
            DeepRecursionEnabled = false,
            Source = "legacy-default",
        };
    }

    private static (ContextProfile Profile, ContextStrategy Strategy, IReadOnlyList<string> Reasons) Select(
        string task)
    {
        HashSet<string> tokens = [
            .. task
                .ToLowerInvariant()
                .Replace('/', ' ')
                .Replace('-', ' ')
                .Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
        ];

        if (tokens.Overlaps(["rename", "typo", "label", "copy", "text", "spelling"]))
        {
            return (ContextProfile.Small, ContextStrategy.Direct, ["localized-task-hint"]);
        }

        if (tokens.Overlaps(["architecture", "migration", "security", "refactor", "rewrite", "redesign"]))
        {
            return (ContextProfile.Large, ContextStrategy.ProgressiveRetrieval, ["high-impact-task-hint"]);
        }

        if (tokens.Overlaps(["bug", "regression", "unknown", "investigate", "debug", "failure", "crash"]))
        {
            return (ContextProfile.Medium, ContextStrategy.ProgressiveRetrieval, ["uncertain-task-hint"]);
        }

        return (ContextProfile.Medium, ContextStrategy.ContextPack, ["default"]);
    }

    private static ContextBudget ReadBudget(JsonObject node, string source)
    {
        int contextTarget = ReadNonNegativeInt(node, "context_target_tokens", source);
        int contextHard = ReadNonNegativeInt(node, "context_hard_tokens", source);
        int outputTarget = ReadNonNegativeInt(node, "output_target_tokens", source);
        int outputHard = ReadNonNegativeInt(node, "output_hard_tokens", source);
        int expansionRounds = ReadNonNegativeInt(node, "max_expansion_rounds", source);
        int delegationDepth = ReadNonNegativeInt(node, "max_delegation_depth", source);

        if (contextHard < contextTarget || outputHard < outputTarget)
        {
            throw new ContextPlanningException(
                $"{source} contains a hard context/output limit smaller than its target.");
        }

        return new ContextBudget
        {
            ContextTargetTokens = contextTarget,
            ContextHardTokens = contextHard,
            OutputTargetTokens = outputTarget,
            OutputHardTokens = outputHard,
            MaxExpansionRounds = expansionRounds,
            MaxDelegationDepth = delegationDepth,
        };
    }

    private static bool ReadDeepRecursion(JsonObject context, string source)
    {
        JsonObject? deepRecursion = context["deep_recursion"] as JsonObject;
        return deepRecursion is not null
            && deepRecursion["enabled"] is JsonValue value
            && value.TryGetValue<bool>(out bool enabled)
            ? enabled
            : false;
    }

    private static ContextMode ParseMode(string value) => value switch
    {
        "legacy" => ContextMode.Legacy,
        "progressive" => ContextMode.Progressive,
        _ => throw new ContextPlanningException($"atlas.json context.mode '{value}' is not supported."),
    };

    private static string ProfileName(ContextProfile profile) => profile switch
    {
        ContextProfile.Small => "small",
        ContextProfile.Medium => "medium",
        ContextProfile.Large => "large",
        _ => throw new ArgumentOutOfRangeException(nameof(profile)),
    };

    private static JsonObject ParseObject(string text, string source)
    {
        try
        {
            JsonNode? node = JsonNode.Parse(
                text,
                documentOptions: new JsonDocumentOptions { MaxDepth = 64 });

            return node as JsonObject
                ?? throw new ContextPlanningException($"{source} must contain a mapping.");
        }
        catch (JsonException exception)
        {
            throw new ContextPlanningException($"Could not parse {source}: {exception.Message}", exception);
        }
    }

    private static JsonObject RequiredObject(JsonObject parent, string key, string source) =>
        parent[key] as JsonObject
        ?? throw new ContextPlanningException($"{source} must contain object '{key}'.");

    private static string ReadRequiredString(JsonObject parent, string key, string source) =>
        parent[key] is JsonValue value
        && value.TryGetValue<string>(out string? text)
        && !string.IsNullOrWhiteSpace(text)
            ? text.Trim()
            : throw new ContextPlanningException($"{source} must contain non-empty string '{key}'.");

    private static int ReadNonNegativeInt(JsonObject parent, string key, string source) =>
        parent[key] is JsonValue value
        && value.TryGetValue<int>(out int number)
        && number >= 0
            ? number
            : throw new ContextPlanningException($"{source} must contain non-negative integer '{key}'.");
}
