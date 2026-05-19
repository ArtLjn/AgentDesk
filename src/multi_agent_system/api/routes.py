"""API 路由模块，提供工单 CRUD、知识库上传、统计查询和 WebSocket 实时推送。"""

import asyncio
from datetime import datetime
from functools import partial
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from loguru import logger

from src.multi_agent_system.models.ticket import (
    BatchTicketCreate,
    TicketCreate,
    TicketResponse,
    TicketStatus,
    TicketStatusUpdate,
)
from src.multi_agent_system.workflow.graph import create_initial_state

__all__ = ["router"]

router = APIRouter()

# WebSocket 连接管理：ticket_id -> 订阅该工单的 WebSocket 列表
_ws_connections: dict[str, list[WebSocket]] = {}

# 全局 WebSocket 连接：接收所有工单状态更新
_global_ws_connections: list[WebSocket] = []


# ============================================================
# 工单接口
# ============================================================


@router.post("/tickets", response_model=dict)
async def create_ticket(body: TicketCreate, request: Request) -> dict:
    """提交新工单，触发工作流后台执行，立即返回 ticket_id。"""
    state = create_initial_state(content=body.content)
    ticket_id = state["ticket_id"]

    # 保存初始状态到数据库
    db_tool = request.app.state.db_tool
    ticket_data = {
        "ticket_id": ticket_id,
        "content": body.content,
        "user_id": body.user_id,
        "status": state["status"],
        "created_at": datetime.now().isoformat(),
    }
    await db_tool.save_ticket(ticket_data)

    # 后台异步执行工作流
    workflow = request.app.state.workflow
    asyncio.create_task(
        _run_workflow(request.app, ticket_id, state)
    )

    logger.info(f"工单已创建: {ticket_id}")
    return {"ticket_id": ticket_id, "status": "received"}


@router.post("/tickets/batch", response_model=dict)
async def create_batch_tickets(body: BatchTicketCreate, request: Request) -> dict:
    """批量提交工单，使用 asyncio.gather 并发执行。

    每个工单独立初始化状态，通过 concurrent_execute 并发触发工作流，
    某个工单初始化失败不影响其他工单。
    """
    from src.multi_agent_system.core.concurrent import concurrent_execute

    settings = request.app.state.settings

    async def _init_one(ticket: TicketCreate) -> dict[str, str]:
        """初始化单个工单并触发后台工作流。"""
        state = create_initial_state(content=ticket.content)
        ticket_id = state["ticket_id"]

        # 保存初始状态
        db_tool = request.app.state.db_tool
        ticket_data = {
            "ticket_id": ticket_id,
            "content": ticket.content,
            "user_id": ticket.user_id,
            "status": state["status"],
            "created_at": datetime.now().isoformat(),
        }
        await db_tool.save_ticket(ticket_data)

        # 后台异步执行工作流
        workflow = request.app.state.workflow
        asyncio.create_task(
            _run_workflow(request.app, ticket_id, state)
        )
        return {"ticket_id": ticket_id, "status": "received"}

    tasks = [
        (f"ticket_{i}", partial(_init_one, ticket))
        for i, ticket in enumerate(body.tickets)
    ]

    results = await concurrent_execute(
        tasks=tasks,
        max_concurrency=settings.max_concurrency,
    )

    logger.info(f"批量工单已提交: {len(body.tickets)} 个")
    return {"results": results}


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, request: Request) -> TicketResponse:
    """根据 ticket_id 查询工单详情。"""
    db_tool = request.app.state.db_tool
    ticket = await db_tool.get_ticket(ticket_id)

    if ticket is None:
        raise HTTPException(status_code=404, detail=f"工单 {ticket_id} 不存在")

    return TicketResponse(
        ticket_id=ticket.get("ticket_id", ticket_id),
        content=ticket.get("content", ""),
        category=ticket.get("category"),
        priority=ticket.get("priority"),
        processing_result=ticket.get("processing_result"),
        review_score=ticket.get("review_score"),
        retry_count=ticket.get("retry_count", 0),
        status=ticket.get("status", "received"),
        error=ticket.get("error"),
        created_at=ticket.get("created_at", datetime.now()),
    )


@router.get("/tickets", response_model=list[TicketResponse])
async def list_tickets(
    request: Request,
    status: str | None = Query(default=None, description="按状态过滤"),
    category: str | None = Query(default=None, description="按分类过滤"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
) -> list[TicketResponse]:
    """工单列表查询，支持状态和分类过滤以及分页。"""
    db_tool = request.app.state.db_tool
    tickets: list[dict[str, Any]] = await db_tool.list_tickets(
        status=status, category=category, limit=limit, offset=offset
    )

    return [
        TicketResponse(
            ticket_id=t.get("ticket_id", ""),
            content=t.get("content", ""),
            category=t.get("category"),
            priority=t.get("priority"),
            processing_result=t.get("processing_result"),
            review_score=t.get("review_score"),
            retry_count=t.get("retry_count", 0),
            status=t.get("status", "received"),
            error=t.get("error"),
            created_at=t.get("created_at", datetime.now()),
        )
        for t in tickets
    ]


# ============================================================
# 知识库接口
# ============================================================


@router.post("/knowledge", response_model=dict)
async def upload_knowledge(
    body: dict[str, Any],
    request: Request,
) -> dict:
    """上传文档到知识库。

    接收 JSON body，需包含 title、content，可选 category。
    """
    knowledge_tool = request.app.state.knowledge_tool

    if knowledge_tool is None:
        raise HTTPException(
            status_code=503,
            detail="知识库服务不可用（Qdrant 未连接）",
        )

    title = body.get("title", "")
    content = body.get("content", "")
    category = body.get("category")

    if not title or not content:
        raise HTTPException(
            status_code=400,
            detail="title 和 content 为必填字段",
        )

    document = {
        "title": title,
        "content": content,
        "category": category,
    }

    try:
        chunk_count = knowledge_tool.add_documents([document])
    except Exception as e:
        logger.error(f"知识库文档上传失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"知识库文档上传失败: {e}",
        ) from e

    return {
        "status": "ok",
        "chunks_added": chunk_count,
        "message": f"文档「{title}」已上传，共 {chunk_count} 个分块",
    }


# ============================================================
# 统计接口
# ============================================================


@router.get("/analytics", response_model=dict)
async def get_analytics(request: Request) -> dict:
    """获取统计面板数据：分类分布 + 优先级分布 + 处理统计。"""
    analytics_tool = request.app.state.analytics_tool

    return {
        "category_distribution": await analytics_tool.get_category_distribution(),
        "priority_distribution": await analytics_tool.get_priority_distribution(),
        "resolution_stats": await analytics_tool.get_resolution_stats(),
        "daily_stats": await analytics_tool.get_daily_stats(),
    }


# ============================================================
# WebSocket 实时推送
# ============================================================


@router.websocket("/ws/tickets/{ticket_id}")
async def websocket_ticket_progress(websocket: WebSocket, ticket_id: str) -> None:
    """WebSocket 端点：客户端连接后实时接收工单处理进度更新。"""
    await websocket.accept()

    # 注册连接
    if ticket_id not in _ws_connections:
        _ws_connections[ticket_id] = []
    _ws_connections[ticket_id].append(websocket)

    try:
        # 保持连接，等待客户端断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.debug(f"WebSocket 客户端断开: ticket_id={ticket_id}")
    finally:
        _ws_connections[ticket_id].remove(websocket)
        if not _ws_connections[ticket_id]:
            del _ws_connections[ticket_id]


@router.websocket("/ws/monitor")
async def websocket_global_monitor(websocket: WebSocket) -> None:
    """全局 WebSocket 端点：接收所有工单的状态更新，用于前端实时刷新。"""
    await websocket.accept()
    _global_ws_connections.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.debug("全局 WebSocket 客户端断开")
    finally:
        if websocket in _global_ws_connections:
            _global_ws_connections.remove(websocket)


# 工作流节点名称到中文标签的映射
_NODE_LABELS: dict[str, str] = {
    "receive": "接收工单",
    "classify": "智能分类",
    "route": "路由决策",
    "process": "工单处理",
    "review": "质量审核",
    "auto_reply": "自动回复",
    "escalate": "升级处理",
    "notify": "发送通知",
    "complete": "归档完成",
    "retry_check": "重试检查",
    "handle_failure": "失败处理",
}


async def _run_workflow(app: Any, ticket_id: str, state: dict) -> None:
    """后台执行工作流，每个节点完成后实时推送状态更新。"""
    workflow = app.state.workflow
    db_tool = app.state.db_tool
    current_state = dict(state)

    try:
        # 流式执行：每完成一个节点就推送一次更新
        async for event in workflow.astream(state):
            for node_name, node_output in event.items():
                if not isinstance(node_output, dict):
                    continue

                # 累积状态
                current_state.update(node_output)

                # 合并已有数据（保留 user_id、created_at 等字段）
                existing = await db_tool.get_ticket(ticket_id) or {}
                db_data = {
                    **existing,
                    "ticket_id": ticket_id,
                    "content": current_state.get("content", ""),
                    "category": current_state.get("category"),
                    "priority": current_state.get("priority"),
                    "processing_result": current_state.get("processing_result"),
                    "review_score": current_state.get("review_score"),
                    "retry_count": current_state.get("retry_count", 0),
                    "status": current_state.get("status", current_state.get("status", "processing")),
                    "error": current_state.get("error"),
                }
                await db_tool.save_ticket(db_data)

                status = db_data.get("status", "processing")
                label = _NODE_LABELS.get(node_name, node_name)
                logger.info(f"工单 {ticket_id} 节点 {node_name} 完成，状态: {status}")

                # 推送节点完成事件
                await _broadcast_ticket_update(
                    ticket_id=ticket_id,
                    status=status,
                    message=f"{label} 完成",
                    node=node_name,
                    data={
                        "category": db_data.get("category"),
                        "priority": db_data.get("priority"),
                        "review_score": db_data.get("review_score"),
                        "retry_count": db_data.get("retry_count", 0),
                    },
                )

    except Exception as e:
        logger.error(f"工单处理异常: {ticket_id}, 错误: {e}")

        existing = await db_tool.get_ticket(ticket_id) or {}
        await db_tool.save_ticket({
            **existing,
            "ticket_id": ticket_id,
            "status": "failed",
            "error": str(e),
        })

        await _broadcast_ticket_update(
            ticket_id=ticket_id,
            status="failed",
            message=f"处理失败: {e}",
            node="error",
        )


async def _broadcast_ticket_update(
    ticket_id: str,
    status: str,
    message: str,
    node: str | None = None,
    data: dict | None = None,
) -> None:
    """向所有 WebSocket 客户端广播状态更新（单工单订阅 + 全局监控）。"""
    now = datetime.now()
    payload = {
        "ticket_id": ticket_id,
        "status": status,
        "message": message,
        "timestamp": now.isoformat(),
        **({"node": node} if node else {}),
        **({"data": data} if data else {}),
    }

    # 收集所有需要发送的连接
    all_connections: list[WebSocket] = []
    all_connections.extend(_global_ws_connections)
    per_ticket = _ws_connections.get(ticket_id, [])
    for ws in per_ticket:
        if ws not in all_connections:
            all_connections.append(ws)

    # 向所有连接发送，清理断开的连接
    disconnected_global: list[WebSocket] = []
    disconnected_ticket: list[WebSocket] = []

    for ws in all_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            if ws in _global_ws_connections:
                disconnected_global.append(ws)
            else:
                disconnected_ticket.append(ws)

    for ws in disconnected_global:
        _global_ws_connections.remove(ws)

    for ws in disconnected_ticket:
        per_ticket.remove(ws)
    if not per_ticket and ticket_id in _ws_connections:
        _ws_connections.pop(ticket_id, None)
