"""Versioned data contracts for the Atlas Flow v2 foundation.

The models in this module describe canonical inputs and derived projections.
They deliberately contain no provider-specific behavior and can be serialized
to JSON/YAML by the CLI and future adapters.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1


class StrictModel(BaseModel):
    """Reject accidental contract drift while allowing model defaults."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DocumentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    REVIEW_NEEDED = "review-needed"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class DocumentMetadata(StrictModel):
    schema_version: int = SCHEMA_VERSION
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: DocumentStatus = DocumentStatus.ACTIVE
    version: int = Field(default=1, ge=1)
    audience: list[str] = Field(default_factory=list)
    visibility: Literal["public", "internal", "private"] = "internal"
    authority: Literal["canonical", "derived", "informative"] = "canonical"
    source: Literal["human", "code", "generated", "external"] = "human"
    owner: str | None = None
    last_reviewed: date | None = None
    review_interval: str = "180d"
    estimated_tokens: int | None = Field(default=None, ge=0)
    risk: Literal["low", "medium", "high", "critical"] = "low"
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    section: str | None = None
    category: str | None = None
    order: int = 0


class ProjectAtlasConfig(StrictModel):
    docs_root: str = "docs"
    data_root: str = ".atlas"


class ProjectDocumentationConfig(StrictModel):
    title: str = "Project documentation"
    default_visibility: Literal["public", "internal", "private"] = "internal"


class ProjectPublishingConfig(StrictModel):
    public: list[str] = Field(default_factory=list)
    internal: list[str] = Field(default_factory=list)
    private: list[str] = Field(default_factory=list)


class ProjectIntelligenceConfig(StrictModel):
    enabled: bool = True
    dashboard: bool = True


class ProjectContextConfig(StrictModel):
    default_budget: Literal["small", "medium", "large"] = "medium"


class ProjectManifest(StrictModel):
    schema_version: int = 2
    project: dict[str, str] = Field(default_factory=dict)
    atlas: ProjectAtlasConfig = Field(default_factory=ProjectAtlasConfig)
    documentation: ProjectDocumentationConfig = Field(default_factory=ProjectDocumentationConfig)
    publishing: ProjectPublishingConfig = Field(default_factory=ProjectPublishingConfig)
    intelligence: ProjectIntelligenceConfig = Field(default_factory=ProjectIntelligenceConfig)
    context: ProjectContextConfig = Field(default_factory=ProjectContextConfig)


class RegistryEntry(StrictModel):
    schema_version: int = SCHEMA_VERSION
    id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    title: str = Field(min_length=1)
    section: str
    category: str | None = None
    visibility: Literal["public", "internal", "private"]
    authority: Literal["canonical", "derived", "informative"]
    status: DocumentStatus
    estimated_tokens: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)


class GraphNode(StrictModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    path: str | None = None
    title: str | None = None
    visibility: Literal["public", "internal", "private"] | None = None


class GraphEdge(StrictModel):
    source: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    target: str = Field(min_length=1)


class KnowledgeGraph(StrictModel):
    schema_version: int = SCHEMA_VERSION
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class TaskMapReads(StrictModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class TaskMap(StrictModel):
    schema_version: int = SCHEMA_VERSION
    id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    risk: Literal["low", "medium", "high", "critical"] = "low"
    read: TaskMapReads = Field(default_factory=TaskMapReads)
    touch: dict[str, list[str]] = Field(default_factory=dict)
    usually_dont_touch: list[str] = Field(default_factory=list)
    verify: list[str] = Field(default_factory=list)
    documentation: list[str] = Field(default_factory=list)


class ContextPack(StrictModel):
    schema_version: int = SCHEMA_VERSION
    id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    include: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    budget: dict[str, int] = Field(default_factory=dict)
    justifications: dict[str, str] = Field(default_factory=dict)


class ContextBudget(StrictModel):
    name: str
    target_tokens: int = Field(gt=0)
    max_tokens: int = Field(gt=0)

    @model_validator(mode="after")
    def max_covers_target(self) -> ContextBudget:
        if self.max_tokens < self.target_tokens:
            raise ValueError("max_tokens must be greater than or equal to target_tokens")
        return self


class ContextItem(StrictModel):
    id: str
    path: str | None = None
    reason: str
    estimated_tokens: int = Field(ge=0)
    required: bool = False


class ContextPlan(StrictModel):
    schema_version: int = SCHEMA_VERSION
    id: str
    intent: str
    profile: str = "implementer"
    risk: str = "low"
    budget: ContextBudget
    estimated_tokens: int = Field(ge=0)
    required: list[ContextItem] = Field(default_factory=list)
    optional: list[ContextItem] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    levels: dict[str, list[str]] = Field(default_factory=dict)
    stop_condition: list[str] = Field(default_factory=list)
    explanations: dict[str, str] = Field(default_factory=dict)


class TokenUsage(StrictModel):
    input: int = Field(default=0, ge=0)
    output: int = Field(default=0, ge=0)
    cached: int = Field(default=0, ge=0)
    avoided_estimate: int = Field(default=0, ge=0)


class CostRange(StrictModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)

    @model_validator(mode="after")
    def max_covers_min(self) -> CostRange:
        if self.max < self.min:
            raise ValueError("max must be greater than or equal to min")
        return self


class TaskCostRecord(StrictModel):
    schema_version: int = SCHEMA_VERSION
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    task_type: str = "unknown"
    components: list[str] = Field(default_factory=list)
    release: str | None = None
    date_started: str | None = None
    date_finished: str | None = None
    complexity: str = "unknown"
    risk: str = "unknown"
    estimate: CostRange | None = None
    observed_tokens: TokenUsage = Field(default_factory=TokenUsage)
    observed_cost_usd: float | None = Field(default=None, ge=0)
    cost_source: Literal["provider_usage", "calculated", "estimated", "allocated", "unknown"] = (
        "unknown"
    )
    billing_mode: Literal["api", "subscription", "free", "local", "unknown"] = "unknown"
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    changes: dict[str, int] = Field(default_factory=dict)
    result: dict[str, int] = Field(default_factory=dict)
    maintenance_cost_score: int | None = Field(default=None, ge=1, le=10)


class DebtRecord(StrictModel):
    schema_version: int = SCHEMA_VERSION
    id: str = Field(min_length=1)
    introduced_by: str | None = None
    component: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: Literal["low", "medium", "high", "critical"]
    remediation_hours: CostRange | None = None
    status: Literal["open", "in-progress", "closed"] = "open"
    owner: str | None = None


class ProjectSummary(StrictModel):
    schema_version: int = SCHEMA_VERSION
    project: str
    period: str = "all-time"
    tasks_completed: int = Field(ge=0)
    tokens: TokenUsage
    estimated_total_usd: CostRange | None = None
    observed_api_usd: float | None = Field(default=None, ge=0)
    documentation_coverage: float | None = Field(default=None, ge=0, le=1)
    technical_debt_open_items: int = Field(default=0, ge=0)
    cost_by_component: dict[str, float] = Field(default_factory=dict)
