using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Orchestration.Goals;

namespace AtlasFlow.Orchestration.Tests;

public sealed class GoalLoaderTests : IDisposable
{
    private readonly string _root =
        Path.Combine(Path.GetTempPath(), $"atlas-goals-{Guid.NewGuid():N}");

    public GoalLoaderTests() => Directory.CreateDirectory(Path.Combine(_root, ".ai", "goals", "P12"));

    public void Dispose()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    [Fact]
    public void LoadsV2JsonGoalsAndTheirExtendedGates()
    {
        File.WriteAllText(
            Path.Combine(_root, ".ai", "goals", "P12", "P12-G01.goal.json"),
            """
            {
              "id": "P12-G01",
              "title": "Progressive context",
              "phase": "P12",
              "state": "REVIEWING",
              "objective": "Load only the context needed for the task.",
              "acceptance": ["The context budget is bounded."],
              "constraints": ["No unbounded recursion."],
              "non_goals": ["Provider-specific behavior."],
              "dependencies": ["P11-G01"],
              "evidence": [{"kind": "test", "path": "tests/context"}],
              "history": ["Created from the framework v0.2 contract."],
              "gates": {
                "build": "required",
                "tests": "optional",
                "review": "required",
                "documentation_impact": "optional",
                "project_intelligence": "required"
              }
            }
            """);

        Goal goal = Assert.Single(new GoalLoader().Load(_root));

        Assert.Equal(new GoalId("P12-G01"), goal.Id);
        Assert.Equal(GoalState.Reviewing, goal.State);
        Assert.Equal([new GoalId("P11-G01")], goal.Dependencies);
        Assert.Equal(1, goal.EvidenceCount);
        Assert.Equal(GateRequirement.Optional, goal.Gates.Documentation);
        Assert.Equal(GateRequirement.Required, goal.Gates.ProjectIntelligence);
        Assert.Contains(GateKind.ProjectIntelligence, goal.Gates.Required());
    }

    [Fact]
    public void InvalidJsonGoalFailsClosedWithItsPath()
    {
        string path = Path.Combine(_root, ".ai", "goals", "P12", "broken.goal.json");
        File.WriteAllText(path, "{\"id\":");

        GoalLoadException exception = Assert.Throws<GoalLoadException>(() => new GoalLoader().Load(_root));

        Assert.Contains(path, exception.Message, StringComparison.Ordinal);
    }
}
