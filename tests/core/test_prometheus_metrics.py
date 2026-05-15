"""Prometheus 指标基础行为测试。

使用独立 CollectorRegistry 验证 Counter / Histogram / Gauge
的基本行为，避免污染全局 Registry。
"""

import pytest
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class TestCounterBehavior:
    """验证 Counter 类型指标可正常递增。"""

    @pytest.fixture
    def registry(self):
        return CollectorRegistry()

    def test_counter_create_and_increment(self, registry):
        c = Counter("test_counter", "测试计数器", ["label"], registry=registry)

        c.labels(label="a").inc()
        c.labels(label="a").inc(2)

        samples = list(c.collect())[0].samples
        value = next(s.value for s in samples if s.labels == {"label": "a"})
        assert value == 3.0


class TestHistogramBehavior:
    """验证 Histogram 类型指标可正常观测数值，并支持自定义 bucket。"""

    @pytest.fixture
    def registry(self):
        return CollectorRegistry()

    def test_histogram_create_and_observe(self, registry):
        h = Histogram("test_histogram", "测试直方图", ["label"], registry=registry)

        h.labels(label="x").observe(0.1)
        h.labels(label="x").observe(0.5)

        samples = list(h.collect())[0].samples
        count = next(s.value for s in samples if s.name == "test_histogram_count")
        assert count == 2.0

    def test_histogram_custom_buckets(self, registry):
        custom_buckets = [0.1, 0.5, 1.0, 2.5, 5.0]
        h = Histogram(
            "test_histogram_buckets",
            "测试自定义 bucket 直方图",
            registry=registry,
            buckets=custom_buckets,
        )

        h.observe(0.3)
        h.observe(1.5)

        samples = list(h.collect())[0].samples
        count = next(s.value for s in samples if s.name == "test_histogram_buckets_count")
        assert count == 2.0


class TestGaugeBehavior:
    """验证 Gauge 类型指标可正常设置/增减。"""

    @pytest.fixture
    def registry(self):
        return CollectorRegistry()

    def test_gauge_create_and_set(self, registry):
        g = Gauge("test_gauge", "测试仪表盘", registry=registry)

        g.set(10)
        g.inc()
        g.dec(2)

        samples = list(g.collect())[0].samples
        value = next(s.value for s in samples)
        assert value == 9.0
