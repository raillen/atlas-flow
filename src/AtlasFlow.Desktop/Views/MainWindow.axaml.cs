using AtlasFlow.Desktop.ViewModels;
using Avalonia.Controls;

namespace AtlasFlow.Desktop.Views;

public sealed partial class MainWindow : Window
{
    private readonly WorkspaceViewModel _viewModel;

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
