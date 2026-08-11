"""Command-line entry point for deterministic Atlas Flow v2 workflows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from atlas_flow.evolution.context import analyze_impact, format_context_plan, plan_context
from atlas_flow.evolution.documents import DocumentParseError
from atlas_flow.evolution.intelligence import IntelligenceStore, format_summary
from atlas_flow.evolution.models import CostRange, TaskCostRecord, TokenUsage
from atlas_flow.evolution.site import build_site, documentation_coverage, freshness_report
from atlas_flow.evolution.validation import validate_project


def _json_dump(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def _report_dict(report: Any) -> dict[str, object]:
    return {
        "valid": report.valid,
        "documents": report.document_count,
        "task_maps": report.task_map_count,
        "context_packs": report.context_pack_count,
        "issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "path": issue.path,
            }
            for issue in report.issues
        ],
    }


def _impact_dict(report: Any) -> dict[str, object]:
    return {
        "changed": report.changed,
        "risk": report.risk,
        "read": [item.__dict__ for item in report.read],
        "possible_updates": [item.__dict__ for item in report.possible_updates],
        "warnings": report.warnings,
    }


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas", description="Atlas Flow v2 project intelligence tools"
    )
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="project root (default: current directory)"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate v2 data and derived relationships")
    validate.add_argument(
        "--write", action="store_true", help="write registry and graph projections"
    )
    _add_json_flag(validate)

    impact = commands.add_parser("impact", help="analyze changed files and affected knowledge")
    impact.add_argument("paths", nargs="*", help="changed paths; defaults to Git changes")
    impact.add_argument("--changed", action="store_true", help="read changed paths from Git")
    _add_json_flag(impact)

    context = commands.add_parser("context", help="plan minimum sufficient context for an intent")
    context.add_argument("intent")
    context.add_argument("--budget", help="small, medium, large or a target token count")
    context.add_argument("--profile", default="implementer")
    _add_json_flag(context)

    graph = commands.add_parser("graph", help="show the derived document graph")
    graph.add_argument(
        "--write", action="store_true", help="write the graph and registry projections"
    )
    _add_json_flag(graph)

    docs = commands.add_parser("docs", help="documentation validation and publishing")
    docs_commands = docs.add_subparsers(dest="docs_command", required=True)
    docs_validate = docs_commands.add_parser("validate")
    _add_json_flag(docs_validate)
    freshness = docs_commands.add_parser("freshness")
    _add_json_flag(freshness)
    coverage = docs_commands.add_parser("coverage")
    _add_json_flag(coverage)
    build = docs_commands.add_parser("build")
    build.add_argument(
        "--visibility", choices=("public", "internal", "private"), default="internal"
    )
    build.add_argument("--output", type=Path)
    _add_json_flag(build)

    cost = commands.add_parser("cost", help="record and aggregate task cost")
    cost_commands = cost.add_subparsers(dest="cost_command", required=True)
    cost_task = cost_commands.add_parser("task")
    cost_task.add_argument("task_id")
    cost_task.add_argument("--title", required=True)
    cost_task.add_argument("--type", default="unknown", dest="task_type")
    cost_task.add_argument("--component", action="append", default=[])
    cost_task.add_argument("--release")
    cost_task.add_argument("--estimate-min", type=float)
    cost_task.add_argument("--estimate-max", type=float)
    cost_task.add_argument("--observed-cost", type=float)
    cost_task.add_argument(
        "--cost-source",
        choices=("provider_usage", "calculated", "estimated", "allocated", "unknown"),
        default="unknown",
    )
    cost_task.add_argument(
        "--billing-mode",
        choices=("api", "subscription", "free", "local", "unknown"),
        default="unknown",
    )
    cost_task.add_argument(
        "--confidence", choices=("high", "medium", "low", "unknown"), default="unknown"
    )
    cost_task.add_argument("--input-tokens", type=int, default=0)
    cost_task.add_argument("--output-tokens", type=int, default=0)
    cost_task.add_argument("--cached-tokens", type=int, default=0)
    cost_task.add_argument("--avoided-tokens", type=int, default=0)
    _add_json_flag(cost_task)
    cost_project = cost_commands.add_parser("project")
    cost_project.add_argument("--write", action="store_true", help="write project-summary.json")
    _add_json_flag(cost_project)

    intelligence = commands.add_parser("intelligence", help="project intelligence projections")
    intelligence_commands = intelligence.add_subparsers(dest="intelligence_command", required=True)
    intelligence_summary = intelligence_commands.add_parser("summary")
    intelligence_summary.add_argument("--write", action="store_true")
    _add_json_flag(intelligence_summary)

    init = commands.add_parser("init", help="create a non-destructive v2 project scaffold")
    init.add_argument("--name")
    _add_json_flag(init)
    return parser


def _handle_init(root: Path, name: str | None) -> list[str]:
    created: list[str] = []
    manifest_path = root / "atlas.config.yaml"
    if not manifest_path.exists():
        manifest = {
            "schema_version": 2,
            "project": {"name": name or root.name, "version": "0.1.0"},
            "atlas": {"docs_root": "docs", "data_root": ".atlas"},
            "documentation": {
                "title": f"{name or root.name} Documentation",
                "default_visibility": "internal",
            },
            "publishing": {"public": [], "internal": [], "private": []},
            "intelligence": {"enabled": True, "dashboard": True},
            "context": {"default_budget": "medium"},
        }
        root.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        created.append(manifest_path.relative_to(root).as_posix())
    directories = (
        root / "docs" / "_meta" / "task-maps",
        root / "docs" / "_meta" / "context-packs",
        root / "docs" / "_meta" / "summaries",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    starter_docs = {
        "docs/USER_ATLAS.md": "# User Atlas\n\nStart with the user documentation.\n",
        "docs/DEVELOPER_ATLAS.md": "# Developer Atlas\n\nStart with contributor documentation.\n",
        "docs/AGENT_ATLAS.md": "# Agent Atlas\n\nStart with the project contract and task maps.\n",
        "docs/_meta/TOKEN_ECONOMY.md": (
            "# Token Economy\n\nUse minimum sufficient context and record estimation method.\n"
        ),
    }
    for relative, content in starter_docs.items():
        path = root / relative
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(relative)
    return created


def run(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if args.command == "validate":
        validation_report = validate_project(root)
        written: list[Path] = []
        if args.write and validation_report.valid:
            from atlas_flow.evolution.registry import write_project_index

            written = write_project_index(root)
        if args.json:
            validation_payload = _report_dict(validation_report)
            if written:
                validation_payload["written"] = [str(path) for path in written]
            _json_dump(validation_payload)
        else:
            print(f"Atlas validation: {'PASS' if validation_report.valid else 'FAIL'}")
            print(
                f"Documents: {validation_report.document_count}; "
                f"task maps: {validation_report.task_map_count};"
            )
            print(f"Context packs: {validation_report.context_pack_count}")
            for issue in validation_report.issues:
                print(f"{issue.severity.upper()} {issue.code}: {issue.message}")
            if written:
                print(f"Written projections: {', '.join(str(path) for path in written)}")
        return 0 if validation_report.valid else 1

    if args.command == "impact":
        impact_report = analyze_impact(root, None if args.changed or not args.paths else args.paths)
        if args.json:
            _json_dump(_impact_dict(impact_report))
        else:
            print(f"Impact risk: {impact_report.risk.upper()}")
            print("Read:")
            for item in impact_report.read:
                print(f"- {item.path} — {item.reason}")
            print("Possible updates:")
            for item in impact_report.possible_updates:
                print(f"- {item.path} — {item.reason}")
        return 0

    if args.command == "context":
        plan = plan_context(root, args.intent, args.budget, args.profile)
        if args.json:
            _json_dump(plan.model_dump(mode="json"))
        else:
            print(format_context_plan(plan))
        return 0

    if args.command == "graph":
        from atlas_flow.evolution.registry import load_project_index

        graph = load_project_index(root)[3]
        graph_written: list[Path] = []
        if args.write:
            from atlas_flow.evolution.registry import write_project_index

            graph_written = write_project_index(root)
        if args.json:
            payload = graph.model_dump(mode="json")
            if graph_written:
                payload["written"] = [str(path) for path in graph_written]
            _json_dump(payload)
        else:
            print(f"Nodes: {len(graph.nodes)}; edges: {len(graph.edges)}")
            for edge in graph.edges:
                print(f"- {edge.source} -[{edge.relation}]-> {edge.target}")
        return 0

    if args.command == "docs":
        if args.docs_command == "validate":
            validation_report = validate_project(root)
            if args.json:
                _json_dump(_report_dict(validation_report))
            else:
                print(f"Documentation validation: {'PASS' if validation_report.valid else 'FAIL'}")
                for issue in validation_report.issues:
                    print(f"{issue.severity.upper()} {issue.code}: {issue.message}")
            return 0 if validation_report.valid else 1
        if args.docs_command == "freshness":
            freshness_data = freshness_report(root)
            if args.json:
                _json_dump(freshness_data)
            else:
                for fresh_item in freshness_data:
                    print(f"{fresh_item['status']:13} {fresh_item['path']}")
            return 0
        if args.docs_command == "coverage":
            coverage_data = documentation_coverage(root)
            if args.json:
                _json_dump(coverage_data)
            else:
                print(f"Documentation metadata coverage: {coverage_data['coverage']}")
                for section, values in coverage_data["by_section"].items():
                    print(f"- {section}: {values['versioned']}/{values['total']}")
            return 0
        result = build_site(root, args.output, args.visibility)
        payload = {
            "output": str(result.output),
            "visibility": result.visibility,
            "pages": result.pages,
        }
        if args.json:
            _json_dump(payload)
        else:
            print(
                f"Documentation site built at {result.output} ({len(result.pages)} generated files)"
            )
        return 0

    if args.command == "cost":
        store = IntelligenceStore(root)
        if args.cost_command == "task":
            if (args.estimate_min is None) != (args.estimate_max is None):
                raise ValueError("--estimate-min and --estimate-max must be supplied together")
            estimate = None
            if args.estimate_min is not None and args.estimate_max is not None:
                estimate = CostRange(min=args.estimate_min, max=args.estimate_max)
            record = TaskCostRecord(
                task_id=args.task_id,
                title=args.title,
                task_type=args.task_type,
                components=args.component,
                release=args.release,
                date_finished=datetime.now(UTC).isoformat(),
                estimate=estimate,
                observed_tokens=TokenUsage(
                    input=args.input_tokens,
                    output=args.output_tokens,
                    cached=args.cached_tokens,
                    avoided_estimate=args.avoided_tokens,
                ),
                observed_cost_usd=args.observed_cost,
                cost_source=args.cost_source,
                billing_mode=args.billing_mode,
                confidence=args.confidence,
            )
            ledger_path = store.append_cost(record)
            task_payload = {
                "record": record.model_dump(mode="json"),
                "ledger": str(ledger_path),
            }
            if args.json:
                _json_dump(task_payload)
            else:
                print(f"Cost recorded for {record.task_id}: {ledger_path}")
            return 0
        summary = store.build_summary()
        summary_path = store.write_summary(summary) if args.write else None
        project_payload: dict[str, Any] = summary.model_dump(mode="json")
        if summary_path:
            project_payload["summary_path"] = str(summary_path)
        if args.json:
            _json_dump(project_payload)
        else:
            print(format_summary(summary))
            if summary_path:
                print(f"Summary written to {summary_path}")
        return 0

    if args.command == "intelligence":
        store = IntelligenceStore(root)
        summary = store.build_summary()
        summary_path = store.write_summary(summary) if args.write else None
        intelligence_payload: dict[str, Any] = summary.model_dump(mode="json")
        if summary_path:
            intelligence_payload["summary_path"] = str(summary_path)
        if args.json:
            _json_dump(intelligence_payload)
        else:
            print(format_summary(summary))
        return 0

    if args.command == "init":
        created = _handle_init(root, args.name)
        payload = {"root": str(root), "created": created}
        if args.json:
            _json_dump(payload)
        else:
            print(f"Atlas v2 scaffold: {len(created)} files created")
            for path in created:
                print(f"- {path}")
        return 0
    raise AssertionError(f"unhandled command {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        return run(parser.parse_args(argv))
    except (DocumentParseError, OSError, ValueError) as exc:
        print(f"atlas: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
