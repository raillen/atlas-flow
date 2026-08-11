# Taste

## Communication
- Communicates in Portuguese (Brazil); expects replies in Portuguese. Confidence: 0.9
- Terse, imperative messages ("continue", "prossiga", "execute", "o que ainda falta implementar?"); no interest in lengthy preamble. Confidence: 0.85

## Workflow
- Delegates broad scope and expects autonomous execution: asked to "continue until a testable and usable MVP is finished" and let the agent drive multi-phase work without intermediate check-ins; a later bare "continue" greenlit several more phases (hardening, release docs, gates, commits) unsupervised; a bare "execute" greenlit launching backend+frontend, smoke-testing API endpoints, fixing a live bug, and verifying the fix — all without asking. Confidence: 0.9
- Requires model/provider diversity for audit/review: the same model used for implementation (e.g., Opus 5) must not be reused for auditing the same project; auditing should use a different model to reduce implementation bias. Confidence: 0.9
- Expects genuine execution, not simulated work or paperwork-only actions. When the user discovers a task was merely documented/registered instead of actually performed, they demand concrete execution with real evidence — not an acknowledgment followed by more documentation. Confidence: 0.85
