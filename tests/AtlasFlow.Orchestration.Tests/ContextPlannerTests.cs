using AtlasFlow.Domain.Context;
using AtlasFlow.Orchestration.Context;

namespace AtlasFlow.Orchestration.Tests;

public sealed class ContextPlannerTests : IDisposable
{
    private readonly string _root =
        Path.Combine(Path.GetTempPath(), $"atlas-context-{Guid.NewGuid():N}");

    public ContextPlannerTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    [Fact]
    public async Task ALegacyProjectGetsABoundedFallbackPlan()
    {
        ContextPlan plan = await new ContextPlanner(_root).PlanAsync("inspect the project");

        Assert.Equal(ContextMode.Legacy, plan.Mode);
        Assert.Equal(ContextProfile.Medium, plan.Profile);
        Assert.Equal(ContextStrategy.ContextPack, plan.Strategy);
        Assert.Equal(16000, plan.Budget.ContextHardTokens);
        Assert.False(plan.DeepRecursionEnabled);
        Assert.Contains("legacy-project", plan.Reasons);
    }

    [Fact]
    public async Task AHighImpactV2TaskUsesProgressiveLargeBudget()
    {
        WriteAtlas();

        ContextPlan plan = await new ContextPlanner(_root).PlanAsync("perform a security migration");

        Assert.Equal(ContextMode.Progressive, plan.Mode);
        Assert.Equal(ContextProfile.Large, plan.Profile);
        Assert.Equal(ContextStrategy.ProgressiveRetrieval, plan.Strategy);
        Assert.Equal(32000, plan.Budget.ContextHardTokens);
        Assert.Equal(1, plan.Budget.MaxDelegationDepth);
        Assert.False(plan.DeepRecursionEnabled);
        Assert.Equal("atlas.json", plan.Source);
    }

    [Fact]
    public async Task AMalformedBudgetFailsClosed()
    {
        WriteAtlas(contextHardTokens: 1000, contextTargetTokens: 2000);

        ContextPlanningException exception = await Assert.ThrowsAsync<ContextPlanningException>(
            () => new ContextPlanner(_root).PlanAsync("rename a label"));

        Assert.Contains("hard context/output limit", exception.Message, StringComparison.Ordinal);
    }

    private void WriteAtlas(int contextTargetTokens = 3000, int contextHardTokens = 6000)
    {
        File.WriteAllText(
            Path.Combine(_root, "atlas.json"),
            $$"""
            {
              "version": 2,
              "framework": {"name": "project-atlas-framework", "version": "0.2.0"},
              "context": {
                "mode": "progressive",
                "profiles": {
                  "small": {
                    "context_target_tokens": {{contextTargetTokens}},
                    "context_hard_tokens": {{contextHardTokens}},
                    "output_target_tokens": 500,
                    "output_hard_tokens": 1000,
                    "max_expansion_rounds": 1,
                    "max_delegation_depth": 0
                  },
                  "medium": {
                    "context_target_tokens": 8000,
                    "context_hard_tokens": 16000,
                    "output_target_tokens": 1500,
                    "output_hard_tokens": 3000,
                    "max_expansion_rounds": 2,
                    "max_delegation_depth": 1
                  },
                  "large": {
                    "context_target_tokens": 16000,
                    "context_hard_tokens": 32000,
                    "output_target_tokens": 3000,
                    "output_hard_tokens": 6000,
                    "max_expansion_rounds": 3,
                    "max_delegation_depth": 1
                  }
                },
                "deep_recursion": {"enabled": false}
              }
            }
            """);
    }
}
