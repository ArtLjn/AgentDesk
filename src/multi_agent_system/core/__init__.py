"""核心模块：统一导出异常处理基础设施。

包含 retry 装饰器、降级注册表、异常层次定义和结构化日志工具。
"""

from src.multi_agent_system.core.exceptions import (
    FallbackExhaustedError,
    NonRetryableError,
    RetryableError,
)
from src.multi_agent_system.core.fallback import FallbackRegistry
from src.multi_agent_system.core.logging import (
    generate_trace_id,
    get_trace_id,
    log_context,
    structured_logger,
    trace_id_var,
)
from src.multi_agent_system.core.retry import with_retry

__all__ = [
    "with_retry",
    "FallbackRegistry",
    "RetryableError",
    "NonRetryableError",
    "FallbackExhaustedError",
    "trace_id_var",
    "log_context",
    "get_trace_id",
    "generate_trace_id",
    "structured_logger",
]
