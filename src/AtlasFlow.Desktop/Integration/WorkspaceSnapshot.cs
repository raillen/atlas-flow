using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Projects;

namespace AtlasFlow.Desktop.Integration;

/// <summary>
/// Resultado agregado das consultas necessárias para compor o shell.
/// </summary>
/// <remarks>
/// O snapshot reutiliza os contratos públicos do núcleo. Ele não redefine
/// modos, capabilities, Goals ou estados no projeto Desktop.
/// </remarks>
public sealed record WorkspaceSnapshot(
    ProjectInspection? Project,
    IReadOnlyList<Goal> Goals,
    string ConnectionDescription)
{
    public static WorkspaceSnapshot BackendUnavailable { get; } = new(
        Project: null,
        Goals: [],
        ConnectionDescription: "Frontend disponível · backend aguardando integração");
}
