"""知识库相关数据模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "KnowledgeChunk",
    "KnowledgeDocument",
]


class KnowledgeDocument(BaseModel):
    """知识库文档。"""

    id: str
    title: str
    content: str
    category: str | None = None
    source: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class KnowledgeChunk(BaseModel):
    """知识库文档分块，用于向量检索。"""

    id: str
    document_id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
