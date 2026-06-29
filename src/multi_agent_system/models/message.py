"""工单消息相关数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "TicketMessage",
    "TicketMessageCreate",
    "TicketMessageSender",
]


class TicketMessageSender(str, Enum):
    """工单消息发送者类型。"""

    USER = "user"
    REVIEWER = "reviewer"
    SYSTEM = "system"
    AGENT = "agent"


class TicketMessageCreate(BaseModel):
    """创建工单消息的请求。"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    sender_id: str | None = None

    @model_validator(mode="after")
    def _validate_content(self) -> "TicketMessageCreate":
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("MESSAGE_CONTENT_REQUIRED: 消息内容不能为空")
        return self


class TicketMessage(BaseModel):
    """工单消息返回结构。"""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    ticket_id: str
    sender_type: TicketMessageSender | str
    sender_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | str
