"""性能指标收集器。

提供请求延迟、吞吐量、错误率等指标的收集和查询功能。
同时集成 prometheus_client，暴露标准 Prometheus 指标。
"""

import time
from collections import deque
from typing import Any

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

# ──────────────────────────────────────────────────────────────
# Prometheus 指标定义（模块级变量，供业务代码直接导入使用）
# ──────────────────────────────────────────────────────────────

HTTP_REQUEST_DURATION = Histogram(
    "multi_agent_http_request_duration_seconds",
    "HTTP 请求处理耗时",
    ["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

HTTP_REQUESTS_TOTAL = Counter(
    "multi_agent_http_requests_total",
    "HTTP 请求总数",
    ["method", "endpoint", "status"],
)

AGENT_EXECUTION_TOTAL = Counter(
    "multi_agent_agent_execution_total",
    "Agent 执行次数",
    ["agent_name", "status"],
)

AGENT_EXECUTION_DURATION = Histogram(
    "multi_agent_agent_execution_duration_seconds",
    "Agent 执行耗时",
    ["agent_name"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

LLM_CALLS_TOTAL = Counter(
    "multi_agent_llm_calls_total",
    "LLM 调用次数",
    ["model", "task_type"],
)

LLM_CALL_DURATION = Histogram(
    "multi_agent_llm_call_duration_seconds",
    "LLM 调用耗时",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 60.0],
)

CACHE_QUERIES_TOTAL = Counter(
    "multi_agent_cache_queries_total",
    "缓存查询次数",
    ["result"],
)

CACHE_SIZE = Gauge(
    "multi_agent_cache_size",
    "当前缓存条目数",
)

CACHE_HIT_RATE = Gauge(
    "multi_agent_cache_hit_rate",
    "缓存命中率",
)

SYSTEM_UPTIME_SECONDS = Gauge(
    "multi_agent_system_uptime_seconds",
    "系统运行时长（秒）",
)

ACTIVE_REQUESTS = Gauge(
    "multi_agent_active_requests",
    "当前活跃请求数",
)

__all__ = [
    "MetricsCollector",
    "metrics_collector",
    "HTTP_REQUEST_DURATION",
    "HTTP_REQUESTS_TOTAL",
    "AGENT_EXECUTION_TOTAL",
    "AGENT_EXECUTION_DURATION",
    "LLM_CALLS_TOTAL",
    "LLM_CALL_DURATION",
    "CACHE_QUERIES_TOTAL",
    "CACHE_SIZE",
    "CACHE_HIT_RATE",
    "SYSTEM_UPTIME_SECONDS",
    "ACTIVE_REQUESTS",
]


class MetricsCollector:
    """性能指标收集器，记录请求延迟、吞吐量和错误率。"""

    def __init__(self, max_history: int = 1000) -> None:
        self._request_times: deque[float] = deque(maxlen=max_history)
        self._error_count = 0
        self._total_count = 0
        self._start_time = time.time()

    def record_request(self, duration_ms: float, is_error: bool = False) -> None:
        """记录一次请求。"""
        self._request_times.append(duration_ms)
        self._total_count += 1
        if is_error:
            self._error_count += 1

    @property
    def total_requests(self) -> int:
        return self._total_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def error_rate(self) -> float:
        return self._error_count / self._total_count if self._total_count > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        if not self._request_times:
            return 0.0
        return sum(self._request_times) / len(self._request_times)

    @property
    def p95_latency_ms(self) -> float:
        if not self._request_times:
            return 0.0
        sorted_times = sorted(self._request_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def throughput(self) -> float:
        """每秒请求数（基于启动时间）。"""
        elapsed = time.time() - self._start_time
        return self._total_count / elapsed if elapsed > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """获取所有指标统计。"""
        return {
            "total_requests": self.total_requests,
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "throughput": round(self.throughput, 2),
            "uptime_seconds": round(time.time() - self._start_time, 2),
        }


# 全局单例
metrics_collector = MetricsCollector()
