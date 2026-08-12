using AtlasFlow.Domain.Execution;

namespace AtlasFlow.Domain.Intelligence;

/// <summary>The durable lifecycle status of an implementation task report.</summary>
public enum TaskReportStatus
{
    Planned,
    Running,
    Success,
    Failed,
    Blocked,
    Cancelled,
}

/// <summary>How a measurement was obtained.</summary>
public enum MeasurementProvenance
{
    Observed,
    Estimated,
    Allocated,
    Unknown,
}

/// <summary>Confidence attached to a non-direct measurement.</summary>
public enum MeasurementConfidence
{
    Low,
    Medium,
    High,
    Unknown,
}

/// <summary>Token counts kept separate so input economy can be measured.</summary>
public sealed record TokenUsage
{
    public int Input { get; init; }

    public int Output { get; init; }

    public int Cached { get; init; }

    public int IntermediateOutput { get; init; }

    public int Retrieved { get; init; }

    public int Injected { get; init; }
}

/// <summary>A monetary measurement with honest provenance.</summary>
public sealed record CostMeasurement
{
    public required decimal Amount { get; init; }

    public required string Currency { get; init; }

    public required MeasurementProvenance Provenance { get; init; }

    public required MeasurementConfidence Confidence { get; init; }
}

/// <summary>A compact report for one implementation task.</summary>
/// <remarks>
/// The report is intentionally a summary. Raw traces remain operational state
/// and are not copied into the canonical Project Intelligence file.
/// </remarks>
public sealed record TaskReport
{
    public required string Id { get; init; }

    public required TaskReportStatus Status { get; init; }

    public string Type { get; init; } = string.Empty;

    public IReadOnlyList<string> Components { get; init; } = [];

    public RiskLevel? Risk { get; init; }

    public string Complexity { get; init; } = string.Empty;

    public string Strategy { get; init; } = string.Empty;

    public TokenUsage Tokens { get; init; } = new();

    public CostMeasurement? DirectCost { get; init; }

    public IReadOnlyList<string> ChangedFiles { get; init; } = [];

    public IReadOnlyList<string> Tests { get; init; } = [];

    public IReadOnlyList<string> Documentation { get; init; } = [];

    public IReadOnlyList<string> Debt { get; init; } = [];

    public IReadOnlyList<string> Evidence { get; init; } = [];

    public IReadOnlyList<string> Models { get; init; } = [];

    public DateTimeOffset? StartedAt { get; init; }

    public DateTimeOffset? FinishedAt { get; init; }
}

/// <summary>Project-level aggregates recomputed from task reports.</summary>
public sealed record ProjectIntelligenceSummary
{
    public required int Tasks { get; init; }

    public required long InputTokens { get; init; }

    public required long OutputTokens { get; init; }

    public required long CachedTokens { get; init; }

    public required long IntermediateOutputTokens { get; init; }

    public required decimal DirectCost { get; init; }
}

/// <summary>Versioned, durable Project Intelligence snapshot.</summary>
public sealed record ProjectIntelligenceSnapshot
{
    public required int Version { get; init; }

    public required DateTimeOffset UpdatedAt { get; init; }

    public required ProjectIntelligenceSummary Summary { get; init; }

    public IReadOnlyList<TaskReport> Tasks { get; init; } = [];

    public IReadOnlyList<string> Debt { get; init; } = [];
}
