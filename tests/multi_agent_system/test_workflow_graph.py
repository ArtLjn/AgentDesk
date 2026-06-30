"""工作流状态流转测试。

使用占位模式（不注入 Agent）测试 LangGraph 工作流的状态机流转，
覆盖分类路由、处理路径选择、审核决策、重试机制等核心逻辑。
"""

import pytest

from src.multi_agent_system.core.tool_base import ToolBase, ToolRegistry
from src.multi_agent_system.workflow.graph import (
    build_ticket_graph,
    create_initial_state,
    retry_decision,
    review_decision,
    route_decision,
)
from src.multi_agent_system.agents.processor_react import ReActProcessorAgent
from pydantic import BaseModel, Field


class _MockSearchParams(BaseModel):
    query: str = Field(description="检索查询")


class _MockSearchTool(ToolBase):
    name = "search_knowledge"
    description = "检索知识库"
    params_model = _MockSearchParams

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def execute(self, query: str) -> str:
        self.queries.append(query)
        return f"优惠券知识库命中: {query}"

    async def fallback(self, query: str) -> str:
        return "知识库不可用"


class _StaticClassifierAgent:
    async def classify(self, content: str) -> dict:
        return {"category": "inquiry", "priority": "P3", "reason": "咨询优惠券使用"}


class _StaticReviewerAgent:
    async def review(self, content: str, processing_result: str, category: str) -> dict:
        return {
            "score": 0.9,
            "feedback": "引用知识库，回复可用",
            "dimensions": {
                "accuracy": 0.28,
                "feasibility": 0.27,
                "completeness": 0.17,
                "professionalism": 0.18,
            },
            "issues": [],
            "suggestion": "保持当前回复",
            "should_retry": False,
        }


class _KnowledgeGapReviewerAgent:
    async def review(self, content: str, processing_result: str, category: str) -> dict:
        return {
            "score": 0.55,
            "feedback": "现有知识库未覆盖该接入流程。",
            "dimensions": {
                "accuracy": 0.12,
                "feasibility": 0.12,
                "completeness": 0.08,
                "professionalism": 0.16,
            },
            "issues": ["知识库未覆盖公司模型对接 Claude Code 的具体步骤"],
            "suggestion": "请用户补充模型类型、接口协议和账号环境。",
            "should_retry": False,
            "issue_type": "knowledge_gap",
            "retry_suppressed": True,
            "clarification_request": "当前知识库未覆盖该模型对接流程，请补充模型类型、接口协议和账号环境。",
        }


class _CapturingProcessorAgent:
    def __init__(self) -> None:
        self.seen_content = ""

    async def process(self, content: str, category: str, priority: str) -> dict:
        self.seen_content = content
        return {"result": "已结合补充信息处理", "references": []}


class _StaticLLMClient:
    async def chat_completions_create(self, **kwargs):  # noqa: ANN003, ANN202
        from unittest.mock import MagicMock

        return MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="Thought: enough.\nFinal Answer: 按知识库规则使用优惠券。"
                    )
                )
            ]
        )


@pytest.fixture
def graph():
    """构建占位模式的工作流图（不注入 Agent，使用关键词匹配降级逻辑）。"""
    return build_ticket_graph(agents=None)


class TestTicketWorkflow:
    """工作流状态流转测试。"""

    @pytest.mark.asyncio
    async def test_inquiry_ticket_process(self, graph):
        """咨询类工单走 process 路径（含 LLM + RAG），不再使用固定文案 auto_reply。"""
        result = await graph.ainvoke(create_initial_state("如何修改个人资料？"))

        assert result["category"] == "inquiry"
        assert result["status"] == "completed"
        assert result["processing_result"] is not None

    @pytest.mark.asyncio
    async def test_coupon_inquiry_prefetches_knowledge_in_process_path(self):
        """优惠券咨询类工单进入 process 后应稳定触发知识库检索。"""
        search_tool = _MockSearchTool()
        registry = ToolRegistry()
        registry.register(search_tool)
        processor = ReActProcessorAgent(
            model="test-model",
            tool_registry=registry,
            client=_StaticLLMClient(),
        )
        graph = build_ticket_graph(
            agents={
                "classifier": _StaticClassifierAgent(),
                "processor": processor,
                "reviewer": _StaticReviewerAgent(),
            }
        )

        result = await graph.ainvoke(create_initial_state("咨询一下平台优惠卷如何使用"))

        assert search_tool.queries == ["咨询一下平台优惠券如何使用"]
        assert result["category"] == "inquiry"
        assert result["status"] == "completed"
        assert result["references"] == ["优惠券知识库命中: 咨询一下平台优惠券如何使用"]
        assert "按知识库规则使用优惠券" in result["processing_result"]

    @pytest.mark.asyncio
    async def test_process_includes_user_input_conversation_context(self):
        """用户补充恢复时，Processor 能看到沟通上下文。"""
        processor = _CapturingProcessorAgent()
        graph = build_ticket_graph(agents={
            "processor": processor,
            "reviewer": _StaticReviewerAgent(),
        })
        state = create_initial_state("退款没有到账")
        state.update({
            "category": "billing",
            "priority": "P2",
            "conversation_context": "[reviewer] 请补充订单号\n[user] 订单号是 123456",
        })

        result = await graph.ainvoke(state)

        assert result["status"] == "completed"
        assert "退款没有到账" in processor.seen_content
        assert "订单号是 123456" in processor.seen_content

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
    async def test_reviewer_message_contains_structured_quality_review(self):
        """Reviewer 消息应体现独立质检维度，方便前端展示多 Agent 协作。"""
        graph = build_ticket_graph(agents={"reviewer": _StaticReviewerAgent()})

        result = await graph.ainvoke(create_initial_state("系统报错 ERR-5001"))

        reviewer_messages = [
            message["content"]
            for message in result["messages"]
            if message["role"] == "reviewer"
        ]
        assert reviewer_messages
        assert "准确性" in reviewer_messages[-1]
        assert "可行性" in reviewer_messages[-1]
        assert "建议" in reviewer_messages[-1]

    @pytest.mark.asyncio
    async def test_knowledge_gap_stops_retry_and_requests_user_input(self):
        """知识库盲区低分时不应反复重试或转人工，应暂停等待用户补充。"""
        graph = build_ticket_graph(agents={"reviewer": _KnowledgeGapReviewerAgent()})

        result = await graph.ainvoke(create_initial_state("询问一下公司的模型如何进行对接 claude code"))

        assert result["status"] == "waiting_user_input"
        assert result["retry_count"] == 0
        assert result["review_retry_suppressed"] is True
        assert result["review_issue_type"] == "knowledge_gap"
        assert result["processing_result"] is not None
        assert "知识库未覆盖" in result["processing_result"]
        assert any(message["role"] == "system" and "等待用户补充" in message["content"] for message in result["messages"])

    @pytest.mark.asyncio
    async def test_billing_ticket_process(self, graph):
        """账务类工单正常处理。"""
        result = await graph.ainvoke(create_initial_state("退款什么时候到账？"))

        assert result["category"] == "billing"
        assert result["status"] == "completed"
        assert result["processing_result"] is not None

    @pytest.mark.asyncio
    async def test_security_report_escalates_to_human_review(self, graph):
        """漏洞/安全风险上报应进入人工审核队列，不自动归档。"""
        result = await graph.ainvoke(
            create_initial_state("我发现支付功能有漏洞，付款后跳转到不知名网页")
        )

        assert result["category"] == "technical"
        assert result["priority"] == "P1"
        assert result["status"] == "pending_human_review"
        assert result["trigger_type"] == "escalate"
        assert "人工审核" in result["trigger_reason"]

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

    def test_inquiry_routes_to_process(self):
        """咨询类工单路由到 process（走 LLM + RAG，不再用固定文案 auto_reply）。"""
        state = create_initial_state("咨询")
        state["category"] = "inquiry"
        state["priority"] = "P3"

        assert route_decision(state) == "process"

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

    def test_security_risk_routes_to_escalate_even_when_technical_p1(self):
        """漏洞/安全风险类工单即使是 technical/P1 也应转人工审核。"""
        state = create_initial_state("我发现支付功能有漏洞，付款后会跳转到不知名网页")
        state["category"] = "technical"
        state["priority"] = "P1"

        assert route_decision(state) == "escalate"

    def test_billing_business_action_routes_to_escalate(self):
        """业务动作 contract 触发人工闭环，避免 Agent 自主归档。"""
        state = create_initial_state("用户描述了一件账务问题")
        state["category"] = "billing"
        state["priority"] = "P1"
        state["risk_level"] = "medium"
        state["requires_human_review"] = True
        state["risk_reason"] = "涉及真实账务处理，需要人工核查订单和支付流水"

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

    def test_reviewer_retry_signal_triggers_retry(self):
        """Reviewer 明确建议返工时，即使分数达标也触发重试检查。"""
        state = create_initial_state("测试")
        state["review_score"] = 0.85
        state["review_should_retry"] = True

        assert review_decision(state) == "retry_check"

    def test_retry_suppressed_routes_to_user_input(self):
        """不可通过重试修复的问题应走用户补充，不进入重试检查。"""
        state = create_initial_state("测试")
        state["review_score"] = 0.55
        state["review_should_retry"] = False
        state["review_retry_suppressed"] = True

        assert review_decision(state) == "request_user_input"

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
