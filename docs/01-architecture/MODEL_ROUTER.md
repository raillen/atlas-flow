# Model Router

Inputs: role, risk, capabilities, roster, availability, implementer provider, historical score, budget, context size.

Initial routing is deterministic ordered policy; adaptive scoring is post-MVP.

Roster:
1. DeepSeek V4 Pro — architecture, reasoning, hard debugging, security.
2. MiMo V2.5 Pro — long-context implementation, refactors, integration.
3. GPT-5.6 Luna — efficient exploration/tests/docs/bulk work when Command Code exposes it.

Probe `cmd --list-models` at runtime. High-risk reviewer should differ from implementer provider when possible. Retries are bounded.
