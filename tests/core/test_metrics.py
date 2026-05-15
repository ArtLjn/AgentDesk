"""MetricsCollector 单元测试。"""

import time

import pytest

from src.multi_agent_system.core.metrics import MetricsCollector


class TestMetricsCollector:
    """MetricsCollector 测试。"""

    def test_initial_state(self) -> None:
        m = MetricsCollector()
        assert m.total_requests == 0
        assert m.error_count == 0
        assert m.error_rate == 0.0
        assert m.avg_latency_ms == 0.0
        assert m.p95_latency_ms == 0.0

    def test_record_request(self) -> None:
        m = MetricsCollector()
        m.record_request(100.0, is_error=False)
        assert m.total_requests == 1
        assert m.error_count == 0
        assert m.error_rate == 0.0

    def test_record_error(self) -> None:
        m = MetricsCollector()
        m.record_request(100.0, is_error=True)
        assert m.total_requests == 1
        assert m.error_count == 1
        assert m.error_rate == 1.0

    def test_avg_latency(self) -> None:
        m = MetricsCollector()
        m.record_request(100.0)
        m.record_request(200.0)
        assert m.avg_latency_ms == 150.0

    def test_p95_latency(self) -> None:
        m = MetricsCollector()
        for i in range(100):
            m.record_request(float(i))
        # 95th percentile of 0-99 should be around 95
        assert m.p95_latency_ms == 95.0

    def test_throughput(self) -> None:
        m = MetricsCollector()
        time.sleep(0.1)
        m.record_request(10.0)
        assert m.throughput > 0

    def test_get_stats(self) -> None:
        m = MetricsCollector()
        m.record_request(100.0, is_error=False)
        stats = m.get_stats()
        assert stats["total_requests"] == 1
        assert stats["error_count"] == 0
        assert "error_rate" in stats
        assert "avg_latency_ms" in stats
        assert "p95_latency_ms" in stats
        assert "throughput" in stats
        assert "uptime_seconds" in stats

    def test_max_history(self) -> None:
        m = MetricsCollector(max_history=5)
        for i in range(10):
            m.record_request(float(i))
        # Only last 5 should be kept
        assert len(m._request_times) == 5
