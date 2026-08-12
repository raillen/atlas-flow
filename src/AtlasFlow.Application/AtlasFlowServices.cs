using AtlasFlow.Application.Contracts;
using AtlasFlow.Application.Services;
using AtlasFlow.Orchestration.Context;
using AtlasFlow.Orchestration.Execution;
using AtlasFlow.Orchestration.Goals;
using AtlasFlow.Persistence;

using Microsoft.Extensions.DependencyInjection;

namespace AtlasFlow.Application;

/// <summary>
/// The single place the runtime is wired up.
/// </summary>
/// <remarks>
/// <para>
/// <c>AtlasFlow.Desktop</c> and <c>AtlasFlow.Cli</c> both call this and then
/// resolve the interfaces in
/// <see cref="Contracts"/>. Neither of them constructs an implementation
/// directly, and neither of them names one: that is what keeps the seam a
/// seam, and what lets the backend and the UI be built in parallel without
/// either side reaching into the other.
/// </para>
/// <para>
/// Project inspection, Goals, bounded context planning, Project Intelligence,
/// Plans and the first Run slice are registered here. Remaining services stay
/// unregistered so a host fails at the boundary that asks for an unported
/// capability rather than receiving a plausible stub.
/// </para>
/// </remarks>
public static class AtlasFlowServices
{
    /// <summary>
    /// Registers the orchestration runtime against an open project.
    /// </summary>
    /// <param name="services">The host's service collection.</param>
    /// <param name="projectRoot">
    /// The directory Atlas Flow was opened on. Every path the services resolve
    /// is relative to this, and anything escaping it is refused.
    /// </param>
    public static IServiceCollection AddAtlasFlow(this IServiceCollection services, string projectRoot)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectRoot);

        services.AddSingleton(new AtlasFlowOptions { ProjectRoot = projectRoot });

        // Ported and real.
        services.AddSingleton<GoalLoader>();
        services.AddSingleton<ContextPlanner>(provider =>
        {
            AtlasFlowOptions options = provider.GetRequiredService<AtlasFlowOptions>();
            return new ContextPlanner(options.ProjectRoot);
        });
        services.AddSingleton<IProjectService, ProjectService>();
        services.AddSingleton<IGoalService, GoalService>();
        services.AddSingleton<IContextService, ContextService>();
        services.AddSingleton<ProjectIntelligenceRepository>(provider =>
        {
            AtlasFlowOptions options = provider.GetRequiredService<AtlasFlowOptions>();
            return new ProjectIntelligenceRepository(options.ProjectRoot);
        });
        services.AddSingleton<IProjectIntelligenceService, ProjectIntelligenceService>();

        // Operational state. One database per project, under .atlas/, because
        // run state belongs to the project it is about and not to the machine.
        services.AddSingleton(provider =>
        {
            AtlasFlowOptions options = provider.GetRequiredService<AtlasFlowOptions>();
            string databaseDirectory = File.Exists(Path.Combine(options.ProjectRoot, "atlas.json"))
                ? Path.Combine(options.ProjectRoot, ".atlas", "runtime")
                : Path.Combine(options.ProjectRoot, ".atlas");
            string databaseFile = File.Exists(Path.Combine(options.ProjectRoot, "atlas.json"))
                ? "atlas.db"
                : "state.db";
            return new AtlasFlowDatabase(Path.Combine(databaseDirectory, databaseFile));
        });
        services.AddSingleton<EventStore>();
        services.AddSingleton<RunRepository>();
        services.AddSingleton<PlanRepository>();
        services.AddSingleton<EvidenceRepository>();

        // The no-op runner is the only one ported. It is not a placeholder:
        // it is how the scheduler, the state machine and the event stream are
        // exercised without an agent or a worktree in the way.
        services.AddSingleton<ITaskRunner, NoOpTaskRunner>();

        services.AddSingleton<IPlanService, PlanService>();
        services.AddSingleton<IRunService, RunService>();

        // Not ported. Left unregistered on purpose: resolving one fails where
        // it is asked for, naming the service, instead of handing back a stub
        // that answers plausibly and is believed.
        //
        //   IDiscussionService     conversations and the decision ledger
        //   IRoutingService        which model each role resolved to
        //   ISettingsService       configuration
        //   IDocumentationService  the canonical docs
        return services;
    }

    /// <summary>
    /// Opens the operational database. Call once, before resolving a service.
    /// </summary>
    /// <remarks>
    /// Explicit rather than lazy. Creating a database is I/O that can fail —
    /// a read-only directory, a full disk — and a lazy first-use
    /// initialization surfaces that failure inside whatever unrelated call
    /// happened to be first. Here it fails at startup, where a host can say so.
    /// </remarks>
    public static async Task<IServiceProvider> InitializeAtlasFlowAsync(
        this IServiceProvider provider,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(provider);

        await provider.GetRequiredService<AtlasFlowDatabase>()
            .InitializeAsync(cancellationToken)
            .ConfigureAwait(false);

        return provider;
    }
}

/// <summary>What the runtime needs to know before it can do anything.</summary>
public sealed record AtlasFlowOptions
{
    /// <summary>The directory Atlas Flow was opened on.</summary>
    public required string ProjectRoot { get; init; }
}
