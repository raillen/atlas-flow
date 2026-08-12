using AtlasFlow.Desktop.Integration;
using AtlasFlow.Desktop.ViewModels;
using Avalonia.Controls;

namespace AtlasFlow.Desktop.Views;

public sealed partial class MainWindow : Window
{
    private readonly WorkspaceViewModel _viewModel;

    // Avalonia's runtime loader requires a public parameterless constructor.
    // The composition root uses the injected constructor below.
    public MainWindow()
        : this(new WorkspaceViewModel(
            new UnavailableAtlasFlowFrontendGateway(),
            new AvaloniaThemeController(),
            new PlanViewModel(new UnavailablePlanService())))
    {
    }

    public MainWindow(WorkspaceViewModel viewModel)
    {
        _viewModel = viewModel;
        InitializeComponent();
        DataContext = viewModel;
        Opened += OnOpened;
    }

    private async void OnOpened(object? sender, EventArgs eventArgs)
    {
        Opened -= OnOpened;
        await _viewModel.InitializeAsync();
    }
}
