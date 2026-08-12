using AtlasFlow.Application.Contracts;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;

using NSubstitute;

namespace AtlasFlow.Desktop.Tests;

public sealed class DiscussViewModelTests
{
    [Fact]
    public async Task Loading_selects_the_most_recent_conversation_and_rehydrates_messages()
    {
        Discussion older = CreateDiscussion("disc-old", DateTimeOffset.UtcNow.AddMinutes(-2));
        Discussion newer = CreateDiscussion("disc-new", DateTimeOffset.UtcNow);
        IDiscussionService service = Substitute.For<IDiscussionService>();
        service.ListAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<IReadOnlyList<DiscussionId>>(
                [older.Id, newer.Id]));
        service.FindAsync(older.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<Discussion?>(older));
        service.FindAsync(newer.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult<Discussion?>(newer));

        DiscussViewModel viewModel = new(service);

        await viewModel.LoadAsync(TestContext.Current.CancellationToken);

        Assert.Equal(newer.Id, viewModel.CurrentDiscussion!.Id);
        Assert.Single(viewModel.Messages);
        Assert.Equal("Definição parcial", viewModel.DiscussionStateLabel);
        await service.Received(1).FindAsync(newer.Id, Arg.Any<CancellationToken>());
    }

    [Fact]
    public async Task Sending_a_message_submits_project_relative_references_and_clears_the_composer()
    {
        Discussion discussion = CreateDiscussion("disc-send", DateTimeOffset.UtcNow);
        DiscussionMessage sent = new()
        {
            Id = "message-sent",
            Author = "user",
            TurnType = TurnType.Message,
            Content = "Quero preservar o contrato.",
            CreatedAt = DateTimeOffset.UtcNow,
        };
        IDiscussionService service = Substitute.For<IDiscussionService>();
        service.StartAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(discussion));
        service.AppendMessageAsync(Arg.Any<AppendMessageRequest>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(sent));

        DiscussViewModel viewModel = new(service);
        await viewModel.StartAsync(TestContext.Current.CancellationToken);
        viewModel.DraftMessage = "  Quero preservar o contrato.  ";
        viewModel.ReferencePath = @"docs\ATLAS.md";
        viewModel.AddFileReference();

        await viewModel.SendMessageAsync(TestContext.Current.CancellationToken);

        await service.Received(1).AppendMessageAsync(
            Arg.Is<AppendMessageRequest>(request =>
                request.DiscussionId == discussion.Id
                && request.Content == "Quero preservar o contrato."
                && request.References.Count == 1
                && request.References[0].Path.Value == "docs/ATLAS.md"
                && request.References[0].Kind == ReferenceKind.File),
            Arg.Any<CancellationToken>());
        Assert.Equal(2, viewModel.Messages.Count);
        Assert.Empty(viewModel.References);
        Assert.Empty(viewModel.DraftMessage);
        Assert.False(viewModel.HasError);
    }

    [Fact]
    public async Task A_reference_validation_failure_keeps_the_composer_for_correction()
    {
        Discussion discussion = CreateDiscussion("disc-rejected", DateTimeOffset.UtcNow);
        IDiscussionService service = Substitute.For<IDiscussionService>();
        service.StartAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(discussion));
        service.AppendMessageAsync(Arg.Any<AppendMessageRequest>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromException<DiscussionMessage>(
                new ProjectPathException("referência fora do projeto")));

        DiscussViewModel viewModel = new(service);
        await viewModel.StartAsync(TestContext.Current.CancellationToken);
        viewModel.DraftMessage = "Analise este arquivo.";
        viewModel.ReferencePath = "../segredo.txt";
        viewModel.AddFileReference();

        await viewModel.SendMessageAsync(TestContext.Current.CancellationToken);

        Assert.True(viewModel.HasError);
        Assert.Equal("referência fora do projeto", viewModel.ErrorMessage);
        Assert.Single(viewModel.References);
        Assert.Equal("Analise este arquivo.", viewModel.DraftMessage);
    }

    [Fact]
    public async Task Proposing_accepting_and_finalizing_a_decision_use_explicit_service_commands()
    {
        Discussion discussion = CreateDiscussion("disc-decision", DateTimeOffset.UtcNow);
        Decision proposed = CreateDecision("decision-1", DecisionState.Proposed);
        Decision accepted = proposed with { State = DecisionState.Accepted };
        IDiscussionService service = Substitute.For<IDiscussionService>();
        service.StartAsync(Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(discussion));
        service.ProposeDecisionAsync(Arg.Any<ProposeDecisionRequest>(), Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(proposed));
        service.AcceptDecisionAsync(discussion.Id, proposed.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(accepted));
        service.FinalizeAsync(discussion.Id, Arg.Any<CancellationToken>())
            .Returns(Task.FromResult(new DiscussionOutcome
            {
                DiscussionId = discussion.Id,
                Recorded = [accepted.Id],
                Written = [new ProjectPath(".atlas/decisions/decision-1.md")],
            }));

        DiscussViewModel viewModel = new(service);
        await viewModel.StartAsync(TestContext.Current.CancellationToken);
        viewModel.DecisionTitle = "Manter o contrato";
        viewModel.DecisionStatement = "O contrato público permanece a fronteira.";
        viewModel.DecisionRationale = "Permite evolução independente do backend.";

        await viewModel.ProposeDecisionAsync(TestContext.Current.CancellationToken);
        await viewModel.AcceptSelectedDecisionAsync(TestContext.Current.CancellationToken);
        await viewModel.FinalizeDiscussionAsync(TestContext.Current.CancellationToken);

        await service.Received(1).ProposeDecisionAsync(
            Arg.Is<ProposeDecisionRequest>(request =>
                request.DiscussionId == discussion.Id
                && request.Title == "Manter o contrato"
                && request.Statement == "O contrato público permanece a fronteira."
                && request.Rationale == "Permite evolução independente do backend."),
            Arg.Any<CancellationToken>());
        await service.Received(1).AcceptDecisionAsync(
            discussion.Id,
            proposed.Id,
            Arg.Any<CancellationToken>());
        await service.Received(1).FinalizeAsync(discussion.Id, Arg.Any<CancellationToken>());
        Assert.Equal(DecisionState.Accepted, viewModel.Decisions.Single().State);
        Assert.Equal(
            "1 decisão(ões) registrada(s) · 1 arquivo(s) escrito(s)",
            viewModel.FinalizationStatusLabel);
        Assert.False(viewModel.CanAcceptDecision);
        Assert.False(viewModel.CanFinalizeDiscussion);
    }

    [Fact]
    public void Missing_discussion_service_keeps_the_define_surface_explicitly_unavailable()
    {
        DiscussViewModel viewModel = new();

        Assert.False(viewModel.CanStartDiscussion);
        Assert.False(viewModel.CanSendMessage);
        Assert.Equal("Discuss aguardando integração", viewModel.IntegrationStatusLabel);
        Assert.Contains("aguardando", viewModel.ComposerStatusLabel, StringComparison.OrdinalIgnoreCase);
    }

    private static Discussion CreateDiscussion(string id, DateTimeOffset createdAt) => new()
    {
        Id = new DiscussionId(id),
        Completeness = Completeness.Partial,
        CreatedAt = createdAt,
        Messages =
        [
            new DiscussionMessage
            {
                Id = $"{id}-message",
                Author = "user",
                TurnType = TurnType.Message,
                Content = "Intenção inicial.",
                CreatedAt = createdAt,
            },
        ],
    };

    private static Decision CreateDecision(string id, DecisionState state) => new()
    {
        Id = new DecisionId(id),
        Title = "Decisão de teste",
        Statement = "O contrato público permanece a fronteira.",
        Rationale = "Permite evolução independente do backend.",
        State = state,
        CreatedAt = DateTimeOffset.UtcNow,
    };
}
