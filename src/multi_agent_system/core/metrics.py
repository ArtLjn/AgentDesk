"""Prometheus 指标收集器。

使用 prometheus_client 暴露标准 Prometheus 格式指标，供 Grafana 查询。
"""

import time
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

__all__ = [
    "metrics_collector",
    "generate_latest",
    "CONTENT_TYPE_LATEST",
]


class MetricsCollector:
    """Prometheus 指标收集器，记录 HTTP 请求、Agent 执行、LLM 调用等指标。"""

    def __init__(self) -> None:
        # HTTP 请求指标
        self.http_requests_total = Counter(
            "multi_agent_http_requests_total",
            "HTTP 请求总数",
            ["method", "endpoint", "status"],
        )
        self.http_request_duration = Histogram(
            "multi_agent_http_request_duration_seconds",
            "HTTP 请求延迟（秒）",
            ["method", "endpoint"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        self.active_requests = Gauge(
            "multi_agent_active_requests",
            "当前活跃请求数",
        )

        # Agent 执行指标
        self.agent_execution_total = Counter(
            "multi_agent_agent_execution_total",
            "Agent 执行次数",
            ["agent_name"],
        )
        self.agent_execution_duration = Histogram(
            "multi_agent_agent_execution_duration_seconds",
            "Agent 执行耗时（秒）",
            ["agent_name"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
        )

        # LLM 调用指标
        self.llm_calls_total = Counter(
            "multi_agent_llm_calls_total",
            "LLM 调用次数",
            ["model", "task_type"],
        )
        self.llm_call_duration = Histogram(
            "multi_agent_llm_call_duration_seconds",
            "LLM 调用延迟（秒）",
            ["model", "task_type"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )
        self.llm_call_errors_total = Counter(
            "multi_agent_llm_call_errors_total",
            "LLM 调用错误次数",
            ["model", "error_type"],
        )

        # 缓存指标
        self.cache_queries_total = Counter(
            "multi_agent_cache_queries_total",
            "缓存查询次数",
            ["result"],
        )
        self.cache_hit_rate = Gauge(
            "multi_agent_cache_hit_rate",
            "缓存命中率",
        )

        # 系统指标
        self.uptime_seconds = Gauge(
            "multi_agent_system_uptime_seconds",
            "系统运行时间（秒）",
        )
        self._start_time = time.time()

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """记录一次 HTTP 请求。"""
        status = str(status_code)
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        self.http_request_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)

    def record_agent_execution(self, agent_name: str, duration_seconds: float) -> None:
        """记录一次 Agent 执行。"""
        self.agent_execution_total.labels(agent_name=agent_name).inc()
        self.agent_execution_duration.labels(agent_name=agent_name).observe(duration_seconds)

    def record_llm_call(
        self,
        model: str,
        task_type: str,
        duration_seconds: float,
        is_error: bool = False,
        error_type: str = "",
    ) -> None:
        """记录一次 LLM 调用。"""
        self.llm_calls_total.labels(model=model, task_type=task_type).inc()
        self.llm_call_duration.labels(model=model, task_type=task_type).observe(duration_seconds)
        if is_error and error_type:
            self.llm_call_errors_total.labels(model=model, error_type=error_type).inc()

    def record_cache_query(self, hit: bool) -> None:
        """记录一次缓存查询。"""
        result = "hit" if hit else "miss"
        self.cache_queries_total.labels(result=result).inc()

    def update_cache_hit_rate(self, hits: int, total: int) -> None:
        """更新缓存命中率。"""
        rate = hits / total if total > 0 else 0.0
        self.cache_hit_rate.set(rate)

    def update_uptime(self) -> None:
        """更新系统运行时间。"""
        self.uptime_seconds.set(time.time() - self._start_time)

    def get_stats(self) -> dict[str, Any]:
        """获取所有指标统计（JSON 格式，供 /metrics 使用）。"""
        return {
            "uptime_seconds": round(time.time() - self._start_time, 2),
        }


# 全局单例
metrics_collector = MetricsCollector()
