using AtlasFlow.Application.Contracts;
using AtlasFlow.Desktop.Integration;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Desktop.Views;
using Avalonia.Automation;
using Avalonia.Controls;
using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.Media.Imaging;
using Avalonia.VisualTree;

using NSubstitute;

namespace AtlasFlow.Desktop.Tests;

public sealed class MainWindowTests
{
    [AvaloniaFact]
    public async Task Shell_composes_navigation_context_and_accessible_actions()
    {
        WorkspaceViewModel viewModel = new(
            new UnavailableAtlasFlowFrontendGateway(),
            new TestThemeController(),
            new PlanViewModel(Substitute.For<IPlanService>()));
        await viewModel.InitializeAsync(TestContext.Current.CancellationToken);

        MainWindow window = new(viewModel);

        try
        {
            window.Show();

            ListBox navigation = window.FindControl<ListBox>("StageNavigation")
                ?? throw new InvalidOperationException("StageNavigation não foi composto.");
            Button toggleNavigation = window.FindControl<Button>("ToggleNavigationButton")
                ?? throw new InvalidOperationException("ToggleNavigationButton não foi composto.");
            Button[] buttons = window.GetVisualDescendants().OfType<Button>().ToArray();
            using Bitmap frame = window.CaptureRenderedFrame()
                ?? throw new InvalidOperationException("O shell não produziu um frame headless.");

            Assert.Same(viewModel.SelectedStage, navigation.SelectedItem);
            Assert.NotNull(toggleNavigation);
            Assert.NotEmpty(buttons);
            Assert.True(frame.PixelSize.Width >= 960);
            Assert.True(frame.PixelSize.Height >= 640);
            Assert.All(
                buttons,
                button => Assert.False(string.IsNullOrWhiteSpace(AutomationProperties.GetName(button))));
        }
        finally
        {
            window.Close();
        }
    }

    private sealed class TestThemeController : IThemeController
    {
        public string CurrentMode => "Escuro";

        public string Toggle() => CurrentMode;
    }
}
