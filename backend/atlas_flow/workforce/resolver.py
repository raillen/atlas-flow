"""Workforce Resolver — Agent/Skill/Recipe/Model/Runner resolution (GAP-03)."""

from dataclasses import dataclass, field

from atlas_flow.goals.models import AgentManifest, RecipeManifest, SkillManifest


@dataclass
class ResolvedAgent:
    name: str
    skills: list[str] = field(default_factory=list)


@dataclass
class ResolvedWorkforce:
    agents: list[ResolvedAgent] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    recipes: list[str] = field(default_factory=list)
    selected_agent: str | None = None
    selected_model: str | None = None
    runner: str | None = None


class WorkforceResolver:
    """Resolves Agent/Skill/Recipe/Model/Runner against Project Atlas registries."""

    @staticmethod
    def resolve_for_role(
        role: str,
        agents: AgentManifest,
        skills: SkillManifest,
        recipes: RecipeManifest,
        risk: str = "medium",
    ) -> ResolvedWorkforce:
        """Select agent, its skills, and relevant recipes for a role."""

        # Agent selection by role name match
        agent_name = role if role in agents.agents else agents.agents[0]

        # Skills: all registered skills for now (progressive disclosure is post-MVP)
        resolved_skills = list(skills.skills)

        # Recipes: select matching recipes
        role_recipes = _select_recipes_for_role(role, recipes)

        return ResolvedWorkforce(
            agents=[ResolvedAgent(name=agent_name, skills=resolved_skills)],
            skills=resolved_skills,
            recipes=role_recipes,
            selected_agent=agent_name,
        )

    @staticmethod
    def skills_for_task(
        task_capabilities: list[str], skills_manifest: SkillManifest
    ) -> list[str]:
        """Match task required capabilities to registered skills."""
        return [s for s in skills_manifest.skills if _skill_matches(s, task_capabilities)]


def _select_recipes_for_role(role: str, recipes: RecipeManifest) -> list[str]:
    recipe_map: dict[str, list[str]] = {
        "goal-planner": ["locked-goal-implementation"],
        "core-implementer": ["locked-goal-implementation", "high-risk-feature"],
        "ui-engineer": ["locked-goal-implementation"],
        "protocol-engineer": ["protocol-change"],
        "release-verifier": ["release-candidate"],
        "chief-architect": ["locked-goal-implementation", "high-risk-feature", "protocol-change"],
    }
    return recipe_map.get(role, recipes.recipes)


def _skill_matches(skill: str, capabilities: list[str]) -> bool:
    """Check if a skill name suggests capability overlap."""
    mapping = {
        "goal-contracts": ["goal_execution", "gates"],
        "dag-planning": ["planning", "dag"],
        "model-routing": ["routing", "model_selection"],
        "acp-integration": ["acp", "agent_session"],
        "ag-ui-integration": ["ag_ui", "ui_events"],
        "mcp-integration": ["mcp", "tools"],
        "command-code-execution": ["cli", "headless"],
        "worktree-isolation": ["worktree", "git"],
        "evidence-gates": ["verification", "evidence"],
        "fault-injection": ["testing", "reliability"],
        "desktop-accessibility": ["accessibility", "a11y"],
        "docs-maintenance": ["documentation"],
        "context-packing": ["context", "knowledge_graph"],
        "decision-ledger": ["decisions"],
        "atlas-navigation": ["atlas", "navigation"],
    }
    expected = mapping.get(skill, [])
    return any(c in capabilities for c in expected)
