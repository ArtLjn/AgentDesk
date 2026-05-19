"""工具基类与注册表，支持 Pydantic Schema 定义和参数校验。"""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from loguru import logger

__all__ = ["ToolBase", "ToolRegistry"]

T = TypeVar("T", bound=BaseModel)


class ToolBase(ABC):
    """工具抽象基类。

    每个工具必须定义：
    - name: 工具名称（唯一标识）
    - description: 工具功能描述
    - params_model: Pydantic BaseModel 描述参数结构
    - execute(): 异步执行方法
    - fallback(): 异步降级方法

    子类示例::

        class SearchTool(ToolBase):
            name = "search"
            description = "Search knowledge base"
            params_model = SearchParams

            async def execute(self, query: str, top_k: int = 3) -> str:
                return await self._search(query, top_k)

            async def fallback(self, query: str, top_k: int = 3) -> str:
                return "Search unavailable"
    """

    name: str = ""
    description: str = ""
    params_model: type[BaseModel] | None = None

    def get_schema(self) -> dict[str, Any]:
        """导出 OpenAI function calling 格式的 JSON Schema。"""
        if self.params_model is None:
            return {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}},
            }

        schema = self.params_model.model_json_schema()
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
        }

    def validate_params(self, params: dict[str, Any]) -> BaseModel:
        """校验参数，返回 Pydantic 模型实例。

        Args:
            params: 原始参数字典

        Returns:
            校验通过的 Pydantic 模型实例

        Raises:
            ValidationError: 参数校验失败
        """
        if self.params_model is None:
            return BaseModel()
        return self.params_model(**params)

    def format_validation_error(self, error: ValidationError) -> str:
        """将 Pydantic 校验错误格式化为 LLM 可理解的反馈文本。"""
        messages = []
        for err in error.errors():
            field = ".".join(str(x) for x in err["loc"])
            msg = err["msg"]
            messages.append(f"- 参数 '{field}': {msg}")
        return "参数校验失败:\n" + "\n".join(messages)

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """执行工具逻辑。"""

    @abstractmethod
    async def fallback(self, **kwargs: Any) -> Any:
        """执行降级逻辑。"""


class ToolRegistry:
    """工具注册表：管理工具注册、Schema 导出和按名查找。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolBase] = {}

    def register(self, tool: ToolBase) -> None:
        """注册工具。"""
        self._tools[tool.name] = tool
        logger.info(f"[ToolRegistry] 注册工具: {tool.name}")

    def get(self, name: str) -> ToolBase | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    def get_schemas(self) -> list[dict[str, Any]]:
        """获取所有工具的 JSON Schema 列表。"""
        return [tool.get_schema() for tool in self._tools.values()]

    def list_tools(self) -> list[str]:
        """获取所有已注册工具名称。"""
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._tools
