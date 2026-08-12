# Project Atlas Integration

Atlas Flow consumes Project Atlas as protocol/dependency, not copied semantics.

## On open

1. Accept any real project directory outside the application bundle.
2. Inspect framework, version, Git and required manifests without executing
   project code.
3. Classify the project as `atlas-ready`, `atlas-needs-adaptation`,
   `atlas-incompatible` or `external`.
4. Show capabilities and a concrete recommendation.
5. Keep exploration and Discuss available; keep Plan/Run/Review blocked unless
   the project is Atlas ready (and Git is present for Run).

The strict loader remains the authority for execution. An external project never
receives a second Goal format or silently degraded execution semantics.

## Adaptation

The adaptation flow is `preview → explicit authorization → apply → re-inspect`.
It creates only new scaffold files, never overwrites existing paths, executes no
project commands, and never invents or completes Goals. Conflicts and
limitations remain visible for manual resolution.

## Canonical writes

Canonical writes go through validated Project Atlas services/commands preserving
authority and Goal locks. No incompatible or destructive auto-migration is
performed without authorization.

## Framework v0.2 compatibility

The runtime now reads both the current v0.1 YAML layout and the v0.2 JSON
layout. When `atlas.json` is present it is the selected project manifest; the
legacy `PROJECT_MANIFEST.yaml` is not used as a fallback for an invalid v2
manifest. This prevents a partially migrated project from appearing healthy
by accident.

The v0.2 reader recognizes:

- `atlas.json` and JSON agent, skill, recipe and orchestration manifests;
- `.atlas/history/project-intelligence.json` as a required project resource;
- `.ai/goals/**/*.goal.json` alongside the existing YAML Goal files;
- the v0.2 Goal states (`DRAFT`, `LOCKED`, `EXECUTING`, `VERIFYING` and
  `REVIEWING`) and the `project_intelligence` gate;
- `documentation_impact` as the v0.2 spelling of the documentation gate.

This is a read boundary, not a migration. The project remains on its current
canonical format until a separate migration Goal defines validation,
conflict handling, atomic writes and rollback evidence. Runtime context
compilation, bounded LPC/PCA retrieval and Project Intelligence task reports
remain planned integration slices rather than implicit behavior.
