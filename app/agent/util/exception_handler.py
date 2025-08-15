import asyncio
from functools import wraps
from logging import Logger

from langgraph.errors import GraphInterrupt


def safe_raise_exception_node(logger: Logger | None = None, ignore_exception: bool = False):
    """
    可以安全的抛出异常的节点，异常会被捕获，返回特定的state通道数据，外层主图会统一处理异常
    Params:
        logger: 一般传递触发异常的类定义的logger
        ignore_exception: 完全忽略异常的节点，当出现异常时可以当做没有这个节点，一般用于旁路节点，比如读取、写入缓存等不影响流程的节点
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if isinstance(e, GraphInterrupt):
                    raise
                if logger:
                    logger.exception("LangGraph Node execute error", exc_info=e)
                return {} if ignore_exception else {"unexpected_error": e}

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if isinstance(e, GraphInterrupt):
                    raise
                if logger:
                    logger.exception("LangGraph Node execute error", exc_info=e)
                return {} if ignore_exception else {"unexpected_error": e}

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator