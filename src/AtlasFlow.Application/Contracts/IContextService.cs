using AtlasFlow.Domain.Context;

namespace AtlasFlow.Application.Contracts;

/// <summary>Plans bounded context before retrieval or task execution.</summary>
/// <remarks>
/// This boundary returns a decision and its limits, never a copied repository
/// payload. It is safe for the desktop to call before showing a task preview.
/// </remarks>
public interface IContextService
{
    Task<ContextPlan> PlanAsync(
        ContextPlanRequest request,
        CancellationToken cancellationToken = default);
}

/// <summary>The task wording used by LPC/PCA classification.</summary>
public sealed record ContextPlanRequest
{
    public required string Task { get; init; }
}
