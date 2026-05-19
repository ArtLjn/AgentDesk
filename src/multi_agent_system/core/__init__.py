"""核心模块：统一导出异常处理基础设施、缓存层和并发执行工具。

包含 retry 装饰器、降级注册表、异常层次定义、结构化日志工具、LLM 缓存和并发执行。
"""

from src.multi_agent_system.core.cache import LLMCache, llm_cache, reset_cache
from src.multi_agent_system.core.cached_client import CachedLLMClient
from src.multi_agent_system.core.concurrent import concurrent_execute, run_with_semaphore
from src.multi_agent_system.core.context_manager import ContextManager
from src.multi_agent_system.core.database import DatabaseManager, get_db_manager, reset_db_manager
from src.multi_agent_system.core.evaluation import EvaluationCollector
from src.multi_agent_system.core.json_parser import parse_json_response
from src.multi_agent_system.core.memory import MemoryManager
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
from src.multi_agent_system.core.agent_metrics import track_agent_execution
from src.multi_agent_system.core.metrics import MetricsCollector, metrics_collector
from src.multi_agent_system.core.retry import with_retry
from src.multi_agent_system.core.tool_base import ToolBase, ToolRegistry

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
    "parse_json_response",
    "ModelRouter",
    "get_model_router",
    "reset_model_router",
    "concurrent_execute",
    "run_with_semaphore",
    "MetricsCollector",
    "metrics_collector",
    "track_agent_execution",
    "DatabaseManager",
    "get_db_manager",
    "reset_db_manager",
    "ToolBase",
    "ToolRegistry",
    "MemoryManager",
    "ContextManager",
    "EvaluationCollector",
]
