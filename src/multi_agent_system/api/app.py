"""FastAPI 应用主模块，管理应用生命周期和路由注册。"""

import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.multi_agent_system.agents.classifier import ClassifierAgent
from src.multi_agent_system.agents.coordinator import CoordinatorAgent
from src.multi_agent_system.agents.processor import ProcessorAgent
from src.multi_agent_system.agents.reviewer import ReviewerAgent
from src.multi_agent_system.config import Settings
from src.multi_agent_system.tools.analytics import AnalyticsTool
from src.multi_agent_system.tools.db_query import DBQueryTool
from src.multi_agent_system.tools.knowledge_search import KnowledgeSearchTool
from src.multi_agent_system.tools.notification import NotificationTool
from src.multi_agent_system.workflow.graph import build_ticket_graph

__all__ = ["app"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化工具、Agent 和工作流，关闭时清理。"""
    logger.info("🚀 多Agent工单处理系统启动")

    settings = Settings()

    # 初始化基础工具
    db_tool = DBQueryTool()
    notification_tool = NotificationTool()
    analytics_tool = AnalyticsTool(db_tool)

    # 尝试初始化知识库工具（Qdrant 可用时才初始化）
    knowledge_tool: KnowledgeSearchTool | None = None
    try:
        knowledge_tool = KnowledgeSearchTool.create_from_settings()
        knowledge_tool.ensure_collection()
        logger.info("知识库工具初始化成功")
    except Exception as e:
        logger.warning(f"知识库工具初始化失败（不影响核心功能）: {e}")

    # 初始化 Agent（知识库工具不可用时传 None，ProcessorAgent 内部会降级）
    classifier = ClassifierAgent.create_from_settings()
    processor = ProcessorAgent.create_from_settings(knowledge_tool=knowledge_tool)
    reviewer = ReviewerAgent.create_from_settings()
    coordinator = CoordinatorAgent.create_from_settings(
        notification_tool=notification_tool,
        knowledge_tool=knowledge_tool,
    )

    # 构建工作流
    agents = {
        "classifier": classifier,
        "processor": processor,
        "reviewer": reviewer,
    }
    workflow = build_ticket_graph(settings=settings, agents=agents)

    # 存到 app.state 供路由使用
    app.state.settings = settings
    app.state.db_tool = db_tool
    app.state.notification_tool = notification_tool
    app.state.analytics_tool = analytics_tool
    app.state.knowledge_tool = knowledge_tool
    app.state.classifier = classifier
    app.state.processor = processor
    app.state.reviewer = reviewer
    app.state.coordinator = coordinator
    app.state.workflow = workflow

    logger.info("应用初始化完成")

    yield

    # 关闭时清理
    logger.info("🛑 应用关闭中，清理资源...")
    from src.multi_agent_system.core.cache import reset_cache
    reset_cache()
    logger.info("✅ 资源清理完成")


class MetricsMiddleware(BaseHTTPMiddleware):
    """记录请求延迟和错误率的中间件。"""

    async def dispatch(self, request: Request, call_next):
        """处理请求并记录指标。"""
        from src.multi_agent_system.core.metrics import metrics_collector
        start = time.time()
        is_error = False
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                is_error = True
            return response
        except Exception:
            is_error = True
            raise
        finally:
            duration_ms = (time.time() - start) * 1000
            metrics_collector.record_request(duration_ms, is_error)


app = FastAPI(
    title="多Agent工单处理系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(MetricsMiddleware)

# 自定义 CORS 中间件：HTTP 正常添加跨域头，WebSocket 直接放行
# Starlette 自带的 CORSMiddleware 会拦截 WebSocket 的 Origin 检查导致 403


class _CORSAllowAll:
    """ASGI 中间件：允许所有来源的 HTTP 和 WebSocket 请求。"""

    def __init__(self, app):  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] == "websocket":
            # WebSocket 直通，不做 Origin 检查
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            # 处理预检请求
            if scope.get("method") == "OPTIONS":
                from starlette.responses import Response

                response = Response(
                    status_code=204,
                    headers={
                        "access-control-allow-origin": "*",
                        "access-control-allow-methods": "*",
                        "access-control-allow-headers": "*",
                        "access-control-max-age": "86400",
                    },
                )
                await response(scope, receive, send)
                return

            # 给正常响应注入 CORS 头
            async def _send_with_cors(message):  # noqa: ANN001
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"access-control-allow-origin", b"*"))
                    headers.append((b"access-control-allow-methods", b"*"))
                    headers.append((b"access-control-allow-headers", b"*"))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, _send_with_cors)
            return

        await self.app(scope, receive, send)


app.add_middleware(_CORSAllowAll)

# 注册路由
from src.multi_agent_system.api.routes import router  # noqa: E402

app.include_router(router, prefix="/api")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> str:
    """返回内置 Web UI 页面。"""
    html_path = Path(__file__).parent.parent / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/health")
async def health_check() -> dict:
    """健康检查端点。"""
    from src.multi_agent_system.core.cache import _get_llm_cache
    from src.multi_agent_system.core.model_router import get_model_router

    cache = _get_llm_cache()
    cache_stats = cache.get_stats() if cache else {"enabled": False}
    router = get_model_router()

    return {
        "status": "healthy",
        "version": "1.0.0",
        "cache": cache_stats,
        "routes": router.get_stats() if router else {},
        "timestamp": time.time(),
    }


@app.get("/metrics")
async def metrics() -> dict:
    """性能指标端点。"""
    from src.multi_agent_system.core.metrics import metrics_collector
    return metrics_collector.get_stats()
