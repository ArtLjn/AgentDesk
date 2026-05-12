"""ReAct Agent 及计算器工具的单元测试"""

import pytest

from src.basic_agents.react_agent import ReActAgent
from src.basic_agents.tools.calculator import calculator


class TestCalculator:
    """计算器工具测试"""

    def test_add(self) -> None:
        assert calculator("2 + 3") == "5"

    def test_multiply(self) -> None:
        assert calculator("4 * 5") == "20"

    def test_complex(self) -> None:
        assert calculator("(10 + 5) / 3") == "5"

    def test_power(self) -> None:
        assert calculator("2 ** 3") == "8"

    def test_negative(self) -> None:
        assert calculator("-5 + 10") == "5"

    def test_invalid_input(self) -> None:
        result = calculator("abc")
        assert "计算错误" in result

    def test_float_result(self) -> None:
        result = calculator("10 / 3")
        assert "3.33" in result


class TestReActAgent:
    """ReAct Agent 非LLM部分测试"""

    def test_tool_registration(self) -> None:
        agent = ReActAgent(model="test")
        agent.register_tool("calculator", calculator)
        assert "calculator" in agent.tools

    def test_parse_action(self) -> None:
        agent = ReActAgent(model="test")
        tool_name, tool_args = agent._parse_action("Action: calculator(2 + 3)")
        assert tool_name == "calculator"
        assert tool_args == "2 + 3"

    def test_parse_action_no_match(self) -> None:
        agent = ReActAgent(model="test")
        tool_name, tool_args = agent._parse_action("Just thinking...")
        assert tool_name == ""
        assert tool_args == ""

    def test_parse_action_with_spaces(self) -> None:
        agent = ReActAgent(model="test")
        tool_name, tool_args = agent._parse_action("Action:  calculator( 2 + 3 )")
        assert tool_name == "calculator"

    def test_get_tools_description(self) -> None:
        agent = ReActAgent(model="test")
        agent.register_tool("calculator", calculator)
        desc = agent._get_tools_description()
        assert "calculator" in desc
        assert "计算器工具" in desc

    @pytest.mark.skip(reason="requires API key")
    def test_run_with_llm(self) -> None:
        """需要真实API Key的集成测试，CI中跳过"""
        agent = ReActAgent()
        agent.register_tool("calculator", calculator)
        result = agent.run("计算 25 乘以 4 等于多少")
        assert result
