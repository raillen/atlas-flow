"""Build a minimal, valid Project Atlas project on disk.

Atlas Flow claims to be generic: it orchestrates whatever project it is opened
on. That claim is only worth something if it is exercised against projects that
are not this one, which is what this builder is for.

Everything written here is the canonical Project Atlas shape, not a reduced
dialect — a fixture that accepts less than the real loader would prove nothing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GoalSpec:
    id: str
    phase: str
    title: str
    acceptance: list[str]
    dependencies: list[str] = field(default_factory=list)
    state: str = "ACTIVE"


@dataclass
class ProjectSpec:
    """One project category to run Atlas Flow against."""

    project_id: str
    name: str
    types: list[str]
    languages: list[str]
    goals: list[GoalSpec]


def write_project(root: Path, spec: ProjectSpec) -> Path:
    """Write every manifest `resolve_project` requires, then commit it."""
    root.mkdir(parents=True, exist_ok=True)
    _write(root / "PROJECT_MANIFEST.yaml", {
        "framework": {
            "name": "project-atlas-framework",
            "version": "0.1.0",
            "entrypoint": "ENTRYPOINT.md",
        },
        "project": {
            "id": spec.project_id,
            "name": spec.name,
            "type": spec.types,
            "status": "in-development",
        },
        "documentation": {"atlas": "docs/ATLAS.md", "state": "PROJECT_STATE.md"},
    })
    (root / "ENTRYPOINT.md").write_text(f"# {spec.name}\n", encoding="utf-8")
    (root / "PROJECT_STATE.md").write_text("# State\n\nIn development.\n", encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "ATLAS.md").write_text("# Atlas\n", encoding="utf-8")

    _write(root / ".ai/context/project-profile.yaml", {
        "project": {
            "id": spec.project_id,
            "type": spec.types,
            "languages": spec.languages,
            "technologies": [],
            "features": [],
            "risk": {"security": "medium"},
        }
    })
    _write(root / ".ai/agents/manifest.yaml", {
        "agents": ["goal-planner", "core-implementer", "reviewer"],
        "selection_basis": ["project type", "risk"],
    })
    _write(root / ".ai/skills/manifest.yaml", {"skills": ["goal-contracts"]})
    _write(root / ".ai/recipes/manifest.yaml", {"recipes": ["implement-goal"]})

    _write(root / ".ai/orchestration/model-policy.yaml", {
        "version": 1,
        "development_harness": "command-code",
        "runtime_discovery": {"command": "cmd --list-models"},
        "roster": [
            {
                "key": "deepseek-v4-pro",
                "provider": "deepseek",
                "command_code_id": "deepseek/deepseek-v4-pro",
                "priority": "primary",
                "availability": "expected",
            }
        ],
        "principles": ["runtime availability beats static assumptions"],
    })
    _write(root / ".ai/orchestration/autonomy-policy.yaml", {
        "default": "agentic",
        "modes": {"agentic": {"description": "plans and executes"}},
        "project_policy": {"current": "agentic"},
    })
    _write(root / ".ai/orchestration/orchestrator.yaml", {
        "development": {"harness": "command-code"},
        "product": {"runtime": "atlas-flow"},
        "protocols": {"agent": "acp", "ui": "ag-ui"},
        "execution": {"isolate_mutating_tasks": True, "worktree_strategy": "per-task"},
    })
    _write(root / ".ai/orchestration/fallbacks.yaml", {
        "availability": "route to the next reachable model",
        "quality": {"max_cross_model_attempts": 2},
        "confidence": {"escalate_below": 0.5},
        "human_escalation": ["unresolvable conflict"],
    })

    for goal in spec.goals:
        _write(root / f".ai/goals/{goal.phase}/{goal.id}.yaml", {
            "id": goal.id,
            "phase": goal.phase,
            "title": goal.title,
            "state": goal.state,
            "objective": f"Deliver {goal.title.lower()}.",
            "constraints": [],
            "non_goals": [],
            "dependencies": goal.dependencies,
            "acceptance": goal.acceptance,
            "gates": {
                "build": "required",
                "tests": "required",
                "review": "required",
                "documentation": "required",
            },
            "evidence": [],
            "history": [],
        })

    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "fixture@atlas-flow.invalid")
    _git(root, "config", "user.name", "Atlas Flow Fixture")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "initial")
    return root


# Three materially different categories: a library with no UI, a web
# application, and a command-line tool. They differ in type, language and Goal
# shape, which is what the runtime is supposed to be indifferent to.
PYTHON_LIBRARY = ProjectSpec(
    project_id="pigment",
    name="Pigment",
    types=["library"],
    languages=["python"],
    goals=[
        GoalSpec(
            id="L01-G01", phase="L01", title="Colour conversion core",
            acceptance=["sRGB to CIELAB", "Round-trip within tolerance"],
        ),
        GoalSpec(
            id="L02-G01", phase="L02", title="Public API surface",
            acceptance=["Documented entry points"], dependencies=["L01-G01"],
        ),
    ],
)

WEB_APPLICATION = ProjectSpec(
    project_id="ledgerly",
    name="Ledgerly",
    types=["web-application", "saas"],
    languages=["typescript", "sql"],
    goals=[
        GoalSpec(
            id="W01-G01", phase="W01", title="Account onboarding",
            acceptance=["Sign-up flow", "Email verification", "Audit trail"],
        ),
    ],
)

CLI_TOOL = ProjectSpec(
    project_id="quill",
    name="Quill",
    types=["cli"],
    languages=["rust"],
    goals=[
        GoalSpec(
            id="C01-G01", phase="C01", title="Argument parsing",
            acceptance=["Subcommands", "Helpful errors"],
        ),
    ],
)

CATEGORIES = [PYTHON_LIBRARY, WEB_APPLICATION, CLI_TOOL]


def _write(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    )
