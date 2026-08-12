using System.Collections.ObjectModel;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;

using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace AtlasFlow.Desktop.ViewModels;

/// <summary>Projects the Define conversation without owning its persistence.</summary>
/// <remarks>
/// Discussion history and reference validation remain application concerns.
/// This view model only keeps the current conversation, composer intent and
/// the references waiting to be submitted by <see cref="IDiscussionService"/>.
/// </remarks>
public sealed partial class DiscussViewModel : ObservableObject
{
    private readonly IDiscussionService? _discussions;

    public DiscussViewModel(IDiscussionService? discussions = null)
    {
        _discussions = discussions;
    }

    public ObservableCollection<DiscussionMessage> Messages { get; } = [];

    public ObservableCollection<MessageReference> References { get; } = [];

    public IReadOnlyList<Decision> Decisions => CurrentDiscussion?.Decisions ?? [];

    public bool HasDiscussion => CurrentDiscussion is not null;

    public bool HasDecisions => Decisions.Count > 0;

    public bool IsDecisionEmptyState => !HasDecisions;

    public bool HasMessages => Messages.Count > 0;

    public bool HasReferences => References.Count > 0;

    public bool IsEmptyState => !HasDiscussion;

    public bool IsServiceUnavailable => _discussions is null;

    public bool CanStartDiscussion => _discussions is not null && !IsBusy;

    public bool CanSendMessage =>
        _discussions is not null
        && CurrentDiscussion is not null
        && !IsBusy
        && !IsFinalized
        && !string.IsNullOrWhiteSpace(DraftMessage);

    public bool CanAddReference =>
        _discussions is not null
        && CurrentDiscussion is not null
        && !IsBusy
        && !IsFinalized
        && !string.IsNullOrWhiteSpace(ReferencePath);

    public bool CanProposeDecision =>
        _discussions is not null
        && CurrentDiscussion is not null
        && !IsBusy
        && !IsFinalized
        && !string.IsNullOrWhiteSpace(DecisionTitle)
        && !string.IsNullOrWhiteSpace(DecisionStatement)
        && !string.IsNullOrWhiteSpace(DecisionRationale);

    public bool CanAcceptDecision =>
        _discussions is not null
        && CurrentDiscussion is not null
        && SelectedDecision?.State == DecisionState.Proposed
        && !IsFinalized
        && !IsBusy;

    public bool CanFinalizeDiscussion =>
        _discussions is not null
        && CurrentDiscussion is not null
        && Decisions.Any(decision => decision.State == DecisionState.Accepted)
        && !IsFinalized
        && !IsBusy;

    public string IntegrationStatusLabel => _discussions is null
        ? "Discuss aguardando integração"
        : "Discuss conectado ao contrato de aplicação";

    public string DiscussionStateLabel => CurrentDiscussion is null
        ? "Nenhuma conversa selecionada"
        : CompletenessLabel(CurrentDiscussion.Completeness);

    public string DiscussionSummaryLabel => CurrentDiscussion is null
        ? "Inicie uma conversa para transformar intenção em decisões revisáveis."
        : $"{Messages.Count} mensagem(ns) · {CurrentDiscussion.Decisions.Count} decisão(ões) · "
          + $"{References.Count} referência(s) na mensagem atual";

    public string DecisionSummaryLabel => CurrentDiscussion is null
        ? "Nenhuma decisão proposta"
        : Decisions.Count == 0
            ? "Nenhuma decisão proposta"
            : $"{Decisions.Count} decisão(ões) · "
              + $"{Decisions.Count(decision => decision.State == DecisionState.Accepted)} aceita(s)";

    public string SelectedDecisionSummary => SelectedDecision is null
        ? "Selecione uma decisão para aceitar ou revisar."
        : $"{SelectedDecision.Title} · {SelectedDecision.State}";

    public string DecisionFormToggleLabel => IsDecisionFormVisible
        ? "Ocultar proposta"
        : "Propor decisão";

    public string ComposerStatusLabel => _discussions is null
        ? "Composer aguardando Discuss"
        : CurrentDiscussion is null
            ? "Inicie uma conversa para habilitar o composer"
            : IsFinalized
                ? "Discuss finalizado no ledger"
            : "Mensagem não é persistida até o envio";

    public string ReferenceSummaryLabel => References.Count switch
    {
        0 => "Nenhuma referência anexada",
        1 => "1 referência aguardando envio",
        _ => $"{References.Count} referências aguardando envio",
    };

    public string FinalizationStatusLabel { get; private set; } = "Nenhuma finalização solicitada.";

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(Decisions))]
    [NotifyPropertyChangedFor(nameof(HasDiscussion))]
    [NotifyPropertyChangedFor(nameof(HasDecisions))]
    [NotifyPropertyChangedFor(nameof(IsDecisionEmptyState))]
    [NotifyPropertyChangedFor(nameof(IsEmptyState))]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    [NotifyPropertyChangedFor(nameof(CanProposeDecision))]
    [NotifyPropertyChangedFor(nameof(CanAcceptDecision))]
    [NotifyPropertyChangedFor(nameof(CanFinalizeDiscussion))]
    [NotifyPropertyChangedFor(nameof(DiscussionStateLabel))]
    [NotifyPropertyChangedFor(nameof(DiscussionSummaryLabel))]
    [NotifyPropertyChangedFor(nameof(DecisionSummaryLabel))]
    [NotifyPropertyChangedFor(nameof(ComposerStatusLabel))]
    private Discussion? _currentDiscussion;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanAcceptDecision))]
    [NotifyPropertyChangedFor(nameof(SelectedDecisionSummary))]
    private Decision? _selectedDecision;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    private string _draftMessage = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    private string _referencePath = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanProposeDecision))]
    private string _decisionTitle = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanProposeDecision))]
    private string _decisionStatement = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanProposeDecision))]
    private string _decisionRationale = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(DecisionFormToggleLabel))]
    private bool _isDecisionFormVisible;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanStartDiscussion))]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    [NotifyPropertyChangedFor(nameof(CanProposeDecision))]
    [NotifyPropertyChangedFor(nameof(CanAcceptDecision))]
    [NotifyPropertyChangedFor(nameof(CanFinalizeDiscussion))]
    [NotifyPropertyChangedFor(nameof(ComposerStatusLabel))]
    private bool _isBusy;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    [NotifyPropertyChangedFor(nameof(CanProposeDecision))]
    [NotifyPropertyChangedFor(nameof(CanAcceptDecision))]
    [NotifyPropertyChangedFor(nameof(CanFinalizeDiscussion))]
    [NotifyPropertyChangedFor(nameof(ComposerStatusLabel))]
    private bool _isFinalized;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasError))]
    private string? _errorMessage;

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    /// <summary>Loads the most recent conversation known by the application.</summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        ClearConversation();
        ErrorMessage = null;
        FinalizationStatusLabel = "Nenhuma finalização solicitada.";
        OnPropertyChanged(nameof(FinalizationStatusLabel));

        if (_discussions is null)
        {
            NotifyCommands();
            return;
        }

        IsBusy = true;
        try
        {
            IReadOnlyList<DiscussionId> ids = await _discussions
                .ListAsync(cancellationToken)
                .ConfigureAwait(true) ?? [];

            List<Discussion> discussions = [];
            foreach (DiscussionId id in ids)
            {
                Discussion? discussion = await _discussions
                    .FindAsync(id, cancellationToken)
                    .ConfigureAwait(true);
                if (discussion is not null)
                {
                    discussions.Add(discussion);
                }
            }

            ApplyDiscussion(discussions.MaxBy(discussion => discussion.CreatedAt));
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
            NotifyCommands();
        }
    }

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_discussions is null)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            Discussion discussion = await _discussions
                .StartAsync(cancellationToken)
                .ConfigureAwait(true);
            ApplyDiscussion(discussion);
            IsFinalized = false;
            FinalizationStatusLabel = "Nenhuma finalização solicitada.";
            OnPropertyChanged(nameof(FinalizationStatusLabel));
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
            NotifyCommands();
        }
    }

    public async Task SendMessageAsync(CancellationToken cancellationToken = default)
    {
        Discussion? discussion = CurrentDiscussion;
        string content = DraftMessage.Trim();
        if (_discussions is null || discussion is null || string.IsNullOrWhiteSpace(content))
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            DiscussionMessage message = await _discussions
                .AppendMessageAsync(
                    new AppendMessageRequest
                    {
                        DiscussionId = discussion.Id,
                        Content = content,
                        References = References.ToArray(),
                    },
                    cancellationToken)
                .ConfigureAwait(true);

            Messages.Add(message);
            CurrentDiscussion = discussion with
            {
                Messages = discussion.Messages.Append(message).ToArray(),
            };
            DraftMessage = string.Empty;
            ClearReferences();
            NotifyCollectionStateChanged();
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
            NotifyCommands();
        }
    }

    public async Task ProposeDecisionAsync(CancellationToken cancellationToken = default)
    {
        Discussion? discussion = CurrentDiscussion;
        string title = DecisionTitle.Trim();
        string statement = DecisionStatement.Trim();
        string rationale = DecisionRationale.Trim();
        if (_discussions is null
            || discussion is null
            || string.IsNullOrWhiteSpace(title)
            || string.IsNullOrWhiteSpace(statement)
            || string.IsNullOrWhiteSpace(rationale))
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            Decision proposed = await _discussions
                .ProposeDecisionAsync(
                    new ProposeDecisionRequest
                    {
                        DiscussionId = discussion.Id,
                        Title = title,
                        Statement = statement,
                        Rationale = rationale,
                    },
                    cancellationToken)
                .ConfigureAwait(true);

            CurrentDiscussion = discussion with
            {
                Decisions = discussion.Decisions.Append(proposed).ToArray(),
            };
            SelectedDecision = proposed;
            DecisionTitle = string.Empty;
            DecisionStatement = string.Empty;
            DecisionRationale = string.Empty;
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
            NotifyCommands();
        }
    }

    public async Task AcceptSelectedDecisionAsync(CancellationToken cancellationToken = default)
    {
        Discussion? discussion = CurrentDiscussion;
        Decision? selected = SelectedDecision;
        if (_discussions is null
            || discussion is null
            || selected is null
            || selected.State != DecisionState.Proposed)
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            Decision accepted = await _discussions
                .AcceptDecisionAsync(discussion.Id, selected.Id, cancellationToken)
                .ConfigureAwait(true);
            ReplaceDecision(accepted);
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
            NotifyCommands();
        }
    }

    public async Task FinalizeDiscussionAsync(CancellationToken cancellationToken = default)
    {
        Discussion? discussion = CurrentDiscussion;
        if (_discussions is null
            || discussion is null
            || !Decisions.Any(decision => decision.State == DecisionState.Accepted))
        {
            return;
        }

        IsBusy = true;
        ErrorMessage = null;
        try
        {
            DiscussionOutcome outcome = await _discussions
                .FinalizeAsync(discussion.Id, cancellationToken)
                .ConfigureAwait(true);
            FinalizationStatusLabel =
                $"{outcome.Recorded.Count} decisão(ões) registrada(s) · {outcome.Written.Count} arquivo(s) escrito(s)";
            IsFinalized = true;
            OnPropertyChanged(nameof(FinalizationStatusLabel));
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
            NotifyCommands();
        }
    }

    public void AddFileReference() => AddReference(ReferenceKind.File);

    public void AddImageReference() => AddReference(ReferenceKind.Image);

    [RelayCommand(CanExecute = nameof(CanStartDiscussion))]
    private Task StartDiscussionAsync(CancellationToken cancellationToken) => StartAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanSendMessage))]
    private Task SendAsync(CancellationToken cancellationToken) => SendMessageAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanAddReference))]
    private void AddFile() => AddFileReference();

    [RelayCommand(CanExecute = nameof(CanAddReference))]
    private void AddImage() => AddImageReference();

    [RelayCommand(CanExecute = nameof(CanProposeDecision))]
    private Task ProposeAsync(CancellationToken cancellationToken) => ProposeDecisionAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanAcceptDecision))]
    private Task AcceptAsync(CancellationToken cancellationToken) => AcceptSelectedDecisionAsync(cancellationToken);

    [RelayCommand(CanExecute = nameof(CanFinalizeDiscussion))]
    private Task FinalizeAsync(CancellationToken cancellationToken) =>
        FinalizeDiscussionAsync(cancellationToken);

    [RelayCommand]
    private void ToggleDecisionForm() => IsDecisionFormVisible = !IsDecisionFormVisible;

    [RelayCommand]
    private void ClearReferences()
    {
        References.Clear();
        NotifyCollectionStateChanged();
    }

    partial void OnIsBusyChanged(bool value) => NotifyCommands();

    partial void OnIsFinalizedChanged(bool value) => NotifyCommands();

    partial void OnCurrentDiscussionChanged(Discussion? value) => NotifyCommands();

    partial void OnDraftMessageChanged(string value) => NotifyCommands();

    partial void OnReferencePathChanged(string value) => NotifyCommands();

    partial void OnSelectedDecisionChanged(Decision? value) => NotifyCommands();

    partial void OnDecisionTitleChanged(string value) => NotifyCommands();

    partial void OnDecisionStatementChanged(string value) => NotifyCommands();

    partial void OnDecisionRationaleChanged(string value) => NotifyCommands();

    private void AddReference(ReferenceKind kind)
    {
        string path = ReferencePath.Trim().Replace('\\', '/').Trim('/');
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        References.Add(new MessageReference
        {
            Path = new ProjectPath(path),
            Kind = kind,
            Label = LastPathSegment(path),
        });
        ReferencePath = string.Empty;
        NotifyCollectionStateChanged();
    }

    private void ApplyDiscussion(Discussion? discussion)
    {
        CurrentDiscussion = discussion;
        SelectedDecision = discussion is { Decisions.Count: > 0 }
            ? discussion.Decisions[0]
            : null;
        Messages.Clear();
        if (discussion is not null)
        {
            foreach (DiscussionMessage message in discussion.Messages)
            {
                Messages.Add(message);
            }
        }

        NotifyCollectionStateChanged();
    }

    private void ClearConversation()
    {
        CurrentDiscussion = null;
        SelectedDecision = null;
        Messages.Clear();
        ClearReferences();
        DraftMessage = string.Empty;
        ReferencePath = string.Empty;
        DecisionTitle = string.Empty;
        DecisionStatement = string.Empty;
        DecisionRationale = string.Empty;
        IsDecisionFormVisible = false;
        IsFinalized = false;
        FinalizationStatusLabel = "Nenhuma finalização solicitada.";
        OnPropertyChanged(nameof(FinalizationStatusLabel));
        NotifyCollectionStateChanged();
    }

    private void NotifyCollectionStateChanged()
    {
        OnPropertyChanged(nameof(HasMessages));
        OnPropertyChanged(nameof(HasReferences));
        OnPropertyChanged(nameof(Decisions));
        OnPropertyChanged(nameof(HasDecisions));
        OnPropertyChanged(nameof(DiscussionSummaryLabel));
        OnPropertyChanged(nameof(ReferenceSummaryLabel));
        OnPropertyChanged(nameof(DecisionSummaryLabel));
        OnPropertyChanged(nameof(CanFinalizeDiscussion));
        NotifyCommands();
    }

    private void NotifyCommands()
    {
        StartDiscussionCommand.NotifyCanExecuteChanged();
        SendCommand.NotifyCanExecuteChanged();
        AddFileCommand.NotifyCanExecuteChanged();
        AddImageCommand.NotifyCanExecuteChanged();
        ProposeCommand.NotifyCanExecuteChanged();
        AcceptCommand.NotifyCanExecuteChanged();
        FinalizeCommand.NotifyCanExecuteChanged();
    }

    private void ReplaceDecision(Decision updated)
    {
        Discussion discussion = CurrentDiscussion
            ?? throw new InvalidOperationException("Não há uma discussão selecionada.");
        CurrentDiscussion = discussion with
        {
            Decisions = discussion.Decisions
                .Select(decision => decision.Id == updated.Id ? updated : decision)
                .ToArray(),
        };
        SelectedDecision = updated;
    }

    private static string LastPathSegment(string path) =>
        path.Split('/', StringSplitOptions.RemoveEmptyEntries).LastOrDefault() ?? path;

    private static string CompletenessLabel(Completeness completeness) => completeness switch
    {
        Completeness.Unknown => "Completude ainda não avaliada",
        Completeness.Partial => "Definição parcial",
        Completeness.Sufficient => "Definição suficiente para revisão",
        Completeness.Locked => "Definição bloqueada",
        _ => completeness.ToString(),
    };
}
