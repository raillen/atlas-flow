using System.Collections.ObjectModel;

using AtlasFlow.Application.Contracts;
using AtlasFlow.Domain.Goals;
using AtlasFlow.Domain.Projects;

using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;

namespace AtlasFlow.Desktop.ViewModels;

/// <summary>
/// The workspace: which project is open, and what Goals it declares.
/// </summary>
/// <remarks>
/// <para>
/// This is the first vertical slice — real services, no stubs. It exists to
/// prove the contract against a real backend before either side is broadened,
/// because a contract nobody has called is a guess.
/// </para>
/// <para>
/// Loading, failure and emptiness are modelled explicitly. A view model built
/// against fakes tends to have none of them: a fake answers instantly, never
/// fails, and always has data. Every one of those three happens here on the
/// first directory a user opens.
/// </para>
/// </remarks>
public sealed partial class WorkspaceViewModel : ObservableObject
{
    private readonly IProjectService _projects;
    private readonly IGoalService _goals;

    public WorkspaceViewModel(IProjectService projects, IGoalService goals)
    {
        _projects = projects;
        _goals = goals;
    }

    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasProject))]
    private ProjectInspection? _project;

    [ObservableProperty]
    private bool _isLoading;

    /// <summary>
    /// Why the Goals could not be read, when they could not be.
    /// </summary>
    /// <remarks>
    /// Separate from the project's own <c>Reason</c>. A project can be
    /// perfectly well-formed and still have one unreadable Goal file, and
    /// collapsing the two would report a broken YAML as a broken project.
    /// </remarks>
    [ObservableProperty]
    [NotifyPropertyChangedFor(nameof(HasError))]
    private string? _error;

    public ObservableCollection<Goal> Goals { get; } = [];

    public bool HasProject => Project is not null;

    public bool HasError => !string.IsNullOrEmpty(Error);

    /// <summary>True once loading finished and there was nothing to show.</summary>
    public bool IsEmpty => !IsLoading && !HasError && Goals.Count == 0 && HasProject;

    public string ProjectHeadline => Project is null
        ? "No project open"
        : $"{Project.ProjectName} — {Describe(Project.Mode)}";

    public string StageAvailability => Project is null
        ? string.Empty
        : $"Plan {YesNo(Project.Capabilities.CanPlan)}  ·  "
          + $"Run {YesNo(Project.Capabilities.CanRun)}  ·  "
          + $"Review {YesNo(Project.Capabilities.CanReview)}";

    [RelayCommand]
    public async Task LoadAsync(CancellationToken cancellationToken)
    {
        IsLoading = true;
        Error = null;
        Goals.Clear();

        try
        {
            Project = await _projects.GetCurrentAsync(cancellationToken).ConfigureAwait(true);

            if (Project is null)
            {
                Error = "No project directory was found. Set ATLAS_FLOW_PROJECT_ROOT.";
                return;
            }

            // An external or unadapted project has no .ai/goals to read. That
            // is an expected outcome, not a failure, and the reason the
            // inspection already produced is the better thing to show.
            if (Project.Mode != ProjectMode.AtlasReady)
            {
                Error = Project.Reason;
                return;
            }

            foreach (Goal goal in await _goals.ListAsync(cancellationToken).ConfigureAwait(true))
            {
                Goals.Add(goal);
            }
        }
#pragma warning disable CA1031 // The window is the last place an exception can
        // be reported to a person. Anything unhandled here becomes a blank
        // screen with no explanation, which is the worst possible outcome.
        catch (Exception exc)
#pragma warning restore CA1031
        {
            Error = exc.Message;
        }
        finally
        {
            IsLoading = false;
            OnPropertyChanged(nameof(IsEmpty));
            OnPropertyChanged(nameof(ProjectHeadline));
            OnPropertyChanged(nameof(StageAvailability));
        }
    }

    private static string Describe(ProjectMode mode) => mode switch
    {
        ProjectMode.AtlasReady => "ready",
        ProjectMode.AtlasNeedsAdaptation => "needs adaptation",
        ProjectMode.AtlasIncompatible => "incompatible framework",
        ProjectMode.External => "external project",
        _ => "unknown",
    };

    private static string YesNo(bool value) => value ? "yes" : "no";
}
