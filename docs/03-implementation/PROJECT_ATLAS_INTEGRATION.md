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
