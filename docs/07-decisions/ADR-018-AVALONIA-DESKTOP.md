# ADR-018 — Avalonia, and the end of the webview

**Status:** Accepted · 2026-08-11
**Supersedes:** [ADR-004](ADR-004-TAURI-REACT.md)
**Related:** [ADR-017](ADR-017-DOTNET-RUNTIME.md), [ADR-013](ADR-013-WORKSPACE-SHELL.md)
**Reopens:** Windows support, a recorded non-goal on P06, P09 and P10

## Context

The webview was the heaviest part of the application and the part the owner most
wanted gone. A Tauri window plus a CPython process plus a Chromium-family
renderer is roughly 250 MB resident to display an orchestrator's task list.

It also could not stand alone. Removing Python (ADR-017) without removing the
webview would have left a React UI with nothing local to talk to except an HTTP
server invented purely to preserve the boundary. The two decisions had to be
made together.

## What this gives up

This is recorded first, because it is the real cost and it is easy to leave out.

The React build met WCAG 2.2 AA and enforced it: `a11y.test.tsx` ran `axe-core`
over rendered DOM on every screen, `theme.test.ts` computed real contrast ratios
for every token pair, and the workspace hand-implemented the WAI-ARIA tabs
pattern. That programme found and fixed two genuine defects — status badges
below 4.5:1, and success and failure at indistinguishable luminance.

**The project got that because it was a browser.** ARIA, screen-reader
translation, focus management, text zoom and high-contrast mode were the
platform's, not the project's.

No native toolkit in any language reproduces `axe-core`. Leaving the webview
means the automated accessibility audit ends. See
[ACCESSIBILITY.md](../02-ui-ux/ACCESSIBILITY.md) for what replaces each piece
and what has no replacement.

## Options considered

The evaluation ran twice, because the platform scope changed mid-decision.

**First pass, Linux only.** GTK4 with libadwaita was the clear answer: full
AT-SPI so Orca works, native theming, system font scaling, and a small binary
because GTK is already installed on the target systems.

**Then Windows re-entered scope**, and GTK4 lost decisively — bundling GTK on
Windows costs about 100 MB, the result is visibly non-native, and GTK's bridge
to UI Automation is incomplete. Losing the accessibility surface on the new
platform defeats the reason GTK4 had been chosen.

Re-evaluated cross-platform:

| Option | Why not |
| --- | --- |
| **Slint** | Lightest true cross-platform native (~20 MB) with real platform accessibility. Rejected on component ecosystem: nearly every control would be built by hand, and the license model needs review before investment. Remains the alternative if binary size becomes a hard constraint. |
| **Iced** | Good Rust ergonomics, and `pane_grid` maps directly onto the workspace docking in ADR-013. Rejected: accessibility is an acknowledged gap. It draws its own controls and exposes no accessibility tree, so a screen reader sees nothing. |
| **GPUI** | Genuinely tempting — a Tailwind-shaped styling API that would have translated the existing UI almost directly, and proven fast in Zed. Rejected on three counts: it ships primitives rather than components, the API churns and is thinly documented, and it has essentially no accessibility. For a project with a WCAG target that last point is disqualifying. |
| **egui** | Simplest to write. Partial AccessKit support, weak text input and IME, non-native appearance. |
| **Compose Multiplatform** | Partial desktop accessibility and a bundled JVM, without compensating anywhere. |
| **Qt** | The best accessibility of any toolkit. Rejected on license model and roughly 50 MB. |

## Decision

**Avalonia 12**, targeting Windows and Linux on x86_64.

It is the only candidate that satisfies all four constraints at once: no
webview, no separate runtime, cross-platform, and a real accessibility surface
on both platforms — UI Automation on Windows, AT-SPI on Linux. These are the
same interfaces the browser was translating ARIA into.

It is not the lightest, and that was the expected cost. The first measurements
narrow the gap more than predicted: the published Linux binary is 20 MB, not the
40 MB estimated here before anything compiled. Resident memory went the other
way — 114 MB for an empty window against an 80 MB estimate.

Slint still wins on bytes. Avalonia wins on the other three axes, and shares a
runtime with [ADR-017](ADR-017-DOTNET-RUNTIME.md), which the Rust options would
have split.

Supporting choices:

- **Compiled XAML bindings repository-wide.** A reflection binding to a missing
  property fails silently and renders an empty control; a compiled binding fails
  the build. For a UI with an accessibility target, that is how a missing label
  gets caught.
- **`RequestedThemeVariant="Default"`.** Follow the OS light/dark setting.
  Pinning it overrides a user who chose dark mode for a reason.
- **`Avalonia.Headless` for tests**, so UI tests run in CI without a display
  server.

## Consequences

**Windows is back in scope**, and it was a recorded non-goal on P06, P09 and
P10. Those Goals inherit: a second platform to build, sign, package as MSI and
test. Nothing on Windows has been tested at all.

**6,266 lines of React are discarded.** Views, view models and theme are written
fresh. Only the palette tokens and the contrast tests port more or less
directly, since relative luminance is arithmetic.

**The accessibility programme is rebuilt, not migrated.** Contrast checks port.
The `axe-core` audit does not. Live regions, reduced motion and per-platform
text scaling are open work listed in
[ACCESSIBILITY.md](../02-ui-ux/ACCESSIBILITY.md), and none of it is optional
before a 1.0 that claims AA.

**ADR-013 survives intact.** The workspace shell was an information-architecture
decision, not a React one. `TabControl` replaces the hand-written tabs pattern
and brings arrow-key navigation, Home/End and roving focus with it — which also
retires the focus bug that pattern produced, where moving focus synchronously
inside the key handler made the first arrow key work and every one after it do
nothing.

**Reversal is expensive but bounded.** Slint is the fallback if size becomes
binding; that swaps the UI layer and keeps every other project. Returning to a
webview means reversing ADR-017 as well, because the reason to have one was to
host a UI that talked to a separate process.
