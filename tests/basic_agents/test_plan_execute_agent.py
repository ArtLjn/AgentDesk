"""Plan-Execute Agent 单元测试"""

import pytest

from src.basic_agents.plan_execute_agent import PlanExecuteAgent, PlanStep, StepStatus
from src.basic_agents.tools.calculator import calculator


class TestPlanStep:
    """PlanStep 数据类测试"""

    def test_default_status_pending(self) -> None:
        step = PlanStep(task="测试步骤")
        assert step.status == StepStatus.PENDING
        assert step.result == ""

    def test_custom_status_and_result(self) -> None:
        step = PlanStep(task="测试步骤", status=StepStatus.COMPLETED, result="完成")
        assert step.status == StepStatus.COMPLETED
        assert step.result == "完成"

    def test_failed_status(self) -> None:
        step = PlanStep(task="测试步骤", status=StepStatus.FAILED, result="出错")
        assert step.status == StepStatus.FAILED
        assert step.result == "出错"


class TestStepStatus:
    """StepStatus 枚举测试"""

    def test_status_values(self) -> None:
        assert StepStatus.PENDING == "pending"
        assert StepStatus.COMPLETED == "completed"
        assert StepStatus.FAILED == "failed"

    def test_status_is_string(self) -> None:
        assert isinstance(StepStatus.PENDING, str)


class TestPlanExecuteAgent:
    """PlanExecuteAgent 非LLM部分测试"""

    def test_tool_registration(self) -> None:
        agent = PlanExecuteAgent(model="test")
        agent.register_tool("calculator", calculator)
        assert "calculator" in agent.tools

    def test_get_tools_description(self) -> None:
        agent = PlanExecuteAgent(model="test")
        agent.register_tool("calculator", calculator)
        desc = agent._get_tools_description()
        assert "calculator" in desc
        assert "计算器" in desc

    def test_get_tools_description_no_doc(self) -> None:
        agent = PlanExecuteAgent(model="test")

        def no_doc_tool(x: str) -> str:
            return x

        agent.register_tool("no_doc", no_doc_tool)
        desc = agent._get_tools_description()
        assert "no_doc" in desc
        assert "无描述" in desc

    def test_parse_result_with_prefix(self) -> None:
        agent = PlanExecuteAgent(model="test")
        result = agent._parse_result("Result: 计算结果是42")
        assert result == "计算结果是42"

    def test_parse_result_no_prefix(self) -> None:
        agent = PlanExecuteAgent(model="test")
        result = agent._parse_result("直接结果")
        assert result == "直接结果"

    def test_parse_action_with_tool(self) -> None:
        agent = PlanExecuteAgent(model="test")
        tool_name, tool_args = agent._parse_action("Action: calculator(2+3)")
        assert tool_name == "calculator"
        assert tool_args == "2+3"

    def test_parse_action_no_match(self) -> None:
        agent = PlanExecuteAgent(model="test")
        tool_name, tool_args = agent._parse_action("Just thinking...")
        assert tool_name == ""
        assert tool_args == ""

    def test_plan_initialization(self) -> None:
        agent = PlanExecuteAgent(model="test")
        assert agent.plan == []
        assert agent.max_retries == 3

    def test_default_model(self) -> None:
        agent = PlanExecuteAgent()
        assert agent.model == "deepseek-chat"

    def test_custom_model(self) -> None:
        agent = PlanExecuteAgent(model="gpt-4")
        assert agent.model == "gpt-4"

    def test_lazy_client_initialization(self) -> None:
        """验证客户端延迟初始化——构造时不创建 OpenAI 客户端"""
        agent = PlanExecuteAgent(model="test")
        assert agent._client is None

    def test_empty_tools_description(self) -> None:
        agent = PlanExecuteAgent(model="test")
        desc = agent._get_tools_description()
        assert desc == ""

    @pytest.mark.skip(reason="requires API key")
    def test_run_with_llm(self) -> None:
        agent = PlanExecuteAgent()
        agent.register_tool("calculator", calculator)
        result = agent.run("计算1+1和2*3")
        assert "1" in result or "2" in result
