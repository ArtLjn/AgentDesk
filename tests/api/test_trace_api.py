"""Trace API 端点测试。"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.multi_agent_system.api.routes import router
from src.multi_agent_system.core.database import DatabaseManager


@pytest.fixture
def app():
    """构建测试用 FastAPI 应用。"""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    db_manager = DatabaseManager(db_path=":memory:")
    asyncio.run(db_manager.initialize())

    app.state.db_manager = db_manager
    app.state.db_tool = MagicMock()
    app.state.db_tool.save_ticket = AsyncMock()
    app.state.db_tool.get_ticket = AsyncMock(return_value=None)
    app.state.notification_tool = MagicMock()
    app.state.analytics_tool = MagicMock()
    app.state.knowledge_tool = None
    app.state.memory_manager = None
    app.state.tool_registry = None
    app.state.workflow = MagicMock()
    app.state.trace_manager = None

    return app


@pytest.fixture
def client(app):
    """创建 TestClient 实例。"""
    return TestClient(app)


class TestTraceAPI:
    """Trace API 端点测试。"""

    def test_get_trace_not_found(self, client: TestClient):
        """查询不存在的 trace 返回 404。"""
        resp = client.get("/api/tickets/TK-NONEXIST/trace")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Trace not found"

    def test_list_traces_empty(self, client: TestClient):
        """空 trace 列表。"""
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_get_trace_stats_not_found(self, client: TestClient):
        """查询不存在的 trace stats 返回 404。"""
        resp = client.get("/api/traces/tr-nonexist/stats")
        assert resp.status_code == 404

    def test_get_trace_with_spans(self, client: TestClient, app):
        """创建 trace + span 后查询。"""
        db: DatabaseManager = app.state.db_manager
        now = time.time()
        asyncio.run(db.save_trace({
            "trace_id": "tr-test", "ticket_id": "TK-001", "status": "completed",
            "start_time": now - 1, "end_time": now, "duration": 1.0,
        }))
        asyncio.run(db.save_span({
            "span_id": "sp-1", "trace_id": "tr-test", "parent_span_id": None,
            "span_type": "node", "name": "classify", "status": "ok",
            "start_time": now - 0.5, "end_time": now, "duration": 0.5,
        }))

        resp = client.get("/api/tickets/TK-001/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trace_id"] == "tr-test"
        assert len(data["spans"]) == 1
        assert data["spans"][0]["name"] == "classify"

    def test_list_traces_with_data(self, client: TestClient, app):
        """有 trace 数据时返回列表。"""
        db: DatabaseManager = app.state.db_manager
        asyncio.run(db.save_ticket({
            "ticket_id": "TK-001",
            "content": "系统登录失败，需要排查",
            "category": "technical",
            "priority": "P1",
            "processing_result": "建议检查账号状态并重置密码",
            "references": ["登录故障手册"],
            "status": "completed",
        }))
        asyncio.run(db.save_trace({
            "trace_id": "tr-1", "ticket_id": "TK-001", "status": "completed",
            "start_time": time.time(),
        }))
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["total"] == 1
        trace = data["traces"][0]
        assert trace["ticket_summary"] == "系统登录失败，需要排查"
        assert trace["ticket_category"] == "technical"
        assert trace["ticket_priority"] == "P1"
        assert trace["reference_count"] == 1

    def test_list_traces_status_filter(self, client: TestClient, app):
        """按 status 过滤 trace 列表。"""
        db: DatabaseManager = app.state.db_manager
        now = time.time()
        asyncio.run(db.save_trace({"trace_id": "tr-1", "ticket_id": "TK-1", "status": "completed", "start_time": now - 1}))
        asyncio.run(db.save_trace({"trace_id": "tr-2", "ticket_id": "TK-2", "status": "running", "start_time": now}))

        resp = client.get("/api/traces?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["total"] == 1

    def test_list_traces_pagination_meta(self, client: TestClient, app):
        """trace 列表返回分页元信息。"""
        db: DatabaseManager = app.state.db_manager
        now = time.time()
        for index in range(3):
            asyncio.run(db.save_trace({
                "trace_id": f"tr-{index}",
                "ticket_id": f"TK-{index}",
                "status": "completed",
                "start_time": now - index,
            }))

        resp = client.get("/api/traces?limit=2&offset=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 1
