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
    assert mock_client.chat_completions_create.call_count == 2
