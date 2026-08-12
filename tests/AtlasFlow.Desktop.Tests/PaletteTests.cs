using AtlasFlow.Desktop.Theme;

namespace AtlasFlow.Desktop.Tests;

public sealed class PaletteTests
{
    [Fact]
    public void Dark_palette_text_and_status_colors_meet_wcag_aa()
    {
        AssertPaletteContrast(Palette.Dark);
    }

    [Fact]
    public void Light_palette_text_and_status_colors_meet_wcag_aa()
    {
        AssertPaletteContrast(Palette.Light);
    }

    private static void AssertPaletteContrast(AtlasPalette palette)
    {
        AssertContrast(palette.PrimaryText, palette.Background, 4.5);
        AssertContrast(palette.SecondaryText, palette.Background, 4.5);
        AssertContrast(palette.MutedText, palette.Background, 4.5);
        AssertContrast(palette.PrimaryText, palette.Surface, 4.5);
        AssertContrast(palette.SecondaryText, palette.Surface, 4.5);
        AssertContrast(palette.MutedText, palette.Surface, 4.5);
        AssertContrast(palette.OnAccent, palette.Accent, 4.5);
        AssertContrast(palette.Focus, palette.Background, 3.0);
        AssertContrast(palette.Success, palette.Background, 4.5);
        AssertContrast(palette.Warning, palette.Background, 4.5);
        AssertContrast(palette.Danger, palette.Background, 4.5);
        AssertContrast(palette.Info, palette.Background, 4.5);
    }

    private static void AssertContrast(string foreground, string background, double minimum)
    {
        double ratio = Palette.ContrastRatio(foreground, background);

        Assert.True(
            ratio >= minimum,
            $"Contraste de {foreground} sobre {background}: {ratio:F2}; mínimo: {minimum:F1}.");
    }
}
