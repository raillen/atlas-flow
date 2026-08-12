using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;

using AtlasFlow.Application;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Desktop.Views;

using Microsoft.Extensions.DependencyInjection;

namespace AtlasFlow.Desktop;

/// <remarks>
/// The base type is written out in full because <c>Application</c> alone is
/// ambiguous here: from inside <c>AtlasFlow.Desktop</c> the compiler finds the
/// <c>AtlasFlow.Application</c> namespace before it finds Avalonia's type.
/// Any file in this project that touches <c>Application.Current</c> hits the
/// same thing; qualify it or alias it at the top of the file.
/// </remarks>
public sealed partial class App : Avalonia.Application
{
    private ServiceProvider? _services;

    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            _services = BuildServices();
            desktop.MainWindow = new MainWindow
            {
                DataContext = _services.GetRequiredService<WorkspaceViewModel>(),
            };

            desktop.ShutdownRequested += (_, _) => _services?.Dispose();
        }

        base.OnFrameworkInitializationCompleted();
    }

    /// <summary>
    /// Wires the runtime against whatever directory the app was pointed at.
    /// </summary>
    /// <remarks>
    /// <c>ATLAS_FLOW_PROJECT_ROOT</c> wins, then the working directory. A
    /// packaged build launched from a menu has a working directory inside its
    /// own bundle, so the variable is not optional there — the previous
    /// implementation learned that by shipping without it.
    /// </remarks>
    private static ServiceProvider BuildServices()
    {
        string root = Environment.GetEnvironmentVariable("ATLAS_FLOW_PROJECT_ROOT")
                      ?? Directory.GetCurrentDirectory();

        ServiceCollection services = new();
        services.AddAtlasFlow(root);
        services.AddSingleton<WorkspaceViewModel>();
        return services.BuildServiceProvider();
    }
}
