/**
 * Colour tokens, in one place so they can be checked rather than trusted.
 *
 * Every pair a screen actually renders is asserted against WCAG 2.2 AA in
 * theme.test.ts. Status colours are the risky ones: a badge is small text on a
 * tint of its own hue, which is exactly the combination that looks fine to the
 * person who picked it and fails for everyone else.
 */

export const surface = {
  page: "#ffffff",
  card: "#ffffff",
  border: "#e2e8f0",
  raised: "#f8fafc",
} as const;

export const text = {
  primary: "#0f172a",
  /** Secondary text. Rendered at 0.8rem, so it is normal text for WCAG. */
  muted: "#57606f",
  /** Timestamps and other de-emphasized detail. Still normal text. */
  faint: "#64748b",
  danger: "#b91c1c",
} as const;

/** Selection and the active tab. `on` is what sits on top of `base`. */
export const accent = {
  base: "#4338ca",
  on: "#ffffff",
  soft: "#eef2ff",
} as const;

export type StatusTone = "positive" | "negative" | "waiting" | "active" | "neutral";

/** Foreground for each tone. Backgrounds are a tint of the same hue. */
export const tone: Record<StatusTone, { fg: string; bg: string; border: string }> = {
  // Deliberately much darker than `negative`: red and green of similar
  // lightness are the pair that disappears in grayscale and for the most
  // common colour-vision deficiencies.
  positive: { fg: "#14532d", bg: "#ecfdf5", border: "#a7f3d0" },
  negative: { fg: "#b91c1c", bg: "#fef2f2", border: "#fecaca" },
  waiting: { fg: "#854d0e", bg: "#fefce8", border: "#fde68a" },
  active: { fg: "#1e40af", bg: "#eff6ff", border: "#bfdbfe" },
  neutral: { fg: "#334155", bg: "#f1f5f9", border: "#cbd5e1" },
};

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
