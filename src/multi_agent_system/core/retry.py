"""带指数退避的异步重试装饰器。

提供 @with_retry 装饰器，支持：
- 指数退避等待（backoff_base ** attempt）
- 可重试/不可重试异常分类
- 可选降级回调函数
- loguru 日志记录
"""

import asyncio
import functools
from typing import Any, Callable, ParamSpec, TypeVar, cast

from loguru import logger

from src.multi_agent_system.core.exceptions import (
    FallbackExhaustedError,
    NonRetryableError,
    RetryableError,
)

__all__ = ["with_retry"]

P = ParamSpec("P")
R = TypeVar("R")

# 默认最大重试次数
_DEFAULT_MAX_RETRIES = 3

# 默认退避基数（秒），等待时间 = backoff_base ** attempt
_DEFAULT_BACKOFF_BASE = 2.0


def with_retry(
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    backoff_base: float = _DEFAULT_BACKOFF_BASE,
    retryable_exceptions: type[RetryableError] | tuple[type[RetryableError], ...] = RetryableError,
    fallback: Callable[..., Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """异步重试装饰器，支持指数退避和降级回调。

    装饰的函数应为 async 函数。重试逻辑：
    1. RetryableError -> 指数退避重试
    2. NonRetryableError -> 跳过重试，尝试降级
    3. 未知异常 -> 视为 NonRetryableError，不重试
    4. 重试耗尽 -> 尝试降级，无降级则抛出 FallbackExhaustedError

    Args:
        max_retries: 最大重试次数（不含首次调用），默认 3
        backoff_base: 退避基数（秒），默认 2.0
        retryable_exceptions: 可重试的异常类型，默认 RetryableError
        fallback: 降级回调函数（同步或异步），接收与被装饰函数相同的参数

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception | None = None

            # 总共尝试 max_retries + 1 次（首次 + 重试）
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    return cast(R, result)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = backoff_base**attempt
                        logger.warning(
                            f"[with_retry] {func.__name__} 第 {attempt + 1} 次失败"
                            f"（可重试），{wait_time:.1f}s 后重试: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(
                            f"[with_retry] {func.__name__} 重试 {max_retries} 次后仍失败: {e}"
                        )
                except NonRetryableError as e:
                    last_exception = e
                    logger.warning(
                        f"[with_retry] {func.__name__} 遇到不可重试异常，跳过重试: {e}"
                    )
                    break
                except Exception as e:
                    # 未知异常视为不可重试
                    last_exception = e
                    logger.warning(
                        f"[with_retry] {func.__name__} 遇到未知异常，跳过重试: {e}"
                    )
                    break

            # 尝试降级回调
            if fallback is not None:
                logger.info(f"[with_retry] {func.__name__} 触发降级回调")
                fallback_result = fallback(*args, **kwargs)
                # 支持异步降级函数
                if asyncio.iscoroutine(fallback_result):
                    return cast(R, await fallback_result)
                return cast(R, fallback_result)

            # 无降级回调，抛出降级耗尽异常
            raise FallbackExhaustedError(
                f"{func.__name__} 重试耗尽且无降级方案",
                cause=last_exception,
            )

        return wrapper

    return decorator
