"""Self-Reflection 模式 Agent 核心实现

支持自我评估与错误修正的 Agent，通过 Act-Reflect-Retry 循环
逐步提升回答质量，直到通过自我评估或达到最大反思轮次。
"""

import os
import re
from dataclasses import dataclass
from typing import Callable, Optional

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

load_dotenv()

__all__ = ["ReflectionAgent", "ReflectionResult"]


@dataclass
class ReflectionResult:
    """单次反思的结果数据

    Attributes:
        answer: 当前回答内容
        reflection: 自我评估意见
        score: 自我评分（1-10）
        is_satisfactory: 回答是否满意
    """

    answer: str
    reflection: str
    score: int = 0
    is_satisfactory: bool = False


class ReflectionAgent:
    """基于 Self-Reflection 模式的 AI 助手，支持自我评估与错误修正

    工作流程：
    1. Act 阶段：LLM 尝试回答问题
    2. Reflect 阶段：LLM 评估自身回答的准确性、完整性和清晰性
    3. Retry 阶段：若评估不通过，携带反思意见重新作答
    4. 循环直到回答通过评估或达到最大反思轮次
    """

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
        self.reflection_history: list[ReflectionResult] = []
        self.max_reflections = 3
        self.min_satisfactory_score = 7

        self.act_prompt = """你是一个AI助手，请回答用户的问题。你可以使用以下工具：

{tools_description}

如果需要使用工具，使用格式：Action: 工具名(参数)
如果不需要工具，直接给出答案，格式为：Answer: 你的答案

用户问题：{query}

之前的尝试和反思（如果有）：
{previous_attempts}

请给出你的回答："""

        self.reflect_prompt = """你是一个严格的自我评审专家。请评估以下回答的质量。

原始问题：{query}

当前回答：{answer}

请从以下维度评估：
1. 准确性：回答是否事实正确？
2. 完整性：回答是否完整覆盖了问题的所有方面？
3. 清晰性：回答是否清晰易懂？

请按以下格式输出：
Score: 1-10的评分
Evaluation: 详细的评估意见
Verdict: satisfactory 或 unsatisfactory"""

    @property
    def client(self) -> OpenAI:
        """延迟初始化 OpenAI 客户端，避免构造时就必须提供 API Key"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key or os.getenv("OPENAI_API_KEY"),
                base_url=self._base_url or os.getenv("OPENAI_BASE_URL"),
            )
        return self._client

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

    def _parse_answer(self, response: str) -> str:
        """从 LLM 响应中提取回答内容

        Args:
            response: LLM 返回的文本
        Returns:
            提取出的回答文本
        """
        answer_match = re.search(r"Answer:\s*(.*)", response, re.DOTALL)
        if answer_match:
            return answer_match.group(1).strip()
        return response.strip()

    def _parse_reflection(self, response: str) -> ReflectionResult:
        """从 LLM 反思响应中解析评分和判定结果

        Args:
            response: LLM 返回的反思文本
        Returns:
            解析后的 ReflectionResult 对象
        """
        score = 0
        is_satisfactory = False
        evaluation = response

        score_match = re.search(r"Score:\s*(\d+)", response)
        if score_match:
            score = int(score_match.group(1))

        verdict_match = re.search(
            r"Verdict:\s*(satisfactory|unsatisfactory)", response, re.IGNORECASE
        )
        if verdict_match:
            is_satisfactory = verdict_match.group(1).lower() == "satisfactory"

        eval_match = re.search(
            r"Evaluation:\s*(.*?)(?=Verdict:|$)", response, re.DOTALL
        )
        if eval_match:
            evaluation = eval_match.group(1).strip()

        return ReflectionResult(
            answer="",
            reflection=evaluation,
            score=score,
            is_satisfactory=is_satisfactory,
        )

    def _format_previous_attempts(self) -> str:
        """格式化历史尝试记录，供下一轮 Act 使用"""
        if not self.reflection_history:
            return "无"
        parts = []
        for i, r in enumerate(self.reflection_history):
            parts.append(
                f"\n第{i + 1}次尝试: {r.answer}\n反思(评分{r.score}/10): {r.reflection}\n"
            )
        return "".join(parts)

    def act(self, query: str, previous_attempts: str = "无") -> str:
        """生成回答，支持工具调用

        Args:
            query: 用户问题
            previous_attempts: 之前尝试的格式化文本
        Returns:
            生成的回答文本
        """
        messages = [
            {
                "role": "user",
                "content": self.act_prompt.format(
                    tools_description=self._get_tools_description(),
                    query=query,
                    previous_attempts=previous_attempts,
                ),
            }
        ]

        # 最多5轮工具调用
        for _ in range(5):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
            content = response.choices[0].message.content
            logger.info(f"Act响应: {content}")

            tool_name, tool_args = self._parse_action(content)
            if tool_name and tool_name in self.tools:
                try:
                    tool_result = self.tools[tool_name](tool_args)
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {"role": "user", "content": f"Observation: {tool_result}"}
                    )
                    continue
                except Exception as e:
                    logger.error(f"工具错误: {e}")

            return self._parse_answer(content)

        return "工具调用次数过多"

    def reflect(self, query: str, answer: str) -> ReflectionResult:
        """自我评估回答质量

        Args:
            query: 原始问题
            answer: 待评估的回答
        Returns:
            包含评分和判定结果的 ReflectionResult
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": self.reflect_prompt.format(query=query, answer=answer),
                }
            ],
            temperature=0,
        )
        content = response.choices[0].message.content
        logger.info(f"Reflect响应: {content}")

        result = self._parse_reflection(content)
        result.answer = answer
        return result

    def run(self, query: str) -> str:
        """运行完整的 Reflection 循环

        Args:
            query: 用户问题
        Returns:
            最终回答（附带自我评估信息）
        """
        self.reflection_history = []

        for i in range(self.max_reflections):
            logger.info(f"反思轮次 {i + 1}/{self.max_reflections}")

            # Act: 生成回答
            previous = self._format_previous_attempts()
            answer = self.act(query, previous)

            # Reflect: 自我评估
            reflection = self.reflect(query, answer)
            self.reflection_history.append(reflection)

            logger.info(f"评分: {reflection.score}/10, 满意: {reflection.is_satisfactory}")

            # 检查是否满意
            if (
                reflection.is_satisfactory
                and reflection.score >= self.min_satisfactory_score
            ):
                return f"{answer}\n\n[自我评估: {reflection.score}/10 - 满意]"

        # 达到最大反思轮次，返回最后一次的回答
        last = self.reflection_history[-1]
        return f"{last.answer}\n\n[自我评估: {last.score}/10 - 未达到满意标准，已尝试{self.max_reflections}次]"
