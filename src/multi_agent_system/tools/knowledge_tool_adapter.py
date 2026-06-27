"""将知识库检索能力适配为 ReAct 可调用工具。"""

from typing import Any

from pydantic import BaseModel, Field

from src.multi_agent_system.core.tool_base import ToolBase, ToolRegistry

__all__ = ["KnowledgeSearchToolAdapter", "register_knowledge_tool"]


class KnowledgeSearchParams(BaseModel):
    """知识库检索参数。"""

    query: str = Field(description="需要检索的工单问题或关键词")
    top_k: int = Field(default=3, ge=1, le=10, description="返回的知识片段数量")
    score_threshold: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="相似度阈值，低于该值的结果会被过滤",
    )


class KnowledgeSearchToolAdapter(ToolBase):
    """ReAct 工具适配器：调用已有知识库检索工具。"""

    name = "search_knowledge"
    description = "检索知识库，获取与当前工单相关的处理手册、FAQ 或业务规则"
    params_model = KnowledgeSearchParams

    def __init__(self, knowledge_tool: Any) -> None:
        self._knowledge_tool = knowledge_tool

    async def execute(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.5,
    ) -> str:
        """执行知识库检索并格式化为 LLM 可读上下文。"""
        results = self._knowledge_tool.search(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        if not results:
            return "未检索到相关知识片段。"

        lines = ["检索到以下知识片段："]
        for index, item in enumerate(results, start=1):
            metadata = item.get("metadata") or {}
            title = metadata.get("title") or "未命名文档"
            category = metadata.get("category") or "未分类"
            score = item.get("score", 0)
            content = item.get("content", "")
            lines.append(
                f"{index}. 标题: {title}；分类: {category}；"
                f"相似度: {score:.2f}\n内容: {content}"
            )
        return "\n".join(lines)

    async def fallback(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.5,
    ) -> str:
        """知识库不可用时的降级结果。"""
        return "知识库检索暂不可用，请根据工单内容和已有上下文给出基础处理建议。"


def register_knowledge_tool(
    registry: ToolRegistry,
    knowledge_tool: Any | None,
) -> None:
    """将知识库工具注册为 ReAct 可调用工具。"""
    if knowledge_tool is None:
        return
    registry.register(KnowledgeSearchToolAdapter(knowledge_tool))
