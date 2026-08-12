using Microsoft.Data.Sqlite;

namespace AtlasFlow.Persistence;

/// <summary>
/// The operational state store: one SQLite file, one connection.
/// </summary>
/// <remarks>
/// <para>
/// Git is canonical (ADR-009). Deleting this database loses no decision, Goal
/// or document — only which runs happened and how far they got. It defaults to
/// a file so that state survives a crash; tests pass
/// <see cref="SharedMemory"/> when durability is beside the point.
/// </para>
/// <para>
/// One connection guarded by a semaphore, mirroring the single event loop the
/// Python original relied on. SQLite serializes writers regardless; doing it
/// here means a caller gets an ordered await instead of a
/// <c>SQLITE_BUSY</c> to interpret.
/// </para>
/// </remarks>
public sealed class AtlasFlowDatabase : IAsyncDisposable
{
    /// <summary>An in-memory database that several connections can share.</summary>
    public const string SharedMemory = "file::memory:?cache=shared";

    private const int SchemaVersion = 4;

    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly string _connectionString;
    private SqliteConnection? _connection;

    public AtlasFlowDatabase(string databasePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(databasePath);

        DatabasePath = databasePath;
        _connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Mode = databasePath.Contains(":memory:", StringComparison.Ordinal)
                ? SqliteOpenMode.Memory
                : SqliteOpenMode.ReadWriteCreate,
            Cache = SqliteCacheMode.Shared,
        }.ToString();
    }

    public string DatabasePath { get; }

    /// <summary>Whether this database outlives the process.</summary>
    public bool IsDurable => !DatabasePath.Contains(":memory:", StringComparison.Ordinal);

    public async Task InitializeAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_connection is not null)
            {
                return;
            }

            if (IsDurable)
            {
                EnsurePrivateDirectory(Path.GetDirectoryName(Path.GetFullPath(DatabasePath)));
            }

            // Held in a local until the schema is applied. If any step throws,
            // the finally disposes it; only a fully prepared connection is
            // handed to the field, and ownership transfers by nulling the local.
            //
            // CA2000 does not follow the transfer-by-nulling half of its own
            // recommended pattern and reports a leak that reading the finally
            // disproves. Suppressed here rather than repository-wide, because
            // everywhere else CA2000 fires it is right — this class hands out
            // commands and readers that genuinely must be disposed.
#pragma warning disable CA2000
            SqliteConnection? connection = new(_connectionString);
#pragma warning restore CA2000
            try
            {
                await connection.OpenAsync(cancellationToken).ConfigureAwait(false);

                await RunAsync(connection, "PRAGMA journal_mode=WAL;", cancellationToken).ConfigureAwait(false);
                await RunAsync(connection, "PRAGMA foreign_keys=ON;", cancellationToken).ConfigureAwait(false);
                await RunAsync(connection, DatabaseSchema.Sql, cancellationToken).ConfigureAwait(false);
                await EnsurePlanContextColumnAsync(connection, cancellationToken).ConfigureAwait(false);
                await RunAsync(
                    connection,
                    $"INSERT OR IGNORE INTO schema_version (version) VALUES ({SchemaVersion});",
                    cancellationToken).ConfigureAwait(false);

                _connection = connection;
                connection = null;
            }
            finally
            {
                if (connection is not null)
                {
                    await connection.DisposeAsync().ConfigureAwait(false);
                }
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>
    /// Creates the database's directory owner-only.
    /// </summary>
    /// <remarks>
    /// Run state names Goals, branches and file paths from the user's projects.
    /// Default directory permissions on a shared machine make that readable by
    /// everyone, which nobody asked for by choosing a local-first tool.
    /// </remarks>
    private static void EnsurePrivateDirectory(string? directory)
    {
        if (string.IsNullOrEmpty(directory))
        {
            return;
        }

        Directory.CreateDirectory(directory);

        if (OperatingSystem.IsLinux() || OperatingSystem.IsMacOS())
        {
            File.SetUnixFileMode(
                directory,
                UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        }
    }

    /// <summary>Runs a write statement.</summary>
    public async Task ExecuteAsync(
        string sql,
        IReadOnlyDictionary<string, object?>? parameters = null,
        CancellationToken cancellationToken = default)
    {
        SqliteConnection connection = Require();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            SqliteCommand command = Build(connection, sql, parameters);
            await using (command.ConfigureAwait(false))
            {
                await command.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>
    /// Runs several statements so that either all of them land or none does.
    /// </summary>
    /// <remarks>
    /// A state change and the event that explains it are written through this.
    /// A partially applied transition leaves the event log unable to account
    /// for the current state, and the event log is what recovery reads.
    /// </remarks>
    public async Task ExecuteInTransactionAsync(
        IReadOnlyList<(string Sql, IReadOnlyDictionary<string, object?>? Parameters)> statements,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(statements);

        SqliteConnection connection = Require();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            SqliteTransaction transaction =
                (SqliteTransaction)await connection.BeginTransactionAsync(cancellationToken).ConfigureAwait(false);

            await using (transaction.ConfigureAwait(false))
            {
                foreach ((string sql, IReadOnlyDictionary<string, object?>? parameters) in statements)
                {
                    SqliteCommand command = Build(connection, sql, parameters);
                    await using (command.ConfigureAwait(false))
                    {
                        command.Transaction = transaction;
                        await command.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
                    }
                }

                await transaction.CommitAsync(cancellationToken).ConfigureAwait(false);
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>Reads rows and projects each one.</summary>
    public async Task<List<T>> QueryAsync<T>(
        string sql,
        Func<SqliteDataReader, T> map,
        IReadOnlyDictionary<string, object?>? parameters = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(map);

        SqliteConnection connection = Require();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            SqliteCommand command = Build(connection, sql, parameters);
            await using (command.ConfigureAwait(false))
            {
                SqliteDataReader reader =
                    await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);

                await using (reader.ConfigureAwait(false))
                {
                    List<T> rows = [];
                    while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
                    {
                        rows.Add(map(reader));
                    }

                    return rows;
                }
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>Reads at most one row.</summary>
    public async Task<T?> QuerySingleAsync<T>(
        string sql,
        Func<SqliteDataReader, T> map,
        IReadOnlyDictionary<string, object?>? parameters = null,
        CancellationToken cancellationToken = default)
        where T : class
    {
        List<T> rows = await QueryAsync(sql, map, parameters, cancellationToken).ConfigureAwait(false);
        return rows.Count > 0 ? rows[0] : null;
    }

    /// <summary>
    /// Applies a satellite store's schema.
    /// </summary>
    /// <remarks>
    /// The decision ledger and the routing scorecard keep their own tables in
    /// this same file, so a discussion and the run it produced share one
    /// transaction log and one thing to back up.
    /// </remarks>
    public Task ApplySchemaAsync(string script, CancellationToken cancellationToken = default) =>
        ExecuteAsync(script, parameters: null, cancellationToken);

    private static async Task RunAsync(SqliteConnection connection, string sql, CancellationToken cancellationToken)
    {
        SqliteCommand command = connection.CreateCommand();
        await using (command.ConfigureAwait(false))
        {
            command.CommandText = sql;
            await command.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
        }
    }

    private static async Task EnsurePlanContextColumnAsync(
        SqliteConnection connection,
        CancellationToken cancellationToken)
    {
        SqliteCommand command = connection.CreateCommand();
        await using (command.ConfigureAwait(false))
        {
            command.CommandText = "PRAGMA table_info(plans);";
            SqliteDataReader reader =
                await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
            await using (reader.ConfigureAwait(false))
            {
                while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
                {
                    if (reader.GetString(1).Equals("context", StringComparison.Ordinal))
                    {
                        return;
                    }
                }
            }
        }

        await RunAsync(
            connection,
            "ALTER TABLE plans ADD COLUMN context TEXT;",
            cancellationToken).ConfigureAwait(false);
    }

    private static SqliteCommand Build(
        SqliteConnection connection,
        string sql,
        IReadOnlyDictionary<string, object?>? parameters)
    {
        SqliteCommand command = connection.CreateCommand();
        command.CommandText = sql;

        if (parameters is not null)
        {
            foreach ((string name, object? value) in parameters)
            {
                command.Parameters.AddWithValue(name, value ?? DBNull.Value);
            }
        }

        return command;
    }

    private SqliteConnection Require() =>
        _connection ?? throw new PersistenceException("The database has not been initialized");

    public async ValueTask DisposeAsync()
    {
        if (_connection is not null)
        {
            await _connection.DisposeAsync().ConfigureAwait(false);
            _connection = null;
        }

        _gate.Dispose();
    }
}

/// <summary>An operational persistence operation failed.</summary>
public sealed class PersistenceException : Exception
{
    public PersistenceException() { }

    public PersistenceException(string message) : base(message) { }

    public PersistenceException(string message, Exception innerException)
        : base(message, innerException) { }
}
