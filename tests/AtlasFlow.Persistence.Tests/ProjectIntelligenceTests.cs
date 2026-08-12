using System.Text.Json.Nodes;

using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Intelligence;
using AtlasFlow.Persistence;

namespace AtlasFlow.Persistence.Tests;

public sealed class ProjectIntelligenceTests : IDisposable
{
    private readonly string _root =
        Path.Combine(Path.GetTempPath(), $"atlas-intelligence-{Guid.NewGuid():N}");

    public ProjectIntelligenceTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    [Fact]
    public async Task MissingHistoryStartsEmptyWithoutCreatingAFile()
    {
        using ProjectIntelligenceRepository repository = new(_root);

        ProjectIntelligenceSnapshot snapshot = await repository.LoadAsync();

        Assert.Equal(0, snapshot.Summary.Tasks);
        Assert.False(File.Exists(Path.Combine(_root, ".atlas", "history", "project-intelligence.json")));
    }

    [Fact]
    public async Task RecordingAReportRecomputesTokenAndCostAggregates()
    {
        using ProjectIntelligenceRepository repository = new(_root);

        ProjectIntelligenceSnapshot snapshot = await repository.RecordAsync(new TaskReport
        {
            Id = "task-1",
            Status = TaskReportStatus.Success,
            Components = ["orchestration"],
            Risk = RiskLevel.Medium,
            Tokens = new TokenUsage
            {
                Input = 100,
                Output = 40,
                Cached = 20,
                IntermediateOutput = 10,
            },
            DirectCost = new CostMeasurement
            {
                Amount = 0.125m,
                Currency = "USD",
                Provenance = MeasurementProvenance.Observed,
                Confidence = MeasurementConfidence.High,
            },
        });

        Assert.Equal(1, snapshot.Summary.Tasks);
        Assert.Equal(100, snapshot.Summary.InputTokens);
        Assert.Equal(40, snapshot.Summary.OutputTokens);
        Assert.Equal(20, snapshot.Summary.CachedTokens);
        Assert.Equal(10, snapshot.Summary.IntermediateOutputTokens);
        Assert.Equal(0.125m, snapshot.Summary.DirectCost);
        Assert.True(File.Exists(Path.Combine(_root, ".atlas", "history", "project-intelligence.json")));
        Assert.Empty(Directory.EnumerateFiles(
            Path.Combine(_root, ".atlas", "history"),
            ".project-intelligence.json.*.tmp"));
    }

    [Fact]
    public async Task UpdatingAReportPreservesUnknownRootAndTaskFields()
    {
        string directory = Path.Combine(_root, ".atlas", "history");
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, "project-intelligence.json");
        await File.WriteAllTextAsync(
            path,
            """
            {
              "version": 1,
              "updated_at": "2026-08-12T12:00:00Z",
              "summary": {},
              "tasks": [{
                "id": "task-1",
                "status": "success",
                "tokens": {},
                "future_task_field": "keep-me"
              }],
              "debt": [],
              "future_root_field": {"keep": true}
            }
            """);

        using ProjectIntelligenceRepository repository = new(_root);
        await repository.RecordAsync(new TaskReport
        {
            Id = "task-1",
            Status = TaskReportStatus.Failed,
        });

        JsonObject document = JsonNode.Parse(await File.ReadAllTextAsync(path))!.AsObject();
        Assert.Equal("keep-me", document["tasks"]![0]!["future_task_field"]!.GetValue<string>());
        Assert.True(document["future_root_field"]!["keep"]!.GetValue<bool>());
        Assert.Equal("failed", document["tasks"]![0]!["status"]!.GetValue<string>());
    }

    [Fact]
    public async Task AnAtlasManifestCannotRedirectHistoryOutsideTheProject()
    {
        await File.WriteAllTextAsync(
            Path.Combine(_root, "atlas.json"),
            """
            {
              "intelligence": {"path": "../outside/project-intelligence.json"}
            }
            """);

        using ProjectIntelligenceRepository repository = new(_root);

        IntelligenceFormatException exception = await Assert.ThrowsAsync<IntelligenceFormatException>(
            () => repository.LoadAsync());

        Assert.Contains("escapes", exception.Message, StringComparison.Ordinal);
    }
}
