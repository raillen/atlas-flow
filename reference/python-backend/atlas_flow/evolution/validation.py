"""Validation for the v2 inputs and derived projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ValidationError

from atlas_flow.evolution.documents import DocumentParseError, discover_documents, load_manifest
from atlas_flow.evolution.models import ContextPack, ProjectManifest, TaskMap
from atlas_flow.evolution.registry import build_graph, build_registry, registry_lookup


class HasId(Protocol):
    id: str


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    issues: list[ValidationIssue]
    document_count: int = 0
    task_map_count: int = 0
    context_pack_count: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors


def _load_models[ModelT: BaseModel](
    directory: Path, model_type: type[ModelT]
) -> tuple[list[ModelT], list[ValidationIssue]]:
    models: list[ModelT] = []
    issues: list[ValidationIssue] = []
    if not directory.is_dir():
        return models, issues
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("expected a YAML mapping")
            models.append(model_type.model_validate(raw))
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError, ValueError) as exc:
            issues.append(ValidationIssue("error", "invalid-yaml", str(exc), path.as_posix()))
    return models, issues


def load_task_maps(
    root: Path, manifest: ProjectManifest
) -> tuple[list[TaskMap], list[ValidationIssue]]:
    directory = root / manifest.atlas.docs_root / "_meta" / "task-maps"
    return _load_models(directory, TaskMap)


def load_context_packs(
    root: Path, manifest: ProjectManifest
) -> tuple[list[ContextPack], list[ValidationIssue]]:
    directory = root / manifest.atlas.docs_root / "_meta" / "context-packs"
    return _load_models(directory, ContextPack)


def validate_project(root: Path) -> ValidationReport:
    """Validate v2 data while keeping legacy Markdown usable."""

    issues: list[ValidationIssue] = []
    try:
        manifest, manifest_path = load_manifest(root)
    except DocumentParseError as exc:
        return ValidationReport([ValidationIssue("error", "invalid-manifest", str(exc))])

    if manifest_path is None:
        issues.append(
            ValidationIssue(
                "warning",
                "legacy-project",
                "No v2 manifest found; legacy documents are being indexed with derived metadata.",
            )
        )

    try:
        documents = discover_documents(root, manifest)
    except DocumentParseError as exc:
        return ValidationReport(issues + [ValidationIssue("error", "invalid-document", str(exc))])

    registry = build_registry(documents)
    graph = build_graph(documents)
    seen: dict[str, str] = {}
    for entry in registry:
        previous = seen.get(entry.id)
        if previous is not None:
            issues.append(
                ValidationIssue(
                    "error",
                    "duplicate-document-id",
                    f"Document ID '{entry.id}' is used by both {previous} and {entry.path}.",
                    entry.path,
                )
            )
        seen[entry.id] = entry.path

    for document in documents:
        if document.has_front_matter and document.metadata.owner is None:
            issues.append(
                ValidationIssue(
                    "warning",
                    "missing-owner",
                    "Versioned document metadata should declare an owner.",
                    document.relative_path,
                )
            )

    for node in graph.nodes:
        if node.type == "reference":
            issues.append(
                ValidationIssue(
                    "warning",
                    "dangling-reference",
                    f"Graph target '{node.id}' is not declared in the document registry.",
                    node.id,
                )
            )

    task_maps, task_issues = load_task_maps(root, manifest)
    context_packs, pack_issues = load_context_packs(root, manifest)
    issues.extend(task_issues)
    issues.extend(pack_issues)
    issues.extend(_duplicate_ids(task_maps, "task-map"))
    issues.extend(_duplicate_ids(context_packs, "context-pack"))
    lookup = registry_lookup(registry)
    for task_map in task_maps:
        references = task_map.read.required + task_map.read.optional + task_map.documentation
        issues.extend(_missing_references(references, lookup, task_map.id))
    for context_pack in context_packs:
        references = context_pack.include + context_pack.optional
        issues.extend(_missing_references(references, lookup, context_pack.id))

    return ValidationReport(
        issues=issues,
        document_count=len(documents),
        task_map_count=len(task_maps),
        context_pack_count=len(context_packs),
    )


def _duplicate_ids(models: Sequence[HasId], kind: str) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for model in models:
        identifier = str(model.id)
        if identifier in seen:
            issues.append(
                ValidationIssue(
                    "error", f"duplicate-{kind}-id", f"Duplicate {kind} ID '{identifier}'."
                )
            )
        seen.add(identifier)
    return issues


def _missing_references(
    references: Sequence[str], lookup: Mapping[str, object], source_id: str
) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            "warning",
            "missing-reference",
            f"{source_id} references '{reference}', which is not in the document registry.",
            source_id,
        )
        for reference in references
        if reference not in lookup
    ]
