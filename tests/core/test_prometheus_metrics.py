"""Prometheus 指标基础行为测试。

仅验证 prometheus_client 的 Counter / Histogram / Gauge
在导入后可正常使用，不涉及具体业务指标值断言。
"""

import pytest
from prometheus_client import Counter, Gauge, Histogram

from src.multi_agent_system.core.metrics import (
    ACTIVE_REQUESTS,
    AGENT_EXECUTION_DURATION,
    AGENT_EXECUTION_TOTAL,
    CACHE_HIT_RATE,
    CACHE_QUERIES_TOTAL,
    CACHE_SIZE,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION,
    LLM_CALLS_TOTAL,
    LLM_CALL_DURATION,
    SYSTEM_UPTIME_SECONDS,
)


class TestCounterBehavior:
    """验证 Counter 类型指标可正常递增。"""

    def test_counter_increment(self):
        c = Counter("test_counter", "测试计数器", ["label"])
        c.labels(label="a").inc()
        c.labels(label="a").inc(2)
        # prometheus_client 不暴露直接取值接口，
        # 只需确认调用不抛异常即视为行为正常。

    def test_http_requests_total_is_counter(self):
        assert isinstance(HTTP_REQUESTS_TOTAL, Counter)

    def test_agent_execution_total_is_counter(self):
        assert isinstance(AGENT_EXECUTION_TOTAL, Counter)

    def test_llm_calls_total_is_counter(self):
        assert isinstance(LLM_CALLS_TOTAL, Counter)

    def test_cache_queries_total_is_counter(self):
        assert isinstance(CACHE_QUERIES_TOTAL, Counter)


class TestHistogramBehavior:
    """验证 Histogram 类型指标可正常观测数值。"""

    def test_histogram_observe(self):
        h = Histogram("test_histogram", "测试直方图", ["label"])
        h.labels(label="x").observe(0.1)
        h.labels(label="x").observe(0.5)

    def test_http_request_duration_is_histogram(self):
        assert isinstance(HTTP_REQUEST_DURATION, Histogram)

    def test_agent_execution_duration_is_histogram(self):
        assert isinstance(AGENT_EXECUTION_DURATION, Histogram)

    def test_llm_call_duration_is_histogram(self):
        assert isinstance(LLM_CALL_DURATION, Histogram)


class TestGaugeBehavior:
    """验证 Gauge 类型指标可正常设置/增减。"""

    def test_gauge_set_and_inc_dec(self):
        g = Gauge("test_gauge", "测试仪表盘")
        g.set(10)
        g.inc()
        g.dec(2)

    def test_cache_size_is_gauge(self):
        assert isinstance(CACHE_SIZE, Gauge)

    def test_cache_hit_rate_is_gauge(self):
        assert isinstance(CACHE_HIT_RATE, Gauge)

    def test_system_uptime_seconds_is_gauge(self):
        assert isinstance(SYSTEM_UPTIME_SECONDS, Gauge)

    def test_active_requests_is_gauge(self):
        assert isinstance(ACTIVE_REQUESTS, Gauge)
