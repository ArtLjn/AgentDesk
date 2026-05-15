"""结构化日志工具：trace_id 链路追踪 + loguru 上下文绑定。

提供 trace_id 上下文变量、日志上下文管理器和结构化日志工具函数，
用于贯穿整个请求处理链路的结构化日志输出。
"""

import contextvars
import time
from typing import Any, Optional
from uuid import uuid4

from loguru import logger

__all__ = [
    "trace_id_var",
    "log_context",
    "get_trace_id",
    "generate_trace_id",
    "structured_logger",
]

# 全局 trace_id 上下文变量
trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)


def generate_trace_id() -> str:
    """生成唯一 trace_id，格式：随机16位十六进制字符串。"""
    return uuid4().hex[:16]


def get_trace_id() -> Optional[str]:
    """获取当前请求的 trace_id。"""
    return trace_id_var.get()


class log_context:
    """日志上下文管理器，自动绑定 trace_id 和其他元数据。

    示例::

        with log_context(agent="classifier", task="classification"):
            logger.info("处理请求")  # 自动带上 trace_id=xxx agent=classifier
    """

    def __init__(self, **kwargs: Any) -> None:
        self.extra = kwargs
        self.token: Optional[contextvars.Token] = None
        self.start_time: float = 0.0

    def __enter__(self) -> "log_context":
        self.start_time = time.perf_counter()
        # 如果没有 trace_id，自动生成
        if get_trace_id() is None:
            trace_id = generate_trace_id()
            self.token = trace_id_var.set(trace_id)
            self.extra["trace_id"] = trace_id
        else:
            self.extra["trace_id"] = get_trace_id()

        # 绑定额外元数据到 loguru 上下文
        logger.contextualize(**self.extra)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # 计算耗时
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        logger.info(f"执行完成，耗时 {duration_ms:.2f}ms")

        # 恢复 trace_id 上下文
        if self.token is not None:
            trace_id_var.reset(self.token)


def structured_logger(
    message: str, level: str = "INFO", **kwargs: Any
) -> None:
    """结构化日志工具函数，自动带上 trace_id。

    Args:
        message: 日志消息
        level: 日志级别，默认 INFO
        **kwargs: 额外的结构化元数据
    """
    trace_id = get_trace_id()
    extra: dict[str, Any] = {"trace_id": trace_id, **kwargs}
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, **extra)
