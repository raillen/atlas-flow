"""Context Engine — context pack generation (GAP-04)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ContextPackEntry:
    path: str
    kind: str  # "doc", "code", "test", "decision", "goal"
    relevance: float = 1.0
    summary: str = ""


@dataclass
class ContextPack:
    goal_id: str
    task_id: str = ""
    docs: list[ContextPackEntry] = field(default_factory=list)
    code: list[ContextPackEntry] = field(default_factory=list)
    tests: list[ContextPackEntry] = field(default_factory=list)
    decisions: list[ContextPackEntry] = field(default_factory=list)
    forbidden_scope: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    total_size_hint: int = 0
    omissions: list[str] = field(default_factory=list)

    def entry_count(self) -> int:
        return len(self.docs) + len(self.code) + len(self.tests) + len(self.decisions)

    def is_within_budget(self, budget_tokens: int = 100_000) -> bool:
        return self.total_size_hint <= budget_tokens


class ContextEngine:
    """Builds smallest sufficient context for a Goal or Task."""

    def __init__(self, project_root: Path) -> None:
        self.root = project_root

    def build_for_goal(self, goal_id: str) -> ContextPack:
        pack = ContextPack(goal_id=goal_id)

        # Direct links: Goal definition
        goal_file = self.root / ".ai" / "goals" / goal_id[:3] / f"{goal_id}.yaml"
        if goal_file.is_file():
            pack.docs.append(
                ContextPackEntry(
                    path=str(goal_file.relative_to(self.root)),
                    kind="goal",
                    relevance=1.0,
                    summary=f"Goal definition for {goal_id}",
                )
            )

        # ATLAS impact edges: relevant architecture docs
        relevant_docs = self._atlas_links_for_goal(goal_id)
        pack.docs.extend(relevant_docs)

        # Accepted decisions (ADRs)
        adrs_dir = self.root / "docs" / "07-decisions"
        if adrs_dir.is_dir():
            for adr in sorted(adrs_dir.glob("ADR-*.md")):
                pack.decisions.append(
                    ContextPackEntry(
                        path=str(adr.relative_to(self.root)),
                        kind="decision",
                        relevance=0.8,
                        summary=adr.stem,
                    )
                )

        # Code: relevant backend modules
        code_mapping = self._code_for_goal(goal_id)
        for code_path in code_mapping:
            if code_path.is_file():
                pack.code.append(
                    ContextPackEntry(
                        path=str(code_path.relative_to(self.root)),
                        kind="code",
                        relevance=0.7,
                    )
                )

        # Tests: matching test files
        test_dir = self.root / "tests"
        if test_dir.is_dir():
            for test_file in sorted(test_dir.rglob("test_*.py")):
                pack.tests.append(
                    ContextPackEntry(
                        path=str(test_file.relative_to(self.root)),
                        kind="test",
                        relevance=0.5,
                    )
                )

        # Validation commands
        pack.validation_commands = [
            "uv run --project backend ruff check .",
            "uv run --project backend mypy",
            "uv run --project backend pytest tests/unit/ -q",
            "uv run --project backend python scripts/validate_docs.py",
            "uv run --project backend python scripts/validate_goals.py",
        ]

        pack.total_size_hint = pack.entry_count() * 2000
        return pack

    def _atlas_links_for_goal(self, goal_id: str) -> list[ContextPackEntry]:
        """Map goal IDs to relevant architecture docs."""
        mapping: dict[str, list[str]] = {
            "P01-G01": [
                "docs/01-architecture/DOMAIN_MODEL.md",
                "docs/03-implementation/PROJECT_ATLAS_INTEGRATION.md",
            ],
            "P02-G01": [
                "docs/01-architecture/CHAT_DISCUSS_MODE.md",
                "docs/01-architecture/DECISION_LEDGER.md",
            ],
            "P03-G01": [
                "docs/01-architecture/EXECUTION_ENGINE.md",
                "docs/01-architecture/PERSISTENCE.md",
                "docs/01-architecture/EVENT_MODEL.md",
                "docs/01-architecture/RECOVERY.md",
            ],
            "P04-G01": [
                "docs/01-architecture/ATLAS_HARNESS.md",
                "docs/01-architecture/ACP_INTEGRATION.md",
            ],
            "P05-G01": [
                "docs/01-architecture/PLANNER_DAG.md",
                "docs/01-architecture/GIT_WORKTREES.md",
            ],
            "P08-G01": [
                "docs/01-architecture/MODEL_ROUTER.md",
                "docs/01-architecture/WORKFORCE_RESOLVER.md",
            ],
        }

        docs = mapping.get(goal_id, [])
        return [
            ContextPackEntry(path=doc_path, kind="doc", relevance=0.9)
            for doc_path in docs
            if (self.root / doc_path).is_file()
        ]

    def _code_for_goal(self, goal_id: str) -> list[Path]:
        """Map goal IDs to code directories."""
        mapping: dict[str, list[str]] = {
            "P01-G01": ["backend/atlas_flow/goals/"],
            "P02-G01": ["backend/atlas_flow/discuss/"],
            "P03-G01": ["backend/atlas_flow/execution/"],
            "P04-G01": ["backend/atlas_flow/harness/"],
            "P05-G01": ["backend/atlas_flow/planner/"],
            "P06-G01": ["apps/desktop/src/"],
            "P07-G01": ["backend/atlas_flow/verification/"],
            "P08-G01": ["backend/atlas_flow/routing/", "backend/atlas_flow/workforce/"],
            "P09-G01": ["backend/atlas_flow/security/", "backend/atlas_flow/execution/faults.py"],
        }
        dirs = mapping.get(goal_id, [])
        return [self.root / d for d in dirs]
