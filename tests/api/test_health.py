"""健康检查和指标端点测试。"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """/health 端点测试。"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self) -> None:
        from src.multi_agent_system.api.app import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "cache" in data
        assert "routes" in data
        assert "timestamp" in data


class TestMetricsEndpoint:
    """/metrics 端点测试。"""

    @pytest.mark.asyncio
    async def test_metrics_returns_200(self) -> None:
        from src.multi_agent_system.api.app import app
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "error_count" in data
        assert "error_rate" in data
        assert "avg_latency_ms" in data
        assert "p95_latency_ms" in data
        assert "throughput" in data
        assert "uptime_seconds" in data
