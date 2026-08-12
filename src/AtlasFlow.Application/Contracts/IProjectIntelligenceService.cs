using AtlasFlow.Domain.Intelligence;

namespace AtlasFlow.Application.Contracts;

/// <summary>Reads and updates the project's compact durable intelligence.</summary>
/// <remarks>
/// Raw traces stay operational. This contract exposes only the compact report
/// and aggregate that the UI, review and future routing analysis need.
/// </remarks>
public interface IProjectIntelligenceService
{
    Task<ProjectIntelligenceSnapshot> GetAsync(CancellationToken cancellationToken = default);

    Task<ProjectIntelligenceSnapshot> RecordAsync(
        TaskReport report,
        CancellationToken cancellationToken = default);
}
