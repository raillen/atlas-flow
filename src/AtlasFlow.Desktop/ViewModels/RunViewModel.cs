using System.Collections.ObjectModel;
using System.ComponentModel;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Execution;
using AtlasFlow.Domain.Planning;

using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace AtlasFlow.Desktop.ViewModels;

/// <summary>Supervising runs through the durable event stream.</summary>
/// <remarks>
/// The view model reads the initial detail once and refreshes only when the
/// application announces an event. It never polls a run on a timer, and it
/// does not infer canonical state from a guessed local transition.
/// </remarks>
public sealed partial class RunViewModel : ObservableObject
{
    private readonly IRunService _runs;
    private readonly PlanViewModel _plan;
    private CancellationTokenSource? _watchCancellation;
    private bool _suppressSelectionReaction;

    public RunViewModel(IRunService runs, PlanViewModel plan)
    {
        _runs = runs;
        _plan = plan;
        _plan.PropertyChanged += OnPlanPropertyChanged;
    }

    public ObservableCollection<Run> Runs { get; } = [];

    public ObservableCollection<RunTask> Tasks { get; } = [];

    public ObservableCollection<DomainEvent> Events { get; } = [];

    public bool HasRuns => Runs.Count > 0;

    public bool HasSelectedRun => SelectedRun is not null;

    public bool CanStartRun =>
        _plan.SelectedPlan?.State == PlanState.Locked
        && !IsBusy
        && !IsWatching;

    public bool CanCancelRun =>
        SelectedRun is not null
        && !SelectedRun.State.IsTerminal()
        && !IsBusy;

    public string SelectedRunState => SelectedRun?.State.ToString().ToUpperInvariant() ?? "SEM RUN";

    public string SelectedRunSummary => SelectedRun is null
        ? "Selecione uma execução para acompanhar o estado e os eventos."
        : $"{Tasks.Count} task(s) · {Events.Count} evento(s) · {SelectedRun.Autonomy}";

    public string TaskProgress => Tasks.Count == 0
        ? "Nenhuma task materializada"
        : $"{Tasks.Count(task => task.State.IsTerminal())}/{Tasks.Count} tasks encerradas";

    public string StreamStatus => IsWatching
        ? "Recebendo eventos ao vivo"
        : "Stream encerrado ou não iniciado";

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasSelectedRun))]
    [NotifyPropertyChangedFor(nameof(CanCancelRun))]
    [NotifyPropertyChangedFor(nameof(SelectedRunState))]
    [NotifyPropertyChangedFor(nameof(SelectedRunSummary))]
    private Run? _selectedRun;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanStartRun))]
    [NotifyPropertyChangedFor(nameof(CanCancelRun))]
    private bool _isBusy;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanStartRun))]
    private bool _isWatching;

    [ObservableProperty]
    private RunDetail? _selectedRunDetail;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasError))]
    private string? _errorMessage;

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    /// <summary>Loads run history and observes the newest run, when present.</summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        StopWatching();
        Runs.Clear();
        Tasks.Clear();
        Events.Clear();
        SelectedRunDetail = null;
        ErrorMessage = null;

        try
        {
            IReadOnlyList<Run> runs = await _runs
                .ListAsync(cancellationToken)
                .ConfigureAwait(true) ?? [];

            foreach (Run run in runs)
            {
                Runs.Add(run);
            }

            OnPropertyChanged(nameof(HasRuns));
            SetSelectedRun(Runs.FirstOrDefault());

            if (SelectedRun is not null)
            {
                await ObserveAsync(SelectedRun, cancellationToken).ConfigureAwait(true);
            }
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception)
        {
            ErrorMessage = exception.Message;
        }
    }

    public async Task StartSelectedPlanAsync(CancellationToken cancellationToken = default)
    {
        Plan? plan = _plan.SelectedPlan;
        if (plan is null || plan.State != PlanState.Locked)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            Run started = await _runs.StartAsync(
                new StartRunRequest
                {
                    GoalId = plan.GoalId,
                    PlanId = plan.Id,
                    Runner = plan.Runner,
                    IntegrationTarget = plan.IntegrationTarget,
                },
                cancellationToken).ConfigureAwait(true);

            await _plan.LoadAsync(_plan.Goal, cancellationToken).ConfigureAwait(true);
            SetSelectedRun(started);
            await ObserveAsync(started, cancellationToken).ConfigureAwait(true);
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

    public async Task CancelSelectedRunAsync(CancellationToken cancellationToken = default)
    {
        Run? run = SelectedRun;
        if (run is null || run.State.IsTerminal())
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            await _runs.CancelAsync(run.Id, cancellationToken).ConfigureAwait(true);
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

    [RelayCommand(CanExecute = nameof(CanStartRun))]
    private Task StartRunAsync(CancellationToken cancellationToken) => StartSelectedPlanAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanCancelRun))]
    private Task CancelRunAsync(CancellationToken cancellationToken) => CancelSelectedRunAsync(cancellationToken);

    partial void OnSelectedRunChanged(Run? oldValue, Run? newValue)
    {
        StartRunCommand.NotifyCanExecuteChanged();
        CancelRunCommand.NotifyCanExecuteChanged();

        if (_suppressSelectionReaction || oldValue?.Id == newValue?.Id)
        {
            return;
        }

        _ = ObserveSelectionAsync(newValue);
    }

    partial void OnIsBusyChanged(bool value)
    {
        StartRunCommand.NotifyCanExecuteChanged();
        CancelRunCommand.NotifyCanExecuteChanged();
    }

    partial void OnIsWatchingChanged(bool value)
    {
        StartRunCommand.NotifyCanExecuteChanged();
        OnPropertyChanged(nameof(StreamStatus));
    }

    partial void OnErrorMessageChanged(string? value) => OnPropertyChanged(nameof(HasError));

    private async Task ObserveSelectionAsync(Run? run)
    {
        try
        {
            await ObserveAsync(run, CancellationToken.None).ConfigureAwait(true);
        }
        catch (OperationCanceledException)
        {
            // Selection changes cancel the previous stream by design.
        }
        catch (Exception exception)
        {
            ErrorMessage = exception.Message;
        }
    }

    private async Task ObserveAsync(Run? run, CancellationToken initialCancellation)
    {
        StopWatching();
        Tasks.Clear();
        Events.Clear();
        SelectedRunDetail = null;
        OnPropertyChanged(nameof(SelectedRunSummary));
        OnPropertyChanged(nameof(TaskProgress));

        if (run is null)
        {
            IsWatching = false;
            return;
        }

        using CancellationTokenSource watchCancellation = new();
        using CancellationTokenSource linkedCancellation =
            CancellationTokenSource.CreateLinkedTokenSource(initialCancellation, watchCancellation.Token);
        _watchCancellation = watchCancellation;

        try
        {
            IsBusy = true;
            RunDetail? detail = await _runs
                .FindAsync(run.Id, linkedCancellation.Token)
                .ConfigureAwait(true);
            if (detail is not null)
            {
                ApplyDetail(detail);
            }

            IsBusy = false;
            IsWatching = !run.State.IsTerminal();
            if (!IsWatching)
            {
                return;
            }

            await foreach (DomainEvent _ in _runs
                .WatchAsync(run.Id, linkedCancellation.Token)
                .ConfigureAwait(true))
            {
                RunDetail? refreshed = await _runs
                    .FindAsync(run.Id, linkedCancellation.Token)
                    .ConfigureAwait(true);
                if (refreshed is not null)
                {
                    ApplyDetail(refreshed);
                }
            }

            RunDetail? final = await _runs
                .FindAsync(run.Id, linkedCancellation.Token)
                .ConfigureAwait(true);
            if (final is not null)
            {
                ApplyDetail(final);
            }
        }
        finally
        {
            IsBusy = false;
            if (ReferenceEquals(_watchCancellation, watchCancellation))
            {
                _watchCancellation = null;
                IsWatching = false;
            }
        }
    }

    private void ApplyDetail(RunDetail detail)
    {
        SelectedRunDetail = detail;
        ReplaceRun(detail.Run);

        Tasks.Clear();
        foreach (RunTask task in detail.Tasks)
        {
            Tasks.Add(task);
        }

        Events.Clear();
        foreach (DomainEvent domainEvent in detail.Events)
        {
            Events.Add(domainEvent);
        }

        OnPropertyChanged(nameof(SelectedRunState));
        OnPropertyChanged(nameof(SelectedRunSummary));
        OnPropertyChanged(nameof(TaskProgress));
        CancelRunCommand.NotifyCanExecuteChanged();
    }

    private void ReplaceRun(Run updated)
    {
        Run? existing = Runs.FirstOrDefault(run => run.Id == updated.Id);
        int index = existing is null ? -1 : Runs.IndexOf(existing);
        if (index >= 0)
        {
            Runs[index] = updated;
        }
        else
        {
            Runs.Insert(0, updated);
            OnPropertyChanged(nameof(HasRuns));
        }

        if (SelectedRun?.Id == updated.Id)
        {
            _suppressSelectionReaction = true;
            SelectedRun = updated;
            _suppressSelectionReaction = false;
        }
    }

    private void SetSelectedRun(Run? run)
    {
        _suppressSelectionReaction = true;
        SelectedRun = run;
        _suppressSelectionReaction = false;
    }

    private void StopWatching() => _watchCancellation?.Cancel();

    private void OnPlanPropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        if (eventArgs.PropertyName is nameof(PlanViewModel.SelectedPlan) or nameof(PlanViewModel.Goal))
        {
            OnPropertyChanged(nameof(CanStartRun));
            StartRunCommand.NotifyCanExecuteChanged();
        }
    }
}
