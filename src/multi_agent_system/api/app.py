"""FastAPI 应用主模块，管理应用生命周期和路由注册。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from loguru import logger

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
    logger.info("应用关闭，清理资源")


app = FastAPI(
    title="多Agent工单处理系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from src.multi_agent_system.api.routes import router  # noqa: E402

app.include_router(router, prefix="/api")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> str:
    """返回内置 Web UI 页面。"""
    html_path = Path(__file__).parent.parent / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")
