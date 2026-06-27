import pytest
from unittest.mock import AsyncMock, MagicMock

from src.multi_agent_system.agents.processor_react import ReActProcessorAgent
from src.multi_agent_system.core.tool_base import ToolBase, ToolRegistry
from pydantic import BaseModel, Field


class MockSearchParams(BaseModel):
    query: str = Field(description="Search query")


class MockSearchTool(ToolBase):
    name = "search_knowledge"
    description = "Search knowledge base"
    params_model = MockSearchParams

    async def execute(self, query: str) -> str:
        return f"Knowledge about {query}"

    async def fallback(self, query: str) -> str:
        return "Knowledge base unavailable"


@pytest.fixture
def mock_client():
    client = MagicMock()
    return client


@pytest.mark.asyncio
async def test_react_processor_runs_loop(mock_client):
    tool = MockSearchTool()
    registry = ToolRegistry()
    registry.register(tool)

    agent = ReActProcessorAgent(
        model="test-model",
        tool_registry=registry,
        client=mock_client,
    )

    # Mock LLM responses: first thinks, then calls tool, then answers
    responses = [
        # Iteration 1: Thought + Action
        "Thought: I need to search for information.\nAction: search_knowledge({\"query\": \"login issue\"})",
        # Iteration 2: Final Answer
        "Thought: I have enough information.\nFinal Answer: Please reset your password.",
    ]

    mock_client.chat_completions_create = AsyncMock(side_effect=[
        MagicMock(choices=[MagicMock(message=MagicMock(content=r))])
        for r in responses
    ])

    result = await agent.process("无法登录", "technical", "P1")

    assert "result" in result
    assert "references" in result
    assert "Knowledge about 无法登录" in result["references"]
    assert "Knowledge about login issue" in result["references"]
    assert mock_client.chat_completions_create.call_count == 2


@pytest.mark.asyncio
async def test_react_processor_keeps_parsed_references_when_no_tool(mock_client):
    """LLM 直接返回 JSON 时，应保留模型给出的 references。"""
    agent = ReActProcessorAgent(
        model="test-model",
        client=mock_client,
    )
    mock_client.chat_completions_create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"result": "请按手册处理", "references": ["登录手册"]}'
                    )
                )
            ]
        )
    )

    result = await agent.process("无法登录", "technical", "P1")

    assert result["result"] == "请按手册处理"
    assert result["references"] == ["登录手册"]


@pytest.mark.asyncio
async def test_react_processor_prefetches_knowledge_for_technical_ticket(mock_client):
    """技术类工单应先检索知识库，避免完全依赖模型主动调用工具。"""
    tool = MockSearchTool()
    registry = ToolRegistry()
    registry.register(tool)
    agent = ReActProcessorAgent(
        model="test-model",
        tool_registry=registry,
        client=mock_client,
    )
    mock_client.chat_completions_create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="Thought: enough.\nFinal Answer: 请根据知识库处理。"
                    )
                )
            ]
        )
    )

    result = await agent.process("ERR-5001 无法登录", "technical", "P1")

    assert result["references"] == ["Knowledge about ERR-5001 无法登录"]
    sent_messages = mock_client.chat_completions_create.call_args.kwargs["messages"]
    assert "Knowledge about ERR-5001 无法登录" in sent_messages[0]["content"]


@pytest.mark.asyncio
async def test_react_processor_keeps_prefetched_references_when_json_has_empty_list(mock_client):
    """模型 JSON 返回空 references 时，不能覆盖预检索到的知识库引用。"""
    tool = MockSearchTool()
    registry = ToolRegistry()
    registry.register(tool)
    agent = ReActProcessorAgent(
        model="test-model",
        tool_registry=registry,
        client=mock_client,
    )
    mock_client.chat_completions_create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"result": "请清理缓存并检查认证服务", "references": []}'
                    )
                )
            ]
        )
    )

    result = await agent.process("ERR-5001 无法登录", "technical", "P1")

    assert result["result"] == "请清理缓存并检查认证服务"
    assert result["references"] == ["Knowledge about ERR-5001 无法登录"]
