# ADR-013 — A workspace shell, not five pages

**Status:** Accepted · 2026-08-11
**Amended:** 2026-08-11 by [ADR-018](ADR-018-AVALONIA-DESKTOP.md). The
information architecture decided here stands unchanged and was never a React
decision. The implementation details below that name Tauri, the webview bridge
or a Content-Security-Policy describe the superseded stack; they are kept
because each records a defect the port can reintroduce in a new form.
**Supersedes:** nothing. Implements what `INFORMATION_ARCHITECTURE.md` already
specified and the code never built.

## Context

The desktop client was five tabs, each a flat list of cards. Every complaint
about it is the same complaint from a different angle:

- **It does not look like an orchestrator.** An orchestrator's job is to hold
  work in flight. The interface showed no work in flight — you had to navigate
  to Build and remember which run you started.
- **The workflow is not comprehensible.** Discuss → Plan → Build → Review is a
  pipeline, and five equal tabs say nothing about sequence. Nothing told you
  where a Goal was in it, or what to do next.
- **The chat is not a chat.** It was a list of echoed strings with an input
  under it, and until today it wrote to nothing.
- **You cannot open a project.** The project came from an environment variable
  read once at startup, which is not a way to use a desktop application.

The canonical IA document already called for "project switcher, current
Goal/run, command/search palette" as *persistent* elements. That was never
implemented. This ADR is not a new direction; it is the direction, built.

## Decision

### One window, one project

Opening a folder stops the backend, points it at the new root, and starts it
again. Each project keeps its own `.atlas-flow/state.db`, as ADR-010 already
requires, and nothing has to be migrated or scoped.

The alternative — a multi-project backend — was rejected. It would put a
project id in every endpoint and turn every piece of `app.state` into a
registry, for a benefit (instant switching) that an IDE-shaped tool does not
need. Restarting costs about three seconds and buys total isolation.

### Sidebar, centre, inspector, status bar

| Region | Holds | Why it is there |
| --- | --- | --- |
| Header | Project switcher, stage navigation | Where am I, and what project is this |
| Sidebar | Goals, grouped by phase, with state | The context, always visible |
| Centre | The active work: chat, plan, run | One thing at a time, at full width |
| Inspector | Detail of what is selected: gates, evidence, routing | Detail on demand, in one place |
| Status bar | The run in flight, with a stop button | Work in flight is never hidden |

The gate this satisfies is "the current context is always visible". The
previous design failed it: a run could be executing and the window would show
no sign of it.

Properties live in the inspector and nowhere else. Scattering them is the
antipattern that makes dense tools unlearnable.

### The chat commands, and says what it did

The chat accepts commands (`run P08-G01`, `cancel`, `evidence P08-G01`) and
executes them against the existing API, answering with clickable artefacts.
Anything that is not a command is a message, and messages go to the Decision
Ledger exactly as before.

Commands are **parsed deterministically in the client**, not sent to a model.
An orchestrator whose control surface guesses is an orchestrator you cannot
trust: "cancel" must cancel, every time, with no inference in between.
Unrecognised input is a message, never a guessed action, and the chat says
which commands it knows.

Free-form natural language driving the orchestrator is a later question, and a
different one — it needs a model in the loop and a confirmation step before
anything destructive.

## Consequences

- The five modes stop being pages and become **stages** in a visible pipeline.
  They remain in the URL of the mental model — Discuss, Plan, Build, Review —
  but as places work moves through, not as unrelated screens.
- The Project tab dissolves: the project switcher goes to the header, the
  backend controls go to settings, the documentation browser becomes a stage.
- The desktop shell grows a native folder dialog and a recents list, so
  `ATLAS_FLOW_PROJECT_ROOT` becomes the override it was meant to be rather than
  the only way in.
- Anything that could only be reached by remembering a run id becomes
  reachable from the status bar.

## Decided while building it

Three things were settled by running the packaged application rather than by
design, and they are recorded here because each one hid behind a green gate.

**The engine belongs in the status bar, and opening a project starts it.**
Backend controls were going to move to settings. They went to the status bar
instead: whether the engine is running is the first question behind every
empty list and failed request in the window, and it was the one fact you had
to go looking for. Opening a project also starts its engine — the old shell
opened onto empty lists until you found a Start button in a tab, which made a
working application look broken on first launch.

**The backend address is resolved at runtime, from the shell.** It was baked
in at build time, so a packaged window could only ever talk to a backend on
one port while `ATLAS_FLOW_API` pretended to be configurable. The shell is
asked on the first request, not while the module loads: the Tauri bridge is
not on `globalThis` yet at module evaluation, and asking then answers null.

**The Content-Security-Policy allows loopback on any port.** It pinned
`connect-src` to `:8000`, which is the same mistake one layer lower, and a
worse one to diagnose: WebKit refuses the request before a packet leaves the
machine, so the backend's log stays empty, a listener on the wrong port sees
nothing, and the window reports "Could not reach the backend" beside a status
bar reporting a healthy engine. Loopback with any port is the rule; a remote
host is never allowed.

Every one of these shipped through a suite that was passing. The end-to-end
test now asserts that *the window* fetched Goals, by reading the backend's
access log — every earlier check went through urllib, which no browser policy
applies to, so the product could be completely broken with every gate green.

## What this does not decide

Docking or rearrangeable panels. "Any panel can become anything" is an
antipattern for exactly this kind of tool: it trades a learnable layout for a
configurable one, and the second is only better once the first is understood.
