"""Reflection Agent 及 ReflectionResult 的单元测试"""

import pytest

from archive.learning.basic_agents.reflection_agent import ReflectionAgent, ReflectionResult
from archive.learning.basic_agents.tools.calculator import calculator


class TestReflectionResult:
    """ReflectionResult 数据类测试"""

    def test_default_values(self) -> None:
        result = ReflectionResult(answer="测试", reflection="反思")
        assert result.score == 0
        assert result.is_satisfactory is False

    def test_custom_values(self) -> None:
        result = ReflectionResult(
            answer="答案", reflection="很好", score=8, is_satisfactory=True
        )
        assert result.score == 8
        assert result.is_satisfactory is True


class TestReflectionAgent:
    """Reflection Agent 非LLM部分测试"""

    def test_initialization(self) -> None:
        agent = ReflectionAgent(model="test")
        assert agent.reflection_history == []
        assert agent.max_reflections == 3
        assert agent.min_satisfactory_score == 7

    def test_lazy_client(self) -> None:
        agent = ReflectionAgent(model="test")
        assert agent._client is None

    def test_tool_registration(self) -> None:
        agent = ReflectionAgent(model="test")
        agent.register_tool("calculator", calculator)
        assert "calculator" in agent.tools

    def test_get_tools_description(self) -> None:
        agent = ReflectionAgent(model="test")
        agent.register_tool("calculator", calculator)
        desc = agent._get_tools_description()
        assert "calculator" in desc
        assert "计算器工具" in desc

    def test_parse_answer_with_prefix(self) -> None:
        agent = ReflectionAgent(model="test")
        result = agent._parse_answer("Answer: 计算结果是42")
        assert result == "计算结果是42"

    def test_parse_answer_without_prefix(self) -> None:
        agent = ReflectionAgent(model="test")
        result = agent._parse_answer("直接结果")
        assert result == "直接结果"

    def test_parse_action(self) -> None:
        agent = ReflectionAgent(model="test")
        tool_name, tool_args = agent._parse_action("Action: calculator(2+3)")
        assert tool_name == "calculator"
        assert tool_args == "2+3"

    def test_parse_action_no_match(self) -> None:
        agent = ReflectionAgent(model="test")
        tool_name, tool_args = agent._parse_action("纯文本，无 Action")
        assert tool_name == ""
        assert tool_args == ""

    def test_parse_reflection_satisfactory(self) -> None:
        agent = ReflectionAgent(model="test")
        response = """Score: 8
Evaluation: 回答准确完整
Verdict: satisfactory"""
        result = agent._parse_reflection(response)
        assert result.score == 8
        assert result.is_satisfactory is True
        assert "准确" in result.reflection

    def test_parse_reflection_unsatisfactory(self) -> None:
        agent = ReflectionAgent(model="test")
        response = """Score: 4
Evaluation: 回答不够完整
Verdict: unsatisfactory"""
        result = agent._parse_reflection(response)
        assert result.score == 4
        assert result.is_satisfactory is False

    def test_parse_reflection_case_insensitive_verdict(self) -> None:
        agent = ReflectionAgent(model="test")
        response = """Score: 9
Evaluation: 优秀
Verdict: Satisfactory"""
        result = agent._parse_reflection(response)
        assert result.is_satisfactory is True

    def test_format_previous_attempts_empty(self) -> None:
        agent = ReflectionAgent(model="test")
        result = agent._format_previous_attempts()
        assert result == "无"

    def test_format_previous_attempts_with_data(self) -> None:
        agent = ReflectionAgent(model="test")
        agent.reflection_history = [
            ReflectionResult(
                answer="答案1", reflection="不够好", score=5, is_satisfactory=False
            )
        ]
        result = agent._format_previous_attempts()
        assert "第1次尝试" in result
        assert "答案1" in result

    def test_format_previous_attempts_multiple(self) -> None:
        agent = ReflectionAgent(model="test")
        agent.reflection_history = [
            ReflectionResult(
                answer="答案1", reflection="不好", score=3, is_satisfactory=False
            ),
            ReflectionResult(
                answer="答案2", reflection="还行", score=6, is_satisfactory=False
            ),
        ]
        result = agent._format_previous_attempts()
        assert "第1次尝试" in result
        assert "第2次尝试" in result
        assert "答案1" in result
        assert "答案2" in result

    def test_parse_reflection_missing_score(self) -> None:
        agent = ReflectionAgent(model="test")
        response = """Evaluation: 没有给出评分
Verdict: unsatisfactory"""
        result = agent._parse_reflection(response)
        assert result.score == 0
        assert result.is_satisfactory is False

    @pytest.mark.skip(reason="requires API key")
    def test_run_with_llm(self) -> None:
        """需要真实API Key的集成测试，CI中跳过"""
        agent = ReflectionAgent()
        agent.register_tool("calculator", calculator)
        result = agent.run("计算2的10次方")
        assert "1024" in result
