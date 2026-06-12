"""Shared test plumbing.

Some suites drive async code with `asyncio.run()` (which closes & unsets the
event loop) while older suites rely on `asyncio.get_event_loop()`. Running them
together used to fail with "There is no current event loop in thread
'MainThread'" depending on file order. This autouse fixture guarantees a usable
loop exists before every test, making the suite order-independent.
"""
import asyncio

import pytest


@pytest.fixture(autouse=True)
def _ensure_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    yield
