# Quality Strategy

Layers: static checks, unit, component, integration, protocol contract, desktop E2E, fault injection, security, performance and real-project dogfood.

Critical deterministic invariants require deterministic fixtures or independent review; model-generated tests alone do not establish independent correctness.

## What each layer can and cannot catch

Three defects shipped past twelve passing gates, and a fourth past the
accessibility suite. None of them was a gap in coverage of the kind more tests
of the same shape would close — each lived in a place a whole layer is blind to.

| Layer | Catches | Blind to |
| --- | --- | --- |
| Unit and integration tests | Logic, contracts, state machines | Anything about the process the code runs in |
| `cargo test` on the shell | Argv parsing, project-root resolution, process liveness, bundle-environment filtering | Whether the window renders or the webview behaves |
| jsdom + axe | Markup, ARIA, focus order as jsdom models it | Real webview focus behaviour — the arrow-key defect passes here either way |
| `package_smoke.sh` | The bundle exists and contains the right files | Whether the application works |
| `e2e_packaged.sh` | The pieces wired together, in a window, from a real bundle | Anything slower or rarer than one walk-through |

The lesson worth keeping: a gate that inspects an artefact says nothing about
the product. `package_smoke.sh` reported PASS before and after every one of
those defects, and it was right both times — it never claimed the app worked.

## The packaged smoke test is not a gate

`scripts/e2e_packaged.sh` needs a display, a window manager, `xdotool` and a
built bundle. It is deliberately outside `run_gates.sh`: a check that silently
skips when its prerequisites are missing is a claim without evidence, and one
that fails on a fresh checkout for lacking a bundle is noise. It says which
prerequisite is missing and exits non-zero when asked to run without one.

Writing it found two more things worth recording, both about the difficulty of
observing a running application rather than about Atlas Flow:

- `xdotool key --window` sends an XSendEvent, which WebKit ignores. The first
  version pressed keys into a void and reported the silence as a broken
  backend.
- Taking the first window named "Atlas Flow" found a leftover instance from an
  earlier session, so the test read someone else's configuration off the screen
  and blamed the app for ignoring its own. It now waits for a window that did
  not exist before the launch.
