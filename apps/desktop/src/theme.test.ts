import { describe, expect, it } from "vitest";
import { STATE_TONES, accent, contrast, surface, text, tone, toneFor } from "./theme";

// WCAG 2.2 AA. Everything the app renders in colour is normal-size text, so
// the 3.0 large-text allowance is not claimed anywhere.
const TEXT_MINIMUM = 4.5;
const NON_TEXT_MINIMUM = 3.0;

describe("text contrast", () => {
  it("primary text is legible on both surfaces", () => {
    expect(contrast(text.primary, surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    expect(contrast(text.primary, surface.raised)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
  });

  it("muted text is legible, not merely lighter", () => {
    // Rendered at 0.8rem — normal text, so it gets no large-text discount.
    expect(contrast(text.muted, surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    expect(contrast(text.muted, surface.raised)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
  });

  it("faint detail such as a timestamp is still readable", () => {
    // The event log renders these at 0.75rem monospace on both surfaces.
    expect(contrast(text.faint, surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    expect(contrast(text.faint, surface.raised)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
  });

  it("the accent carries legible text on top of it", () => {
    // The active tab is white on the accent; a mid-tone accent fails here.
    expect(contrast(accent.on, accent.base)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    expect(contrast(text.primary, accent.soft)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
  });

  it("error text is legible on the surfaces it appears on", () => {
    expect(contrast(text.danger, surface.page)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    expect(contrast(text.danger, tone.negative.bg)).toBeGreaterThanOrEqual(TEXT_MINIMUM);
  });
});

describe("status tones", () => {
  it("every tone is legible on its own tint", () => {
    for (const [name, colours] of Object.entries(tone)) {
      expect(
        contrast(colours.fg, colours.bg),
        `${name} foreground on its tint`,
      ).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    }
  });

  it("every tone is legible when a badge sits directly on the page", () => {
    for (const [name, colours] of Object.entries(tone)) {
      expect(
        contrast(colours.fg, surface.page),
        `${name} foreground on the page`,
      ).toBeGreaterThanOrEqual(TEXT_MINIMUM);
    }
  });

  it("tone borders are distinguishable from the surface they sit on", () => {
    for (const [name, colours] of Object.entries(tone)) {
      expect(
        contrast(colours.border, colours.bg),
        `${name} border against its own tint`,
      ).toBeGreaterThanOrEqual(1.2);
    }
  });

  it("keeps a non-colour cue available for every state", () => {
    // Colour is never the only signal: the badge always shows its label. This
    // guards the mapping, so a new state cannot appear with no tone at all.
    for (const state of Object.keys(STATE_TONES)) {
      expect(toneFor(state)).toBeTruthy();
    }
    expect(toneFor("SOMETHING_NEW")).toBe("neutral");
  });

  it("distinguishes success from failure by more than hue alone", () => {
    // Red/green confusion is the common case; their tints must differ in
    // luminance too, so a monochrome or colour-blind reading still separates them.
    expect(
      Math.abs(contrast(tone.positive.fg, surface.page) -
        contrast(tone.negative.fg, surface.page)),
    ).toBeGreaterThan(0.4);
  });
});

describe("focus indication", () => {
  it("the focus ring is visible against every surface", () => {
    const ring = "#1e40af";
    expect(contrast(ring, surface.page)).toBeGreaterThanOrEqual(NON_TEXT_MINIMUM);
    expect(contrast(ring, surface.raised)).toBeGreaterThanOrEqual(NON_TEXT_MINIMUM);
  });
});
