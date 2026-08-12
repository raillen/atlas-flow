using AtlasFlow.Application;
using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;

using Microsoft.Extensions.DependencyInjection;

namespace AtlasFlow.Integration.Tests;

/// <summary>The Discuss vertical slice: SQLite thread to Git decision ledger.</summary>
public sealed class DiscussionSliceTests : IAsyncLifetime
{
    private readonly string _root =
        Path.Combine(Path.GetTempPath(), $"atlas-discuss-{Guid.NewGuid():N}");

    private ServiceProvider _provider = null!;

    public async Task InitializeAsync()
    {
        Directory.CreateDirectory(_root);
        await File.WriteAllTextAsync(Path.Combine(_root, "README.md"), "Discuss reference");
        await File.WriteAllBytesAsync(Path.Combine(_root, "diagram.png"), [137, 80, 78, 71]);

        ServiceCollection services = new();
        services.AddAtlasFlow(_root);
        _provider = services.BuildServiceProvider();
        await _provider.InitializeAtlasFlowAsync();
    }

    public async Task DisposeAsync()
    {
        await _provider.DisposeAsync();
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    private IDiscussionService Discussions =>
        _provider.GetRequiredService<IDiscussionService>();

    [Fact]
    public async Task ADiscussionRoundTripsMessagesReferencesAndDecisions()
    {
        Discussion started = await Discussions.StartAsync();
        DiscussionMessage message = await Discussions.AppendMessageAsync(new AppendMessageRequest
        {
            DiscussionId = started.Id,
            Content = "  Manter o contrato explícito.  ",
            References =
            [
                new MessageReference
                {
                    Path = new ProjectPath("README.md"),
                    Kind = ReferenceKind.File,
                    Label = "README",
                },
                new MessageReference
                {
                    Path = new ProjectPath("diagram.png"),
                    Kind = ReferenceKind.Image,
                    Label = "Diagrama",
                    MimeType = "image/png",
                },
            ],
        });
        Decision proposed = await Discussions.ProposeDecisionAsync(new ProposeDecisionRequest
        {
            DiscussionId = started.Id,
            Title = "Contrato explícito",
            Statement = "A UI consome apenas IDiscussionService.",
            Rationale = "Frontend e backend podem evoluir separadamente.",
            AffectedDomains = ["architecture", "ux", "architecture"],
            RequiresAdr = true,
        });
        Decision accepted = await Discussions.AcceptDecisionAsync(started.Id, proposed.Id);

        Discussion? loaded = await Discussions.FindAsync(started.Id);

        Assert.NotNull(loaded);
        Assert.Equal(message.Content, loaded.Messages.Single().Content);
        Assert.Equal("README.md", loaded.Messages.Single().References[0].Path.Value);
        Assert.Equal(ReferenceKind.Image, loaded.Messages.Single().References[1].Kind);
        Assert.Equal(["architecture", "ux"], loaded.Decisions.Single().AffectedDomains);
        Assert.Equal(DecisionState.Accepted, accepted.State);
    }

    [Fact]
    public async Task FinalizationWritesTheLedgerAndRequestedAdrThenLocksTheDiscussion()
    {
        Discussion discussion = await Discussions.StartAsync();
        Decision decision = await Discussions.ProposeDecisionAsync(new ProposeDecisionRequest
        {
            DiscussionId = discussion.Id,
            Title = "Persistir decisões",
            Statement = "Decisões aceitas devem chegar ao Git.",
            Rationale = "SQLite é operacional e pode ser descartado.",
            RequiresAdr = true,
        });
        await Discussions.AcceptDecisionAsync(discussion.Id, decision.Id);

        DiscussionOutcome outcome = await Discussions.FinalizeAsync(discussion.Id);
        Discussion? finalized = await Discussions.FindAsync(discussion.Id);

        Assert.Equal([decision.Id], outcome.Recorded);
        Assert.Contains(new ProjectPath("docs/01-architecture/DECISION_LEDGER.md"), outcome.Written);
        Assert.Single(
            outcome.Written,
            path => path.Value.StartsWith("docs/07-decisions/ADR-", StringComparison.Ordinal));
        Assert.Equal(Completeness.Locked, finalized?.Completeness);
        Assert.Contains($"Discussion `{discussion.Id}`", await File.ReadAllTextAsync(
            Path.Combine(_root, "docs/01-architecture/DECISION_LEDGER.md")));
        await Assert.ThrowsAsync<DiscussionStateException>(() => Discussions.AppendMessageAsync(new AppendMessageRequest
        {
            DiscussionId = discussion.Id,
            Content = "Não pode mais mudar",
        }));
    }

    [Fact]
    public async Task AReferenceOutsideTheProjectIsRejectedBeforePersistence()
    {
        Discussion discussion = await Discussions.StartAsync();

        await Assert.ThrowsAsync<ProjectPathException>(() => Discussions.AppendMessageAsync(new AppendMessageRequest
        {
            DiscussionId = discussion.Id,
            Content = "Não ler fora do workspace",
            References =
            [
                new MessageReference
                {
                    Path = new ProjectPath("../outside.txt"),
                    Kind = ReferenceKind.File,
                    Label = "fora",
                },
            ],
        }));

        Discussion? unchanged = await Discussions.FindAsync(discussion.Id);
        Assert.Empty(unchanged?.Messages ?? []);
    }
}
