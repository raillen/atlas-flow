# Planner and Task DAG

Input: locked Goal, context pack, repo graph, Agents/Skills/Recipes, risk/autonomy.

Task node: id, objective, capabilities, dependencies, artifacts, write scope, gates, risk, cost class, parallelizable.

Invariants: acyclic; dependencies complete; parallel mutable branches have explicit integration; overlapping write scopes are not admitted unsafely; plan is reviewable before execution in Controlled/Agentic modes.
