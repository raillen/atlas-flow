import pytest

from atlas_flow.execution.persistence import Persistence, PersistenceError
from atlas_flow.execution.plans import PlanRecord, PlanState, PlanTask


@pytest.mark.asyncio
async def test_plan_snapshot_can_lock_and_be_consumed_but_not_mutated(db: Persistence) -> None:
    plan = PlanRecord(
        project_id="sample",
        goal_id="P01-G01",
        goal_revision="revision-1",
        tasks=[PlanTask(id="task-1", objective="Do the work")],
    )
    await db.save_plan(plan)

    locked = plan.model_copy(update={"state": PlanState.LOCKED})
    await db.save_plan(locked)
    consumed = locked.model_copy(update={"state": PlanState.CONSUMED})
    await db.save_plan(consumed)

    loaded = await db.load_plan(plan.id)
    assert loaded is not None
    assert loaded.state == PlanState.CONSUMED

    with pytest.raises(PersistenceError, match="immutable"):
        await db.save_plan(consumed.model_copy(update={"runner": "other"}))


@pytest.mark.asyncio
async def test_plan_history_is_scoped_to_goal(db: Persistence) -> None:
    first = PlanRecord(project_id="sample", goal_id="P01-G01", goal_revision="r1")
    second = PlanRecord(project_id="sample", goal_id="P02-G01", goal_revision="r1")
    await db.save_plan(first)
    await db.save_plan(second)

    plans = await db.list_plans("P01-G01")
    assert [item.id for item in plans] == [first.id]
