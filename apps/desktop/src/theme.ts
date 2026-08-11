/**
 * Semantic theme tokens.
 *
 * Components consume CSS custom properties so one rendered tree can switch
 * between light and dark without duplicating components or inline styles.
 * Literal palettes stay here as the source for contrast tests and audits.
 */

export type ThemeMode = "dark" | "light";

export type StatusTone = "positive" | "negative" | "waiting" | "active" | "neutral";

type ColourSet = {
  fg: string;
  bg: string;
  border: string;
};

export type ThemePalette = {
  surface: {
    page: string;
    card: string;
    border: string;
    raised: string;
    chrome: string;
    selected: string;
  };
  text: {
    primary: string;
    muted: string;
    faint: string;
    danger: string;
  };
  accent: {
    base: string;
    on: string;
    soft: string;
    softText: string;
  };
  focus: string;
  tone: Record<StatusTone, ColourSet>;
};

const darkPalette: ThemePalette = {
  surface: {
    page: "#0b0f14",
    card: "#141a22",
    border: "#283342",
    raised: "#1b2430",
    chrome: "#0f141b",
    selected: "#202a3a",
  },
  text: {
    primary: "#f3f6fa",
    muted: "#a7b0bd",
    faint: "#8692a2",
    danger: "#fca5a5",
  },
  accent: {
    base: "#6d28d9",
    on: "#ffffff",
    soft: "#2a2142",
    softText: "#c4b5fd",
  },
  focus: "#93c5fd",
  tone: {
    positive: { fg: "#86efac", bg: "#10251a", border: "#1f6f3d" },
    negative: { fg: "#fca5a5", bg: "#2b1518", border: "#7f1d1d" },
    waiting: { fg: "#fde68a", bg: "#2a2413", border: "#7c5a12" },
    active: { fg: "#93c5fd", bg: "#13233a", border: "#28548c" },
    neutral: { fg: "#cbd5e1", bg: "#1b2430", border: "#475569" },
  },
};

const lightPalette: ThemePalette = {
  surface: {
    page: "#f6f7fb",
    card: "#ffffff",
    border: "#d9dee8",
    raised: "#eef1f6",
    chrome: "#edf0f5",
    selected: "#e4e7f2",
  },
  text: {
    primary: "#1b2330",
    muted: "#475467",
    faint: "#5b6677",
    danger: "#b42318",
  },
  accent: {
    base: "#6d28d9",
    on: "#ffffff",
    soft: "#ede9fe",
    softText: "#5b21b6",
  },
  focus: "#5b21b6",
  tone: {
    positive: { fg: "#166534", bg: "#dcfce7", border: "#86efac" },
    negative: { fg: "#b42318", bg: "#fee4e2", border: "#fda29b" },
    waiting: { fg: "#854d0e", bg: "#fef3c7", border: "#facc15" },
    active: { fg: "#1d4ed8", bg: "#dbeafe", border: "#93c5fd" },
    neutral: { fg: "#475569", bg: "#eef2f7", border: "#94a3b8" },
  },
};

export const palette = {
  dark: darkPalette,
  light: lightPalette,
} as const satisfies Record<ThemeMode, ThemePalette>;

const cssToken = (name: string): string => `var(--atlas-${name})`;

/** Runtime tokens. CSS resolves these against the active root theme. */
export const surface = {
  page: cssToken("surface-page"),
  card: cssToken("surface-card"),
  border: cssToken("border"),
  raised: cssToken("surface-raised"),
  /** Chrome: the frame around the work, quieter than the work itself. */
  chrome: cssToken("surface-chrome"),
  /** A selected row in a list that stays selected across stages. */
  selected: cssToken("surface-selected"),
} as const;

/**
 * Spacing and sizes for a tool, not a page.
 *
 * A professional tool is read for hours and holds a lot at once, so its
 * rhythm is tighter than a document's. These are the only sizes; picking a
 * number inline is how a layout drifts.
 */
export const space = {
  hair: 2,
  tight: 4,
  snug: 8,
  base: 12,
  loose: 16,
  wide: 24,
} as const;

export const size = {
  header: 40,
  status: 28,
  sidebar: 240,
  inspector: 288,
  /** Below this the inspector folds away; the work matters more than detail. */
  inspectorBreakpoint: 1024,
} as const;

export const type = {
  ui: "0.75rem",
  small: "0.6875rem",
  tiny: "0.625rem",
  heading: "0.875rem",
} as const;

export const text = {
  primary: cssToken("text-primary"),
  /** Secondary text. Rendered at 0.8rem, so it is normal text for WCAG. */
  muted: cssToken("text-muted"),
  /** Timestamps and other de-emphasized detail. Still normal text. */
  faint: cssToken("text-faint"),
  danger: cssToken("danger"),
} as const;

/** Selection and the active tab. `on` is what sits on top of `base`. */
export const accent = {
  base: cssToken("accent"),
  on: cssToken("accent-on"),
  soft: cssToken("accent-soft"),
  softText: cssToken("accent-soft-text"),
} as const;

/** Foreground for each tone. Backgrounds are a tint of the same hue. */
export const tone: Record<StatusTone, ColourSet> = {
  positive: { fg: cssToken("tone-positive-fg"), bg: cssToken("tone-positive-bg"), border: cssToken("tone-positive-border") },
  negative: { fg: cssToken("tone-negative-fg"), bg: cssToken("tone-negative-bg"), border: cssToken("tone-negative-border") },
  waiting: { fg: cssToken("tone-waiting-fg"), bg: cssToken("tone-waiting-bg"), border: cssToken("tone-waiting-border") },
  active: { fg: cssToken("tone-active-fg"), bg: cssToken("tone-active-bg"), border: cssToken("tone-active-border") },
  neutral: { fg: cssToken("tone-neutral-fg"), bg: cssToken("tone-neutral-bg"), border: cssToken("tone-neutral-border") },
};

export const THEME_STORAGE_KEY = "atlas-flow.theme";

export function isThemeMode(value: string | null): value is ThemeMode {
  return value === "dark" || value === "light";
}

export function readStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(stored) ? stored : "dark";
  } catch {
    return "dark";
  }
}

/** Which tone a state or verdict is shown in. */
export const STATE_TONES: Record<string, StatusTone> = {
  PASSED: "positive",
  SUCCEEDED: "positive",
  COMPLETED: "positive",
  DONE: "positive",
  REACHABLE: "positive",
  FAILED: "negative",
  BLOCKED: "negative",
  STOPPED: "negative",
  DEGRADED: "negative",
  PENDING: "waiting",
  READY: "waiting",
  RUNNING: "active",
  ACTIVE: "active",
  VERIFYING: "active",
  REVIEWING: "active",
  PLANNED: "neutral",
  UNROUTABLE: "neutral",
};

export function toneFor(value: string): StatusTone {
  return STATE_TONES[value] ?? "neutral";
}

/** Relative luminance per WCAG 2.2. */
export function luminance(hex: string): number {
  const channel = (value: number) => {
    const v = value / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  const int = parseInt(hex.replace("#", ""), 16);
  const r = channel((int >> 16) & 0xff);
  const g = channel((int >> 8) & 0xff);
  const b = channel(int & 0xff);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(foreground: string, background: string): number {
  const a = luminance(foreground);
  const b = luminance(background);
  const [light, dark] = a > b ? [a, b] : [b, a];
  return (light + 0.05) / (dark + 0.05);
}
