using AtlasFlow.Application;
using AtlasFlow.Desktop.Integration;
using AtlasFlow.Desktop.ViewModels;
using AtlasFlow.Desktop.Views;
using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using Microsoft.Extensions.DependencyInjection;

namespace AtlasFlow.Desktop;

/// <remarks>
/// The base type is written out in full because <c>Application</c> alone is
/// ambiguous here: from inside <c>AtlasFlow.Desktop</c> the compiler finds the
/// <c>AtlasFlow.Application</c> namespace before it finds Avalonia's type.
/// </remarks>
public sealed partial class App : Avalonia.Application
{
    private ServiceProvider? _serviceProvider;

    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            ServiceCollection services = new();
            ConfigureServices(services);
            _serviceProvider = services.BuildServiceProvider(new ServiceProviderOptions
            {
                ValidateOnBuild = true,
                ValidateScopes = true,
            });

            // Database initialization is explicit and happens before the first
            // window can issue a planning or execution command.
            _serviceProvider.InitializeAtlasFlowAsync().GetAwaiter().GetResult();

            desktop.MainWindow = _serviceProvider.GetRequiredService<MainWindow>();
            desktop.Exit += (_, _) => _serviceProvider?.Dispose();
        }

        base.OnFrameworkInitializationCompleted();
    }

    private static void ConfigureServices(IServiceCollection services)
    {
        string root = Environment.GetEnvironmentVariable("ATLAS_FLOW_PROJECT_ROOT")
                      ?? Directory.GetCurrentDirectory();

        services.AddAtlasFlow(root);
        services.AddSingleton<IAtlasFlowFrontendGateway, ApplicationAtlasFlowFrontendGateway>();
        services.AddSingleton<IThemeController, AvaloniaThemeController>();
        services.AddSingleton<PlanViewModel>();
        services.AddSingleton<DiscussViewModel>();
        services.AddSingleton<RunViewModel>();
        services.AddSingleton<WorkspaceViewModel>();
        services.AddSingleton<MainWindow>();
    }
}
