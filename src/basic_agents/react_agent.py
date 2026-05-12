"""ReAct 模式 Agent 核心实现"""

import os
import re
from typing import Callable, Optional

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

load_dotenv()

__all__ = ["ReActAgent"]


class ReActAgent:
    """基于 ReAct 模式的 AI 助手，支持工具调用和多轮推理"""

    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._client: Optional[OpenAI] = None
        self.model = model
        self.tools: dict[str, Callable] = {}
        self.conversation_history: list[dict] = []
        self.max_iterations = 10

    @property
    def client(self) -> OpenAI:
        """延迟初始化 OpenAI 客户端，避免构造时就必须提供 API Key"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key or os.getenv("OPENAI_API_KEY"),
                base_url=self._base_url or os.getenv("OPENAI_BASE_URL"),
            )
        return self._client

        self.system_prompt = """你是一个ReAct模式的AI助手，遵循以下思考流程：
1. Thought: 思考当前问题需要做什么
2. Action: 决定要调用的工具，格式为：Action: 工具名(参数)
3. Observation: 工具返回的结果
4. 重复上述步骤，直到你可以回答用户的问题

当你确定可以回答问题时，使用格式：Final Answer: 你的回答

可用工具：
{tools_description}"""

    def register_tool(self, name: str, func: Callable, description: str = "") -> None:
        """注册工具

        Args:
            name: 工具名称
            func: 工具函数
            description: 工具描述（可选，默认从函数 docstring 获取）
        """
        self.tools[name] = func
        logger.info(f"注册工具: {name}")

    def _get_tools_description(self) -> str:
        """获取所有已注册工具的描述文本"""
        desc = []
        for name, func in self.tools.items():
            doc = func.__doc__.strip() if func.__doc__ else "无描述"
            desc.append(f"- {name}: {doc}")
        return "\n".join(desc)

    def _parse_action(self, response: str) -> tuple[str, str]:
        """从 LLM 响应中解析 Action 调用

        Args:
            response: LLM 返回的文本
        Returns:
            (工具名, 参数) 元组，解析失败时返回 ("", "")
        """
        action_match = re.search(r"Action:\s*(\w+)\((.*?)\)", response, re.DOTALL)
        if action_match:
            tool_name = action_match.group(1)
            tool_args = action_match.group(2).strip('"\'')
            return tool_name, tool_args
        return "", ""

    def run(self, query: str) -> str:
        """运行 ReAct 推理循环

        Args:
            query: 用户输入的问题
        Returns:
            最终回答文本
        """
        self.conversation_history = [
            {
                "role": "system",
                "content": self.system_prompt.format(
                    tools_description=self._get_tools_description()
                ),
            },
            {"role": "user", "content": query},
        ]

        for i in range(self.max_iterations):
            logger.info(f"迭代 {i + 1}/{self.max_iterations}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.conversation_history,
                temperature=0,
            )
            llm_response = response.choices[0].message.content
            logger.info(f"LLM响应: {llm_response}")

            if "Final Answer:" in llm_response:
                return llm_response.split("Final Answer:")[-1].strip()

            tool_name, tool_args = self._parse_action(llm_response)
            if not tool_name or tool_name not in self.tools:
                logger.warning(f"无法解析Action或工具不存在: {tool_name}")
                self.conversation_history.append(
                    {"role": "assistant", "content": llm_response}
                )
                self.conversation_history.append(
                    {
                        "role": "user",
                        "content": f"Observation: 工具 {tool_name} 不存在或格式错误，请重新思考",
                    }
                )
                continue

            try:
                logger.info(f"调用工具: {tool_name}({tool_args})")
                tool_result = self.tools[tool_name](tool_args)
                logger.info(f"工具返回: {tool_result}")
            except Exception as e:
                tool_result = f"工具调用错误: {str(e)}"
                logger.error(tool_result)

            self.conversation_history.append(
                {"role": "assistant", "content": llm_response}
            )
            self.conversation_history.append(
                {"role": "user", "content": f"Observation: {tool_result}"}
            )

        return "已达到最大迭代次数，未能完成任务"
