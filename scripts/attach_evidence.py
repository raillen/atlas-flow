#!/usr/bin/env python3
"""Attach evidence for a gate to a Goal, and optionally close the Goal.

Evidence is a claim about something that happened, so this script will not
invent one: every entry needs a gate, a verdict and a reference that a reader
can go and check. `--complete` moves the Goal to DONE, and refuses unless every
gate the Goal declares required is covered by passing evidence.

    python scripts/attach_evidence.py P08-G01 review \\
        --verdict PASSED \\
        --reference "docs/07-decisions/reviews/2026-08-11-P08.md" \\
        --summary "gpt-5.6-luna, 3 findings, all addressed"

Git stays the authority for Goal state (ADR-009), so this edits the Goal file
rather than writing a row in the operational database.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from atlas_flow.verification.goal_completion import (  # noqa: E402
    DONE,
    check_declared_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
GATES = ("build", "tests", "review", "documentation")
VERDICTS = ("PASSED", "FAILED", "PENDING")


def find_goal(goal_id: str) -> Path:
    matches = sorted((ROOT / ".ai" / "goals").rglob(f"{goal_id}.yaml"))
    if not matches:
        raise SystemExit(f"No Goal file for {goal_id}")
    return matches[0]


def attach(
    path: Path, gate: str, verdict: str, reference: str, summary: str
) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Malformed Goal file: {path}")

    detail = " — ".join(filter(None, (summary, reference)))
    entry = {gate: f"{verdict}: {detail}" if verdict != "PASSED" else detail}

    evidence = list(data.get("evidence") or [])
    # Replace an earlier entry for the same gate rather than stacking claims:
    # two answers for one gate is not more evidence, it is an unresolved
    # disagreement about what happened.
    evidence = [
        item for item in evidence if not (isinstance(item, dict) and gate in item)
    ]
    evidence.append(entry)
    data["evidence"] = evidence

    history = list(data.get("history") or [])
    history.append(
        f"{datetime.now(UTC).date().isoformat()}: {gate} gate {verdict} — {detail}"
    )
    data["history"] = history
    return data


def write(path: Path, data: dict[str, object]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal_id")
    parser.add_argument("gate", choices=GATES)
    parser.add_argument("--verdict", choices=VERDICTS, default="PASSED")
    parser.add_argument(
        "--reference", required=True,
        help="Where the evidence lives: a path, a commit, a run id, a URL.",
    )
    parser.add_argument("--summary", default="", help="One line on what it says.")
    parser.add_argument(
        "--complete", action="store_true",
        help="Also move the Goal to DONE. Refused unless every required gate "
             "has passing evidence.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = find_goal(args.goal_id)
    data = attach(path, args.gate, args.verdict, args.reference, args.summary)

    if args.complete:
        check = check_declared_evidence(data)
        if not check.completable:
            print(f"Refusing to complete {args.goal_id}: {check.describe()}",
                  file=sys.stderr)
            return 1
        if args.verdict != "PASSED":
            print(f"Refusing to complete {args.goal_id}: this evidence is "
                  f"{args.verdict}", file=sys.stderr)
            return 1
        data["state"] = DONE
        history = list(data["history"])  # type: ignore[arg-type]
        history.append(
            f"{datetime.now(UTC).date().isoformat()}: moved to DONE — every "
            f"required gate has passing evidence."
        )
        data["history"] = history

    if args.dry_run:
        print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88))
        return 0

    write(path, data)
    print(f"{args.goal_id}: {args.gate} = {args.verdict} → {path}")
    if args.complete:
        print(f"{args.goal_id}: state = DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
