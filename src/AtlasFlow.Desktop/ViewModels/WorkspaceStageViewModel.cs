using CommunityToolkit.Mvvm.ComponentModel;

namespace AtlasFlow.Desktop.ViewModels;

public sealed partial class WorkspaceStageViewModel(
    string key,
    string title,
    string kicker,
    string description,
    string nextAction,
    bool isEnabled) : ObservableObject
{
    public string Key { get; } = key;

    public string Title { get; } = title;

    public string Kicker { get; } = kicker;

    public string Description { get; } = description;

    public string NextAction { get; } = nextAction;

    [ObservableProperty]
    public partial bool IsEnabled { get; set; } = isEnabled;

    public string AvailabilityLabel => IsEnabled ? "Disponível" : "Requer Project Atlas";

    partial void OnIsEnabledChanged(bool value) => OnPropertyChanged(nameof(AvailabilityLabel));
}
