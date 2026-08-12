using System.Collections.ObjectModel;
using AtlasFlow.Desktop.Integration;
using AtlasFlow.Domain.Projects;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace AtlasFlow.Desktop.ViewModels;

public sealed partial class WorkspaceViewModel : ObservableObject
{
    public const double ExpandedNavigationWidth = 232;
    public const double CompactNavigationWidth = 64;
    public const double DefaultContextWidth = 384;

    private readonly IAtlasFlowFrontendGateway _gateway;
    private readonly IThemeController _themeController;
    private readonly PlanViewModel _plan;
    private readonly RunViewModel _run;
    private readonly DiscussViewModel _discuss;
    private WorkspaceStageViewModel _selectedStage;

    public WorkspaceViewModel(
        IAtlasFlowFrontendGateway gateway,
        IThemeController themeController,
        PlanViewModel plan,
        RunViewModel run,
        DiscussViewModel? discuss = null)
    {
        _gateway = gateway;
        _themeController = themeController;
        _plan = plan;
        _run = run;
        _discuss = discuss ?? new DiscussViewModel();

        Stages =
        [
            new("attention", "Attention", "COMMAND CENTER", "Veja bloqueios, decisões e trabalho que precisa de supervisão.", "Revisar o que requer atenção", true),
            new("define", "Define", "DISCUSS", "Transforme intenção em conversa, decisões e um Project Draft verificável.", "Iniciar ou retomar uma conversa", true),
            new("plan", "Plan", "GOAL PLANNING", "Revise escopo, dependências, riscos e gates antes de bloquear o plano.", "Selecionar um Goal para planejar", false),
            new("run", "Run", "EXECUTION", "Acompanhe tasks, agentes, worktrees e eventos sem perder o contexto atual.", "Abrir uma execução ativa", false),
            new("review", "Review", "EVIDENCE", "Relacione critérios de aceite, gates e evidências antes de concluir um Goal.", "Revisar a matriz de evidências", false),
            new("knowledge", "Knowledge", "PROJECT TRUTH", "Navegue por documentação, ADRs, Goals e conhecimento canônico do projeto.", "Explorar a verdade mantida em Git", true),
        ];

        _selectedStage = Stages[0];
        ThemeModeLabel = _themeController.CurrentMode;
    }

    public ObservableCollection<WorkspaceStageViewModel> Stages { get; }

    public WorkspaceStageViewModel SelectedStage
    {
        get => _selectedStage;
        set
        {
            if (value is null || !value.IsEnabled)
            {
                OnPropertyChanged();
                return;
            }

            SetProperty(ref _selectedStage, value);
            OnPropertyChanged(nameof(IsPlanStageSelected));
            OnPropertyChanged(nameof(IsRunStageSelected));
            OnPropertyChanged(nameof(IsDefineStageSelected));
            OnPropertyChanged(nameof(IsPrimarySurfaceVisible));
        }
    }

    public PlanViewModel Plan => _plan;

    public RunViewModel Run => _run;

    public DiscussViewModel Discuss => _discuss;

    public bool IsDefineStageSelected => string.Equals(
        SelectedStage.Key,
        "define",
        StringComparison.Ordinal);

    public bool IsPlanStageSelected => string.Equals(
        SelectedStage.Key,
        "plan",
        StringComparison.Ordinal);

    public bool IsRunStageSelected => string.Equals(
        SelectedStage.Key,
        "run",
        StringComparison.Ordinal);

    public bool IsPrimarySurfaceVisible =>
        !IsDefineStageSelected && !IsPlanStageSelected && !IsRunStageSelected;

    [ObservableProperty]
    public partial string ProjectName { get; private set; } = "Nenhum projeto aberto";

    [ObservableProperty]
    public partial string ProjectPath { get; private set; } = "Selecione um workspace Project Atlas";

    [ObservableProperty]
    public partial string ProjectModeLabel { get; private set; } = "Aguardando projeto";

    [ObservableProperty]
    public partial string ProjectModeDescription { get; private set; } = "Carregando contexto do workspace.";

    [ObservableProperty]
    public partial string ConnectionDescription { get; private set; } = "Inicializando frontend";

    [ObservableProperty]
    public partial string GoalSummaryLabel { get; private set; } = "Nenhum Goal carregado";

    [ObservableProperty]
    public partial string? ErrorMessage { get; private set; }

    [ObservableProperty]
    public partial bool IsBusy { get; private set; }

    [ObservableProperty]
    public partial bool IsNavigationExpanded { get; private set; } = true;

    [ObservableProperty]
    public partial double NavigationPanelWidth { get; private set; } = ExpandedNavigationWidth;

    [ObservableProperty]
    public partial bool IsContextVisible { get; private set; } = true;

    [ObservableProperty]
    public partial double ContextPanelWidth { get; private set; } = DefaultContextWidth;

    [ObservableProperty]
    public partial string ThemeModeLabel { get; private set; }

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        if (IsBusy)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;

        try
        {
            WorkspaceSnapshot snapshot = await _gateway.LoadWorkspaceAsync(cancellationToken);
            ApplySnapshot(snapshot);
            await _plan.LoadAsync(
                snapshot.Project?.Mode == ProjectMode.AtlasReady
                    ? snapshot.Goals.Count > 0 ? snapshot.Goals[0] : null
                    : null,
                cancellationToken).ConfigureAwait(true);
            await _discuss.LoadAsync(cancellationToken).ConfigureAwait(true);
            await _run.LoadAsync(cancellationToken).ConfigureAwait(true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
            ErrorMessage = "Não foi possível carregar o workspace. Verifique a integração e tente novamente.";
            ConnectionDescription = "Frontend disponível · integração indisponível";
            await _plan.LoadAsync(null, cancellationToken).ConfigureAwait(true);
            await _discuss.LoadAsync(cancellationToken).ConfigureAwait(true);
            await _run.LoadAsync(cancellationToken).ConfigureAwait(true);
        }
        finally
        {
            IsBusy = false;
        }
    }

    public void SelectStage(string key)
    {
        WorkspaceStageViewModel? stage = Stages.FirstOrDefault(
            candidate => string.Equals(candidate.Key, key, StringComparison.Ordinal));

        if (stage is not null)
        {
            SelectedStage = stage;
        }
    }

    [RelayCommand]
    private void ToggleNavigation()
    {
        IsNavigationExpanded = !IsNavigationExpanded;
        NavigationPanelWidth = IsNavigationExpanded ? ExpandedNavigationWidth : CompactNavigationWidth;
    }

    [RelayCommand]
    private void ToggleContext()
    {
        IsContextVisible = !IsContextVisible;
        ContextPanelWidth = IsContextVisible ? DefaultContextWidth : 0;
    }

    [RelayCommand]
    private void ToggleTheme() => ThemeModeLabel = _themeController.Toggle();

    partial void OnErrorMessageChanged(string? value) => OnPropertyChanged(nameof(HasError));

    private void ApplySnapshot(WorkspaceSnapshot snapshot)
    {
        ConnectionDescription = snapshot.ConnectionDescription;
        GoalSummaryLabel = snapshot.Goals.Count == 0
            ? "Nenhum Goal carregado"
            : $"{snapshot.Goals.Count} Goal(s) no projeto";

        if (snapshot.Project is null)
        {
            ProjectName = "Nenhum projeto aberto";
            ProjectPath = "Selecione um workspace Project Atlas";
            ProjectModeLabel = "Núcleo conectado";
            ProjectModeDescription = "Nenhum projeto aberto. Selecione um workspace Project Atlas para continuar.";
            SetStageAvailability("define", true);
            SetStageAvailability("plan", false);
            SetStageAvailability("run", false);
            SetStageAvailability("review", false);
            SetStageAvailability("knowledge", true);
            return;
        }

        ProjectName = snapshot.Project.ProjectName;
        ProjectPath = snapshot.Project.Root;
        ProjectModeLabel = LabelFor(snapshot.Project.Mode);
        ProjectModeDescription = snapshot.Project.Reason;

        SetStageAvailability("define", snapshot.Project.Capabilities.CanDiscuss);
        SetStageAvailability("plan", snapshot.Project.Capabilities.CanPlan);
        SetStageAvailability("run", snapshot.Project.Capabilities.CanRun);
        SetStageAvailability("review", snapshot.Project.Capabilities.CanReview);
        SetStageAvailability("knowledge", snapshot.Project.Capabilities.CanExplore);
    }

    private void SetStageAvailability(string key, bool isEnabled)
    {
        WorkspaceStageViewModel? stage = Stages.FirstOrDefault(
            candidate => string.Equals(candidate.Key, key, StringComparison.Ordinal));

        if (stage is not null)
        {
            stage.IsEnabled = isEnabled;
        }
    }

    private static string LabelFor(ProjectMode mode) => mode switch
    {
        ProjectMode.External => "Projeto externo",
        ProjectMode.AtlasNeedsAdaptation => "Adaptação necessária",
        ProjectMode.AtlasIncompatible => "Atlas incompatível",
        ProjectMode.AtlasReady => "Project Atlas pronto",
        _ => throw new ArgumentOutOfRangeException(nameof(mode), mode, "Modo de projeto desconhecido."),
    };
}
