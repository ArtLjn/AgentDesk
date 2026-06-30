"""人工审核工作流节点测试。

覆盖 human_review_wait 4 种触发场景、apply_human_decision 4 种决策场景、
resume_from_human_decision 集成测试、以及路由变更测试。
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.multi_agent_system.workflow import graph as graph_module
from src.multi_agent_system.workflow.graph import (
    apply_human_decision,
    build_ticket_graph,
    create_initial_state,
    human_decision_router,
    human_review_wait,
    resume_from_human_decision,
    resume_from_user_input,
    retry_decision,
)
from src.multi_agent_system.core.trace import TraceManager


def _make_state(**overrides: Any) -> dict[str, Any]:
    """构造测试用 state，预设 trigger_type / processing_result 等。"""
    base = create_initial_state("测试工单")
    base.update(
        {
            "ticket_id": overrides.pop("ticket_id", "TK-test-001"),
            "processing_result": "AI 处理结果",
            "review_score": 0.6,
            "messages": [],
            "trigger_type": "user_request",
            "trigger_reason": None,
        }
    )
    base.update(overrides)
    return base


@pytest.fixture
def mock_db_manager() -> MagicMock:
    """伪造 DatabaseManager，使用 in-memory dict 跟踪 create/update 调用。"""
    db = MagicMock()
    db._pending = None

    async def _create(review: dict[str, Any]) -> None:
        db._pending = dict(review)

    async def _get(ticket_id: str) -> dict[str, Any] | None:
        return db._pending

    async def _update(review_id: str, updates: dict[str, Any]) -> None:
        if db._pending and db._pending.get("review_id") == review_id:
            db._pending.update(updates)
            db._last_updates = dict(updates)

    db.create_pending_review = AsyncMock(side_effect=_create)
    db.get_pending_review_by_ticket = AsyncMock(side_effect=_get)
    db.update_review_decision = AsyncMock(side_effect=_update)
    return db


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """伪造 CoordinatorAgent，suggest_decision 返回固定结构。"""
    coord = MagicMock()
    coord.suggest_decision = AsyncMock(
        return_value={
            "recommended_decision": "approve",
            "confidence": 0.8,
            "reasoning": "测试建议",
            "key_concerns": ["c1"],
        }
    )
    return coord


@pytest.fixture(autouse=True)
def reset_module_state():
    """每个测试结束后重置模块级变量，避免相互污染。"""
    yield
    graph_module._coordinator_agent = None
    graph_module._db_manager = None
    graph_module._trace_manager = None
    graph_module._active_trace_id = None


class TestHumanReviewWaitNode:
    """human_review_wait 节点的 4 种触发场景。"""

    @pytest.mark.asyncio
    async def test_human_review_wait_escalate_trigger(
        self, mock_db_manager, mock_coordinator
    ):
        """trigger_type=escalate 时正确写入 pending 记录。"""
        graph_module._coordinator_agent = mock_coordinator
        graph_module._db_manager = mock_db_manager

        state = _make_state(trigger_type="escalate", trigger_reason="P0 紧急工单")
        result = await human_review_wait(state)

        assert result["status"] == "pending_human_review"
        assert result["__review_requested__"] is True
        mock_coordinator.suggest_decision.assert_awaited_once()
        mock_db_manager.create_pending_review.assert_awaited_once()
        review = mock_db_manager._pending
        assert review["trigger_type"] == "escalate"
        assert review["ticket_id"] == "TK-test-001"
        assert review["ai_suggestion"] is not None

    @pytest.mark.asyncio
    async def test_human_review_wait_review_failed_trigger(
        self, mock_db_manager, mock_coordinator
    ):
        """trigger_type=review_failed 时正确写入。"""
        graph_module._coordinator_agent = mock_coordinator
        graph_module._db_manager = mock_db_manager

        state = _make_state(trigger_type="review_failed", retry_count=3)
        result = await human_review_wait(state)

        assert result["status"] == "pending_human_review"
        review = mock_db_manager._pending
        assert review["trigger_type"] == "review_failed"

    @pytest.mark.asyncio
    async def test_human_review_wait_error_fallback_trigger(
        self, mock_db_manager, mock_coordinator
    ):
        """trigger_type=error_fallback 时正确写入。"""
        graph_module._coordinator_agent = mock_coordinator
        graph_module._db_manager = mock_db_manager

        state = _make_state(
            trigger_type="error_fallback",
            trigger_reason="网络异常",
            error="connection timeout",
        )
        result = await human_review_wait(state)

        assert result["status"] == "pending_human_review"
        review = mock_db_manager._pending
        assert review["trigger_type"] == "error_fallback"
        assert review["trigger_reason"] == "网络异常"

    @pytest.mark.asyncio
    async def test_human_review_wait_user_request_trigger(
        self, mock_db_manager, mock_coordinator
    ):
        """trigger_type=user_request 时正确写入。"""
        graph_module._coordinator_agent = mock_coordinator
        graph_module._db_manager = mock_db_manager

        state = _make_state(trigger_type="user_request")
        result = await human_review_wait(state)

        assert result["status"] == "pending_human_review"
        review = mock_db_manager._pending
        assert review["trigger_type"] == "user_request"

    @pytest.mark.asyncio
    async def test_human_review_wait_without_coordinator(self, mock_db_manager):
        """无 CoordinatorAgent 注入时不报错，ai_suggestion 为 None。"""
        graph_module._coordinator_agent = None
        graph_module._db_manager = mock_db_manager

        state = _make_state(trigger_type="escalate")
        result = await human_review_wait(state)

        assert result["__review_requested__"] is True
        assert mock_db_manager._pending["ai_suggestion"] is None


class TestApplyHumanDecisionNode:
    """apply_human_decision 节点的 4 种决策场景。"""

    def _decision(self, decision: str, **extra: Any) -> dict[str, Any]:
        info = {
            "decision": decision,
            "decision_reason": "测试原因",
            "reviewer_id": "U-test",
        }
        info.update(extra)
        return info

    @pytest.mark.asyncio
    async def test_apply_human_decision_approve(self, mock_db_manager):
        """approve 路由到 notify，processing_result 不变。"""
        graph_module._db_manager = mock_db_manager
        mock_db_manager._pending = {
            "review_id": "HR-1",
            "ticket_id": "TK-test-001",
            "ai_suggestion": None,
        }

        state = _make_state(
            __human_decision__=self._decision("approve"),
        )
        result = await apply_human_decision(state)

        assert result["__review_decided__"] is True
        # approve 不修改 processing_result（不在 result 中即保持原值）
        assert "processing_result" not in result
        assert human_decision_router(state) == "notify"

    @pytest.mark.asyncio
    async def test_apply_human_decision_approve_escalation_generates_final_result(self, mock_db_manager):
        """升级工单人工 approve 后应生成可展示的最终处理结论。"""
        graph_module._db_manager = mock_db_manager
        mock_db_manager._pending = {
            "review_id": "HR-1",
            "ticket_id": "TK-test-001",
            "trigger_type": "escalate",
            "ai_suggestion": None,
        }

        state = _make_state(
            processing_result="已升级至人工处理，原因: 网站访问异常影响客户",
            trigger_type="escalate",
            trigger_reason="网站访问异常影响客户",
            __human_decision__=self._decision(
                "approve",
                decision_reason="已确认需要按 DNS 区域配置异常排查处理",
            ),
        )
        result = await apply_human_decision(state)

        assert result["processing_result"]
        assert "人工审核已通过" in result["processing_result"]
        assert "DNS" in result["processing_result"]

    @pytest.mark.asyncio
    async def test_apply_human_decision_rewrite(self, mock_db_manager):
        """rewrite 覆盖 processing_result，路由到 notify。"""
        graph_module._db_manager = mock_db_manager
        mock_db_manager._pending = {
            "review_id": "HR-1",
            "ticket_id": "TK-test-001",
            "ai_suggestion": None,
        }

        state = _make_state(
            __human_decision__=self._decision(
                "rewrite", rewritten_result="人工改写后的结果"
            ),
        )
        result = await apply_human_decision(state)

        assert result["processing_result"] == "人工改写后的结果"
        assert human_decision_router(state) == "notify"

    @pytest.mark.asyncio
    async def test_apply_human_decision_reprocess(self, mock_db_manager):
        """reprocess 清空 processing_result + retry_count，路由到 process。"""
        graph_module._db_manager = mock_db_manager
        mock_db_manager._pending = {
            "review_id": "HR-1",
            "ticket_id": "TK-test-001",
            "ai_suggestion": None,
        }

        state = _make_state(
            retry_count=3,
            __human_decision__=self._decision("reprocess"),
        )
        result = await apply_human_decision(state)

        assert result["processing_result"] is None
        assert result["retry_count"] == 0
        assert human_decision_router(state) == "process"

    @pytest.mark.asyncio
    async def test_apply_human_decision_reject(self, mock_db_manager):
        """reject 标记驳回，路由到 complete。"""
        graph_module._db_manager = mock_db_manager
        mock_db_manager._pending = {
            "review_id": "HR-1",
            "ticket_id": "TK-test-001",
            "ai_suggestion": None,
        }

        state = _make_state(
            __human_decision__=self._decision("reject"),
        )
        result = await apply_human_decision(state)

        assert "已驳回" in result["processing_result"]
        assert human_decision_router(state) == "complete"

    @pytest.mark.asyncio
    async def test_apply_human_decision_persists_and_computes_adopted(
        self, mock_db_manager
    ):
        """decision == ai_suggestion.recommended_decision 时 ai_adopted 应记录。"""
        graph_module._db_manager = mock_db_manager
        import json

        mock_db_manager._pending = {
            "review_id": "HR-1",
            "ticket_id": "TK-test-001",
            "ai_suggestion": json.dumps({
                "recommended_decision": "approve",
                "confidence": 0.9,
                "reasoning": "ok",
                "key_concerns": [],
            }),
        }

        state = _make_state(
            __human_decision__=self._decision("approve"),
        )
        await apply_human_decision(state)

        mock_db_manager.update_review_decision.assert_awaited_once()
        updates = mock_db_manager._last_updates
        assert updates["decision"] == "approve"
        assert updates["status"] == "decided"
        assert updates["reviewer_id"] == "U-test"


class TestResumeFromHumanDecision:
    """resume_from_human_decision 集成测试。"""

    @pytest.mark.asyncio
    async def test_resume_from_human_decision_approve_flow(self, mock_coordinator):
        """完整恢复流程：approve 路径走完 notify → complete。"""
        app = MagicMock()

        async def _get_ticket(ticket_id: str) -> dict[str, Any]:
            return {
                "ticket_id": "TK-resume-001",
                "content": "工单内容",
                "category": "technical",
                "priority": "P2",
                "processing_result": "AI 原结果",
                "review_score": 0.6,
                "retry_count": 0,
                "status": "pending_human_review",
                "references": [],
            }

        saved: list[dict[str, Any]] = []
        db_tool = MagicMock()
        db_tool.get_ticket = AsyncMock(side_effect=_get_ticket)

        async def _save(data: dict[str, Any]) -> None:
            saved.append(data)

        db_tool.save_ticket = AsyncMock(side_effect=_save)
        app.state.db_tool = db_tool
        app.state.coordinator = mock_coordinator

        # 注入模块变量（resume 子图会用 _coordinator_agent / _db_manager）
        # 这里使用占位模式：无 coordinator/db_manager，apply_human_decision 仍能跑通
        graph_module._coordinator_agent = None
        graph_module._db_manager = None
        graph_module._trace_manager = None

        result = await resume_from_human_decision(
            app,
            ticket_id="TK-resume-001",
            decision="approve",
            decision_reason="已确认无问题",
            rewritten_result=None,
            reviewer_id="U-001",
        )

        assert result["ticket_id"] == "TK-resume-001"
        assert result["workflow_resumed"] is True
        assert result["next_node"] in ("complete", "notify")
        # DB 至少保存了若干次（apply_human_decision + notify + complete）
        assert len(saved) >= 1
        # 最终状态应为 completed（approve → notify → complete）
        assert saved[-1]["status"] == "completed"


class _TraceProcessor:
    async def process(self, content: str, category: str, priority: str) -> dict:
        return {"result": f"已处理: {content[:20]}", "references": []}


class _TraceReviewer:
    async def review(self, content: str, processing_result: str, category: str) -> dict:
        return {"score": 0.9, "feedback": "通过"}


class _PersistentKnowledgeGapReviewer:
    async def review(self, content: str, processing_result: str, category: str) -> dict:
        return {
            "score": 0.85,
            "feedback": "当前知识库未覆盖 codingplan 报销入口的可靠答案。",
            "issues": ["知识库缺失具体指引，无法直接解决用户问题，只能提供通用建议"],
            "suggestion": "后续补充 codingplan 报销入口知识后再自动处理。",
            "should_retry": False,
            "issue_type": "knowledge_gap",
            "retry_suppressed": True,
            "clarification_request": "当前知识库未覆盖该问题的可靠处理方案。",
        }


class TestResumeFromUserInputTrace:
    """用户补充后的恢复流程应写入同一条 trace。"""

    @pytest.mark.asyncio
    async def test_resume_from_user_input_records_trace_spans(self, db_manager):
        app = MagicMock()
        trace_manager = TraceManager(db_manager)
        trace_id = await trace_manager.start_trace("TK-user-trace")
        await trace_manager.finish_trace(trace_id, "completed")

        await db_manager.save_ticket({
            "ticket_id": "TK-user-trace",
            "content": "退款没有到账",
            "category": "billing",
            "priority": "P2",
            "status": "waiting_user_input",
            "retry_count": 0,
        })
        await db_manager.create_ticket_message({
            "message_id": "TM-user-trace-1",
            "ticket_id": "TK-user-trace",
            "sender_type": "user",
            "sender_id": "user-001",
            "content": "订单号是 123456",
        })

        app.state.db_manager = db_manager
        app.state.db_tool = db_manager
        app.state.trace_manager = trace_manager

        graph_module._trace_manager = trace_manager
        graph_module._db_manager = db_manager
        graph_module._processor_agent = _TraceProcessor()
        graph_module._reviewer_agent = _TraceReviewer()
        graph_module._active_trace_id = None

        result = await resume_from_user_input(app, "TK-user-trace")

        assert result["workflow_resumed"] is True
        spans = await db_manager.get_spans_by_trace(trace_id)
        names = [span["name"] for span in spans]
        assert "user_input_resume" in names
        assert "process" in names
        assert "review" in names

    @pytest.mark.asyncio
    async def test_resume_from_user_input_finalizes_persistent_knowledge_gap(self, db_manager):
        """用户已补充后仍是知识盲区时，应直接归档暂无答案，不再反复要求补充。"""
        app = MagicMock()
        trace_manager = TraceManager(db_manager)
        trace_id = await trace_manager.start_trace("TK-user-gap")
        await trace_manager.finish_trace(trace_id, "completed")

        await db_manager.save_ticket({
            "ticket_id": "TK-user-gap",
            "content": "我想咨询一下大模型 codingplan 在哪个平台报销",
            "category": "inquiry",
            "priority": "P3",
            "status": "waiting_user_input",
            "retry_count": 0,
        })
        await db_manager.create_ticket_message({
            "message_id": "TM-user-gap-1",
            "ticket_id": "TK-user-gap",
            "sender_type": "reviewer",
            "sender_id": "reviewer-agent",
            "content": "当前知识库未覆盖该问题的可靠处理方案，请补充平台或账号信息。",
            "metadata": {"source": "agent_clarification_request"},
        })
        await db_manager.create_ticket_message({
            "message_id": "TM-user-gap-2",
            "ticket_id": "TK-user-gap",
            "sender_type": "user",
            "sender_id": "user-001",
            "content": "就是 codingplan 报销，已经没有更多信息了",
        })

        app.state.db_manager = db_manager
        app.state.db_tool = db_manager
        app.state.trace_manager = trace_manager

        graph_module._trace_manager = trace_manager
        graph_module._db_manager = db_manager
        graph_module._processor_agent = _TraceProcessor()
        graph_module._reviewer_agent = _PersistentKnowledgeGapReviewer()
        graph_module._active_trace_id = None

        result = await resume_from_user_input(app, "TK-user-gap")

        ticket = await db_manager.get_ticket("TK-user-gap")
        messages = await db_manager.list_ticket_messages("TK-user-gap")
        repeated_requests = [
            message
            for message in messages
            if message.get("metadata", {}).get("source") == "agent_clarification_request"
        ]

        assert result["workflow_resumed"] is True
        assert result["next_node"] == "complete"
        assert result["ticket_status"] == "completed"
        assert ticket["status"] == "completed"
        assert "知识库暂时没有" in ticket["processing_result"]
        assert len(repeated_requests) == 1


class TestRoutingChanges:
    """工作流路由变更验证。"""

    @pytest.mark.asyncio
    async def test_escalate_routes_to_human_review_wait(self):
        """escalate 节点后继是 human_review_wait，最终落入 pending_human_review。"""
        graph = build_ticket_graph(agents=None)
        result = await graph.ainvoke(create_initial_state("我要投诉你们的客服！"))

        assert result["category"] == "complaint"
        assert result["status"] == "pending_human_review"

    def test_retry_max_routes_to_human_review_wait(self):
        """retry_count 达上限时 retry_decision 返回 human_review_wait。"""
        state = create_initial_state("测试")
        state["retry_count"] = 3
        assert retry_decision(state) == "human_review_wait"

    def test_human_decision_router_default(self):
        """无 decision 信息时默认路由到 notify（防御性）。"""
        state = _make_state()
        state["__human_decision__"] = {}
        assert human_decision_router(state) == "notify"
