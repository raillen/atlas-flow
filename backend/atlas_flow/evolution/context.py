"""Minimum-sufficient context planning and explainable impact analysis."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from atlas_flow.evolution.documents import ParsedDocument
from atlas_flow.evolution.models import (
    ContextBudget,
    ContextItem,
    ContextPlan,
    RegistryEntry,
    TaskMap,
)
from atlas_flow.evolution.registry import load_project_index, registry_lookup
from atlas_flow.evolution.validation import load_context_packs, load_task_maps

DEFAULT_BUDGETS = {
    "small": (8_000, 12_000),
    "medium": (20_000, 32_000),
    "large": (48_000, 80_000),
}


@dataclass(frozen=True)
class ImpactItem:
    path: str
    reason: str
    relation: str


@dataclass(frozen=True)
class ImpactReport:
    changed: list[str]
    risk: str
    read: list[ImpactItem]
    possible_updates: list[ImpactItem]
    warnings: list[str]


def estimate_tokens(text: str) -> int:
    """Use a transparent heuristic when a model tokenizer is unavailable."""

    return max(1, (len(text) + 3) // 4)


def budget_for(name_or_tokens: str | int | None, default: str = "medium") -> ContextBudget:
    if name_or_tokens is None:
        name_or_tokens = default
    if isinstance(name_or_tokens, int):
        if name_or_tokens <= 0:
            raise ValueError("context budget must be positive")
        return ContextBudget(
            name="custom", target_tokens=name_or_tokens, max_tokens=int(name_or_tokens * 1.6)
        )
    if name_or_tokens.isdigit():
        return budget_for(int(name_or_tokens), default)
    try:
        target, maximum = DEFAULT_BUDGETS[name_or_tokens]
    except KeyError as exc:
        raise ValueError(f"unknown context budget '{name_or_tokens}'") from exc
    return ContextBudget(name=name_or_tokens, target_tokens=target, max_tokens=maximum)


def _tokens_for_document(document: ParsedDocument) -> int:
    return document.metadata.estimated_tokens or estimate_tokens(document.body)


def _terms(intent: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9][a-z0-9_-]+", intent.lower()) if len(term) > 2}


def _score_document(document: ParsedDocument, terms: set[str]) -> int:
    haystack = " ".join(
        [
            document.metadata.title,
            document.relative_path,
            " ".join(document.metadata.tags),
            document.body[:20_000],
        ]
    ).lower()
    return sum(haystack.count(term) for term in terms)


def _find_task_map(task_maps: list[TaskMap], intent: str) -> TaskMap | None:
    normalized = intent.strip().lower()
    exact = next((item for item in task_maps if item.intent.lower() == normalized), None)
    if exact is not None:
        return exact
    terms = _terms(intent)
    scored = [(len(terms & _terms(item.intent)), item) for item in task_maps]
    matches = [item for score, item in scored if score > 0]
    return sorted(matches, key=lambda item: item.id)[0] if matches else None


def _resolve_reference(reference: str, lookup: dict[str, RegistryEntry]) -> RegistryEntry | None:
    return lookup.get(reference) or lookup.get(reference.lstrip("./"))


def _item_for_reference(
    reference: str,
    lookup: dict[str, RegistryEntry],
    documents: dict[str, ParsedDocument],
    reason: str,
    required: bool,
) -> ContextItem:
    entry = _resolve_reference(reference, lookup)
    if entry is None:
        return ContextItem(
            id=reference,
            reason=f"{reason}; reference not indexed",
            estimated_tokens=0,
            required=required,
        )
    document = documents[entry.path]
    return ContextItem(
        id=entry.id,
        path=entry.path,
        reason=reason,
        estimated_tokens=_tokens_for_document(document),
        required=required,
    )


def _add_unique(items: list[ContextItem], candidate: ContextItem) -> None:
    if all(item.id != candidate.id for item in items):
        items.append(candidate)


def plan_context(
    root: Path,
    intent: str,
    budget: str | int | None = None,
    profile: str = "implementer",
) -> ContextPlan:
    """Plan context using explicit packs first, then lexical retrieval."""

    if not intent.strip():
        raise ValueError("context intent must not be empty")
    manifest, documents_list, registry, _ = load_project_index(root)
    documents = {document.relative_path: document for document in documents_list}
    lookup = registry_lookup(registry)
    task_maps, _ = load_task_maps(root, manifest)
    context_packs, _ = load_context_packs(root, manifest)
    task_map = _find_task_map(task_maps, intent)
    pack = next((item for item in context_packs if item.intent.lower() == intent.lower()), None)
    selected_required: list[ContextItem] = []
    selected_optional: list[ContextItem] = []

    for reference, reason in (
        ("AGENTS.md", "L0 project contract"),
        ("docs/ATLAS.md", "L0 intent router"),
    ):
        path = root / reference
        if path.is_file():
            _add_unique(
                selected_required,
                ContextItem(
                    id=reference,
                    path=reference,
                    reason=reason,
                    estimated_tokens=estimate_tokens(path.read_text(encoding="utf-8")),
                    required=True,
                ),
            )

    if task_map is not None:
        for reference in task_map.read.required:
            _add_unique(
                selected_required,
                _item_for_reference(
                    reference, lookup, documents, f"required by {task_map.id}", True
                ),
            )
        for reference in task_map.read.optional:
            _add_unique(
                selected_optional,
                _item_for_reference(
                    reference, lookup, documents, f"optional in {task_map.id}", False
                ),
            )
    if pack is not None:
        for reference in pack.include:
            _add_unique(
                selected_required,
                _item_for_reference(reference, lookup, documents, f"included by {pack.id}", True),
            )
        for reference in pack.optional:
            _add_unique(
                selected_optional,
                _item_for_reference(reference, lookup, documents, f"optional in {pack.id}", False),
            )

    terms = _terms(intent)
    lexical = sorted(
        (
            (-_score_document(document, terms), document.relative_path, document)
            for document in documents_list
        ),
        key=lambda item: (item[0], item[1]),
    )
    for score, _, document in lexical:
        if score == 0:
            continue
        candidate = ContextItem(
            id=document.metadata.id,
            path=document.relative_path,
            reason="lexical match for intent",
            estimated_tokens=_tokens_for_document(document),
            required=False,
        )
        if candidate.id not in {item.id for item in selected_required}:
            _add_unique(selected_optional, candidate)

    if (
        budget is None
        and pack is not None
        and {
            "target_tokens",
            "max_tokens",
        }.issubset(pack.budget)
    ):
        context_budget = ContextBudget(
            name=pack.id,
            target_tokens=pack.budget["target_tokens"],
            max_tokens=pack.budget["max_tokens"],
        )
    else:
        context_budget = budget_for(budget, manifest.context.default_budget)
    required_tokens = sum(item.estimated_tokens for item in selected_required)
    optional: list[ContextItem] = []
    total_tokens = required_tokens
    for item in selected_optional:
        if total_tokens + item.estimated_tokens > context_budget.target_tokens:
            break
        optional.append(item)
        total_tokens += item.estimated_tokens

    excluded = list(
        dict.fromkeys(
            (task_map.usually_dont_touch if task_map else []) + (pack.exclude if pack else [])
        )
    )
    selected_ids = ",".join(item.id for item in selected_required + optional)
    identifier = hashlib.sha256(
        f"{intent}|{profile}|{context_budget.name}|{selected_ids}".encode()
    ).hexdigest()[:12]
    levels = {
        "L0": [
            item.id for item in selected_required if item.path in {"AGENTS.md", "docs/ATLAS.md"}
        ],
        "L1": [task_map.id] if task_map else [],
        "L2": [
            item.id
            for item in selected_required + optional
            if item.path not in {"AGENTS.md", "docs/ATLAS.md"}
        ],
        "L3": [],
    }
    stop_condition = ["contracts-located", "implementation-surface-known", "tests-known"]
    if required_tokens > context_budget.max_tokens:
        stop_condition.append("required-context-exceeds-budget")
    return ContextPlan(
        id=f"CTXPLAN-{identifier}",
        intent=intent,
        profile=profile,
        risk=task_map.risk if task_map else "low",
        budget=context_budget,
        estimated_tokens=total_tokens,
        required=selected_required,
        optional=optional,
        excluded=excluded,
        levels=levels,
        stop_condition=stop_condition,
        explanations={item.id: item.reason for item in selected_required + optional},
    )


def changed_files(root: Path) -> list[str]:
    """Read changed paths without executing project code."""

    commands = (
        ["git", "diff", "--name-only", "HEAD", "--"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    paths: set[str] = set()
    for command in commands:
        try:
            result = subprocess.run(
                command, cwd=root, check=True, capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.SubprocessError):
            continue
        paths.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(paths)


def analyze_impact(root: Path, paths: list[str] | None = None) -> ImpactReport:
    """Find documentation and graph neighbors affected by changed paths."""

    _, documents_list, registry, graph = load_project_index(root)
    changed = sorted(set(paths or changed_files(root)))
    read: dict[tuple[str, str], ImpactItem] = {}
    possible: dict[tuple[str, str], ImpactItem] = {}
    doc_by_id = {entry.id: entry for entry in registry}
    path_to_id = {entry.path: entry.id for entry in registry}

    for changed_path in changed:
        changed_id = path_to_id.get(changed_path)
        if changed_id:
            entry = doc_by_id[changed_id]
            read[(entry.path, "direct")] = ImpactItem(entry.path, "changed document", "direct")
            for edge in graph.edges:
                if edge.source == changed_id or edge.target == changed_id:
                    neighbor = doc_by_id.get(
                        edge.target if edge.source == changed_id else edge.source
                    )
                    if neighbor:
                        possible[(neighbor.path, edge.relation)] = ImpactItem(
                            neighbor.path, f"graph relation: {edge.relation}", edge.relation
                        )
        stem = Path(changed_path).stem.lower()
        for document in documents_list:
            if changed_path in document.body or (stem and stem in document.body.lower()):
                possible[(document.relative_path, "text")] = ImpactItem(
                    document.relative_path, f"mentions {changed_path}", "text"
                )

    for key in list(read):
        possible.pop(key, None)
    risk = "high" if len(changed) > 10 else "medium" if changed else "low"
    warnings = ["No changed paths detected."] if not changed else []
    return ImpactReport(
        changed,
        risk,
        sorted(read.values(), key=lambda item: item.path),
        sorted(possible.values(), key=lambda item: item.path),
        warnings,
    )


def format_context_plan(plan: ContextPlan) -> str:
    lines = [
        f"Intent: {plan.intent}",
        f"Risk: {plan.risk.upper()}",
        f"Budget: {plan.budget.target_tokens} target / {plan.budget.max_tokens} max",
        f"Estimated context: {plan.estimated_tokens} tokens (heuristic)",
        "",
        "Required:",
    ]
    lines.extend(f"- {item.path or item.id} — {item.reason}" for item in plan.required)
    lines.append("Optional:")
    lines.extend(f"- {item.path or item.id} — {item.reason}" for item in plan.optional)
    lines.append(f"Excluded: {', '.join(plan.excluded) if plan.excluded else 'none'}")
    lines.append(f"Stop condition: {', '.join(plan.stop_condition)}")
    return "\n".join(lines)
