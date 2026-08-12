using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Context;
using AtlasFlow.Orchestration.Context;

namespace AtlasFlow.Application.Services;

/// <summary>Application boundary for the LPC/PCA context planner.</summary>
public sealed class ContextService(ContextPlanner planner) : IContextService
{
    public Task<ContextPlan> PlanAsync(
        ContextPlanRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Task);

        return planner.PlanAsync(request.Task, cancellationToken);
    }
}
