"""工单相关数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "BatchTicketCreate",
    "TicketCategory",
    "TicketCreate",
    "TicketPriority",
    "TicketResponse",
    "TicketStatus",
    "TicketStatusUpdate",
]


class TicketStatus(str, Enum):
    """工单处理状态。"""

    RECEIVED = "received"
    CLASSIFYING = "classifying"
    PROCESSING = "processing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class TicketCategory(str, Enum):
    """工单分类。"""

    TECHNICAL = "technical"
    BILLING = "billing"
    COMPLAINT = "complaint"
    INQUIRY = "inquiry"


class TicketPriority(str, Enum):
    """工单优先级。"""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TicketCreate(BaseModel):
    """用户提交的工单。"""

    content: str
    user_id: str | None = None


class TicketResponse(BaseModel):
    """API 返回的工单详情。"""

    ticket_id: str
    content: str
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    processing_result: str | None = None
    review_score: float | None = None
    retry_count: int = 0
    status: TicketStatus = TicketStatus.RECEIVED
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class TicketStatusUpdate(BaseModel):
    """WebSocket 推送的工单状态更新。"""

    ticket_id: str
    status: TicketStatus
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)


class BatchTicketCreate(BaseModel):
    """批量提交工单请求。"""

    tickets: list[TicketCreate] = Field(..., min_length=1, max_length=50)
