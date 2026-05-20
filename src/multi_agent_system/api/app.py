"""FastAPI 应用主模块，管理应用生命周期和路由注册。"""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

from src.multi_agent_system.agents.classifier import ClassifierAgent
from src.multi_agent_system.agents.coordinator import CoordinatorAgent
from src.multi_agent_system.agents.processor import ReActProcessorAgent
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
    """应用生命周期管理：启动时初始化数据库、Agent 和工作流，关闭时清理。"""
    logger.info("🚀 多Agent工单处理系统启动")

    settings = Settings()

    # Initialize database
    from src.multi_agent_system.core.database import get_db_manager

    db_manager = await get_db_manager()
    app.state.db_manager = db_manager

    # Initialize base tools
    db_tool = DBQueryTool(db_manager=db_manager)
    notification_tool = NotificationTool()
    analytics_tool = AnalyticsTool(db_manager=db_manager)

    # Try to initialize knowledge base tool
    knowledge_tool = None
    try:
        knowledge_tool = KnowledgeSearchTool.create_from_settings()
        knowledge_tool.ensure_collection()
        logger.info("知识库工具初始化成功")
    except Exception as e:
        logger.warning(f"知识库工具初始化失败（不影响核心功能）: {e}")

    # Initialize memory manager
    from src.multi_agent_system.core.memory import MemoryManager

    memory_manager = MemoryManager(db_manager=db_manager)

    # Initialize trace manager
    from src.multi_agent_system.core.trace import TraceManager

    trace_manager = TraceManager(db_manager=db_manager)

    # Initialize tool registry and register tools
    from src.multi_agent_system.core.tool_base import ToolRegistry

    tool_registry = ToolRegistry()
    # Register tools that support ToolBase
    # (KnowledgeSearchTool and NotificationTool need to be refactored to inherit ToolBase)

    # Initialize Agents
    classifier = ClassifierAgent.create_from_settings()
    processor = ReActProcessorAgent.create_from_settings(
        tool_registry=tool_registry,
        knowledge_tool=knowledge_tool,
    )
    reviewer = ReviewerAgent.create_from_settings()
    coordinator = CoordinatorAgent.create_from_settings(
        notification_tool=notification_tool,
        knowledge_tool=knowledge_tool,
    )

    # Build workflow
    agents = {
        "classifier": classifier,
        "processor": processor,
        "reviewer": reviewer,
    }
    workflow = build_ticket_graph(settings=settings, agents=agents, trace_manager=trace_manager)

    # Store in app state
    app.state.settings = settings
    app.state.db_manager = db_manager
    app.state.db_tool = db_tool
    app.state.notification_tool = notification_tool
    app.state.analytics_tool = analytics_tool
    app.state.knowledge_tool = knowledge_tool
    app.state.memory_manager = memory_manager
    app.state.trace_manager = trace_manager
    app.state.tool_registry = tool_registry
    app.state.classifier = classifier
    app.state.processor = processor
    app.state.reviewer = reviewer
    app.state.coordinator = coordinator
    app.state.workflow = workflow

    # Restore unfinished checkpoints
    checkpoints = await db_manager.list_active_checkpoints()
    if checkpoints:
        logger.info(f"发现 {len(checkpoints)} 个未完成的检查点（恢复功能待实现）")

    logger.info("应用初始化完成")

    yield

    # Cleanup
    logger.info("🛑 应用关闭中，清理资源...")
    from src.multi_agent_system.core.cache import reset_cache

    reset_cache()
    await db_manager.close()
    logger.info("✅ 资源清理完成")


class MetricsMiddleware(BaseHTTPMiddleware):
    """记录请求延迟和错误率的中间件。"""

    async def dispatch(self, request: Request, call_next):
        """处理请求并记录指标。"""
        from src.multi_agent_system.core.metrics import metrics_collector

        metrics_collector.active_requests.inc()
        start = time.time()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.time() - start
            endpoint = request.url.path
            metrics_collector.record_http_request(
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
                duration_seconds=duration,
            )
            metrics_collector.active_requests.dec()
            metrics_collector.update_uptime()


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

# React SPA 静态文件托管
# 构建产物位于 web/dist/，由 Vite 生成
_WEB_DIST = Path(__file__).parent.parent.parent.parent / "web" / "dist"
_WEB_INDEX = _WEB_DIST / "index.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> Response:
    """返回 React SPA 入口页面。"""
    if _WEB_INDEX.exists():
        return HTMLResponse(_WEB_INDEX.read_text(encoding="utf-8"))
    # 降级：无构建产物时返回旧版内置 HTML
    legacy_html = Path(__file__).parent.parent / "web" / "index.html"
    if legacy_html.exists():
        return HTMLResponse(legacy_html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>No frontend found. Run <code>cd web && npm run build</code></h1>", status_code=404)


# SPA fallback：所有非 /api 和非静态文件的请求返回 index.html
@app.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
async def spa_fallback(path: str) -> Response:
    """SPA 路由回退：未匹配的路径返回 index.html 交给 React Router 处理。"""
    # 静态文件优先
    static_file = _WEB_DIST / path
    if static_file.exists() and static_file.is_file():
        return Response(content=static_file.read_bytes(), media_type="application/octet-stream")
    # SPA fallback
    if _WEB_INDEX.exists():
        return HTMLResponse(_WEB_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Not Found</h1>", status_code=404)


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
    """性能指标端点（JSON 格式）。"""
    from src.multi_agent_system.core.metrics import metrics_collector
    return metrics_collector.get_stats()


@app.get("/prometheus")
async def prometheus_metrics():
    """Prometheus 指标抓取端点（标准 exposition 格式）。"""
    from starlette.responses import Response
    from src.multi_agent_system.core.metrics import generate_latest, CONTENT_TYPE_LATEST, metrics_collector

    metrics_collector.update_uptime()
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
