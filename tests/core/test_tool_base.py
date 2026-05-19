import pytest
from pydantic import BaseModel, Field, ValidationError

from src.multi_agent_system.core.tool_base import ToolBase, ToolRegistry


class MockParams(BaseModel):
    query: str = Field(description="Search query")
    top_k: int = Field(default=3, ge=1, le=10)


class MockTool(ToolBase):
    name = "mock_search"
    description = "A mock search tool"
    params_model = MockParams

    async def execute(self, query: str, top_k: int = 3) -> str:
        return f"Results for {query}: {top_k} items"

    async def fallback(self, query: str, top_k: int = 3) -> str:
        return f"Fallback for {query}"


def test_tool_schema_generation():
    tool = MockTool()
    schema = tool.get_schema()
    assert schema["name"] == "mock_search"
    assert schema["description"] == "A mock search tool"
    assert "parameters" in schema
    assert schema["parameters"]["properties"]["query"]["type"] == "string"


def test_tool_registry():
    registry = ToolRegistry()
    tool = MockTool()
    registry.register(tool)

    assert registry.get("mock_search") is tool
    schemas = registry.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "mock_search"


def test_param_validation_success():
    tool = MockTool()
    validated = tool.validate_params({"query": "test", "top_k": 5})
    assert validated.query == "test"
    assert validated.top_k == 5


def test_param_validation_failure():
    tool = MockTool()
    with pytest.raises(ValidationError):
        tool.validate_params({"query": "test", "top_k": 100})  # exceeds max 10
