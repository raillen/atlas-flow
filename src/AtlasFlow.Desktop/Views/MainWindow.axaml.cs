using Avalonia.Controls;
using Avalonia.Interactivity;

using AtlasFlow.Desktop.ViewModels;

namespace AtlasFlow.Desktop.Views;

public sealed partial class MainWindow : Window
{
    public MainWindow() => InitializeComponent();

    /// <remarks>
    /// The first load runs when the window opens rather than in the view
    /// model's constructor. Reading a project is I/O, and a constructor that
    /// blocks on it is a constructor that can fail before there is anywhere to
    /// show why.
    /// </remarks>
    protected override async void OnLoaded(RoutedEventArgs e)
    {
        base.OnLoaded(e);

        if (DataContext is WorkspaceViewModel workspace)
        {
            await workspace.LoadAsync(CancellationToken.None);
        }
    }
}
