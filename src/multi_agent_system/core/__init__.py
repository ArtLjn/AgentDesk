"""核心模块：统一导出异常处理基础设施和缓存层。

包含 retry 装饰器、降级注册表、异常层次定义、结构化日志工具和 LLM 缓存。
"""

from src.multi_agent_system.core.cache import LLMCache, llm_cache, reset_cache
from src.multi_agent_system.core.cached_client import CachedLLMClient
from src.multi_agent_system.core.model_router import (
    ModelRouter,
    get_model_router,
    reset_model_router,
)
from src.multi_agent_system.core.exceptions import (
    FallbackExhaustedError,
    NonRetryableError,
    RetryableError,
)
from src.multi_agent_system.core.fallback import FallbackRegistry, fallback_registry
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
    "fallback_registry",
    "RetryableError",
    "NonRetryableError",
    "FallbackExhaustedError",
    "trace_id_var",
    "log_context",
    "get_trace_id",
    "generate_trace_id",
    "structured_logger",
    "LLMCache",
    "llm_cache",
    "reset_cache",
    "CachedLLMClient",
    "ModelRouter",
    "get_model_router",
    "reset_model_router",
]
