using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Intelligence;
using AtlasFlow.Domain.Planning;
using AtlasFlow.Orchestration.Planning;
using AtlasFlow.Persistence;

namespace AtlasFlow.Application.Services;

/// <summary>Drawing, reviewing and locking a task graph.</summary>
public sealed class PlanService(
    AtlasFlowOptions options,
    PlanRepository plans,
    IGoalService goals,
    IContextService context,
    IProjectIntelligenceService intelligence) : IPlanService
{
    private readonly string _projectRoot = options.ProjectRoot;
    private readonly PlanRepository _plans = plans;
    private readonly IGoalService _goals = goals;
    private readonly IContextService _context = context;
    private readonly IProjectIntelligenceService _intelligence = intelligence;

    public async Task<IReadOnlyList<Plan>> ListForGoalAsync(
        GoalId goalId,
        CancellationToken cancellationToken = default) =>
        await _plans.ListAsync(goalId, cancellationToken).ConfigureAwait(false);

    public Task<Plan?> FindAsync(PlanId id, CancellationToken cancellationToken = default) =>
        _plans.FindAsync(id, cancellationToken);

    public async Task<Plan> CreateAsync(CreatePlanRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        Goal goal = await _goals.FindAsync(request.GoalId, cancellationToken).ConfigureAwait(false)
            ?? throw new PlanStateException($"No Goal '{request.GoalId}' in this project");

        Plan plan = GoalPlanner.Draw(
            goal,
            new DirectoryInfo(_projectRoot).Name,
            request.Autonomy,
            request.Runner,
            request.IntegrationTarget);

        plan = plan with
        {
            Context = await _context.PlanAsync(
                new ContextPlanRequest { Task = goal.Objective },
                cancellationToken).ConfigureAwait(false),
        };

        // Validated before it is stored, not before it is run. A plan a person
        // is about to review must not contain a cycle they are expected to
        // spot for themselves.
        IReadOnlyList<string> errors = TaskGraph.Validate(plan.Tasks);
        if (errors.Count > 0)
        {
            throw new PlanStateException($"The drawn plan is not a valid graph: {string.Join("; ", errors)}");
        }

        await _plans.SaveAsync(plan, cancellationToken).ConfigureAwait(false);
        await RecordIntelligenceAsync(ProjectIntelligenceReportFactory.Planned(plan), cancellationToken)
            .ConfigureAwait(false);
        return plan;
    }

    private async Task RecordIntelligenceAsync(
        TaskReport report,
        CancellationToken cancellationToken)
    {
        try
        {
            await _intelligence.RecordAsync(report, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (
            exception is IOException
            or UnauthorizedAccessException
            or IntelligenceFormatException)
        {
            // Project Intelligence is derived state. A plan remains usable
            // when its rebuildable history projection cannot be written.
        }
    }

    public async Task<Plan> LockAsync(PlanId id, CancellationToken cancellationToken = default)
    {
        Plan plan = await _plans.FindAsync(id, cancellationToken).ConfigureAwait(false)
            ?? throw new PlanStateException($"No plan '{id}'");

        if (plan.State != PlanState.Draft)
        {
            throw new PlanStateException($"Plan {id} is already {plan.State}");
        }

        // The last moment anything about the graph can change. After this the
        // reviewed graph and the executed graph are the same graph, which is
        // the entire purpose of locking.
        IReadOnlyList<WriteScopeConflict> conflicts = TaskGraph.FindWriteScopeConflicts(plan.Tasks);
        if (conflicts.Count > 0)
        {
            string described = string.Join(
                "; ",
                conflicts.Select(c => $"{c.First} and {c.Second} both write '{c.SharedPath}'"));
            throw new PlanStateException($"Cannot lock a plan with overlapping write scopes: {described}");
        }

        Plan locked = plan with { State = PlanState.Locked };
        await _plans.SaveAsync(locked, cancellationToken).ConfigureAwait(false);
        return locked;
    }
}
