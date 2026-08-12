using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Intelligence;
using AtlasFlow.Persistence;

namespace AtlasFlow.Application.Services;

/// <summary>Application boundary for the durable Project Intelligence file.</summary>
public sealed class ProjectIntelligenceService(ProjectIntelligenceRepository repository)
    : IProjectIntelligenceService
{
    public Task<ProjectIntelligenceSnapshot> GetAsync(CancellationToken cancellationToken = default) =>
        repository.LoadAsync(cancellationToken);

    public Task<ProjectIntelligenceSnapshot> RecordAsync(
        TaskReport report,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(report);
        return repository.RecordAsync(report, cancellationToken);
    }
}
