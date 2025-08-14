import asyncio
from functools import wraps
from logging import Logger

from langgraph.types import Command
from langgraph.graph import END


def safe_node(logger: Logger | None = None, continue_current_graph: bool = False):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if logger:
                    logger.exception("LangGraph Node execute error", exc_info=e)
                return {"unexpected_error": e}

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if logger:
                    logger.exception("LangGraph Node execute error", exc_info=e)
                return {"unexpected_error": e}

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator