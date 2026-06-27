"""Plan-React 混合模式 Agent 实现

Plan 阶段由 LLM 分解复杂任务为有序子步骤，
Execute 阶段每步委托给 ReActAgent 执行，支持灵活推理与工具调用。
"""

import os
import re
from typing import Callable, Optional

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

from archive.learning.basic_agents.plan_execute_agent import PlanStep, StepStatus
from archive.learning.basic_agents.react_agent import ReActAgent, _sanitize_text

load_dotenv()

__all__ = ["PlanReactAgent"]


class PlanReactAgent:
    """Plan-React 混合模式 Agent

    外层 Plan-Execute 负责任务分解与步骤编排，
    内层 ReAct 负责每个步骤的推理与工具调用。

    工作流程：
    1. Plan 阶段：LLM 将复杂任务分解为有序子步骤
    2. Execute 阶段：每步调用 ReActAgent.run() 灵活执行
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
        self.plan: list[PlanStep] = []

        # 内层 ReAct 执行引擎
        self._react_agent = ReActAgent(
            model=model, api_key=api_key, base_url=base_url
        )

        self.plan_prompt = """你是一个任务规划专家。请将用户的复杂任务分解为具体的、可执行的子步骤。

要求：
1. 每个子步骤应该是原子性的，可以独立执行
2. 步骤之间应该有逻辑顺序
3. 每个步骤一行，格式为：步骤编号. 步骤描述

用户任务：{query}

请给出执行计划："""

    @property
    def client(self) -> OpenAI:
        """延迟初始化 OpenAI 客户端，避免构造时就必须提供 API Key"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key or os.getenv("OPENAI_API_KEY"),
                base_url=self._base_url or os.getenv("OPENAI_BASE_URL"),
            )
        return self._client

    @property
    def tools(self) -> dict[str, Callable]:
        """代理访问内部 ReActAgent 的工具字典"""
        return self._react_agent.tools

    def register_tool(self, name: str, func: Callable, description: str = "") -> None:
        """注册工具到内部 ReActAgent

        Args:
            name: 工具名称
            func: 工具函数
            description: 工具描述（可选，默认从函数 docstring 获取）
        """
        self._react_agent.register_tool(name, func, description)
        logger.info(f"PlanReactAgent 注册工具: {name}")

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
        """使用 ReActAgent 执行单个计划步骤

        Args:
            step: 待执行的计划步骤
            previous_results: 已完成步骤的结果摘要
        Returns:
            更新后的计划步骤（包含状态和结果）
        """
        # 构造带上下文的执行提示
        context = f"当前子任务：{step.task}"
        if previous_results:
            context = f"已完成步骤的结果：\n{previous_results}\n\n{context}"

        logger.info(f"ReAct 执行步骤: {step.task}")
        try:
            result = self._react_agent.run(context)
            step.status = StepStatus.COMPLETED
            step.result = result
        except Exception as e:
            step.status = StepStatus.FAILED
            step.result = f"执行错误: {str(e)}"
            logger.error(f"步骤执行失败: {step.task} - {e}")

        return step

    def run(self, query: str) -> str:
        """运行完整的 Plan-React 流程

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

        # 2. 逐步执行（每步用 ReAct）
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
            status_icon = "✓" if step.status == StepStatus.COMPLETED else "✗"
            summary += f"{status_icon} 步骤{i + 1}: {step.task}\n  结果: {step.result}\n\n"

        return summary
