import { describe, expect, it } from "vitest";
import {
  STATE_TONES,
  contrast,
  palette,
  size,
  space,
  toneFor,
  type ThemeMode,
  type ThemePalette,
} from "./theme";

// WCAG 2.2 AA. Everything the app renders in colour is normal-size text, so
// the 3.0 large-text allowance is not claimed anywhere.
const TEXT_MINIMUM = 4.5;
const NON_TEXT_MINIMUM = 3.0;
const themes: Array<[ThemeMode, ThemePalette]> = [
  ["dark", palette.dark],
  ["light", palette.light],
];

for (const [mode, current] of themes) {
  describe(`${mode} theme contrast`, () => {
    it("primary text is legible on both surfaces", () => {
      expect(contrast(current.text.primary, current.surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      expect(contrast(current.text.primary, current.surface.raised)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    });

    it("muted text is legible, not merely lighter", () => {
      expect(contrast(current.text.muted, current.surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      expect(contrast(current.text.muted, current.surface.raised)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    });

    it("faint detail such as a timestamp is still readable", () => {
      expect(contrast(current.text.faint, current.surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      expect(contrast(current.text.faint, current.surface.raised)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    });

    it("the accent carries legible text on top of it", () => {
      expect(contrast(current.accent.on, current.accent.base)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      expect(contrast(current.text.primary, current.accent.soft)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    });

    it("error text is legible on the surfaces it appears on", () => {
      expect(contrast(current.text.danger, current.surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      expect(contrast(current.text.danger, current.tone.negative.bg)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    });

    it("every tone is legible on its own tint", () => {
      for (const [name, colours] of Object.entries(current.tone)) {
        expect(
          contrast(colours.fg, colours.bg),
          `${name} foreground on its tint`,
        ).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      }
    });

    it("every tone is legible when a badge sits directly on the page", () => {
      for (const [name, colours] of Object.entries(current.tone)) {
        expect(
          contrast(colours.fg, current.surface.page),
          `${name} foreground on the page`,
        ).toBeGreaterThanOrEqual(TEXT_MINIMUM);
      }
    });

    it("tone borders are distinguishable from the surface they sit on", () => {
      for (const [name, colours] of Object.entries(current.tone)) {
        expect(
          contrast(colours.border, colours.bg),
          `${name} border against its own tint`,
        ).toBeGreaterThanOrEqual(1.2);
      }
    });

    it("distinguishes success from failure by more than hue alone", () => {
      expect(
        Math.abs(contrast(current.tone.positive.fg, current.surface.page) -
          contrast(current.tone.negative.fg, current.surface.page)),
      ).toBeGreaterThan(0.4);
    });

    it("keeps the focus ring visible against every surface", () => {
      expect(contrast(current.focus, current.surface.page)).toBeGreaterThanOrEqual(NON_TEXT_MINIMUM);
      expect(contrast(current.focus, current.surface.raised)).toBeGreaterThanOrEqual(NON_TEXT_MINIMUM);
    });
  });
}

describe("status mapping", () => {
  it("keeps a non-colour cue available for every state", () => {
    // Colour is never the only signal: the badge always shows its label.
    for (const state of Object.keys(STATE_TONES)) {
      expect(toneFor(state)).toBeTruthy();
    }
    expect(toneFor("SOMETHING_NEW")).toBe("neutral");
  });
});

describe("density tokens", () => {
  it("has one scale, in ascending order", () => {
    const values = Object.values(space);
    expect([...values].sort((a, b) => a - b)).toEqual(values);
  });

  it("leaves room for both panels on a normal window", () => {
    const smallest = 1280;
    const centre = smallest - size.sidebar - size.inspector;
    expect(centre).toBeGreaterThan(600);
  });

  it("folds the inspector before the centre gets narrower than the sidebar", () => {
    const centreAtBreakpoint = size.inspectorBreakpoint - size.sidebar - size.inspector;
    expect(centreAtBreakpoint).toBeGreaterThan(size.sidebar);
  });

  it("keeps both themes distinguishable and readable", () => {
    for (const current of Object.values(palette)) {
      expect(contrast(current.surface.chrome, current.surface.card)).toBeGreaterThan(1.02);
      expect(contrast(current.text.primary, current.surface.chrome)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(current.text.primary, current.surface.selected)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(current.text.muted, current.surface.selected)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
