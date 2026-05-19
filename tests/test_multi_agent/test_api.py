"""API 端点测试。

使用 FastAPI TestClient 测试工单 CRUD、知识库上传和统计接口，
通过 mock 外部依赖（workflow、知识库工具）隔离 API 层逻辑。
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.multi_agent_system.api.routes import router
from src.multi_agent_system.core.database import DatabaseManager
from src.multi_agent_system.tools.analytics import AnalyticsTool
from src.multi_agent_system.tools.db_query import DBQueryTool


@pytest.fixture
def app():
    """构建测试用 FastAPI 应用，mock 掉所有外部依赖。"""
    app = FastAPI()
    app.include_router(router, prefix="/api")

    # 初始化工具（使用内存 SQLite 数据库，每个 fixture 独立）
    db_manager = DatabaseManager(db_path=":memory:")
    import asyncio
    asyncio.run(db_manager.initialize())

    db_tool = DBQueryTool(db_manager=db_manager)
    analytics_tool = AnalyticsTool(db_manager=db_manager)

    # mock workflow（避免真正调用 LLM）
    mock_workflow = AsyncMock()

    # mock 知识库工具
    mock_knowledge_tool = MagicMock()

    # 注入到 app.state（模拟 lifespan 中初始化的依赖）
    app.state.db_manager = db_manager
    app.state.db_tool = db_tool
    app.state.workflow = mock_workflow
    app.state.knowledge_tool = mock_knowledge_tool
    app.state.analytics_tool = analytics_tool

    return app


@pytest.fixture
def client(app):
    """创建 TestClient 实例。"""
    return TestClient(app)


class TestTicketAPI:
    """工单 API 测试。"""

    def test_create_ticket(self, client):
        """POST /api/tickets 创建工单。"""
        response = client.post(
            "/api/tickets",
            json={"content": "系统报错", "user_id": "U001"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "ticket_id" in data
        assert data["status"] == "received"

    def test_create_ticket_without_user_id(self, client):
        """POST /api/tickets 不传 user_id 也能成功创建。"""
        response = client.post(
            "/api/tickets",
            json={"content": "咨询问题"},
        )

        assert response.status_code == 200
        assert "ticket_id" in response.json()

    def test_get_ticket(self, client):
        """GET /api/tickets/{id} 查询工单详情。"""
        # 先创建一个工单
        create_resp = client.post(
            "/api/tickets",
            json={"content": "查询测试"},
        )
        ticket_id = create_resp.json()["ticket_id"]

        # 通过 API 查询
        response = client.get(f"/api/tickets/{ticket_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["ticket_id"] == ticket_id
        assert data["content"] == "查询测试"

    def test_get_ticket_not_found(self, client):
        """GET /api/tickets/{id} 查询不存在的工单返回 404。"""
        response = client.get("/api/tickets/nonexistent_id")

        assert response.status_code == 404

    def test_list_tickets(self, client):
        """GET /api/tickets 返回工单列表。"""
        # 创建两个工单
        client.post("/api/tickets", json={"content": "工单1"})
        client.post("/api/tickets", json={"content": "工单2"})

        response = client.get("/api/tickets")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    def test_list_tickets_with_filter(self, client):
        """GET /api/tickets?status=completed 按状态过滤。"""
        # 创建一个工单并通过 workflow 模拟完成
        create_resp = client.post("/api/tickets", json={"content": "已完成工单"})
        ticket_id = create_resp.json()["ticket_id"]

        # 直接修改数据库中的状态为 completed
        import asyncio
        db_tool = client.app.state.db_tool
        asyncio.run(db_tool.save_ticket({
            "ticket_id": ticket_id,
            "content": "已完成工单",
            "status": "completed",
            "category": "technical",
            "created_at": datetime.now().isoformat(),
        }))

        response = client.get("/api/tickets?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert all(t["status"] == "completed" for t in data)

    def test_list_tickets_with_category_filter(self, client):
        """GET /api/tickets?category=technical 按分类过滤。"""
        import asyncio
        db_tool = client.app.state.db_tool
        asyncio.run(db_tool.save_ticket({
            "ticket_id": "T020",
            "content": "技术工单",
            "status": "completed",
            "category": "technical",
            "created_at": datetime.now().isoformat(),
        }))
        asyncio.run(db_tool.save_ticket({
            "ticket_id": "T021",
            "content": "账务工单",
            "status": "completed",
            "category": "billing",
            "created_at": datetime.now().isoformat(),
        }))

        response = client.get("/api/tickets?category=technical")

        assert response.status_code == 200
        data = response.json()
        assert all(t["category"] == "technical" for t in data)


class TestKnowledgeAPI:
    """知识库 API 测试。"""

    def test_upload_knowledge(self, client):
        """POST /api/knowledge 上传知识库文档。"""
        client.app.state.knowledge_tool.add_documents = MagicMock(return_value=3)

        response = client.post(
            "/api/knowledge",
            json={"title": "测试文档", "content": "这是测试内容"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["chunks_added"] == 3

    def test_upload_knowledge_missing_fields(self, client):
        """POST /api/knowledge 缺少必填字段返回 400。"""
        response = client.post(
            "/api/knowledge",
            json={"title": "只有标题"},
        )

        assert response.status_code == 400

    def test_upload_knowledge_no_tool(self, client):
        """知识库工具不可用时返回 503。"""
        client.app.state.knowledge_tool = None

        response = client.post(
            "/api/knowledge",
            json={"title": "测试", "content": "内容"},
        )

        assert response.status_code == 503


class TestAnalyticsAPI:
    """统计 API 测试。"""

    def test_analytics(self, client):
        """GET /api/analytics 返回统计数据。"""
        import asyncio
        db_tool = client.app.state.db_tool
        asyncio.run(db_tool.save_ticket({
            "ticket_id": "A001",
            "content": "技术问题",
            "category": "technical",
            "priority": "P1",
            "status": "completed",
            "review_score": 0.9,
            "retry_count": 0,
            "created_at": datetime.now().isoformat(),
        }))

        response = client.get("/api/analytics")

        assert response.status_code == 200
        data = response.json()
        assert "category_distribution" in data
        assert "priority_distribution" in data
        assert "resolution_stats" in data
        assert "daily_stats" in data

    def test_analytics_empty(self, client):
        """无工单数据时统计接口正常返回。"""
        response = client.get("/api/analytics")

        assert response.status_code == 200
        data = response.json()
        assert data["resolution_stats"]["total"] == 0
