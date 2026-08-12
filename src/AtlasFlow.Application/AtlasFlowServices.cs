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
/// <b>Nothing is registered yet.</b> The interfaces exist, the implementations
/// do not. A host that calls this today gets a container that will throw on
/// the first resolve — which is the honest behaviour, and better than a silent
/// null.
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

        // Registrations land here as each module is ported. The order the UI
        // needs them, which is also the order they are being written:
        //
        //   IProjectService        project inspection, files, adaptation
        //   IGoalService           the Goals in Git, and whether they may close
        //   IDiscussionService     conversations and the decision ledger
        //   IPlanService           drawing and locking a task graph
        //   IRunService            execution and the AG-UI event stream
        //   IRoutingService        which model each role resolved to
        //   ISettingsService       configuration
        //   IDocumentationService  the canonical docs
        return services;
    }
}

/// <summary>What the runtime needs to know before it can do anything.</summary>
public sealed record AtlasFlowOptions
{
    /// <summary>The directory Atlas Flow was opened on.</summary>
    public required string ProjectRoot { get; init; }
}
