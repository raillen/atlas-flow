using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Planning;

namespace AtlasFlow.Desktop.Integration;

/// <summary>Explicit fallback for XAML/design-time construction.</summary>
public sealed class UnavailablePlanService : IPlanService
{
    private static InvalidOperationException Unavailable() =>
        new InvalidOperationException("Plan service is unavailable until the application composition root is connected.");

    public Task<IReadOnlyList<Plan>> ListForGoalAsync(
        GoalId goalId,
        CancellationToken cancellationToken = default) =>
        Task.FromException<IReadOnlyList<Plan>>(Unavailable());

    public Task<Plan?> FindAsync(PlanId id, CancellationToken cancellationToken = default) =>
        Task.FromException<Plan?>(Unavailable());

    public Task<Plan> CreateAsync(
        CreatePlanRequest request,
        CancellationToken cancellationToken = default) =>
        Task.FromException<Plan>(Unavailable());

    public Task<Plan> LockAsync(PlanId id, CancellationToken cancellationToken = default) =>
        Task.FromException<Plan>(Unavailable());
}
