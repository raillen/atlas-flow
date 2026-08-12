namespace AtlasFlow.Domain.Context;

/// <summary>The bounded context budget profile selected for a task.</summary>
public enum ContextProfile
{
    Small,
    Medium,
    Large,
}

/// <summary>The retrieval strategy selected by LPC/PCA.</summary>
public enum ContextStrategy
{
    Direct,
    StructuralRetrieval,
    ContextPack,
    ProgressiveRetrieval,
}

/// <summary>Whether the project has opted into progressive context.</summary>
public enum ContextMode
{
    Legacy,
    Progressive,
}

/// <summary>Input, output and delegation limits for one context plan.</summary>
public sealed record ContextBudget
{
    public required int ContextTargetTokens { get; init; }

    public required int ContextHardTokens { get; init; }

    public required int OutputTargetTokens { get; init; }

    public required int OutputHardTokens { get; init; }

    public required int MaxExpansionRounds { get; init; }

    public required int MaxDelegationDepth { get; init; }
}

/// <summary>
/// The bounded context decision made before retrieval or execution begins.
/// </summary>
/// <remarks>
/// This is a decision record, not the context payload. Pointers and selected
/// sources are resolved by a later engine so the UI and orchestration layers
/// can share the same budget without copying a repository into the contract.
/// </remarks>
public sealed record ContextPlan
{
    public required ContextProfile Profile { get; init; }

    public required ContextStrategy Strategy { get; init; }

    public required ContextMode Mode { get; init; }

    public required ContextBudget Budget { get; init; }

    public required IReadOnlyList<string> Reasons { get; init; }

    public bool DeepRecursionEnabled { get; init; }

    /// <summary>The policy source used to make the decision.</summary>
    public required string Source { get; init; }
}
