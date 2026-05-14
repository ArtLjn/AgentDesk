"""核心模块：统一导出异常处理基础设施。

包含 retry 装饰器、降级注册表和异常层次定义。
"""

from src.multi_agent_system.core.exceptions import (
    FallbackExhaustedError,
    NonRetryableError,
    RetryableError,
)
from src.multi_agent_system.core.fallback import FallbackRegistry
from src.multi_agent_system.core.retry import with_retry

__all__ = [
    "with_retry",
    "FallbackRegistry",
    "RetryableError",
    "NonRetryableError",
    "FallbackExhaustedError",
]
