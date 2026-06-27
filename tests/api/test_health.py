"""健康检查和指标端点测试。"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import MagicMock, patch


def _client_for(app):
    """创建兼容新版 httpx 的 ASGI 测试客户端。"""
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


class TestHealthEndpoint:
    """/health 端点测试。"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self) -> None:
        from src.multi_agent_system.api.app import app
        async with _client_for(app) as client:
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
        async with _client_for(app) as client:
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


class TestApplicationStartup:
    """应用启动依赖注册测试。"""

    @pytest.mark.asyncio
    async def test_lifespan_registers_knowledge_search_tool(self) -> None:
        """知识库初始化成功时，应注册 ReAct 可调用的 search_knowledge 工具。"""
        from src.multi_agent_system.api.app import app

        knowledge_tool = MagicMock()
        knowledge_tool.ensure_collection = MagicMock()

        with patch(
            "src.multi_agent_system.api.app.KnowledgeSearchTool.create_from_settings",
            return_value=knowledge_tool,
        ):
            async with app.router.lifespan_context(app):
                assert "search_knowledge" in app.state.tool_registry
