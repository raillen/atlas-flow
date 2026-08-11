# Accessibility

Target: WCAG 2.2 AA.

## What is enforced automatically

Colour is the part of accessibility that quietly rots, so the palette is data
rather than scattered literals. `apps/desktop/src/theme.ts` holds every token,
and `theme.test.ts` computes real contrast ratios for every pair the screens
render:

| Check | Threshold |
| --- | --- |
| Primary, muted and faint text on both surfaces | 4.5:1 |
| Every status tone on its own tint, and on the page | 4.5:1 |
| Text on the accent (the active tab) | 4.5:1 |
| Focus ring against both surfaces | 3:1 |
| Success and failure separated in luminance, not only hue | — |

Nothing in the app claims the 3:1 large-text allowance: every coloured element
is normal-size text.

Writing those checks found two real failures, now fixed: amber `PENDING` and
green `SUCCEEDED` badges were below 4.5:1 on white, and the success and failure
colours had nearly identical luminance — indistinguishable in grayscale and for
the most common colour-vision deficiencies.

## Keyboard and focus

- Primary navigation implements the WAI-ARIA tabs pattern: arrow keys move
  between tabs, Home and End jump to the ends, and only the active tab is in the
  tab order. `App.test.ts` covers the key model.
- `:focus-visible` draws a 2px ring in `index.css`. The rule never removes an
  outline without replacing it — keyboard navigation is unusable the moment
  focus becomes invisible.
- `prefers-contrast: more` switches the ring to black.

## Motion and text size

- `prefers-reduced-motion: reduce` collapses animation and transition durations
  and disables smooth scrolling.
- All sizing is in `rem` from a `100%` root, so the OS text-size setting scales
  the interface.

## Non-colour cues

Every status is a labelled badge: the word is always present, so a grayscale
screenshot or a screen reader loses nothing. `toneFor` falls back to a neutral
tone for an unknown state rather than rendering it invisibly.

Live regions: the Build screen marks its event log and agent activity list
`aria-live="polite"` while a run is active, and `"off"` once it is not, so a
finished run does not keep announcing itself.

## Rendered-DOM audit

`a11y.test.tsx` renders the shell and every screen in jsdom and runs axe-core
over the result, failing on any serious or critical violation. Contrast is
excluded there because the token tests cover it properly; jsdom cannot resolve
computed colours anyway, and a check that silently passes is worse than none.

It also asserts what axe cannot: that exactly one tab is in the tab order, that
the tab panel is labelled by its tab, that a live region exists while a run is
active, and that every button has an accessible name.

One test audits the audit — it renders a known violation and expects it to be
found. Without that, a misconfigured axe would make every other check pass by
looking at nothing.

## Not yet done

- **No screen-reader walkthrough.** Deferred by owner decision on 2026-08-11,
  not declared unnecessary: automated rules catch structure, not whether the
  result is comprehensible when read aloud. It stays recorded as outstanding on
  P09.
- **The Plan DAG has no textual alternative yet** beyond the task list it is
  derived from.
