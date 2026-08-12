using AtlasFlow.Domain;
using AtlasFlow.Domain.Planning;

namespace AtlasFlow.Orchestration.Planning;

/// <summary>A plan's task graph is not a valid DAG.</summary>
public sealed class TaskGraphException : Exception
{
    public TaskGraphException() { }

    public TaskGraphException(string message) : base(message) { }

    public TaskGraphException(string message, Exception innerException)
        : base(message, innerException) { }
}

/// <summary>Two tasks that may run at once would write the same place.</summary>
public sealed record WriteScopeConflict(TaskId First, TaskId Second, string SharedPath);

/// <summary>Checking and ordering a plan's task graph.</summary>
public static class TaskGraph
{
    /// <summary>
    /// Every reason the graph is unusable, or empty if it is fine.
    /// </summary>
    /// <remarks>
    /// Returns all the problems rather than throwing on the first. A plan is
    /// reviewed by a person before it is locked, and showing them one broken
    /// dependency at a time turns one review into five.
    /// </remarks>
    public static IReadOnlyList<string> Validate(IReadOnlyList<PlanTask> tasks)
    {
        ArgumentNullException.ThrowIfNull(tasks);

        List<string> errors = [];
        HashSet<TaskId> known = [.. tasks.Select(task => task.Id)];

        foreach (PlanTask task in tasks)
        {
            foreach (TaskId dependency in task.Dependencies.Where(d => !known.Contains(d)))
            {
                errors.Add($"Task '{task.Id}' depends on unknown task '{dependency}'");
            }
        }

        if (FindCycle(tasks) is { } cycle)
        {
            errors.Add($"Cycle detected involving task '{cycle}'");
        }

        return errors;
    }

    /// <summary>
    /// Pairs of concurrent tasks whose write scopes overlap.
    /// </summary>
    /// <remarks>
    /// Two tasks are concurrent when neither depends on the other. Letting two
    /// such tasks write the same directory is how a run produces a result that
    /// depends on which finished last.
    /// </remarks>
    public static IReadOnlyList<WriteScopeConflict> FindWriteScopeConflicts(IReadOnlyList<PlanTask> tasks)
    {
        ArgumentNullException.ThrowIfNull(tasks);

        List<WriteScopeConflict> conflicts = [];

        for (int i = 0; i < tasks.Count; i++)
        {
            for (int j = i + 1; j < tasks.Count; j++)
            {
                PlanTask first = tasks[i];
                PlanTask second = tasks[j];

                if (first.Dependencies.Contains(second.Id) || second.Dependencies.Contains(first.Id))
                {
                    continue;
                }

                string? shared = FirstOverlap(first, second);
                if (shared is not null)
                {
                    conflicts.Add(new WriteScopeConflict(first.Id, second.Id, shared));
                }
            }
        }

        return conflicts;
    }

    /// <summary>Tasks in an order where every dependency comes first.</summary>
    /// <exception cref="TaskGraphException">The graph has a cycle or a dangling dependency.</exception>
    public static IReadOnlyList<PlanTask> InDependencyOrder(IReadOnlyList<PlanTask> tasks)
    {
        ArgumentNullException.ThrowIfNull(tasks);

        List<PlanTask> remaining = [.. tasks];
        List<PlanTask> ordered = [];
        HashSet<TaskId> done = [];

        while (remaining.Count > 0)
        {
            List<PlanTask> ready =
                [.. remaining.Where(task => task.Dependencies.All(done.Contains))];

            if (ready.Count == 0)
            {
                throw new TaskGraphException(
                    "Cannot resolve execution order: cycle or missing dependency");
            }

            foreach (PlanTask task in ready)
            {
                ordered.Add(task);
                done.Add(task.Id);
                remaining.Remove(task);
            }
        }

        return ordered;
    }

    private static TaskId? FindCycle(IReadOnlyList<PlanTask> tasks)
    {
        Dictionary<TaskId, Mark> marks = tasks.ToDictionary(task => task.Id, _ => Mark.Unvisited);
        Dictionary<TaskId, IReadOnlyList<TaskId>> edges =
            tasks.ToDictionary(task => task.Id, task => task.Dependencies);

        foreach (TaskId start in tasks.Select(task => task.Id))
        {
            if (marks[start] == Mark.Unvisited && HasCycleFrom(start, marks, edges))
            {
                return start;
            }
        }

        return null;
    }

    private static bool HasCycleFrom(
        TaskId node,
        Dictionary<TaskId, Mark> marks,
        Dictionary<TaskId, IReadOnlyList<TaskId>> edges)
    {
        marks[node] = Mark.InProgress;

        foreach (TaskId next in edges.GetValueOrDefault(node, []))
        {
            if (!marks.TryGetValue(next, out Mark mark))
            {
                // A dangling dependency. Validate reports it separately; it is
                // not a cycle and must not be counted as one.
                continue;
            }

            if (mark == Mark.InProgress || (mark == Mark.Unvisited && HasCycleFrom(next, marks, edges)))
            {
                return true;
            }
        }

        marks[node] = Mark.Done;
        return false;
    }

    private static string? FirstOverlap(PlanTask first, PlanTask second)
    {
        foreach (ProjectPath a in first.WriteScope)
        {
            foreach (ProjectPath b in second.WriteScope)
            {
                string shared = SharedPrefix(a.Value, b.Value);
                if (shared.Length > 0)
                {
                    return shared;
                }
            }
        }

        return null;
    }

    /// <summary>The longest directory prefix two paths share.</summary>
    private static string SharedPrefix(string a, string b)
    {
        string[] left = a.Trim('/').Split('/');
        string[] right = b.Trim('/').Split('/');

        List<string> common = [];
        for (int i = 0; i < Math.Min(left.Length, right.Length); i++)
        {
            if (!string.Equals(left[i], right[i], StringComparison.Ordinal))
            {
                break;
            }

            common.Add(left[i]);
        }

        return string.Join('/', common);
    }

    private enum Mark
    {
        Unvisited,
        InProgress,
        Done,
    }
}
