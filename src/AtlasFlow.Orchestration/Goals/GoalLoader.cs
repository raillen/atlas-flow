using System.Collections.Concurrent;

using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;

namespace AtlasFlow.Orchestration.Goals;

/// <summary>A Goal file on disk could not be read as a Goal.</summary>
public sealed class GoalLoadException : Exception
{
    public GoalLoadException() { }

    public GoalLoadException(string message) : base(message) { }

    public GoalLoadException(string message, Exception innerException)
        : base(message, innerException) { }
}

/// <summary>
/// Reads the Goals a project declares under <c>.ai/goals/</c>.
/// </summary>
/// <remarks>
/// <para>
/// Git is canonical (ADR-009), so this is the authority on what Goals exist —
/// not the database. Nothing here writes: a Goal moves because a run produced
/// evidence, and that write goes to the file.
/// </para>
/// <para>
/// Results are cached against a signature of the files they came from. The
/// desktop asks for the Goal list on every navigation, and re-parsing every
/// Goal each time was measured on the previous implementation as the
/// difference between 6ms and 250ms.
/// </para>
/// </remarks>
public sealed class GoalLoader
{
    private const string GoalsDirectory = ".ai/goals";

    private readonly ConcurrentDictionary<string, CacheEntry> _cache = new(StringComparer.Ordinal);

    /// <summary>Every Goal in the project, ordered by phase and then by id.</summary>
    /// <exception cref="GoalLoadException">A Goal file exists but cannot be read.</exception>
    public IReadOnlyList<Goal> Load(string projectRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);

        string root = Path.GetFullPath(projectRoot);
        Signature signature = Signature.Of(root);

        if (_cache.TryGetValue(root, out CacheEntry? cached) && cached.Signature == signature)
        {
            return cached.Goals;
        }

        IReadOnlyList<Goal> goals = Read(root);
        _cache[root] = new CacheEntry(signature, goals);
        return goals;
    }

    /// <summary>Drops every cached project. For tests and for an explicit reload.</summary>
    public void Forget() => _cache.Clear();

    private static IReadOnlyList<Goal> Read(string root)
    {
        string directory = Path.Combine(root, GoalsDirectory);
        if (!Directory.Exists(directory))
        {
            throw new GoalLoadException($"Goals directory not found: {directory}");
        }

        List<Goal> goals = [];
        foreach (string file in GoalFiles(directory))
        {
            goals.Add(ReadOne(file));
        }

        return [.. goals.OrderBy(goal => goal.Phase, StringComparer.Ordinal)
                        .ThenBy(goal => goal.Id.Value, StringComparer.Ordinal)];
    }

    private static IEnumerable<string> GoalFiles(string directory) =>
        Directory.EnumerateFiles(directory, "*.yaml", SearchOption.AllDirectories)
                 .OrderBy(path => path, StringComparer.Ordinal);

    private static Goal ReadOne(string path)
    {
        Manifest manifest = Manifest.Read(path);
        if (manifest.Error is { } error)
        {
            throw new GoalLoadException($"{path}: {error}");
        }

        string? id = manifest.Text("id");
        if (id is null)
        {
            throw new GoalLoadException($"{path}: a Goal must declare an id");
        }

        return new Goal
        {
            Id = new GoalId(id),
            Phase = manifest.Text("phase") ?? string.Empty,
            Title = manifest.Text("title") ?? id,
            State = ParseState(manifest.Text("state"), path),
            Objective = manifest.Text("objective") ?? string.Empty,
            Gates = ReadGates(manifest.Section("gates")),
            Constraints = manifest.Strings("constraints"),
            NonGoals = manifest.Strings("non_goals"),
            Dependencies = [.. manifest.Strings("dependencies").Select(value => new GoalId(value))],
            Acceptance = manifest.Strings("acceptance"),
            History = manifest.Strings("history"),
            EvidenceCount = manifest.SequenceLength("evidence"),
        };
    }

    /// <summary>
    /// Reads the four gates, defaulting an absent one to required.
    /// </summary>
    /// <remarks>
    /// Absent means required, never optional. A Goal file that forgets to
    /// declare its review gate must not thereby be allowed to close without a
    /// review — the safe reading of silence is the strict one.
    /// </remarks>
    private static GoalGates ReadGates(Manifest? gates) => new()
    {
        Build = Requirement(gates?.Text("build")),
        Tests = Requirement(gates?.Text("tests")),
        Review = Requirement(gates?.Text("review")),
        Documentation = Requirement(gates?.Text("documentation")),
    };

    private static GateRequirement Requirement(string? declared) =>
        string.Equals(declared, "optional", StringComparison.OrdinalIgnoreCase)
            ? GateRequirement.Optional
            : GateRequirement.Required;

    private static GoalState ParseState(string? declared, string path) => declared switch
    {
        "PLANNED" => GoalState.Planned,
        "READY" => GoalState.Ready,
        "ACTIVE" => GoalState.Active,
        "BLOCKED" => GoalState.Blocked,
        "DONE" => GoalState.Done,
        "CANCELLED" => GoalState.Cancelled,
        null => throw new GoalLoadException($"{path}: a Goal must declare a state"),

        // Not defaulted. A Goal whose state nobody recognises is a Goal nobody
        // can reason about, and reading it as PLANNED would hide the typo
        // behind a plausible-looking board.
        _ => throw new GoalLoadException($"{path}: '{declared}' is not a known Goal state"),
    };

    private sealed record CacheEntry(Signature Signature, IReadOnlyList<Goal> Goals);

    /// <summary>
    /// What the Goal files looked like on disk, cheaply.
    /// </summary>
    /// <remarks>
    /// One stat per file rather than one parse per file. An edit changes the
    /// write time, and a new or deleted Goal changes the set; either
    /// invalidates the cache.
    /// </remarks>
    private sealed record Signature(IReadOnlyList<(string Path, long Ticks)> Files)
    {
        internal static Signature Of(string root)
        {
            string directory = Path.Combine(root, GoalsDirectory);
            if (!Directory.Exists(directory))
            {
                return new Signature([]);
            }

            List<(string, long)> files = [];
            foreach (string path in GoalFiles(directory))
            {
                long ticks;
                try
                {
                    ticks = File.GetLastWriteTimeUtc(path).Ticks;
                }
                catch (Exception exc) when (exc is IOException or UnauthorizedAccessException)
                {
                    ticks = -1;
                }

                files.Add((path, ticks));
            }

            return new Signature(files);
        }

        public bool Equals(Signature? other) =>
            other is not null && Files.SequenceEqual(other.Files);

        public override int GetHashCode() => Files.Count;
    }
}
