"""Regression tests for the AF-EVO-001 deterministic foundation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_flow.cli import main
from atlas_flow.evolution.context import analyze_impact, plan_context
from atlas_flow.evolution.documents import freshness_of, load_manifest, parse_document
from atlas_flow.evolution.intelligence import IntelligenceStore
from atlas_flow.evolution.models import (
    ContextBudget,
    CostRange,
    DocumentMetadata,
    TaskCostRecord,
    TokenUsage,
)
from atlas_flow.evolution.site import build_site
from atlas_flow.evolution.validation import validate_project


def write_manifest(root: Path) -> None:
    (root / "atlas.config.yaml").write_text(
        """schema_version: 2
project:
  name: fixture
  version: 0.1.0
atlas:
  docs_root: docs
  data_root: .atlas
documentation:
  title: Fixture docs
  default_visibility: internal
context:
  default_budget: small
""",
        encoding="utf-8",
    )


def write_document(root: Path, relative: str, metadata: str, body: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{metadata}---\n# Title\n\n{body}\n", encoding="utf-8")


def make_fixture(root: Path) -> None:
    write_manifest(root)
    write_document(
        root,
        "docs/architecture.md",
        """id: DOC-ARCH
title: Architecture
visibility: public
owner: platform
last_reviewed: 2026-08-11
review_interval: 180d
tags: [architecture, context]
related: [DOC-CONTRACT]
""",
        "The context engine selects the architecture contract.",
    )
    write_document(
        root,
        "docs/contract.md",
        """id: DOC-CONTRACT
title: Contract
visibility: internal
owner: platform
""",
        "The contract protects the public API.",
    )
    write_document(
        root,
        "docs/private.md",
        """id: DOC-PRIVATE
title: Private Notes
visibility: private
owner: platform
""",
        "Do not publish this document.",
    )
    (root / "docs" / "_meta" / "task-maps").mkdir(parents=True)
    (root / "docs" / "_meta" / "task-maps" / "context.yaml").write_text(
        """schema_version: 1
id: TASKMAP-context
intent: context engine
risk: medium
read:
  required: [DOC-ARCH]
  optional: [DOC-CONTRACT]
usually_dont_touch: [authentication, telemetry]
verify: [unit-tests]
""",
        encoding="utf-8",
    )
    (root / "docs" / "_meta" / "context-packs").mkdir(parents=True)
    (root / "docs" / "_meta" / "context-packs" / "context.yaml").write_text(
        """schema_version: 1
id: CONTEXT-context
intent: context engine
include: [DOC-ARCH]
optional: [DOC-CONTRACT]
exclude: [authentication]
""",
        encoding="utf-8",
    )


def test_validation_accepts_v2_fixture_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    make_fixture(tmp_path)
    report = validate_project(tmp_path)
    assert report.valid
    assert report.document_count == 3
    assert report.task_map_count == 1
    assert report.context_pack_count == 1

    write_document(tmp_path, "docs/duplicate.md", "id: DOC-ARCH\ntitle: Duplicate\n", "bad")
    duplicate_report = validate_project(tmp_path)
    assert not duplicate_report.valid
    assert any(issue.code == "duplicate-document-id" for issue in duplicate_report.errors)


def test_context_plan_uses_contracts_budget_and_negative_context(tmp_path: Path) -> None:
    make_fixture(tmp_path)
    plan = plan_context(tmp_path, "context engine", budget="small", profile="reviewer")

    assert plan.risk == "medium"
    assert "DOC-ARCH" in {item.id for item in plan.required}
    assert "DOC-CONTRACT" in {item.id for item in plan.optional}
    assert "authentication" in plan.excluded
    assert plan.budget.max_tokens == 12_000
    assert plan.profile == "reviewer"
    assert plan.explanations["DOC-ARCH"]


def test_impact_reports_direct_and_related_document_changes(tmp_path: Path) -> None:
    make_fixture(tmp_path)
    report = analyze_impact(tmp_path, ["docs/architecture.md"])

    assert report.changed == ["docs/architecture.md"]
    assert report.read[0].path == "docs/architecture.md"
    assert any(item.path == "docs/contract.md" for item in report.possible_updates)


def test_site_public_build_does_not_publish_internal_or_private_docs(tmp_path: Path) -> None:
    make_fixture(tmp_path)
    result = build_site(tmp_path, tmp_path / "site", "public")
    search = json.loads((result.output / "search.json").read_text(encoding="utf-8"))

    assert result.pages == ["docs/architecture.html", "index.html", "search.json"]
    assert [entry["id"] for entry in search] == ["DOC-ARCH"]
    assert not (result.output / "docs" / "contract.html").exists()
    assert "Private Notes" not in (result.output / "index.html").read_text(encoding="utf-8")


def test_cost_ledger_aggregates_latest_task_without_inventing_observed_cost(tmp_path: Path) -> None:
    make_fixture(tmp_path)
    store = IntelligenceStore(tmp_path)
    store.append_cost(
        TaskCostRecord(
            task_id="TASK-1",
            title="First",
            components=["context"],
            estimate={"min": 1.0, "max": 2.0},
            observed_tokens=TokenUsage(input=100, output=20, avoided_estimate=40),
            confidence="medium",
        )
    )
    summary = store.build_summary()

    assert summary.tasks_completed == 1
    assert summary.tokens.input == 100
    assert summary.estimated_total_usd is not None
    assert summary.observed_api_usd is None
    assert summary.cost_by_component == {}


def test_init_is_non_destructive_and_cli_json_is_machine_readable(tmp_path: Path) -> None:
    existing = tmp_path / "docs" / "ATLAS.md"
    existing.parent.mkdir()
    existing.write_text("# Existing\n", encoding="utf-8")

    assert main(["--root", str(tmp_path), "init", "--json"]) == 0
    assert main(["--root", str(tmp_path), "init", "--json"]) == 0
    assert existing.read_text(encoding="utf-8") == "# Existing\n"
    assert (tmp_path / "atlas.config.yaml").is_file()
    assert (tmp_path / "docs" / "AGENT_ATLAS.md").is_file()


def test_document_freshness_is_explicit_for_versioned_docs(tmp_path: Path) -> None:
    write_manifest(tmp_path)
    write_document(
        tmp_path,
        "docs/stale.md",
        "id: DOC-STALE\nlast_reviewed: 2020-01-01\nreview_interval: 30d\n",
        "old",
    )
    manifest, _ = load_manifest(tmp_path)
    document = parse_document(tmp_path, tmp_path / "docs" / "stale.md", manifest)
    assert freshness_of(document.metadata) == "NEEDS REVIEW"
    assert isinstance(document.metadata, DocumentMetadata)


def test_manifest_paths_and_ranges_cannot_escape_or_become_inverted(tmp_path: Path) -> None:
    (tmp_path / "atlas.config.yaml").write_text(
        "schema_version: 2\natlas:\n  docs_root: ../outside\n", encoding="utf-8"
    )
    report = validate_project(tmp_path)
    assert not report.valid
    assert report.errors[0].code == "invalid-manifest"
    with pytest.raises(ValueError, match="target_tokens"):
        ContextBudget(name="bad", target_tokens=10, max_tokens=9)
    with pytest.raises(ValueError, match="max"):
        CostRange(min=3, max=2)
