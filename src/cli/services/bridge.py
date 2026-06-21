import asyncio
from typing import Any


class AsyncServiceBridge:
    """Centralized bridge to run coroutines safely without nested loop conflicts."""

    @staticmethod
    def run(coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        else:
            return asyncio.run(coro)
