"""知识库工具适配器测试。"""

import pytest

from src.multi_agent_system.core.tool_base import ToolRegistry
from src.multi_agent_system.tools.knowledge_tool_adapter import register_knowledge_tool


class FakeKnowledgeTool:
    """测试用知识库工具。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, float]] = []

    def search(self, query: str, top_k: int = 3, score_threshold: float = 0.5) -> list[dict]:
        self.calls.append((query, top_k, score_threshold))
        return [
            {
                "content": "登录失败时先检查账号状态，再重置密码。",
                "score": 0.91,
                "metadata": {"title": "登录故障处理手册", "category": "technical"},
            }
        ]


def test_register_knowledge_tool_adds_search_tool() -> None:
    """注册知识库工具后，ReAct 工具表应包含 search_knowledge。"""
    registry = ToolRegistry()
    knowledge_tool = FakeKnowledgeTool()

    register_knowledge_tool(registry, knowledge_tool)

    assert "search_knowledge" in registry
    schema = registry.get("search_knowledge").get_schema()
    assert schema["name"] == "search_knowledge"
    assert "query" in schema["parameters"]["properties"]


@pytest.mark.asyncio
async def test_search_knowledge_tool_formats_results() -> None:
    """search_knowledge 应返回可直接喂给 ReAct 的中文上下文。"""
    registry = ToolRegistry()
    knowledge_tool = FakeKnowledgeTool()
    register_knowledge_tool(registry, knowledge_tool)

    tool = registry.get("search_knowledge")
    result = await tool.execute(query="无法登录", top_k=2, score_threshold=0.7)

    assert knowledge_tool.calls == [("无法登录", 2, 0.7)]
    assert "登录故障处理手册" in result
    assert "登录失败时先检查账号状态" in result
    assert "相似度: 0.91" in result
