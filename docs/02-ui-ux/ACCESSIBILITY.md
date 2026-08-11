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

## Not yet done

- **No rendered-DOM audit.** The checks above are on tokens and pure functions;
  there is no jsdom or axe-core pass over the actual component tree, so ARIA
  relationships and focus order in the rendered output are verified by reading,
  not by test.
- **No screen-reader walkthrough** has been performed.
- **The Plan DAG has no textual alternative yet** beyond the task list it is
  derived from.
