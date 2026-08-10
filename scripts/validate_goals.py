"""Validate Goal files: schema, uniqueness, dependencies and evidence.

A Goal in state DONE asserts that its required gates passed. This validator
enforces that the assertion is backed by declared evidence, so a Goal cannot be
marked done by editing one word in a YAML file.
"""

import sys
from pathlib import Path

import yaml

from atlas_flow.verification.goal_completion import DONE, check_declared_evidence

root = Path(__file__).resolve().parents[1]
errors: list[str] = []
goals: dict[str, dict[str, object]] = {}

REQUIRED_FIELDS = {
    "id", "phase", "title", "state", "objective",
    "constraints", "acceptance", "gates", "dependencies", "evidence",
}
VALID_STATES = {"PLANNED", "READY", "ACTIVE", "BLOCKED", "DONE", "CANCELLED"}

for path in sorted(root.glob(".ai/goals/*/*.yaml")):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        errors.append(f"{path}: expected a mapping")
        continue

    missing = REQUIRED_FIELDS - set(data)
    if missing:
        errors.append(f"{path}: missing {sorted(missing)}")
        continue

    goal_id = str(data["id"])
    if goal_id in goals:
        errors.append(f"duplicate Goal id: {goal_id}")
    goals[goal_id] = data

    if not data["acceptance"]:
        errors.append(f"{goal_id}: acceptance must not be empty")

    state = str(data["state"])
    if state not in VALID_STATES:
        errors.append(
            f"{goal_id}: unknown state '{state}' (expected one of {sorted(VALID_STATES)})"
        )

    if state == DONE:
        check = check_declared_evidence(data)
        if not check.completable:
            errors.append(
                f"{goal_id}: state is DONE but {check.describe()}. "
                "Attach evidence for every required gate, or move the Goal "
                "back to ACTIVE."
            )

for goal_id, data in goals.items():
    dependencies = data.get("dependencies") or []
    if not isinstance(dependencies, list):
        errors.append(f"{goal_id}: dependencies must be a list")
        continue
    for dependency in dependencies:
        if dependency not in goals:
            errors.append(f"{goal_id}: depends on unknown Goal '{dependency}'")
        elif data["state"] == DONE and goals[dependency]["state"] != DONE:
            errors.append(
                f"{goal_id}: is DONE but depends on '{dependency}', "
                f"which is {goals[dependency]['state']}"
            )

if errors:
    print("\n".join(errors))
    sys.exit(1)

done = sum(1 for g in goals.values() if g["state"] == DONE)
print(f"Goal validation: PASS ({len(goals)} goals, {done} DONE)")
