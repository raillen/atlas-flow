using System.Globalization;

namespace AtlasFlow.Desktop.Theme;

public sealed record AtlasPalette(
    string Background,
    string Surface,
    string ElevatedSurface,
    string Border,
    string PrimaryText,
    string SecondaryText,
    string MutedText,
    string Accent,
    string OnAccent,
    string Focus,
    string Success,
    string Warning,
    string Danger,
    string Info);

/// <summary>Valores auditáveis das paletas consumidas pelo shell.</summary>
public static class Palette
{
    public static AtlasPalette Dark { get; } = new(
        Background: "#070708",
        Surface: "#111114",
        ElevatedSurface: "#18181C",
        Border: "#2A2A31",
        PrimaryText: "#F7F7F8",
        SecondaryText: "#B4B4BA",
        MutedText: "#92929A",
        Accent: "#65D6A7",
        OnAccent: "#07110D",
        Focus: "#75E1B4",
        Success: "#65D6A7",
        Warning: "#E7B85A",
        Danger: "#F08088",
        Info: "#7BB4F0");

    public static AtlasPalette Light { get; } = new(
        Background: "#F4F5F2",
        Surface: "#FFFFFF",
        ElevatedSurface: "#E9EDE8",
        Border: "#C9CFC7",
        PrimaryText: "#171A18",
        SecondaryText: "#3F4742",
        MutedText: "#59635D",
        Accent: "#176B50",
        OnAccent: "#FFFFFF",
        Focus: "#176B50",
        Success: "#176B50",
        Warning: "#76540C",
        Danger: "#A92F3A",
        Info: "#245F9E");

    public static double ContrastRatio(string foreground, string background)
    {
        double foregroundLuminance = RelativeLuminance(foreground);
        double backgroundLuminance = RelativeLuminance(background);
        double lighter = Math.Max(foregroundLuminance, backgroundLuminance);
        double darker = Math.Min(foregroundLuminance, backgroundLuminance);
        return (lighter + 0.05) / (darker + 0.05);
    }

    private static double RelativeLuminance(string hexadecimal)
    {
        if (hexadecimal.Length != 7 || !hexadecimal.StartsWith('#'))
        {
            throw new ArgumentException("A cor deve usar o formato hexadecimal #RRGGBB.", nameof(hexadecimal));
        }

        int value = int.Parse(
            hexadecimal.AsSpan(1),
            NumberStyles.HexNumber,
            CultureInfo.InvariantCulture);

        double red = LinearChannel((value >> 16) & 0xff);
        double green = LinearChannel((value >> 8) & 0xff);
        double blue = LinearChannel(value & 0xff);
        return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue);
    }

    private static double LinearChannel(int channel)
    {
        double normalized = channel / 255d;
        return normalized <= 0.04045
            ? normalized / 12.92
            : Math.Pow((normalized + 0.055) / 1.055, 2.4);
    }
}
