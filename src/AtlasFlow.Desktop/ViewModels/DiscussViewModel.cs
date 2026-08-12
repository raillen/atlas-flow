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

    public bool HasDiscussion => CurrentDiscussion is not null;

    public bool HasMessages => Messages.Count > 0;

    public bool HasReferences => References.Count > 0;

    public bool IsEmptyState => !HasDiscussion;

    public bool IsServiceUnavailable => _discussions is null;

    public bool CanStartDiscussion => _discussions is not null && !IsBusy;

    public bool CanSendMessage =>
        _discussions is not null
        && CurrentDiscussion is not null
        && !IsBusy
        && !string.IsNullOrWhiteSpace(DraftMessage);

    public bool CanAddReference =>
        _discussions is not null
        && CurrentDiscussion is not null
        && !IsBusy
        && !string.IsNullOrWhiteSpace(ReferencePath);

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
        : CurrentDiscussion.Decisions.Count == 0
            ? "Nenhuma decisão proposta"
            : $"{CurrentDiscussion.Decisions.Count} decisão(ões) · "
              + $"{CurrentDiscussion.Decisions.Count(decision => decision.State == DecisionState.Accepted)} aceita(s)";

    public string ComposerStatusLabel => _discussions is null
        ? "Composer aguardando Discuss"
        : CurrentDiscussion is null
            ? "Inicie uma conversa para habilitar o composer"
            : "Mensagem não é persistida até o envio";

    public string ReferenceSummaryLabel => References.Count switch
    {
        0 => "Nenhuma referência anexada",
        1 => "1 referência aguardando envio",
        _ => $"{References.Count} referências aguardando envio",
    };

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasDiscussion))]
    [NotifyPropertyChangedFor(nameof(IsEmptyState))]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    [NotifyPropertyChangedFor(nameof(DiscussionStateLabel))]
    [NotifyPropertyChangedFor(nameof(DiscussionSummaryLabel))]
    [NotifyPropertyChangedFor(nameof(DecisionSummaryLabel))]
    [NotifyPropertyChangedFor(nameof(ComposerStatusLabel))]
    private Discussion? _currentDiscussion;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    private string _draftMessage = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    private string _referencePath = string.Empty;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(CanStartDiscussion))]
    [NotifyPropertyChangedFor(nameof(CanSendMessage))]
    [NotifyPropertyChangedFor(nameof(CanAddReference))]
    private bool _isBusy;

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasError))]
    private string? _errorMessage;

    public bool HasError => !string.IsNullOrWhiteSpace(ErrorMessage);

    /// <summary>Loads the most recent conversation known by the application.</summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        ClearConversation();
        ErrorMessage = null;

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

    [RelayCommand]
    private void ClearReferences()
    {
        References.Clear();
        NotifyCollectionStateChanged();
    }

    partial void OnIsBusyChanged(bool value) => NotifyCommands();

    partial void OnCurrentDiscussionChanged(Discussion? value) => NotifyCommands();

    partial void OnDraftMessageChanged(string value) => NotifyCommands();

    partial void OnReferencePathChanged(string value) => NotifyCommands();

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
        Messages.Clear();
        ClearReferences();
        DraftMessage = string.Empty;
        ReferencePath = string.Empty;
        NotifyCollectionStateChanged();
    }

    private void NotifyCollectionStateChanged()
    {
        OnPropertyChanged(nameof(HasMessages));
        OnPropertyChanged(nameof(HasReferences));
        OnPropertyChanged(nameof(DiscussionSummaryLabel));
        OnPropertyChanged(nameof(ReferenceSummaryLabel));
        OnPropertyChanged(nameof(DecisionSummaryLabel));
        NotifyCommands();
    }

    private void NotifyCommands()
    {
        StartDiscussionCommand.NotifyCanExecuteChanged();
        SendCommand.NotifyCanExecuteChanged();
        AddFileCommand.NotifyCanExecuteChanged();
        AddImageCommand.NotifyCanExecuteChanged();
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
