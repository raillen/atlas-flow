namespace AtlasFlow.Persistence;

/// <summary>The operational schema, version 4.</summary>
/// <remarks>
/// The base schema is idempotent. Incremental changes that cannot be expressed
/// with <c>IF NOT EXISTS</c> are applied by
/// <see cref="AtlasFlowDatabase.EnsurePlanContextColumnAsync"/> during startup.
/// </remarks>
internal static class DatabaseSchema
{
    internal const string Sql = """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            goal_id TEXT NOT NULL,
            goal_revision TEXT NOT NULL,
            state TEXT NOT NULL,
            autonomy TEXT NOT NULL DEFAULT 'agentic',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            objective TEXT NOT NULL,
            role TEXT,
            risk TEXT NOT NULL DEFAULT 'medium',
            scope TEXT NOT NULL DEFAULT '[]',
            state TEXT NOT NULL,
            dependencies TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            runner TEXT,
            model_provider TEXT,
            model_id TEXT,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            error_msg TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (run_id) REFERENCES runs(id)
        );

        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            project_id TEXT NOT NULL,
            run_id TEXT,
            type TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            payload TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            run_id TEXT,
            task_id TEXT,
            gate TEXT NOT NULL,
            kind TEXT NOT NULL,
            uri TEXT NOT NULL DEFAULT '',
            digest TEXT NOT NULL DEFAULT '',
            verdict TEXT NOT NULL,
            attached_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            goal_id TEXT NOT NULL,
            goal_revision TEXT NOT NULL,
            state TEXT NOT NULL,
            autonomy TEXT NOT NULL,
            runner TEXT NOT NULL,
            integration_target TEXT NOT NULL,
            created_at TEXT NOT NULL,
            context TEXT,
            tasks TEXT NOT NULL DEFAULT '[]'
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_goal ON evidence(goal_id);
        CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
        CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
        CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts(task_id);
        CREATE INDEX IF NOT EXISTS idx_plans_goal ON plans(goal_id);
        """;
}
