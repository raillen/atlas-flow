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
}
