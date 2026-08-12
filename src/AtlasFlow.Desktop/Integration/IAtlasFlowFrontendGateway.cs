namespace AtlasFlow.Desktop.Integration;

/// <summary>
/// Porta de leitura que o renderer necessita do núcleo do Atlas Flow.
/// </summary>
/// <remarks>
/// A implementação futura adapta <c>AtlasFlow.Application</c> para estes read
/// models. O backend não referencia o projeto Desktop, e a UI não conhece
/// persistência, processos, transporte ou tipos internos de orquestração.
/// </remarks>
public interface IAtlasFlowFrontendGateway
{
    Task<WorkspaceSnapshot> LoadWorkspaceAsync(CancellationToken cancellationToken);
}
