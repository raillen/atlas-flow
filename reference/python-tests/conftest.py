"""Shared test fixtures."""

from collections.abc import AsyncIterator

import pytest_asyncio

from atlas_flow.execution.persistence import Persistence


@pytest_asyncio.fixture
async def db() -> AsyncIterator[Persistence]:
    """An initialized in-memory store that is always closed.

    aiosqlite runs each connection on its own thread; leaving one open past
    the end of the event loop raises "Event loop is closed" from that thread
    during garbage collection, which surfaces as an unrelated warning in some
    later test.
    """
    persistence = Persistence(":memory:")
    await persistence.initialize()
    try:
        yield persistence
    finally:
        await persistence.close()
