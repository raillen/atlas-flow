# Accessibility

Target: WCAG 2.2 AA, as far as WCAG applies to a native application.

That qualifier is new and it is not a softening. WCAG is written for the web.
A native Avalonia window has no DOM, no ARIA attributes and no `axe-core`. The
success criteria about contrast, focus visibility, text scaling and non-colour
cues still apply and are still enforced. The criteria expressed as markup rules
have to be met through UI Automation instead, and the automated audit that used
to verify them does not survive the port.

## What the port cost, stated plainly

The React build had 343 lines of `a11y.test.tsx` running `axe-core` over
rendered DOM, failing on any serious or critical violation. It caught real
defects. **It has no direct replacement.**

| Was | Now |
| --- | --- |
| `axe-core` over rendered DOM | Automation-peer assertions in headless tests, hand-written per rule |
| ARIA tabs pattern in markup | `TabControl` plus `AutomationProperties`, verified through peers |
| `aria-live="polite"` | UI Automation notification events — **partial, see gaps** |
| `prefers-reduced-motion` | Platform query, **not yet implemented** |
| Browser text zoom | OS scale factor via Avalonia; **needs verification per platform** |

What Avalonia gives back is a real accessibility surface rather than a
simulated one: UI Automation on Windows and AT-SPI on Linux are the interfaces
Narrator and Orca actually consume, and they are the same interfaces the browser
was translating ARIA into. The tree is real. The audit tooling for it is not.

## What is enforced automatically

Colour is the part of accessibility that quietly rots, so the palette is data
rather than scattered literals. `src/AtlasFlow.Desktop/Theme/Palette.cs` holds
every token, and `AtlasFlow.Desktop.Tests` computes real contrast ratios for
every pair the views render:

| Check | Threshold |
| --- | --- |
| Primary, muted and faint text on both surfaces | 4.5:1 |
| Every status tone on its own tint, and on the page | 4.5:1 |
| Text on the accent (the active tab) | 4.5:1 |
| Focus ring against both surfaces | 3:1 |
| Success and failure separated in luminance, not only hue | — |

Nothing in the app claims the 3:1 large-text allowance: every coloured element
is normal-size text.

These checks port directly. Relative luminance is arithmetic over sRGB and does
not care what language computes it. The two failures the original suite found —
amber `PENDING` and green `SUCCEEDED` below 4.5:1 on white, and success and
failure at near-identical luminance — must stay fixed, and the tests that prove
it must be ported before the palette is trusted again.

## Keyboard and focus

- Primary workspace navigation uses `TabControl`, which implements arrow-key
  movement, Home and End, and roving focus natively. The React build had to
  hand-write the WAI-ARIA tabs pattern; the platform control owns it here.
- The bug that pattern produced is worth keeping in view. Focus was moved
  synchronously inside the key handler, onto a tab whose `tabIndex` was still
  `-1` from the previous render: the first arrow key worked and every one after
  it did nothing. Arrow navigation that moves once is worse than none, because
  it looks supported. If focus is ever moved manually here, it moves after the
  layout pass, and a headless test must press the key more than once.
- Avalonia's `:focus-visible` pseudo-class draws the ring. The style never
  removes an adornment without replacing it — keyboard navigation is unusable
  the moment focus becomes invisible.
- Disabled stages stay visibly labelled with their reason and remain reachable
  by a screen reader. A control that vanishes when unavailable cannot explain
  why it is unavailable.

## Non-colour cues

Every status is a labelled badge: the word is always present, so a grayscale
screenshot or a screen reader loses nothing. The tone lookup falls back to a
neutral tone for an unknown state rather than rendering it invisibly.

## Automation properties

Every interactive control carries an `AutomationProperties.Name`. Compiled
bindings are on repository-wide, so a binding to a property that does not exist
fails the build rather than rendering an unlabelled control — which is the
Avalonia-specific reason that setting is not merely a preference.

Headless tests assert through automation peers what `axe-core` used to assert
through the DOM: that exactly one tab is selected, that the tab panel is
associated with its tab, and that every button has an accessible name.

## Verification

`Avalonia.Headless` runs the real control tree without a display server, so
these tests run in CI. That covers structure.

It does not cover whether Narrator or Orca produce something comprehensible.
Nothing automated does.

## Not yet done

Carried forward from the previous stack, still outstanding:

- **No screen-reader walkthrough.** Deferred by owner decision on 2026-08-11,
  not declared unnecessary: automated rules catch structure, not whether the
  result is comprehensible when read aloud. It stays recorded as outstanding on
  P09, and the platform change does not close it.

New with this stack, and none of it is optional before a 1.0 that claims AA:

- **Live-region equivalent.** The Build screen announced run events through
  `aria-live="polite"`. UI Automation notification events are the counterpart;
  Avalonia's support for raising them needs to be established, and if it is
  insufficient the announcement strategy has to change rather than be dropped.
- **Reduced motion.** `prefers-reduced-motion` has no cross-platform Avalonia
  equivalent. Reading the OS setting is per-platform work that has not started.
- **Text scaling verified per platform.** Sizing follows the OS scale factor in
  principle. It has been asserted, not measured, on either platform.
- **Windows is new.** Every claim here has to hold under Narrator and UIA, not
  only under Orca and AT-SPI. Nothing on Windows has been tested at all.
