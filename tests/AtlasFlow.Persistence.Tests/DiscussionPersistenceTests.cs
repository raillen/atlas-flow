using AtlasFlow.Domain;
using AtlasFlow.Domain.Discuss;
using AtlasFlow.Persistence;

using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence.Tests;

public sealed class DiscussionPersistenceTests
{
    [Fact]
    public async Task ALegacyDiscussSchemaIsUpgradedAndRehydrated()
    {
        string directory = Path.Combine(Path.GetTempPath(), $"atlas-discuss-migration-{Guid.NewGuid():N}");
        string path = Path.Combine(directory, "state.db");
        Directory.CreateDirectory(directory);

        try
        {
            await using (SqliteConnection legacy = new($"Data Source={path}"))
            {
                await legacy.OpenAsync();
                await using SqliteCommand command = legacy.CreateCommand();
                command.CommandText = """
                    CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
                    INSERT INTO schema_version (version) VALUES (4);
                    CREATE TABLE discussions (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        title TEXT NOT NULL DEFAULT '',
                        started_at TEXT NOT NULL
                    );
                    CREATE TABLE discussion_messages (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        content TEXT NOT NULL,
                        turn_type TEXT NOT NULL DEFAULT 'message',
                        references_json TEXT NOT NULL DEFAULT '[]'
                    );
                    CREATE TABLE decisions (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        statement TEXT NOT NULL,
                        rationale TEXT NOT NULL,
                        status TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        affected_domains TEXT NOT NULL DEFAULT '[]',
                        requires_adr INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO discussions (id, project_id, title, started_at)
                    VALUES ('disc-legacy', 'project-1', 'Legacy', '2026-08-12T10:00:00.0000000+00:00');
                    INSERT INTO discussion_messages
                        (id, session_id, timestamp, content, references_json)
                    VALUES ('msg-legacy', 'disc-legacy', '2026-08-12T10:01:00.0000000+00:00',
                            'Legacy message', '[{"path":"README.md","kind":"file","label":"README"}]');
                    INSERT INTO decisions
                        (id, session_id, title, statement, rationale, status, timestamp,
                         affected_domains, requires_adr)
                    VALUES ('dec-legacy', 'disc-legacy', 'Legacy decision', 'Keep it', 'Compatibility',
                            'ACCEPTED', '2026-08-12T10:02:00.0000000+00:00', '["architecture"]', 1);
                    """;
                await command.ExecuteNonQueryAsync();
            }

            await using AtlasFlowDatabase database = new(path);
            await database.InitializeAsync();
            DiscussionRepository repository = new(database);

            Discussion? loaded = await repository.FindAsync(
                new DiscussionId("disc-legacy"));

            Assert.NotNull(loaded);
            Assert.Equal(Completeness.Unknown, loaded.Completeness);
            Assert.Equal("Legacy message", loaded.Messages.Single().Content);
            Assert.Equal("README.md", loaded.Messages.Single().References.Single().Path.Value);
            Assert.Equal(DecisionState.Accepted, loaded.Decisions.Single().State);
            Assert.True(loaded.Decisions.Single().RequiresAdr);
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }
}
