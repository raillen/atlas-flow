using AtlasFlow.Domain;

namespace AtlasFlow.Application.Contracts;

/// <summary>Which model each role resolved to, and why.</summary>
/// <remarks>
/// There is no provider SDK anywhere in Atlas Flow and there will not be one
/// (ADR-012). Models are reached through Command Code and ACP, so this service
/// reports discovery rather than performing it.
/// </remarks>
public interface IRoutingService
{
    /// <summary>The current routing picture for the project.</summary>
    Task<RoutingSnapshot> GetSnapshotAsync(CancellationToken cancellationToken = default);

    /// <summary>What a specific run actually routed to.</summary>
    Task<RoutingSnapshot?> GetForRunAsync(RunId runId, CancellationToken cancellationToken = default);
}

/// <summary>Whether model discovery reached anything.</summary>
public enum RoutingState
{
    /// <summary>Not probed yet. Probing costs a subprocess round trip.</summary>
    Pending,

    Reachable,

    /// <summary>Reachable, but not everything the policy expects is present.</summary>
    Degraded,
}

/// <summary>How one model has performed.</summary>
public sealed record ModelStats
{
    public required string ModelKey { get; init; }

    public required int Uses { get; init; }

    public required int Successes { get; init; }

    public required int Failures { get; init; }

    public required double SuccessRate { get; init; }

    public required double AverageLatencyMs { get; init; }
}

/// <summary>What one abstract role resolved to.</summary>
public sealed record RoleRoute
{
    public required string Role { get; init; }

    public string? Selected { get; init; }

    public string? Provider { get; init; }

    /// <summary>Why this model and not another. Rendered, so it is for a person.</summary>
    public required string Explanation { get; init; }

    public int FallbackAttempts { get; init; }
}

/// <summary>Routing as of one moment.</summary>
public sealed record RoutingSnapshot
{
    public required RoutingState State { get; init; }

    /// <summary>Why the state is what it is.</summary>
    public required string Reason { get; init; }

    public required DateTimeOffset ProbedAt { get; init; }

    public IReadOnlyList<string> Available { get; init; } = [];

    public IReadOnlyList<RoleRoute> Roles { get; init; } = [];

    /// <summary>
    /// Observed performance per model.
    /// </summary>
    /// <remarks>
    /// Fed and persisted, but routing order is still the deterministic policy
    /// order. Reordering candidates by observed success is RFC-001 and is not
    /// implemented — the numbers are shown, not used.
    /// </remarks>
    public IReadOnlyList<ModelStats> Stats { get; init; } = [];
}
