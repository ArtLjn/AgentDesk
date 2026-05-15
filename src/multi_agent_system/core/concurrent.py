"""异步并发执行工具。

提供 asyncio.gather 封装，支持并发度限制和异常隔离。
每个任务独立执行，某个任务失败不影响其他任务。
"""

import asyncio
from typing import Any, Callable, Coroutine

from loguru import logger

from src.multi_agent_system.core.logging import log_context

__all__ = ["concurrent_execute", "run_with_semaphore"]


async def concurrent_execute(
    tasks: list[tuple[str, Callable[[], Coroutine]]],
    max_concurrency: int = 5,
) -> dict[str, Any]:
    """并发执行多个异步任务，支持并发度限制和异常隔离。

    每个任务独立执行，某个任务失败不影响其他任务。

    Args:
        tasks: 任务列表，每个元素为 (task_name, async_callable) 元组
        max_concurrency: 最大并发数

    Returns:
        结果字典，key 为任务名称，value 为任务结果或异常信息
    """
    if not tasks:
        return {}

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run_task(name: str, func: Callable[[], Coroutine]) -> tuple[str, Any]:
        async with semaphore:
            with log_context(agent=name):
                try:
                    result = await func()
                    logger.debug(f"[concurrent] 任务 {name} 完成")
                    return (name, result)
                except Exception as e:
                    logger.warning(f"[concurrent] 任务 {name} 失败: {e}")
                    return (name, {"error": str(e), "failed": True})

    coroutines = [_run_task(name, func) for name, func in tasks]
    task_results = await asyncio.gather(*coroutines)

    return dict(task_results)


async def run_with_semaphore(
    func: Callable[..., Coroutine],
    semaphore: asyncio.Semaphore,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """在信号量控制下执行异步函数。

    Args:
        func: 异步函数
        semaphore: 信号量
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数返回值
    """
    async with semaphore:
        return await func(*args, **kwargs)
