"""Append-only cost/debt ledgers and project intelligence aggregation."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

from atlas_flow.evolution.documents import discover_documents, load_manifest, resolve_project_path
from atlas_flow.evolution.models import (
    CostRange,
    DebtRecord,
    ProjectSummary,
    TaskCostRecord,
    TokenUsage,
)


class IntelligenceStore:
    """Store rebuildable intelligence projections under the project's data root."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest, _ = load_manifest(root)
        self.data_root = resolve_project_path(root, self.manifest.atlas.data_root, "data_root")
        self.intelligence_root = self.data_root / "intelligence"
        self.ledger_path = self.intelligence_root / "ledger.jsonl"
        self.debt_path = self.intelligence_root / "debt.jsonl"
        self.summary_path = self.intelligence_root / "project-summary.json"

    def append_cost(self, record: TaskCostRecord) -> Path:
        self.intelligence_root.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")
        return self.ledger_path

    def append_debt(self, record: DebtRecord) -> Path:
        self.intelligence_root.mkdir(parents=True, exist_ok=True)
        with self.debt_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")
        return self.debt_path

    def cost_records(self) -> list[TaskCostRecord]:
        return _read_jsonl(self.ledger_path, TaskCostRecord)

    def debt_records(self) -> list[DebtRecord]:
        return _read_jsonl(self.debt_path, DebtRecord)

    def build_summary(self) -> ProjectSummary:
        records = self.cost_records()
        latest: dict[str, TaskCostRecord] = {}
        for record in records:
            latest[record.task_id] = record
        selected = list(latest.values())
        tokens = TokenUsage(
            input=sum(record.observed_tokens.input for record in selected),
            output=sum(record.observed_tokens.output for record in selected),
            cached=sum(record.observed_tokens.cached for record in selected),
            avoided_estimate=sum(record.observed_tokens.avoided_estimate for record in selected),
        )
        observed_costs = [
            record.observed_cost_usd for record in selected if record.observed_cost_usd is not None
        ]
        estimated = [record.estimate for record in selected if record.estimate is not None]
        cost_by_component: dict[str, float] = {}
        for record in selected:
            if record.observed_cost_usd is None or not record.components:
                continue
            share = record.observed_cost_usd / len(record.components)
            for component in record.components:
                cost_by_component[component] = cost_by_component.get(component, 0.0) + share
        documents = discover_documents(self.root, self.manifest)
        versioned = sum(document.has_front_matter for document in documents)
        coverage = versioned / len(documents) if documents else None
        open_debt = sum(record.status != "closed" for record in self.debt_records())
        return ProjectSummary(
            project=self.manifest.project.get("name", self.root.name),
            tasks_completed=len(selected),
            tokens=tokens,
            observed_api_usd=sum(observed_costs) if observed_costs else None,
            estimated_total_usd=(
                CostRange(
                    min=sum(item.min for item in estimated), max=sum(item.max for item in estimated)
                )
                if estimated
                else None
            ),
            documentation_coverage=coverage,
            technical_debt_open_items=open_debt,
            cost_by_component={
                key: round(value, 6) for key, value in sorted(cost_by_component.items())
            },
        )

    def write_summary(self, summary: ProjectSummary | None = None) -> Path:
        summary = summary or self.build_summary()
        self.intelligence_root.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix="project-summary-", suffix=".json", dir=self.intelligence_root
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(summary.model_dump(mode="json"), stream, indent=2, sort_keys=True)
                stream.write("\n")
            Path(temporary).replace(self.summary_path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return self.summary_path


def _read_jsonl[RecordT: BaseModel](path: Path, model_type: type[RecordT]) -> list[RecordT]:
    if not path.is_file():
        return []
    records: list[RecordT] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(model_type.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{path}:{line_number}: invalid intelligence record: {exc}") from exc
    return records


def format_summary(summary: ProjectSummary) -> str:
    estimated = "unknown"
    if summary.estimated_total_usd is not None:
        estimated = (
            f"US$ {summary.estimated_total_usd.min:.2f}–{summary.estimated_total_usd.max:.2f}"
        )
    observed = (
        "unknown" if summary.observed_api_usd is None else f"US$ {summary.observed_api_usd:.2f}"
    )
    coverage = (
        "unknown"
        if summary.documentation_coverage is None
        else f"{summary.documentation_coverage:.0%}"
    )
    return "\n".join(
        [
            f"Project: {summary.project}",
            f"Tasks completed: {summary.tasks_completed}",
            f"Tokens: {summary.tokens.input} input / {summary.tokens.output} output / "
            f"{summary.tokens.cached} cached",
            f"Observed API cost: {observed}",
            f"Estimated total cost: {estimated}",
            f"Documentation metadata coverage: {coverage}",
            f"Open technical debt: {summary.technical_debt_open_items}",
        ]
    )
