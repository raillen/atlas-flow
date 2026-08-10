# Goal Engine

Consumes Project Atlas Goals; no second Goal format.

State machine:
`DRAFT → PLANNED → LOCKED → EXECUTING → VERIFYING → REVIEWING → DONE`, with policy-defined `BLOCKED`.

Responsibilities: schema validation, legal transitions, lock protection, dependencies, amendment, evidence completeness and closure.

Locked Goals change only through explicit amendment. Test failure never justifies weaker acceptance.
