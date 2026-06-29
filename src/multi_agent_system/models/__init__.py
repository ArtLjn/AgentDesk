"""数据模型包，包含工单和知识库相关模型。"""

from .knowledge import KnowledgeChunk, KnowledgeDocument
from .message import TicketMessage, TicketMessageCreate, TicketMessageSender
from .ticket import (
    TicketCategory,
    TicketCreate,
    TicketPriority,
    TicketResponse,
    TicketStatus,
    TicketStatusUpdate,
)

__all__ = [
    "KnowledgeChunk",
    "KnowledgeDocument",
    "TicketMessage",
    "TicketMessageCreate",
    "TicketMessageSender",
    "TicketCategory",
    "TicketCreate",
    "TicketPriority",
    "TicketResponse",
    "TicketStatus",
    "TicketStatusUpdate",
]
