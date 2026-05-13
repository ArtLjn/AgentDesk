"""Plan-React 混合 Agent 单元测试"""

from unittest.mock import MagicMock, patch

import pytest

from src.basic_agents.plan_execute_agent import PlanStep, StepStatus
from src.basic_agents.plan_react_agent import PlanReactAgent
from src.basic_agents.tools.calculator import calculator


class TestPlanReactAgent:
    """PlanReactAgent 非LLM部分测试"""

    def test_tool_registration(self) -> None:
        agent = PlanReactAgent(model="test")
        agent.register_tool("calculator", calculator)
        assert "calculator" in agent.tools

    def test_tool_registered_to_react_agent(self) -> None:
        """验证工具同时注册到内部 ReActAgent"""
        agent = PlanReactAgent(model="test")
        agent.register_tool("calculator", calculator)
        assert "calculator" in agent._react_agent.tools

    def test_default_model(self) -> None:
        agent = PlanReactAgent()
        assert agent.model == "deepseek-chat"

    def test_custom_model(self) -> None:
        agent = PlanReactAgent(model="gpt-4")
        assert agent.model == "gpt-4"

    def test_plan_initialization(self) -> None:
        agent = PlanReactAgent(model="test")
        assert agent.plan == []

    def test_lazy_client_initialization(self) -> None:
        """验证客户端延迟初始化"""
        agent = PlanReactAgent(model="test")
        assert agent._client is None

    def test_create_plan_parsing(self) -> None:
        """验证步骤解析逻辑"""
        agent = PlanReactAgent(model="test")
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="1. 搜索资料\n2. 分析结果\n3. 撰写报告"))
        ]

        with patch("src.basic_agents.plan_react_agent.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            # 触发客户端初始化
            agent._client = mock_openai.return_value
            steps = agent.create_plan("调研某个主题")

        assert len(steps) == 3
        assert steps[0].task == "搜索资料"
        assert steps[1].task == "分析结果"
        assert steps[2].task == "撰写报告"
        assert all(s.status == StepStatus.PENDING for s in steps)

    def test_create_plan_empty_response(self) -> None:
        """验证空响应返回空计划"""
        agent = PlanReactAgent(model="test")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="无法分解此任务"))]

        with patch("src.basic_agents.plan_react_agent.OpenAI") as mock_openai:
            mock_openai.return_value.chat.completions.create.return_value = mock_response
            agent._client = mock_openai.return_value
            steps = agent.create_plan("无效任务")

        assert len(steps) == 0

    def test_execute_step_success(self) -> None:
        """验证步骤执行委托给 ReActAgent"""
        agent = PlanReactAgent(model="test")
        step = PlanStep(task="计算1+1")

        with patch.object(agent._react_agent, "run", return_value="1+1=2") as mock_run:
            result = agent.execute_step(step, "")

        assert result.status == StepStatus.COMPLETED
        assert result.result == "1+1=2"
        mock_run.assert_called_once()

    def test_execute_step_with_context(self) -> None:
        """验证前置结果作为上下文传递给 ReActAgent"""
        agent = PlanReactAgent(model="test")
        step = PlanStep(task="分析数据")
        previous = "步骤1: 搜索到3篇论文"

        with patch.object(agent._react_agent, "run", return_value="分析完成") as mock_run:
            agent.execute_step(step, previous)

        call_args = mock_run.call_args[0][0]
        assert "已完成步骤的结果" in call_args
        assert "搜索到3篇论文" in call_args
        assert "分析数据" in call_args

    def test_execute_step_failure(self) -> None:
        """验证步骤执行失败时状态正确"""
        agent = PlanReactAgent(model="test")
        step = PlanStep(task="错误的任务")

        with patch.object(agent._react_agent, "run", side_effect=RuntimeError("API 错误")):
            result = agent.execute_step(step, "")

        assert result.status == StepStatus.FAILED
        assert "API 错误" in result.result

    def test_run_full_flow(self) -> None:
        """验证完整 Plan-React 流程编排"""
        agent = PlanReactAgent(model="test")

        mock_steps = [
            PlanStep(task="步骤A"),
            PlanStep(task="步骤B"),
        ]

        def fake_create_plan(query: str) -> list[PlanStep]:
            agent.plan = mock_steps
            return mock_steps

        with (
            patch.object(agent, "create_plan", side_effect=fake_create_plan),
            patch.object(agent, "execute_step") as mock_exec,
        ):
            def fake_execute(step: PlanStep, _: str) -> PlanStep:
                step.status = StepStatus.COMPLETED
                step.result = f"完成 {step.task}"
                return step

            mock_exec.side_effect = fake_execute
            result = agent.run("测试任务")

        assert "执行完成" in result
        assert "2/2 步骤成功" in result
        assert "步骤A" in result
        assert "步骤B" in result

    def test_run_with_failed_step(self) -> None:
        """验证包含失败步骤的流程"""
        agent = PlanReactAgent(model="test")

        mock_steps = [
            PlanStep(task="成功步骤"),
            PlanStep(task="失败步骤"),
        ]

        def fake_create_plan(query: str) -> list[PlanStep]:
            agent.plan = mock_steps
            return mock_steps

        with (
            patch.object(agent, "create_plan", side_effect=fake_create_plan),
            patch.object(agent, "execute_step") as mock_exec,
        ):
            call_count = 0

            def fake_execute(step: PlanStep, _: str) -> PlanStep:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    step.status = StepStatus.COMPLETED
                    step.result = "成功"
                else:
                    step.status = StepStatus.FAILED
                    step.result = "出错"
                return step

            mock_exec.side_effect = fake_execute
            result = agent.run("测试任务")

        assert "1/2 步骤成功" in result

    def test_run_empty_plan(self) -> None:
        """验证空计划时返回提示"""
        agent = PlanReactAgent(model="test")

        with patch.object(agent, "create_plan", return_value=[]):
            result = agent.run("无法理解的任务")

        assert result == "无法创建执行计划"

    @pytest.mark.skip(reason="requires API key")
    def test_run_with_llm(self) -> None:
        agent = PlanReactAgent()
        agent.register_tool("calculator", calculator)
        result = agent.run("计算1+1和2*3")
        assert "步骤" in result
