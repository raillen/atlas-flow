using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Projects;

namespace AtlasFlow.Desktop.Integration;

/// <summary>
/// Agrega os contratos públicos de aplicação consumidos pelo shell.
/// </summary>
/// <remarks>
/// Este adapter é registrado no composition root do Desktop e mantém o shell
/// dependente apenas do snapshot agregado, sem acoplar a UI a persistência ou
/// à orquestração.
/// </remarks>
public sealed class ApplicationAtlasFlowFrontendGateway(
    IProjectService projects,
    IGoalService goals) : IAtlasFlowFrontendGateway
{
    public async Task<WorkspaceSnapshot> LoadWorkspaceAsync(CancellationToken cancellationToken)
    {
        ProjectInspection? project = await projects.GetCurrentAsync(cancellationToken);
        if (project is null)
        {
            return new WorkspaceSnapshot(
                Project: null,
                Goals: [],
                ConnectionDescription: "Núcleo conectado · nenhum projeto aberto");
        }

        IReadOnlyList<Goal> projectGoals = await goals.ListAsync(cancellationToken);
        return new WorkspaceSnapshot(
            Project: project,
            Goals: projectGoals,
            ConnectionDescription: "Núcleo conectado · projeto carregado");
    }
}
