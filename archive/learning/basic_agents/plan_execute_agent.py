"""Plan-Execute 模式 Agent 实现，支持复杂任务分解与依赖处理"""

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

from archive.learning.basic_agents.react_agent import _sanitize_text

load_dotenv()

__all__ = ["PlanExecuteAgent", "PlanStep", "StepStatus"]


class StepStatus(str, Enum):
    """计划步骤的状态枚举"""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanStep:
    """计划中的单个步骤

    Args:
        task: 步骤描述
        status: 步骤状态，默认为 PENDING
        result: 步骤执行结果，默认为空字符串
    """

    task: str
    status: StepStatus = StepStatus.PENDING
    result: str = ""


class PlanExecuteAgent:
    """基于 Plan-Execute 模式的 AI 助手，支持复杂任务分解与逐步执行

    工作流程：
    1. Plan 阶段：LLM 将复杂任务分解为有序子步骤
    2. Execute 阶段：逐步执行每个子步骤，按需调用工具
    3. 汇总结果：收集所有步骤结果并生成最终报告
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
        self.plan: list[PlanStep] = []
        self.max_retries = 3

        self.plan_prompt = """你是一个任务规划专家。请将用户的复杂任务分解为具体的、可执行的子步骤。

要求：
1. 每个子步骤应该是原子性的，可以独立执行
2. 步骤之间应该有逻辑顺序
3. 每个步骤一行，格式为：步骤编号. 步骤描述

用户任务：{query}

请给出执行计划："""

        self.execute_prompt = """你是一个任务执行专家。请执行以下子任务。

当前子任务：{step_task}

已完成步骤的结果：
{previous_results}

可用工具：
{tools_description}

请执行当前子任务并给出结果。如果需要使用工具，使用格式：Action: 工具名(参数)
如果不需要工具，直接给出结果，格式为：Result: 你的结果"""

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
            tool_args = action_match.group(2).strip("\"'")
            return tool_name, tool_args
        return "", ""

    def _parse_result(self, response: str) -> str:
        """从 LLM 响应中解析 Result 内容

        Args:
            response: LLM 返回的文本
        Returns:
            解析出的结果文本，无 Result 前缀时返回原始响应
        """
        result_match = re.search(r"Result:\s*(.*)", response, re.DOTALL)
        if result_match:
            return result_match.group(1).strip()
        return response.strip()

    def create_plan(self, query: str) -> list[PlanStep]:
        """根据用户查询创建执行计划

        Args:
            query: 用户的复杂任务描述
        Returns:
            分解后的计划步骤列表
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self.plan_prompt.format(query=query)}],
            temperature=0,
        )
        content = response.choices[0].message.content
        logger.info(f"规划结果:\n{content}")

        # 解析步骤：匹配 "1. xxx" / "1、xxx" / "步骤1: xxx" 等格式
        steps = []
        for line in content.strip().split("\n"):
            line = line.strip()
            match = re.match(r"(?:步骤\s*)?\d+[.、:：]\s*(.+)", line)
            if match:
                steps.append(PlanStep(task=match.group(1)))

        self.plan = steps
        logger.info(f"创建计划，共 {len(steps)} 个步骤")
        return steps

    def execute_step(self, step: PlanStep, previous_results: str) -> PlanStep:
        """执行单个计划步骤

        Args:
            step: 待执行的计划步骤
            previous_results: 已完成步骤的结果摘要
        Returns:
            更新后的计划步骤（包含状态和结果）
        """
        messages = [
            {
                "role": "user",
                "content": self.execute_prompt.format(
                    step_task=step.task,
                    previous_results=previous_results,
                    tools_description=self._get_tools_description(),
                ),
            }
        ]

        for attempt in range(self.max_retries):
            logger.info(f"执行步骤: {step.task} (尝试 {attempt + 1})")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
            content = response.choices[0].message.content
            logger.info(f"LLM响应: {content}")

            # 检查是否需要调用工具
            tool_name, tool_args = self._parse_action(content)
            if tool_name and tool_name in self.tools:
                try:
                    tool_result = self.tools[tool_name](tool_args)
                    logger.info(f"工具返回: {tool_result}")
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": f"Observation: {tool_result}"})
                    continue  # 继续对话获取最终结果
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.result = f"工具调用错误: {str(e)}"
                    return step

            # 解析结果
            result = self._parse_result(content)
            step.status = StepStatus.COMPLETED
            step.result = result
            return step

        step.status = StepStatus.FAILED
        step.result = "达到最大重试次数"
        return step

    def run(self, query: str) -> str:
        """运行完整的 Plan-Execute 流程

        Args:
            query: 用户的复杂任务描述
        Returns:
            执行结果汇总报告
        """
        query = _sanitize_text(query)
        # 1. 创建计划
        self.create_plan(query)
        if not self.plan:
            return "无法创建执行计划"

        # 2. 逐步执行
        previous_results = ""
        for i, step in enumerate(self.plan):
            logger.info(f"执行步骤 {i + 1}/{len(self.plan)}: {step.task}")
            self.execute_step(step, previous_results)

            if step.status == StepStatus.COMPLETED:
                previous_results += f"\n步骤{i + 1} ({step.task}): {step.result}"
            else:
                previous_results += f"\n步骤{i + 1} ({step.task}): 执行失败 - {step.result}"

        # 3. 汇总结果
        completed = [s for s in self.plan if s.status == StepStatus.COMPLETED]
        summary = f"执行完成：{len(completed)}/{len(self.plan)} 步骤成功\n\n"
        for i, step in enumerate(self.plan):
            status_icon = "V" if step.status == StepStatus.COMPLETED else "X"
            summary += f"{status_icon} 步骤{i + 1}: {step.task}\n  结果: {step.result}\n\n"

        return summary
