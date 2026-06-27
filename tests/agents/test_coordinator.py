"""CoordinatorAgent 辅助决策（suggest_decision）单元测试。

覆盖场景：
1. LLM 正常返回 JSON -> 直接返回建议
2. LLM 抛可重试异常 -> 重试耗尽后走降级
3. LLM 返回非法 JSON -> NonRetryableError -> 走降级
4. 4 种 trigger_type 走降级 -> 输出符合规则

注意：直接测 _fallback_suggest_decision 静态方法以覆盖 4 种 trigger_type，
不依赖 with_retry 的重试延迟。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.multi_agent_system.agents.coordinator import CoordinatorAgent


def _make_llm_response(content: str) -> MagicMock:
    """构造 LLM API mock 响应。"""
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    return resp


def _build_agent() -> CoordinatorAgent:
    """构造一个不触发 Settings 实例化的 CoordinatorAgent。"""
    notif = MagicMock()
    know = MagicMock()
    agent = CoordinatorAgent(
        model="test-model",
        notification_tool=notif,
        knowledge_tool=know,
        api_key="test-key",
        base_url="http://test",
    )
    return agent


class TestSuggestDecision:
    """suggest_decision 方法覆盖测试。"""

    @pytest.mark.asyncio
    async def test_suggest_decision_llm_success(self) -> None:
        """场景 1：LLM 正常返回 JSON，直接返回建议。"""
        agent = _build_agent()
        expected = {
            "recommended_decision": "approve",
            "confidence": 0.85,
            "reasoning": "AI 处理完整、无安全隐患",
            "key_concerns": ["无"],
        }
        agent._client = AsyncMock()
        agent._client.chat_completions_create = AsyncMock(
            return_value=_make_llm_response(json.dumps(expected, ensure_ascii=False))
        )

        result = await agent.suggest_decision(
            ticket_id="TK-001",
            trigger_type="user_request",
            trigger_reason="用户主动复审",
            processing_result="已回复解决方案",
            review_score=0.85,
        )

        assert result["recommended_decision"] == "approve"
        assert result["confidence"] == 0.85
        assert "无安全隐患" in result["reasoning"]
        # 验证全部 4 个字段都返回
        assert set(result.keys()) >= {
            "recommended_decision", "confidence", "reasoning", "key_concerns"
        }
        assert isinstance(result["key_concerns"], list)

    @pytest.mark.asyncio
    async def test_suggest_decision_invalid_structure_falls_back(self) -> None:
        """场景：LLM 返回结构不合规（非法 recommended_decision），触发降级。"""
        agent = _build_agent()
        # recommended_decision=bogus 不是合法枚举值
        bad_payload = {"recommended_decision": "bogus", "confidence": 0.5}
        agent._client = AsyncMock()
        agent._client.chat_completions_create = AsyncMock(
            return_value=_make_llm_response(json.dumps(bad_payload, ensure_ascii=False))
        )

        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await agent.suggest_decision(
                ticket_id="TK-004",
                trigger_type="user_request",
                trigger_reason="用户主动复审",
                processing_result=None,
                review_score=None,
            )

        assert result.get("fallback") is True
        assert result["recommended_decision"] == "approve"

    @pytest.mark.asyncio
    async def test_suggest_decision_missing_required_field_falls_back(self) -> None:
        """场景：LLM 返回缺关键字段（无 reasoning），触发降级。"""
        agent = _build_agent()
        bad_payload = {"recommended_decision": "approve", "confidence": 0.9}
        agent._client = AsyncMock()
        agent._client.chat_completions_create = AsyncMock(
            return_value=_make_llm_response(json.dumps(bad_payload, ensure_ascii=False))
        )

        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await agent.suggest_decision(
                ticket_id="TK-005",
                trigger_type="error_fallback",
                trigger_reason="工作流异常",
                processing_result=None,
                review_score=None,
            )

        assert result.get("fallback") is True
        assert result["recommended_decision"] == "reprocess"

    @pytest.mark.asyncio
    async def test_suggest_decision_confidence_out_of_range_falls_back(self) -> None:
        """场景：LLM 返回 confidence=1.5 越界，触发降级。"""
        agent = _build_agent()
        bad_payload = {
            "recommended_decision": "approve",
            "confidence": 1.5,
            "reasoning": "x",
            "key_concerns": [],
        }
        agent._client = AsyncMock()
        agent._client.chat_completions_create = AsyncMock(
            return_value=_make_llm_response(json.dumps(bad_payload, ensure_ascii=False))
        )

        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await agent.suggest_decision(
                ticket_id="TK-006",
                trigger_type="escalate",
                trigger_reason="VIP",
                processing_result=None,
                review_score=None,
            )

        assert result.get("fallback") is True

    @pytest.mark.asyncio
    async def test_suggest_decision_llm_retryable_error_falls_back(self) -> None:
        """场景 2：LLM 抛可重试异常，重试耗尽后走降级。"""
        from openai import APIError

        agent = _build_agent()
        agent._client = AsyncMock()
        agent._client.chat_completions_create = AsyncMock(
            side_effect=APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            )
        )

        # patch asyncio.sleep 避免重试真实等待
        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await agent.suggest_decision(
                ticket_id="TK-002",
                trigger_type="escalate",
                trigger_reason="VIP 升级",
                processing_result=None,
                review_score=None,
            )

        # 降级路径会附加 fallback=True
        assert result.get("fallback") is True
        assert result["recommended_decision"] == "reprocess"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_suggest_decision_invalid_json_falls_back(self) -> None:
        """场景 3：LLM 返回非法 JSON，触发 NonRetryableError 后走降级。"""
        agent = _build_agent()
        agent._client = AsyncMock()
        agent._client.chat_completions_create = AsyncMock(
            return_value=_make_llm_response("这不是合法 JSON")
        )

        with patch("asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await agent.suggest_decision(
                ticket_id="TK-003",
                trigger_type="review_failed",
                trigger_reason="AI 多次审核未通过",
                processing_result="AI 草稿",
                review_score=0.4,
            )

        assert result.get("fallback") is True
        assert result["recommended_decision"] == "rewrite"
        assert result["confidence"] == 0.6

    @pytest.mark.parametrize(
        ("trigger_type", "expected_decision", "expected_confidence"),
        [
            ("escalate", "reprocess", 0.5),
            ("review_failed", "rewrite", 0.6),
            ("error_fallback", "reprocess", 0.4),
            ("user_request", "approve", 0.3),
        ],
    )
    def test_fallback_suggest_decision_by_trigger(
        self,
        trigger_type: str,
        expected_decision: str,
        expected_confidence: float,
    ) -> None:
        """场景 4：4 种 trigger_type 的降级规则。"""
        result = CoordinatorAgent._fallback_suggest_decision(trigger_type, None)
        assert result["recommended_decision"] == expected_decision
        assert result["confidence"] == expected_confidence
        assert "reasoning" in result
        assert isinstance(result["key_concerns"], list)
        assert len(result["key_concerns"]) >= 1


class TestFallbackSuggestDecisionConfidenceRange:
    """补充：所有 trigger_type 的置信度都落在 0.3-0.6 区间。"""

    @pytest.mark.parametrize(
        "trigger_type",
        ["escalate", "review_failed", "error_fallback", "user_request"],
    )
    def test_confidence_within_expected_range(self, trigger_type: str) -> None:
        result = CoordinatorAgent._fallback_suggest_decision(trigger_type, None)
        assert 0.3 <= result["confidence"] <= 0.6


class TestFallbackRegistry:
    """验证降级方法已正确注册到全局 registry。"""

    def test_registered_in_fallback_registry(self) -> None:
        from src.multi_agent_system.core import fallback_registry

        fallbacks = fallback_registry.get("coordinator.suggest_decision")
        assert len(fallbacks) >= 1
        assert fallbacks[0].__name__ == "_fallback_suggest_decision"
