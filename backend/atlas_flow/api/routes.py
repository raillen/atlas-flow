"""HTTP routes backing the desktop modes (P06).

Every endpoint here reads real state: runs, tasks, attempts, events and
evidence come from the operational database, Goals and documentation come from
Git. Nothing on this surface is synthesized for display.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from atlas_flow.api.schemas import (
    AttemptView,
    CreateRunRequest,
    DecisionRequest,
    DocContent,
    DocEntry,
    EventView,
    EvidenceView,
    GateView,
    GoalVerification,
    GoalView,
    MessageRequest,
    ModelStatsView,
    RoleRouteView,
    RoutingView,
    RunDetail,
    RunView,
    TaskView,
)
from atlas_flow.discuss.finalize import FinalizationPipeline
from atlas_flow.discuss.ledger import DecisionLedger
from atlas_flow.discuss.models import DecisionCandidate, DiscussionSession, Message
from atlas_flow.discuss.store import DiscussionStore
from atlas_flow.execution.cancellation import CancellationRegistry
from atlas_flow.execution.goal_runner import GoalRunner
from atlas_flow.execution.models import RunState, can_transition
from atlas_flow.execution.persistence import Persistence
from atlas_flow.goals.loader import resolve_project
from atlas_flow.goals.models import Goal
from atlas_flow.planner.dag import Plan, TaskNode
from atlas_flow.routing.discovery import ModelRegistry
from atlas_flow.routing.router import ModelRouter
from atlas_flow.routing.store import RoutingStore
from atlas_flow.security.guard import SecurityError, SecurityGuard
from atlas_flow.verification.gates import GateCoordinator, GateKind
from atlas_flow.verification.goal_completion import check_completion, required_gates

router = APIRouter(prefix="/api")



DOC_SECTIONS = {
    "00-product": "Product",
    "01-architecture": "Architecture",
    "02-ui-ux": "UI/UX",
    "03-implementation": "Implementation",
    "04-quality": "Quality",
    "05-governance": "Governance",
    "06-user-guide": "User guide",
    "07-decisions": "Decisions",
    "08-rfcs": "RFCs",
    "09-references": "References",
}


def _db(request: Request) -> Persistence:
    persistence: Persistence = request.app.state.persistence
    return persistence


def _root(request: Request) -> Path:
    root: Path = request.app.state.project_root
    return root


def _goals(request: Request) -> dict[str, Goal]:
    context = resolve_project(_root(request))
    return {
        goal.id: goal for phase in context.phases for goal in phase.goals
    }


@router.get("/goals")
def list_goals(request: Request) -> list[GoalView]:
    return [GoalView.of(goal) for goal in _goals(request).values()]


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, request: Request) -> GoalView:
    goal = _goals(request).get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Unknown Goal: {goal_id}")
    return GoalView.of(goal)


@router.get("/goals/{goal_id}/verification")
async def get_goal_verification(goal_id: str, request: Request) -> GoalVerification:
    goal = _goals(request).get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Unknown Goal: {goal_id}")

    coordinator = GateCoordinator(_db(request))
    evidence = await coordinator.load_evidence(goal_id)
    declared = goal.gates.model_dump()

    gates = []
    for name, requirement in declared.items():
        result = coordinator.evaluate_gate(GateKind(name))
        gates.append(
            GateView(
                gate=name,
                requirement=requirement,
                verdict=str(result.verdict),
                evidence_ids=result.evidence_ids,
                details=result.details,
            )
        )

    check = check_completion(goal, evidence)
    return GoalVerification(
        goal_id=goal_id,
        gates=gates,
        evidence=[EvidenceView.of(item) for item in evidence],
        completable=check.completable,
        blocking="" if check.completable else check.describe(),
    )


@router.get("/runs")
async def list_runs(request: Request) -> list[RunView]:
    db = _db(request)
    runs = await db.list_runs()
    views = []
    for run in runs:
        tasks = await db.load_tasks(run.id)
        views.append(RunView.of(run, task_count=len(tasks)))
    return views


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> RunDetail:
    db = _db(request)
    run = await db.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")

    tasks = await db.load_tasks(run_id)
    return RunDetail(
        run=RunView.of(run, task_count=len(tasks)),
        tasks=[TaskView.of(task) for task in tasks],
        attempts=[AttemptView.of(a) for a in await db.load_attempts(run_id)],
        events=[EventView.of(e) for e in await db.load_events(run_id)],
    )


@router.post("/runs/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: str, request: Request) -> RunView:
    """Ask a run to stop, and stop the attempt it has in flight.

    Cooperative: the request is recorded and the runner winds down between
    tasks, so no state change is interrupted between the row and the event that
    explains it. What is not cooperative is the attempt already talking to a
    model — that is cancelled outright, because waiting for it is the thing the
    caller asked to stop.
    """
    db = _db(request)
    run = await db.load_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")

    # Asked of the state machine rather than a list kept alongside it: a run
    # past RUNNING has no path to CANCELLED, and accepting a request that
    # cannot be carried out is worse than refusing it.
    if not can_transition(run.state, RunState.CANCELLED, "run"):
        raise HTTPException(
            status_code=409,
            detail=f"Run {run_id} is {run.state} and cannot be cancelled",
        )

    cancellation: CancellationRegistry = request.app.state.cancellation
    cancellation.request(run_id)

    harness = request.app.state.harness
    for task in await db.load_tasks(run_id):
        await harness.cancel_task(task.id)

    tasks = await db.load_tasks(run_id)
    return RunView.of(run, task_count=len(tasks))


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str, request: Request) -> list[EventView]:
    return [EventView.of(e) for e in await _db(request).load_events(run_id)]


@router.post("/runs", status_code=202)
async def create_run(body: CreateRunRequest, request: Request) -> RunView:
    """Start a run for a Goal and return as soon as it is scheduled.

    Execution continues in the background; the client follows it through the
    event stream rather than holding a request open for the whole run.
    """
    goal = _goals(request).get(body.goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Unknown Goal: {body.goal_id}")

    harness = request.app.state.harness
    if harness.resolve(body.runner) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown runner '{body.runner}'. Available: {harness.runners()}",
        )

    runner = GoalRunner(
        _db(request),
        harness,
        request.app.state.config,
        router=request.app.state.router,
        worktrees=request.app.state.worktrees,
        routing_store=request.app.state.routing_store,
        cancellation=request.app.state.cancellation,
        gate_commands=request.app.state.gate_commands,
    )
    plan = plan_for_goal(goal)

    task = asyncio.create_task(
        runner.execute(plan, goal_revision=goal.id, runner_name=body.runner,
                       integration_target=body.integration_target)
    )
    request.app.state.background.add(task)
    task.add_done_callback(request.app.state.background.discard)

    # The run row exists as soon as execute() has scheduled it; poll briefly so
    # the client gets an id back instead of an empty response.
    for _ in range(50):
        await asyncio.sleep(0.02)
        runs = [r for r in await _db(request).list_runs() if r.goal_id == goal.id]
        if runs:
            return RunView.of(runs[0])

    raise HTTPException(status_code=504, detail="Run did not start in time")


def plan_for_goal(goal: Goal) -> Plan:
    """Derive a task per acceptance criterion.

    This is the deterministic baseline decomposition: one verifiable task per
    thing the Goal says must be true. A model-driven planner can replace it,
    but the contract — every acceptance criterion is owned by a task — is what
    keeps the plan answerable to the Goal.
    """
    return Plan(
        goal_id=goal.id,
        tasks=[
            TaskNode(
                id=f"{goal.id}-t{index}",
                objective=criterion,
                gates=[str(gate) for gate in required_gates(goal)],
            )
            for index, criterion in enumerate(goal.acceptance, start=1)
        ],
    )


@router.get("/routing")
async def get_routing(request: Request) -> RoutingView:
    """What the router can reach, and what past runs learned about it."""
    registry: ModelRegistry = request.app.state.registry
    discovery = registry.current
    store: RoutingStore = request.app.state.routing_store
    model_router: ModelRouter = request.app.state.router

    roles = []
    for role in sorted(ModelRouter.ROLE_DEFAULTS):
        decision = model_router.route(role)
        roles.append(
            RoleRouteView(
                role=role,
                selected=decision.selected.key if decision.selected else None,
                provider=decision.selected.provider if decision.selected else None,
                explanation=model_router.why_this_model(decision),
                fallback_attempts=decision.fallback_attempts,
            )
        )

    return RoutingView(
        state=discovery.state,
        reachable=discovery.reachable,
        degraded=discovery.degraded,
        reason=discovery.reason,
        probed_at=discovery.probed_at,
        available=discovery.available,
        roles=roles,
        stats=[
            ModelStatsView(
                model_key=stat.model_key,
                uses=stat.uses,
                successes=stat.successes,
                failures=stat.failures,
                success_rate=round(stat.success_rate, 3),
                average_latency_ms=round(stat.average_latency_ms, 1),
            )
            for stat in await store.stats()
        ],
    )


@router.get("/runs/{run_id}/routing")
async def get_run_routing(run_id: str, request: Request) -> list[dict[str, object]]:
    """Why each task in this run got the model it got."""
    store: RoutingStore = request.app.state.routing_store
    return await store.decisions_for_run(run_id)


@router.get("/discussions")
async def list_discussions(request: Request) -> list[str]:
    store: DiscussionStore = request.app.state.discussions
    return await store.list_sessions()


@router.post("/discussions", status_code=201)
async def create_discussion(request: Request) -> dict[str, str]:
    store: DiscussionStore = request.app.state.discussions
    session = DiscussionSession(project_id=request.app.state.config.project_id)
    await store.save_session(session)
    return {"session_id": session.id}


@router.get("/discussions/{session_id}")
async def get_discussion(session_id: str, request: Request) -> DiscussionSession:
    store: DiscussionStore = request.app.state.discussions
    session = await store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown discussion: {session_id}")
    return session


@router.post("/discussions/{session_id}/messages", status_code=201)
async def add_message(session_id: str, body: MessageRequest, request: Request) -> Message:
    store: DiscussionStore = request.app.state.discussions
    if await store.load_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown discussion: {session_id}")

    message = Message(content=body.content, turn_type=body.turn_type)
    await store.save_message(session_id, message)
    return message


@router.post("/discussions/{session_id}/decisions", status_code=201)
async def propose_decision(
    session_id: str, body: DecisionRequest, request: Request
) -> DecisionCandidate:
    store: DiscussionStore = request.app.state.discussions
    session = await store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown discussion: {session_id}")

    decision = DecisionCandidate(
        title=body.title,
        statement=body.statement,
        rationale=body.rationale,
        affected_domains=body.affected_domains,
        requires_adr=body.requires_adr,
    )
    DecisionLedger.propose(session, decision)
    await store.save_decision(session_id, decision)
    return decision


@router.post("/discussions/{session_id}/decisions/{decision_id}/accept")
async def accept_decision(
    session_id: str, decision_id: str, request: Request
) -> DecisionCandidate:
    store: DiscussionStore = request.app.state.discussions
    session = await store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown discussion: {session_id}")

    try:
        DecisionLedger.accept(session, decision_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        # The decision exists but has already been resolved; that is a conflict
        # with its current state, not a missing resource.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    decision = next(d for d in session.decisions if d.id == decision_id)
    await store.save_decision(session_id, decision)
    return decision


@router.post("/discussions/{session_id}/finalize")
async def finalize_discussion(
    session_id: str, request: Request, overwrite: bool = False
) -> dict[str, object]:
    """Write the discussion's accepted decisions into the project's docs."""
    store: DiscussionStore = request.app.state.discussions
    session = await store.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown discussion: {session_id}")

    report = FinalizationPipeline.analyze(session)
    if not report.ready:
        raise HTTPException(
            status_code=409,
            detail=report.summary(),
        )

    result = FinalizationPipeline.write_artifacts(
        session, _root(request), overwrite=overwrite
    )
    return {
        "written": result.paths,
        "adr_count": result.adr_count,
        "summary": report.summary(),
    }


@router.get("/docs")
def list_docs(request: Request) -> list[DocEntry]:
    root = _root(request) / "docs"
    entries: list[DocEntry] = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        section = relative.parts[0] if len(relative.parts) > 1 else "root"
        entries.append(
            DocEntry(
                path=str(relative),
                title=_title_of(path),
                section=DOC_SECTIONS.get(section, section),
            )
        )
    return entries


@router.get("/docs/{doc_path:path}")
def get_doc(doc_path: str, request: Request) -> DocContent:
    root = (_root(request) / "docs").resolve()

    # One traversal guard for the whole runtime, so there is one place to get
    # right and one place to test.
    try:
        target = SecurityGuard.validate_path(root, doc_path)
    except SecurityError as exc:
        raise HTTPException(
            status_code=404, detail=f"Unknown document: {doc_path}"
        ) from exc

    if target.suffix != ".md" or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Unknown document: {doc_path}")

    return DocContent(path=doc_path, content=target.read_text(encoding="utf-8"))


def _title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem
