# AG-UI Integration

AG-UI is frontend ↔ Atlas Flow runtime event contract.

Uses: streaming discussion, shared Project Draft, approval requests, Goal/Run lifecycle, task patches and cancellation/resume.

Frontend never consumes raw provider streams. Backend normalizes to domain events/AG-UI projections.

Namespaced custom events: `atlas.goal.*`, `atlas.task.*`, `atlas.runner.*`, `atlas.evidence.*`, `atlas.routing.*`.
