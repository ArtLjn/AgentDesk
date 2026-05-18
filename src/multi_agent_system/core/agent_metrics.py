"""Agent 执行指标装饰器。

为 Agent 的公共方法自动记录执行次数和耗时。
"""

import functools
import time
from typing import Any, Callable, ParamSpec, TypeVar

from loguru import logger

__all__ = ["track_agent_execution"]

P = ParamSpec("P")
R = TypeVar("R")


def track_agent_execution(agent_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """装饰器：记录 Agent 方法执行次数和耗时。

    Args:
        agent_name: Agent 名称（如 classifier、processor、reviewer）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            from src.multi_agent_system.core.metrics import metrics_collector

            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result  # type: ignore[no-any-return]
            finally:
                duration = time.time() - start
                metrics_collector.record_agent_execution(agent_name, duration)
                logger.debug(f"[Metrics] {agent_name}.{func.__name__} 耗时 {duration:.3f}s")

        return wrapper  # type: ignore[return-value]

    return decorator
