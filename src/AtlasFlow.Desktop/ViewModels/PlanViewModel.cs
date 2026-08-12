using System.Collections.ObjectModel;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Context;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Intelligence;
using AtlasFlow.Domain.Planning;

using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace AtlasFlow.Desktop.ViewModels;

/// <summary>Reviewing and locking the plan selected for the workspace.</summary>
/// <remarks>
/// The view model owns presentation state only. Plan validity, immutability and
/// the transition to <see cref="PlanState.Locked"/> remain application rules.
/// </remarks>
public sealed partial class PlanViewModel : ObservableObject
{
    private readonly IPlanService _plans;
    private readonly IProjectIntelligenceService? _intelligenceService;
    private Goal? _goal;

    public PlanViewModel(
        IPlanService plans,
        IProjectIntelligenceService? intelligenceService = null)
    {
        _plans = plans;
        _intelligenceService = intelligenceService;
    }

    public ObservableCollection<Plan> Plans { get; } = [];

    public Goal? Goal => _goal;

    public bool HasGoal => _goal is not null;

    public bool HasPlans => Plans.Count > 0;

    public bool CanCreatePlan => HasGoal && !IsBusy;

    public bool CanLockPlan => SelectedPlan?.State == PlanState.Draft && !IsBusy;

    public string GoalTitle => _goal?.Title ?? "Nenhum Goal selecionado";

    public string GoalObjective => _goal?.Objective ?? "Selecione um Goal para desenhar um plano.";

    public string SelectedPlanState => SelectedPlan?.State.ToString().ToUpperInvariant() ?? "SEM PLANO";

    public string SelectedPlanSummary => SelectedPlan is null
        ? "Nenhum snapshot criado"
        : $"{SelectedPlan.Tasks.Count} tarefa(s) · {SelectedPlan.Runner} · integra em {SelectedPlan.IntegrationTarget}";

    public string SelectedContextState => SelectedPlan?.Context is null
        ? "Contexto ainda não planejado"
        : $"{ProfileLabel(SelectedPlan.Context.Profile)} · "
          + $"{StrategyLabel(SelectedPlan.Context.Strategy)} · "
          + ModeLabel(SelectedPlan.Context.Mode);

    public string SelectedContextSummary => SelectedPlan?.Context is not { } context
        ? "Crie um snapshot para registrar a decisão LPC/PCA junto do plano."
        : $"Entrada: {context.Budget.ContextTargetTokens}/{context.Budget.ContextHardTokens} tokens · "
          + $"saída: {context.Budget.OutputTargetTokens}/{context.Budget.OutputHardTokens} · "
          + $"expansão: {context.Budget.MaxExpansionRounds} · delegação: {context.Budget.MaxDelegationDepth}";

    public string SelectedContextReasons => SelectedPlan?.Context is not { } context
        ? "Nenhum payload é enviado antes de existir uma decisão revisável."
        : context.Reasons.Count == 0
            ? "Sem justificativa adicional registrada."
            : $"Motivo: {string.Join(" · ", context.Reasons)} · fonte: {context.Source}";

    public string IntelligenceStatusLabel => Intelligence is null
        ? _intelligenceService is null
            ? "Project Intelligence aguardando integração"
            : "Histórico de inteligência indisponível"
        : Intelligence.Summary.Tasks == 0
            ? "Nenhum relatório registrado"
            : $"Snapshot carregado · {Intelligence.Summary.Tasks} relatório(s)";

    public string IntelligenceSummaryLabel => Intelligence is null
        ? "A inteligência do projeto aparecerá depois do primeiro plano."
        : $"{Intelligence.Summary.InputTokens} tokens de entrada · "
          + $"{Intelligence.Summary.OutputTokens} de saída · "
          + $"{Intelligence.Summary.IntermediateOutputTokens} intermediários";

    public string IntelligenceCostLabel => Intelligence is null || Intelligence.Summary.DirectCost == 0
        ? "Custo direto: não observado"
        : "Custo direto: registrado com provenance";

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanLockPlan))]
    [NotifyPropertyChangedFor(nameof(SelectedPlanState))]
    [NotifyPropertyChangedFor(nameof(SelectedPlanSummary))]
    [NotifyPropertyChangedFor(nameof(SelectedContextState))]
    [NotifyPropertyChangedFor(nameof(SelectedContextSummary))]
    [NotifyPropertyChangedFor(nameof(SelectedContextReasons))]
    private Plan? _selectedPlan;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(IntelligenceStatusLabel))]
    [NotifyPropertyChangedFor(nameof(IntelligenceSummaryLabel))]
    [NotifyPropertyChangedFor(nameof(IntelligenceCostLabel))]
    private ProjectIntelligenceSnapshot? _intelligence;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanCreatePlan))]
    [NotifyPropertyChangedFor(nameof(CanLockPlan))]
    private bool _isBusy;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasError))]
    private string? _errorMessage;

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    /// <summary>Loads plan history for the Goal currently visible in the shell.</summary>
    public async Task LoadAsync(Goal? goal, CancellationToken cancellationToken = default)
    {
        _goal = goal;
        Plans.Clear();
        SelectedPlan = null;
        Intelligence = null;
        ErrorMessage = null;
        NotifyGoalChanged();

        if (goal is null)
        {
            return;
        }

        IsBusy = true;
        try
        {
            IReadOnlyList<Plan> plans = await _plans
                .ListForGoalAsync(goal.Id, cancellationToken)
                .ConfigureAwait(true);

            foreach (Plan plan in plans)
            {
                Plans.Add(plan);
            }

            SelectedPlan = Plans.FirstOrDefault();
            await LoadIntelligenceAsync(cancellationToken).ConfigureAwait(true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception)
        {
            ErrorMessage = exception.Message;
        }
        finally
        {
            IsBusy = false;
            OnPropertyChanged(nameof(HasPlans));
        }
    }

    public async Task CreateDraftAsync(CancellationToken cancellationToken = default)
    {
        if (_goal is null)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            Plan created = await _plans.CreateAsync(
                new CreatePlanRequest { GoalId = _goal.Id },
                cancellationToken).ConfigureAwait(true);

            Plans.Insert(0, created);
            SelectedPlan = created;
            await LoadIntelligenceAsync(cancellationToken).ConfigureAwait(true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception)
        {
            ErrorMessage = exception.Message;
        }
        finally
        {
            IsBusy = false;
            OnPropertyChanged(nameof(HasPlans));
        }
    }

    public async Task LockSelectedAsync(CancellationToken cancellationToken = default)
    {
        if (SelectedPlan is null || SelectedPlan.State != PlanState.Draft)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            Plan locked = await _plans
                .LockAsync(SelectedPlan.Id, cancellationToken)
                .ConfigureAwait(true);

            int index = Plans.IndexOf(SelectedPlan);
            if (index >= 0)
            {
                Plans[index] = locked;
            }

            SelectedPlan = locked;
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception)
        {
            ErrorMessage = exception.Message;
        }
        finally
        {
            IsBusy = false;
        }
    }

    [RelayCommand(CanExecute = nameof(CanCreatePlan))]
    private Task CreatePlanAsync(CancellationToken cancellationToken) => CreateDraftAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanLockPlan))]
    private Task LockPlanAsync(CancellationToken cancellationToken) => LockSelectedAsync(cancellationToken);

    partial void OnIsBusyChanged(bool value)
    {
        CreatePlanCommand.NotifyCanExecuteChanged();
        LockPlanCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedPlanChanged(Plan? value)
    {
        CreatePlanCommand.NotifyCanExecuteChanged();
        LockPlanCommand.NotifyCanExecuteChanged();
    }

    private void NotifyGoalChanged()
    {
        OnPropertyChanged(nameof(Goal));
        OnPropertyChanged(nameof(HasGoal));
        OnPropertyChanged(nameof(GoalTitle));
        OnPropertyChanged(nameof(GoalObjective));
        OnPropertyChanged(nameof(CanCreatePlan));
        CreatePlanCommand.NotifyCanExecuteChanged();
    }

    private async Task LoadIntelligenceAsync(CancellationToken cancellationToken)
    {
        if (_intelligenceService is null)
        {
            Intelligence = null;
            return;
        }

        try
        {
            Intelligence = await _intelligenceService
                .GetAsync(cancellationToken)
                .ConfigureAwait(true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch
        {
            // Project Intelligence is a derived projection. Its unavailability
            // must not hide an otherwise usable Goal and Plan workspace.
            Intelligence = null;
        }
    }

    private static string ProfileLabel(ContextProfile profile) => profile switch
    {
        ContextProfile.Small => "Small",
        ContextProfile.Medium => "Medium",
        ContextProfile.Large => "Large",
        _ => profile.ToString(),
    };

    private static string StrategyLabel(ContextStrategy strategy) => strategy switch
    {
        ContextStrategy.Direct => "Direct",
        ContextStrategy.StructuralRetrieval => "Structural retrieval",
        ContextStrategy.ContextPack => "Context pack",
        ContextStrategy.ProgressiveRetrieval => "Progressive retrieval",
        _ => strategy.ToString(),
    };

    private static string ModeLabel(ContextMode mode) => mode switch
    {
        ContextMode.Legacy => "Legacy",
        ContextMode.Progressive => "Progressive",
        _ => mode.ToString(),
    };
}
