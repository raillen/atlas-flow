using System.Runtime.CompilerServices;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;

namespace AtlasFlow.Desktop.Integration;

/// <summary>Explicit fallback for XAML/design-time construction.</summary>
public sealed class UnavailableRunService : IRunService
{
    private static InvalidOperationException Unavailable() =>
        new("Run service is unavailable until the application composition root is connected.");

    public Task<IReadOnlyList<Run>> ListAsync(CancellationToken cancellationToken = default) =>
        Task.FromException<IReadOnlyList<Run>>(Unavailable());

    public Task<RunDetail?> FindAsync(RunId id, CancellationToken cancellationToken = default) =>
        Task.FromException<RunDetail?>(Unavailable());

    public Task<Run> StartAsync(StartRunRequest request, CancellationToken cancellationToken = default) =>
        Task.FromException<Run>(Unavailable());

    public Task CancelAsync(RunId id, CancellationToken cancellationToken = default) =>
        Task.FromException(Unavailable());

    public async IAsyncEnumerable<DomainEvent> WatchAsync(
        RunId id,
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        await Task.FromException(Unavailable()).ConfigureAwait(false);
        yield break;
    }

    public async IAsyncEnumerable<DomainEvent> WatchAllAsync(
        [EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        await Task.FromException(Unavailable()).ConfigureAwait(false);
        yield break;
    }
}
