"""性能指标收集器。

提供请求延迟、吞吐量、错误率等指标的收集和查询功能。
"""

import time
from collections import deque
from typing import Any

from loguru import logger

__all__ = ["MetricsCollector", "metrics_collector"]


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
