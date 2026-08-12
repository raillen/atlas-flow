using System.Text.Json.Nodes;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Execution;

namespace AtlasFlow.Persistence;

/// <summary>Receives an event after it has been committed.</summary>
public delegate Task EventListener(DomainEvent domainEvent, CancellationToken cancellationToken);

/// <summary>The durable event log, and the fan-out from it.</summary>
/// <remarks>
/// Listeners run <em>after</em> the commit, never inside the transaction. A
/// slow or throwing subscriber must not be able to roll back durable state or
/// hold the write lock — the run is the thing that matters, and a UI that
/// missed a notification is a smaller problem than a run that failed because
/// the UI was slow.
/// </remarks>
public sealed class EventStore(AtlasFlowDatabase database)
{
    private const string Insert = """
        INSERT OR IGNORE INTO events (id, timestamp, project_id, run_id, type, version, payload)
        VALUES ($id, $timestamp, $projectId, $runId, $type, $version, $payload)
        """;

    private readonly AtlasFlowDatabase _database = database;
    private readonly List<EventListener> _listeners = [];
    private readonly Lock _gate = new();

    /// <summary>Observes events as they are committed.</summary>
    public IDisposable Subscribe(EventListener listener)
    {
        ArgumentNullException.ThrowIfNull(listener);

        lock (_gate)
        {
            _listeners.Add(listener);
        }

        return new Subscription(this, listener);
    }

    /// <summary>Writes one event and tells the subscribers.</summary>
    public async Task AppendAsync(DomainEvent domainEvent, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(domainEvent);

        await _database.ExecuteAsync(Insert, ParametersFor(domainEvent), cancellationToken).ConfigureAwait(false);
        await PublishAsync(domainEvent, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>Every event recorded for a run, in the order it happened.</summary>
    public Task<List<DomainEvent>> ListForRunAsync(RunId runId, CancellationToken cancellationToken = default) =>
        _database.QueryAsync(
            "SELECT * FROM events WHERE run_id = $runId ORDER BY seq",
            Read,
            new Dictionary<string, object?> { ["$runId"] = runId.Value },
            cancellationToken);

    /// <summary>Every event in the project, oldest first.</summary>
    public Task<List<DomainEvent>> ListAllAsync(CancellationToken cancellationToken = default) =>
        _database.QueryAsync("SELECT * FROM events ORDER BY seq", Read, null, cancellationToken);

    /// <summary>
    /// The statement that writes one event, for callers batching it with a
    /// state change so that both land or neither does.
    /// </summary>
    internal static (string Sql, IReadOnlyDictionary<string, object?> Parameters) InsertStatement(
        DomainEvent domainEvent) => (Insert, ParametersFor(domainEvent));

    internal async Task PublishAsync(DomainEvent domainEvent, CancellationToken cancellationToken)
    {
        EventListener[] listeners;
        lock (_gate)
        {
            listeners = [.. _listeners];
        }

        foreach (EventListener listener in listeners)
        {
            try
            {
                await listener(domainEvent, cancellationToken).ConfigureAwait(false);
            }
#pragma warning disable CA1031 // A subscriber must not be able to break a run.
            catch (Exception)
#pragma warning restore CA1031
            {
                // Deliberately swallowed, and deliberately not logged from here:
                // this type has no logger and giving it one would make every
                // caller supply one to write a line nobody reads.
            }
        }
    }

    private static Dictionary<string, object?> ParametersFor(DomainEvent domainEvent) => new()
    {
        ["$id"] = domainEvent.Id,
        ["$timestamp"] = SqlValues.Text(domainEvent.Timestamp),
        ["$projectId"] = domainEvent.ProjectId,
        ["$runId"] = domainEvent.RunId?.Value,
        ["$type"] = SqlValues.Text(domainEvent.Type),
        ["$version"] = 1,
        ["$payload"] = domainEvent.Payload.ToJsonString(),
    };

    private static DomainEvent Read(Microsoft.Data.Sqlite.SqliteDataReader reader)
    {
        string? runId = reader.NullableString("run_id");
        return new DomainEvent
        {
            Id = reader.String("id"),
            Timestamp = reader.Moment("timestamp"),
            ProjectId = reader.String("project_id"),
            RunId = runId is null ? null : new RunId(runId),
            Type = SqlValues.EventTypeOf(reader.String("type")),
            Payload = JsonNode.Parse(reader.String("payload")) as JsonObject ?? [],
        };
    }

    private sealed class Subscription(EventStore store, EventListener listener) : IDisposable
    {
        public void Dispose()
        {
            lock (store._gate)
            {
                store._listeners.Remove(listener);
            }
        }
    }
}
