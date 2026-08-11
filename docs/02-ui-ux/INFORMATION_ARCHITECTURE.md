# Information Architecture

Atlas Flow is a workspace, not a set of pages. See
[ADR-013](../07-decisions/ADR-013-WORKSPACE-SHELL.md) for why.

## The task the interface has to serve

A person opens Atlas Flow on a project and wants to answer four questions,
usually in this order and often several times a day:

1. **What is this project trying to do?** → Goals, and where each one stands.
2. **What is happening right now?** → the run in flight, and whether it is going
   well.
3. **What does it need from me?** → a decision, a permission, a review.
4. **Can I trust that it is done?** → evidence, per gate, traceable to a command.

Every region below exists to answer one of those without navigating away from
the others.

## Regions

```
┌───────────────────────────────────────────────────────────┐
│ ▣ project ▾            Discuss  Plan  Build  Review  Docs │  header
├────────────┬─────────────────────────────┬────────────────┤
│  P00 ✓     │                             │  Gates         │
│  P01 ✓     │      the active stage       │  Evidence      │  sidebar
│  P08 ●     │      (chat / plan / run)    │  Routing       │  centre
│  P09 ○     │                             │                │  inspector
├────────────┴─────────────────────────────┴────────────────┤
│ ● run-4f2a · P08-G01 · 3/5 tasks · mimo-v2.5     [Stop]   │  status
└───────────────────────────────────────────────────────────┘
```

**Header** — which project is open, and which stage of the pipeline is showing.
The project switcher opens a folder or returns to a recent one; opening a
project restarts the backend against that root.

**Sidebar** — the Goals this project declares, grouped by phase, each with its
state. This is the context, and it does not go away when you change stage.
Selecting a Goal drives the inspector.

**Centre** — one stage at a time, at full width. Stages are the pipeline a Goal
moves through, not unrelated screens.

**Inspector** — everything known about the selected Goal or run: gate verdicts,
attached evidence, the model each role routed to and why. Properties live here
and nowhere else.

**Status bar** — the run in flight, and the engine. Both are always visible;
the run always offers to stop. A run executing with no sign of it in the window
was the single worst thing about the previous design, and the engine is the
first question behind every empty list and failed request in the window, so
neither is something you should have to navigate to find.

## Stages

| Stage | Answers | Ends when |
| --- | --- | --- |
| Discuss | What should we build, and what did we decide? | Decisions accepted; ADRs written |
| Plan | What will this Goal take? | A task DAG exists |
| Build | What is happening, and what did each agent do? | Every task is terminal |
| Review | Can this Goal be called done? | Every required gate has passing evidence |
| Docs | What does this project already say? | — (reference, not a stage) |

The pipeline is left to right, and the header shows it in that order. A Goal
does not have to travel it linearly, but the order is the default reading, and
the previous design communicated no order at all.

## Persistent affordances

- **Project switcher** — header, always.
- **Run in flight** — status bar, always, with a stop button.
- **Engine** — status bar, always, with its address and a stop control. Opening
  a project starts it; nobody should have to press Start to make a working
  application stop looking broken.
- **Selected Goal** — sidebar selection drives the inspector, across stages.
- **Keyboard** — every stage reachable by arrow keys from the stage list; every
  critical flow (open project, run a Goal, cancel, accept a decision) reachable
  without a pointer.

## What is deliberately absent

- **Docking and rearrangeable panels.** A learnable layout beats a configurable
  one until the layout is learned.
- **An icon-only toolbar.** Icons are not the only explanation for any action
  here; anything not universally understood carries a label.
- **Modes without a visible marker.** If the interface behaves differently, the
  window says so.
