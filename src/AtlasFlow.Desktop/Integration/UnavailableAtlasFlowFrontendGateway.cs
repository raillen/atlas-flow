namespace AtlasFlow.Desktop.Integration;

/// <summary>
/// Estado seguro usado enquanto o adaptador para <c>AtlasFlow.Application</c>
/// está sendo portado em paralelo.
/// </summary>
public sealed class UnavailableAtlasFlowFrontendGateway : IAtlasFlowFrontendGateway
{
    public Task<WorkspaceSnapshot> LoadWorkspaceAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(WorkspaceSnapshot.BackendUnavailable);
    }
}
