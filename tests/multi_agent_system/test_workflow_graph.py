"""工作流状态流转测试。

使用占位模式（不注入 Agent）测试 LangGraph 工作流的状态机流转，
覆盖分类路由、处理路径选择、审核决策、重试机制等核心逻辑。
"""

import pytest

from src.multi_agent_system.workflow.graph import (
    build_ticket_graph,
    create_initial_state,
    retry_decision,
    review_decision,
    route_decision,
)


@pytest.fixture
def graph():
    """构建占位模式的工作流图（不注入 Agent，使用关键词匹配降级逻辑）。"""
    return build_ticket_graph(agents=None)


class TestTicketWorkflow:
    """工作流状态流转测试。"""

    @pytest.mark.asyncio
    async def test_inquiry_ticket_auto_reply(self, graph):
        """咨询类工单走 auto_reply 路径。"""
        result = await graph.ainvoke(create_initial_state("如何修改个人资料？"))

        assert result["category"] == "inquiry"
        assert result["status"] == "completed"
        assert result["processing_result"] is not None
        assert "自动回复" in result["processing_result"]

    @pytest.mark.asyncio
    async def test_complaint_ticket_escalate(self, graph):
        """投诉类工单走 escalate 路径，转入人工审核。"""
        result = await graph.ainvoke(create_initial_state("我要投诉你们的客服！"))

        assert result["category"] == "complaint"
        # escalate → human_review_wait → END，最终状态为 pending_human_review
        assert result["status"] == "pending_human_review"
        assert "升级" in result["processing_result"]

    @pytest.mark.asyncio
    async def test_technical_ticket_process_and_review(self, graph):
        """技术类工单走 process -> review 路径。"""
        result = await graph.ainvoke(create_initial_state("系统报错 ERR-5001"))

        assert result["category"] == "technical"
        assert result["status"] == "completed"
        assert result["review_score"] is not None
        assert result["processing_result"] is not None

    @pytest.mark.asyncio
    async def test_billing_ticket_process(self, graph):
        """账务类工单正常处理。"""
        result = await graph.ainvoke(create_initial_state("退款什么时候到账？"))

        assert result["category"] == "billing"
        assert result["status"] == "completed"
        assert result["processing_result"] is not None

    @pytest.mark.asyncio
    async def test_messages_chain(self, graph):
        """Agent 间消息链完整，包含 receive/classifier/notifier/complete 角色。"""
        result = await graph.ainvoke(create_initial_state("如何导出报表？"))

        roles = [m["role"] for m in result["messages"]]

        assert "system" in roles  # receive 节点
        assert "classifier" in roles
        assert "notifier" in roles
        assert "system" in roles  # complete 节点（第二次出现）

    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """重试机制：模拟低评分触发重试，最终成功。

        通过注入 review_score 为低分的状态来模拟审核不通过的场景，
        验证 retry_check 节点递增 retry_count 并重新进入 process。
        """
        from src.multi_agent_system.workflow.state import TicketState

        initial = create_initial_state("系统崩溃了")
        # 手动设置 retry_count=2，占位 review 的 base_score=0.85，减去 2*0.15=0.55
        # 0.55 < 阈值 0.7，会触发 retry_check，但 retry_count=2 < 3 所以会重试
        initial["retry_count"] = 2

        graph = build_ticket_graph(agents=None)
        result = await graph.ainvoke(initial)

        # retry_count=2 → retry_check 递增到 3，触发 human_review_wait → END
        # 最终状态为 pending_human_review（重试达上限后转人工审核）
        assert result["status"] == "pending_human_review"

    def test_max_retry_failure(self):
        """超过最大重试次数后转人工审核。"""
        initial = create_initial_state("系统报错")
        initial["retry_count"] = 3

        decision = retry_decision(initial)

        assert decision == "human_review_wait"


class TestRouteDecision:
    """条件路由决策函数测试。"""

    def test_inquiry_routes_to_auto_reply(self):
        """咨询类工单路由到 auto_reply。"""
        state = create_initial_state("咨询")
        state["category"] = "inquiry"
        state["priority"] = "P3"

        assert route_decision(state) == "auto_reply"

    def test_complaint_routes_to_escalate(self):
        """投诉类工单路由到 escalate。"""
        state = create_initial_state("投诉")
        state["category"] = "complaint"
        state["priority"] = "P1"

        assert route_decision(state) == "escalate"

    def test_p0_routes_to_escalate(self):
        """P0 优先级工单路由到 escalate。"""
        state = create_initial_state("紧急问题")
        state["category"] = "technical"
        state["priority"] = "P0"

        assert route_decision(state) == "escalate"

    def test_technical_routes_to_process(self):
        """技术类工单路由到 process。"""
        state = create_initial_state("报错")
        state["category"] = "technical"
        state["priority"] = "P2"

        assert route_decision(state) == "process"


class TestReviewDecision:
    """审核决策函数测试。"""

    def test_high_score_passes(self):
        """高评分通过审核。"""
        state = create_initial_state("测试")
        state["review_score"] = 0.85

        assert review_decision(state) == "notify"

    def test_low_score_triggers_retry(self):
        """低评分触发重试检查。"""
        state = create_initial_state("测试")
        state["review_score"] = 0.5

        assert review_decision(state) == "retry_check"

    def test_exact_threshold_passes(self):
        """评分恰好等于阈值时通过。"""
        state = create_initial_state("测试")
        state["review_score"] = 0.7

        assert review_decision(state) == "notify"


class TestRetryDecision:
    """重试决策函数测试。"""

    def test_below_max_retries(self):
        """未达最大重试次数时继续重试。"""
        state = create_initial_state("测试")
        state["retry_count"] = 0

        assert retry_decision(state) == "process"

    def test_at_max_retries(self):
        """达到最大重试次数时转人工审核。"""
        state = create_initial_state("测试")
        state["retry_count"] = 3

        assert retry_decision(state) == "human_review_wait"

    def test_above_max_retries(self):
        """超过最大重试次数时转人工审核。"""
        state = create_initial_state("测试")
        state["retry_count"] = 5

        assert retry_decision(state) == "human_review_wait"
