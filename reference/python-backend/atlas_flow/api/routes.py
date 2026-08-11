"""HTTP routes backing the desktop modes (P06).

Every endpoint here reads real state: runs, tasks, attempts, events and
evidence come from the operational database, Goals and documentation come from
Git. Nothing on this surface is synthesized for display.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from atlas_flow.api.schemas import (
    AdaptationApplyRequest,
    AdaptationApplyView,
    AdaptationPreviewView,
    AttemptView,
    ConfigSourceView,
    CreatePlanRequest,
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
    PlanView,
    ProjectFileContent,
    ProjectFileView,
    ProjectInspectionView,
    ProviderView,
    RoleRouteView,
    RoutingView,
    RunDetail,
    RunView,
    SettingsDocumentView,
    SettingsPatchRequest,
    SettingsResetRequest,
    SettingsSaveResponse,
    SettingsValidateRequest,
    SettingView,
    TaskView,
)
from atlas_flow.discuss.finalize import FinalizationPipeline
from atlas_flow.discuss.ledger import DecisionLedger
from atlas_flow.discuss.models import (
    DecisionCandidate,
    DiscussionSession,
    Message,
    MessageReference,
    ReferenceKind,
)
from atlas_flow.discuss.store import DiscussionStore
from atlas_flow.execution.cancellation import CancellationRegistry
from atlas_flow.execution.goal_runner import GoalRunner
from atlas_flow.execution.models import RunState, can_transition
from atlas_flow.execution.persistence import Persistence
from atlas_flow.execution.plans import PlanRecord, PlanState, PlanTask
from atlas_flow.goals.loader import resolve_project
from atlas_flow.goals.models import Goal
from atlas_flow.planner.dag import Plan, TaskNode
from atlas_flow.project.adaptation import (
    AdaptationError,
    apply_adaptation,
    preview_adaptation,
)
from atlas_flow.project.inspection import ProjectInspection, inspect_project
from atlas_flow.routing.discovery import ModelRegistry
from atlas_flow.routing.router import ModelRouter
from atlas_flow.routing.store import RoutingStore
from atlas_flow.security.guard import SecurityError, SecurityGuard
from atlas_flow.settings import (
    ConfigScope,
    SettingsError,
    apply_settings,
    inspect_mcp,
    load_settings,
    reset_settings,
)
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


def _inspection(request: Request) -> ProjectInspection:
    return inspect_project(_root(request))


def _require_capability(request: Request, capability: str) -> None:
    inspection = _inspection(request)
    if not getattr(inspection.capabilities, capability):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Project is {inspection.mode}; {capability} is unavailable. "
                f"{inspection.reason} {inspection.recommendation}"
            ),
        )


def _goals(request: Request) -> dict[str, Goal]:
    _require_capability(request, "can_plan")
    context = resolve_project(_root(request))
    return {
        goal.id: goal for phase in context.phases for goal in phase.goals
    }


@router.get("/project/inspection")
def get_project_inspection(request: Request) -> ProjectInspectionView:
    return ProjectInspectionView.of(_inspection(request))


def _settings_document(request: Request) -> SettingsDocumentView:
    root = _root(request)
    config = request.app.state.config
    views = load_settings(root)
    settings = [
        SettingView(
            key=view.key,
            value=view.value,
            default=view.default,
            source=ConfigSourceView(
                value=view.source,
                scope=view.scope,
                environment_variable=view.environment_variable,
            ),
            restart_required=view.restart_required,
            applies_to=view.applies_to,
            description=view.description,
            kind=view.kind,
        )
        for view in views.values()
    ]
    providers = [
        ProviderView(
            key=entry.key,
            provider=entry.provider,
            command_code_id=entry.command_code_id,
            priority=entry.priority,
            availability=entry.availability,
            credential_ref=config.provider_credential_refs.get(entry.provider),
            credential_configured=bool(
                config.provider_credential_refs.get(entry.provider)
                and os.environ.get(config.provider_credential_refs[entry.provider])
            ),
        )
        for entry in request.app.state.router.ROSTER
    ]
    inspection = _inspection(request)
    return SettingsDocumentView(
        settings=settings,
        providers=providers,
        mcp=inspect_mcp(root, config),
        diagnostics={
            "projectRoot": str(root),
            "projectId": config.project_id,
            "projectMode": inspection.mode,
            "engineUrl": os.environ.get("ATLAS_FLOW_API", "http://localhost:8000"),
            "databasePath": str(config.database_path),
            "runners": request.app.state.harness.runners(),
            "registryState": request.app.state.registry.current.state,
            "registryReason": request.app.state.registry.current.reason,
        },
    )


@router.get("/settings")
def get_settings(request: Request) -> SettingsDocumentView:
    return _settings_document(request)


@router.post("/settings/validate")
def validate_settings(
    body: SettingsValidateRequest, request: Request
) -> SettingsDocumentView:
    try:
        scope = ConfigScope(body.scope)
        current = load_settings(_root(request))
        for key in body.values:
            if key not in current:
                raise SettingsError(f"Unknown setting: {key}")
            if current[key].source.value == "environment":
                raise SettingsError(
                    f"{key} is controlled by {current[key].environment_variable}"
                )
        # apply_settings performs the same type validation but is not called:
        # validation must not write files.
        from atlas_flow.settings import PROJECT_KEYS, USER_KEYS, _validate_value
        allowed = USER_KEYS if scope == ConfigScope.USER else PROJECT_KEYS
        invalid = sorted(set(body.values) - allowed)
        if invalid:
            raise SettingsError(f"Settings cannot be written in {scope}: {', '.join(invalid)}")
        for key, value in body.values.items():
            _validate_value(current[key].kind, key, value)
    except (ValueError, SettingsError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _settings_document(request)


@router.put("/settings")
def save_settings(
    body: SettingsPatchRequest, request: Request
) -> SettingsSaveResponse:
    try:
        scope = ConfigScope(body.scope)
        before = load_settings(_root(request))
        after = apply_settings(_root(request), body.values, scope)
    except (ValueError, SettingsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    document = _settings_document(request)
    changed = [key for key in body.values if before[key].value != after[key].value]
    restart = [key for key in changed if after[key].restart_required]
    return SettingsSaveResponse(
        **document.model_dump(),
        changed=changed,
        written_paths=[],
    ).model_copy(
        update={
            "restart_required": bool(restart),
            "restart_reason": (
                "Restart the engine to apply: " + ", ".join(restart) if restart else None
            ),
        }
    )


@router.post("/settings/reset")
def reset_settings_route(
    body: SettingsResetRequest, request: Request
) -> SettingsDocumentView:
    try:
        reset_settings(_root(request), body.keys, ConfigScope(body.scope))
    except (ValueError, SettingsError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _settings_document(request)


@router.post("/settings/mcp/validate")
def validate_settings_mcp(request: Request) -> dict[str, object]:
    return inspect_mcp(_root(request), request.app.state.config)


@router.get("/project/files")
def list_project_files(request: Request) -> list[ProjectFileView]:
    _require_capability(request, "can_explore")
    root = _root(request).resolve()
    ignored = {".git", ".atlas-flow", "node_modules", "dist", "build", "target"}
    files: list[ProjectFileView] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if (
            not path.is_file()
            or path.is_symlink()
            or any(part in ignored for part in relative.parts)
            or path.name in {".env", ".env.local", ".envrc"}
        ):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        kind = "binary" if _looks_binary(path) else "text"
        files.append(ProjectFileView(path=str(relative), kind=kind, size=size))
        if len(files) >= 500:
            break
    return files


@router.get("/project/files/{file_path:path}")
def get_project_file(file_path: str, request: Request) -> ProjectFileContent:
    _require_capability(request, "can_explore")
    root = _root(request).resolve()
    try:
        target = SecurityGuard.validate_path(root, file_path)
    except SecurityError as exc:
        raise HTTPException(status_code=404, detail="Unknown project file") from exc
    if (
        not target.is_file()
        or target.is_symlink()
        or target.name in {".env", ".env.local", ".envrc"}
        or any(
            part in {".git", ".atlas-flow", "node_modules", "dist", "build", "target"}
            for part in target.relative_to(root).parts
        )
    ):
        raise HTTPException(status_code=404, detail="Unknown project file")
    if _looks_binary(target):
        raise HTTPException(status_code=415, detail="Binary project files are not previewed")
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Could not read project file") from exc
    max_bytes = 512_000
    return ProjectFileContent(
        path=file_path,
        content=raw[:max_bytes].decode("utf-8", errors="replace"),
        truncated=len(raw) > max_bytes,
    )


@router.post("/project/adaptation/preview")
def get_adaptation_preview(request: Request) -> AdaptationPreviewView:
    inspection = _inspection(request)
    return AdaptationPreviewView.of(preview_adaptation(_root(request), inspection))


@router.post("/project/adaptation/apply")
def apply_project_adaptation(
    body: AdaptationApplyRequest, request: Request
) -> AdaptationApplyView:
    inspection = _inspection(request)
    try:
        written = apply_adaptation(_root(request), inspection, body.paths)
    except AdaptationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    refreshed = _inspection(request)
    return AdaptationApplyView(
        written=written,
        inspection=ProjectInspectionView.of(refreshed),
    )


@router.get("/goals")
def list_goals(request: Request) -> list[GoalView]:
    inspection = _inspection(request)
    if not inspection.capabilities.can_plan:
        return []
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


@router.post("/goals/{goal_id}/plans", status_code=201)
async def create_plan(
    goal_id: str, body: CreatePlanRequest, request: Request
) -> PlanView:
    _require_capability(request, "can_plan")
    goal = _goals(request).get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Unknown Goal: {goal_id}")
    if request.app.state.harness.resolve(body.runner) is None:
        raise HTTPException(status_code=400, detail=f"Unknown runner '{body.runner}'")

    plan = plan_for_goal(goal)
    record = PlanRecord(
        project_id=request.app.state.config.project_id,
        goal_id=goal.id,
        goal_revision=goal.id,
        autonomy=body.autonomy,
        runner=body.runner,
        integration_target=body.integration_target,
        tasks=[PlanTask.of(task) for task in plan.tasks],
    )
    await _db(request).save_plan(record)
    return PlanView.of(record)


@router.get("/goals/{goal_id}/plans")
async def list_goal_plans(goal_id: str, request: Request) -> list[PlanView]:
    _require_capability(request, "can_plan")
    if goal_id not in _goals(request):
        raise HTTPException(status_code=404, detail=f"Unknown Goal: {goal_id}")
    return [PlanView.of(plan) for plan in await _db(request).list_plans(goal_id)]


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, request: Request) -> PlanView:
    _require_capability(request, "can_plan")
    plan = await _db(request).load_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan: {plan_id}")
    return PlanView.of(plan)


@router.post("/plans/{plan_id}/lock")
async def lock_plan(plan_id: str, request: Request) -> PlanView:
    _require_capability(request, "can_plan")
    plan = await _db(request).load_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Unknown plan: {plan_id}")
    if plan.state != PlanState.DRAFT:
        raise HTTPException(status_code=409, detail=f"Plan {plan_id} is already {plan.state}")
    locked = plan.model_copy(update={"state": PlanState.LOCKED})
    await _db(request).save_plan(locked)
    return PlanView.of(locked)


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
    _require_capability(request, "can_run")
    goal = _goals(request).get(body.goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Unknown Goal: {body.goal_id}")

    harness = request.app.state.harness
    plan_record = None
    if body.plan_id is not None:
        plan_record = await _db(request).load_plan(body.plan_id)
        if plan_record is None:
            raise HTTPException(status_code=404, detail=f"Unknown plan: {body.plan_id}")
        if plan_record.state != PlanState.LOCKED:
            raise HTTPException(
                status_code=409,
                detail=f"Plan {body.plan_id} must be LOCKED before execution",
            )
        if plan_record.goal_id != goal.id or plan_record.goal_revision != goal.id:
            raise HTTPException(
                status_code=409, detail="Plan does not match the current Goal revision"
            )
        if (
            body.runner != plan_record.runner
            or body.integration_target != plan_record.integration_target
        ):
            raise HTTPException(
                status_code=409, detail="Run settings do not match the locked plan"
            )
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
    plan = plan_for_goal(goal) if plan_record is None else plan_record.to_plan()

    task = asyncio.create_task(
        runner.execute(plan, goal_revision=goal.id, runner_name=body.runner,
                       integration_target=body.integration_target)
    )
    request.app.state.background.add(task)
    task.add_done_callback(request.app.state.background.discard)
    if plan_record is not None:
        await _db(request).save_plan(plan_record.model_copy(update={"state": PlanState.CONSUMED}))

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

    references = [
        _validate_message_reference(_root(request), reference)
        for reference in body.references
    ]
    message = Message(
        content=body.content,
        turn_type=body.turn_type,
        references=references,
    )
    await store.save_message(session_id, message)
    return message


def _validate_message_reference(root: Path, reference: MessageReference) -> MessageReference:
    """Keep references project-local and derive binary image references safely."""
    try:
        target = SecurityGuard.validate_path(root, reference.path)
    except SecurityError as exc:
        raise HTTPException(status_code=422, detail="Reference path escapes the project") from exc
    if not target.is_file() or target.is_symlink():
        raise HTTPException(
            status_code=422,
            detail=f"Reference is not a project file: {reference.path}",
        )
    kind = reference.kind
    if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        kind = ReferenceKind.IMAGE
    return reference.model_copy(update={"kind": kind, "label": reference.label or target.name})


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
    _require_capability(request, "can_plan")
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


def _looks_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    return 0 in sample
