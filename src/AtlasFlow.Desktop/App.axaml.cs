using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;

using AtlasFlow.Desktop.Views;

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
    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.MainWindow = new MainWindow();
        }

        base.OnFrameworkInitializationCompleted();
    }
}
