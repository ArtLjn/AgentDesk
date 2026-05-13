"""API 路由模块，提供工单 CRUD、知识库上传、统计查询和 WebSocket 实时推送。"""

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from loguru import logger

from src.multi_agent_system.models.ticket import (
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


# ============================================================
# 工单接口
# ============================================================


@router.post("/tickets", response_model=dict)
async def create_ticket(body: TicketCreate, request: Request) -> dict:
    """提交新工单，触发工作流后台执行，立即返回 ticket_id。"""
    state = create_initial_state(content=body.content)
    ticket_id = state["ticket_id"]

    # 保存初始状态到内存数据库
    db_tool = request.app.state.db_tool
    ticket_data = {
        "ticket_id": ticket_id,
        "content": body.content,
        "user_id": body.user_id,
        "status": state["status"],
        "created_at": datetime.now().isoformat(),
    }
    db_tool.save_ticket(ticket_data)

    # 后台异步执行工作流
    workflow = request.app.state.workflow
    asyncio.create_task(
        _run_workflow(request.app, ticket_id, state)
    )

    logger.info(f"工单已创建: {ticket_id}")
    return {"ticket_id": ticket_id, "status": "received"}


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, request: Request) -> TicketResponse:
    """根据 ticket_id 查询工单详情。"""
    db_tool = request.app.state.db_tool
    ticket = db_tool.get_ticket(ticket_id)

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
    # 直接访问内部存储，因为 DBQueryTool 没有列表查询方法
    tickets: list[dict[str, Any]] = list(db_tool._tickets.values())

    # 按条件过滤
    if status is not None:
        tickets = [t for t in tickets if t.get("status") == status]
    if category is not None:
        tickets = [t for t in tickets if t.get("category") == category]

    # 按创建时间倒序排列
    tickets.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # 分页
    paginated = tickets[offset : offset + limit]

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
        for t in paginated
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
        "category_distribution": analytics_tool.get_category_distribution(),
        "priority_distribution": analytics_tool.get_priority_distribution(),
        "resolution_stats": analytics_tool.get_resolution_stats(),
        "daily_stats": analytics_tool.get_daily_stats(),
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


async def _run_workflow(app: Any, ticket_id: str, state: dict) -> None:
    """后台执行工作流，完成后更新数据库并通过 WebSocket 推送结果。"""
    workflow = app.state.workflow
    db_tool = app.state.db_tool

    try:
        # 执行工作流
        result = await workflow.ainvoke(state)

        # 将最终状态写入内存数据库
        final_data = {
            "ticket_id": result.get("ticket_id", ticket_id),
            "content": result.get("content", ""),
            "category": result.get("category"),
            "priority": result.get("priority"),
            "processing_result": result.get("processing_result"),
            "review_score": result.get("review_score"),
            "retry_count": result.get("retry_count", 0),
            "status": result.get("status", "completed"),
            "error": result.get("error"),
        }
        db_tool.save_ticket(final_data)

        logger.info(f"工单处理完成: {ticket_id}, 状态: {final_data['status']}")

        # 通过 WebSocket 推送最终状态
        await _broadcast_ticket_update(
            ticket_id=ticket_id,
            status=final_data["status"],
            message=f"工单处理完成，最终状态: {final_data['status']}",
        )

    except Exception as e:
        logger.error(f"工单处理异常: {ticket_id}, 错误: {e}")

        # 更新数据库为失败状态
        db_tool.save_ticket({
            "ticket_id": ticket_id,
            "status": "failed",
            "error": str(e),
        })

        # 推送失败状态
        await _broadcast_ticket_update(
            ticket_id=ticket_id,
            status="failed",
            message=f"工单处理失败: {e}",
        )


async def _broadcast_ticket_update(
    ticket_id: str,
    status: str,
    message: str,
) -> None:
    """向订阅指定工单的所有 WebSocket 客户端广播状态更新。"""
    connections = _ws_connections.get(ticket_id, [])
    if not connections:
        return

    update = TicketStatusUpdate(
        ticket_id=ticket_id,
        status=TicketStatus(status),
        message=message,
        timestamp=datetime.now(),
    )

    # 向所有订阅者发送，失败时移除断开的连接
    disconnected: list[WebSocket] = []
    for ws in connections:
        try:
            await ws.send_json(update.model_dump(mode="json"))
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        connections.remove(ws)
    if not connections:
        _ws_connections.pop(ticket_id, None)
