using System.Collections.ObjectModel;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Goals;
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
    private Goal? _goal;

    public PlanViewModel(IPlanService plans)
    {
        _plans = plans;
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

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanLockPlan))]
    [NotifyPropertyChangedFor(nameof(SelectedPlanState))]
    [NotifyPropertyChangedFor(nameof(SelectedPlanSummary))]
    private Plan? _selectedPlan;

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
}
