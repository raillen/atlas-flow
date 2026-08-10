"""Project Atlas canonical models (P01)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoalGates(BaseModel):
    build: str  # "required" | "optional"
    tests: str
    review: str
    documentation: str


class Goal(BaseModel):
    id: str
    phase: str
    title: str
    state: str  # PLANNED, READY, ACTIVE, BLOCKED, DONE, CANCELLED
    objective: str
    constraints: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    gates: GoalGates
    evidence: list[object] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)


class Phase(BaseModel):
    id: str
    goals: list[Goal] = Field(default_factory=list)


class ProjectProfile(BaseModel):
    id: str
    types: list[str] = Field(alias="type", default_factory=list)
    languages: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    risk: dict[str, str] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class AgentManifest(BaseModel):
    agents: list[str]
    selection_basis: list[str]


class SkillManifest(BaseModel):
    skills: list[str]


class RecipeManifest(BaseModel):
    recipes: list[str]


class ModelPolicyEntry(BaseModel):
    key: str
    provider: str
    command_code_id: str
    priority: str  # "primary" | "efficient-third"
    availability: str  # "expected" | "probe-required"


class ModelPolicy(BaseModel):
    version: int
    development_harness: str
    runtime_discovery: dict[str, object]
    roster: list[ModelPolicyEntry]
    principles: list[str]


class AutonomyPolicy(BaseModel):
    default: str
    modes: dict[str, object]
    project_policy: dict[str, object]


class OrchestratorConfig(BaseModel):
    development: dict[str, object]
    product: dict[str, object]
    protocols: dict[str, object]
    execution: dict[str, object]


class FallbackConfig(BaseModel):
    availability: str
    quality: dict[str, object]
    confidence: dict[str, object]
    human_escalation: list[str]


class ProjectAtlasContext(BaseModel):
    """Complete resolved Project Atlas context."""
    project: ProjectProfile
    phases: list[Phase]
    agents: AgentManifest
    skills: SkillManifest
    recipes: RecipeManifest
    model_policy: ModelPolicy
    autonomy_policy: AutonomyPolicy
    orchestrator: OrchestratorConfig
    fallbacks: FallbackConfig
