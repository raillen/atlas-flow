using System.Text.Json;
using System.Text.Json.Nodes;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence;

/// <summary>Durable discussion history and decision candidates.</summary>
/// <remarks>
/// The database is operational state, not the decision ledger. It keeps the
/// thread available after a restart; <c>DiscussionService</c> is responsible
/// for validating transitions and writing accepted decisions to Git.
/// </remarks>
public sealed class DiscussionRepository(AtlasFlowDatabase database)
{
    private readonly AtlasFlowDatabase _database = database;

    public Task<List<DiscussionId>> ListAsync(CancellationToken cancellationToken = default) =>
        _database.QueryAsync(
            "SELECT id FROM discussions ORDER BY created_at DESC, id DESC",
            reader => new DiscussionId(reader.String("id")),
            cancellationToken: cancellationToken);

    public async Task<Discussion?> FindAsync(
        DiscussionId id,
        CancellationToken cancellationToken = default)
    {
        Discussion? discussion = await _database.QuerySingleAsync(
            "SELECT id, completeness, created_at FROM discussions WHERE id = $id",
            ReadDiscussion,
            new Dictionary<string, object?> { ["$id"] = id.Value },
            cancellationToken).ConfigureAwait(false);

        if (discussion is null)
        {
            return null;
        }

        List<DiscussionMessage> messages = await _database.QueryAsync(
            """
            SELECT id, author, turn_type, content, created_at, references_json
            FROM discussion_messages
            WHERE discussion_id = $discussionId
            ORDER BY created_at, id
            """,
            ReadMessage,
            new Dictionary<string, object?> { ["$discussionId"] = id.Value },
            cancellationToken).ConfigureAwait(false);

        List<Decision> decisions = await _database.QueryAsync(
            """
            SELECT id, title, statement, rationale, state, affected_domains,
                   requires_adr, created_at
            FROM decisions
            WHERE discussion_id = $discussionId
            ORDER BY created_at, id
            """,
            ReadDecision,
            new Dictionary<string, object?> { ["$discussionId"] = id.Value },
            cancellationToken).ConfigureAwait(false);

        return discussion with
        {
            Messages = messages,
            Decisions = decisions,
        };
    }

    public Task CreateAsync(
        Discussion discussion,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(discussion);

        return _database.ExecuteAsync(
            """
            INSERT INTO discussions (id, completeness, created_at)
            VALUES ($id, $completeness, $createdAt)
            """,
            new Dictionary<string, object?>
            {
                ["$id"] = discussion.Id.Value,
                ["$completeness"] = SqlValues.Text(discussion.Completeness),
                ["$createdAt"] = SqlValues.Text(discussion.CreatedAt),
            },
            cancellationToken);
    }

    public Task AppendMessageAsync(
        DiscussionId discussionId,
        DiscussionMessage message,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(message);

        return _database.ExecuteAsync(
            """
            INSERT INTO discussion_messages
                (id, discussion_id, author, turn_type, content, created_at, references_json)
            VALUES ($id, $discussionId, $author, $turnType, $content, $createdAt, $references)
            """,
            new Dictionary<string, object?>
            {
                ["$id"] = message.Id,
                ["$discussionId"] = discussionId.Value,
                ["$author"] = message.Author,
                ["$turnType"] = SqlValues.Text(message.TurnType),
                ["$content"] = message.Content,
                ["$createdAt"] = SqlValues.Text(message.CreatedAt),
                ["$references"] = SerializeReferences(message.References),
            },
            cancellationToken);
    }

    public Task AddDecisionAsync(
        DiscussionId discussionId,
        Decision decision,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(decision);

        return _database.ExecuteAsync(
            """
            INSERT INTO decisions
                (id, discussion_id, title, statement, rationale, state,
                 affected_domains, requires_adr, created_at)
            VALUES ($id, $discussionId, $title, $statement, $rationale, $state,
                    $affectedDomains, $requiresAdr, $createdAt)
            """,
            DecisionParameters(discussionId, decision),
            cancellationToken);
    }

    public Task UpdateDecisionAsync(
        DiscussionId discussionId,
        Decision decision,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(decision);

        return _database.ExecuteAsync(
            """
            UPDATE decisions
            SET title = $title,
                statement = $statement,
                rationale = $rationale,
                state = $state,
                affected_domains = $affectedDomains,
                requires_adr = $requiresAdr,
                created_at = $createdAt
            WHERE id = $id AND discussion_id = $discussionId
            """,
            DecisionParameters(discussionId, decision),
            cancellationToken);
    }

    public Task UpdateCompletenessAsync(
        DiscussionId discussionId,
        Completeness completeness,
        CancellationToken cancellationToken = default) =>
        _database.ExecuteAsync(
            "UPDATE discussions SET completeness = $completeness WHERE id = $id",
            new Dictionary<string, object?>
            {
                ["$id"] = discussionId.Value,
                ["$completeness"] = SqlValues.Text(completeness),
            },
            cancellationToken);

    private static Dictionary<string, object?> DecisionParameters(
        DiscussionId discussionId,
        Decision decision) => new()
        {
            ["$id"] = decision.Id.Value,
            ["$discussionId"] = discussionId.Value,
            ["$title"] = decision.Title,
            ["$statement"] = decision.Statement,
            ["$rationale"] = decision.Rationale,
            ["$state"] = SqlValues.Text(decision.State),
            ["$affectedDomains"] = SqlValues.Json(decision.AffectedDomains),
            ["$requiresAdr"] = decision.RequiresAdr ? 1 : 0,
            ["$createdAt"] = SqlValues.Text(decision.CreatedAt),
        };

    private static Discussion ReadDiscussion(SqliteDataReader reader) => new()
    {
        Id = new DiscussionId(reader.String("id")),
        Completeness = SqlValues.CompletenessOf(reader.String("completeness")),
        CreatedAt = reader.Moment("created_at"),
    };

    private static DiscussionMessage ReadMessage(SqliteDataReader reader) => new()
    {
        Id = reader.String("id"),
        Author = reader.String("author"),
        TurnType = SqlValues.TurnTypeOf(reader.String("turn_type")),
        Content = reader.String("content"),
        CreatedAt = reader.Moment("created_at"),
        References = DeserializeReferences(reader.String("references_json")),
    };

    private static Decision ReadDecision(SqliteDataReader reader) => new()
    {
        Id = new DecisionId(reader.String("id")),
        Title = reader.String("title"),
        Statement = reader.String("statement"),
        Rationale = reader.String("rationale"),
        State = SqlValues.DecisionStateOf(reader.String("state")),
        AffectedDomains = SqlValues.StringsOf(reader.String("affected_domains")),
        RequiresAdr = reader.GetBoolean(reader.GetOrdinal("requires_adr")),
        CreatedAt = reader.Moment("created_at"),
    };

    private static string SerializeReferences(IReadOnlyList<MessageReference> references)
    {
        JsonArray array = [];
        foreach (MessageReference reference in references)
        {
            array.Add(new JsonObject
            {
                ["path"] = reference.Path.Value,
                ["kind"] = SqlValues.Text(reference.Kind),
                ["label"] = reference.Label,
                ["mime_type"] = reference.MimeType,
            });
        }

        return array.ToJsonString();
    }

    private static List<MessageReference> DeserializeReferences(string json)
    {
        JsonNode? parsed;
        try
        {
            parsed = JsonNode.Parse(json);
        }
        catch (JsonException exception)
        {
            throw new PersistenceException("Stored discussion references are not valid JSON", exception);
        }

        if (parsed is not JsonArray array)
        {
            throw new PersistenceException("Stored discussion references are not an array");
        }

        List<MessageReference> references = [];
        foreach (JsonObject reference in array.OfType<JsonObject>())
        {
            references.Add(new MessageReference
            {
                Path = new ProjectPath(Required(reference, "path")),
                Kind = SqlValues.ReferenceKindOf(Required(reference, "kind")),
                Label = Required(reference, "label"),
                MimeType = reference["mime_type"]?.GetValue<string>(),
            });
        }

        return references;
    }

    private static string Required(JsonObject node, string key) =>
        node[key]?.GetValue<string>()
        ?? throw new PersistenceException($"Stored discussion reference has no '{key}'");
}
