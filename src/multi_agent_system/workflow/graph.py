"""LangGraph 工单处理状态机定义。

使用 StateGraph 构建完整的工单处理流程，包含分类、路由、处理、审核、
重试等节点。支持 Agent 注入模式：传入 agents 时使用 LLM Agent，
否则使用占位实现（向后兼容）。
"""

import time
from typing import TYPE_CHECKING, Literal

from langgraph.graph import END, START, StateGraph

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core.logging import generate_trace_id, log_context, trace_id_var
from src.multi_agent_system.core.metrics import AGENT_EXECUTION_DURATION, AGENT_EXECUTION_TOTAL
from src.multi_agent_system.models.ticket import TicketCategory, TicketPriority
from src.multi_agent_system.workflow.state import TicketState

if TYPE_CHECKING:
    from src.multi_agent_system.agents.classifier import ClassifierAgent
    from src.multi_agent_system.agents.processor import ProcessorAgent
    from src.multi_agent_system.agents.reviewer import ReviewerAgent

__all__ = ["build_ticket_graph", "create_initial_state"]


def _get_settings() -> Settings:
    """获取配置单例。"""
    return Settings()


# 占位分类关键词映射：关键词 -> (分类, 优先级)
_CLASSIFY_RULES: dict[str, tuple[str, str]] = {
    "崩溃": (TicketCategory.TECHNICAL.value, TicketPriority.P1.value),
    "报错": (TicketCategory.TECHNICAL.value, TicketPriority.P2.value),
    "无法登录": (TicketCategory.TECHNICAL.value, TicketPriority.P1.value),
    "退款": (TicketCategory.BILLING.value, TicketPriority.P2.value),
    "账单": (TicketCategory.BILLING.value, TicketPriority.P2.value),
    "扣费": (TicketCategory.BILLING.value, TicketPriority.P1.value),
    "投诉": (TicketCategory.COMPLAINT.value, TicketPriority.P1.value),
    "不满": (TicketCategory.COMPLAINT.value, TicketPriority.P1.value),
    "咨询": (TicketCategory.INQUIRY.value, TicketPriority.P3.value),
    "如何": (TicketCategory.INQUIRY.value, TicketPriority.P3.value),
    "怎么": (TicketCategory.INQUIRY.value, TicketPriority.P3.value),
}


def create_initial_state(content: str, ticket_id: str | None = None) -> TicketState:
    """创建工单初始状态。

    Args:
        content: 工单内容
        ticket_id: 工单ID，不传时自动生成

    Returns:
        初始化后的工单状态字典
    """
    if ticket_id is None:
        ticket_id = f"TK-{generate_trace_id()}"

    # 绑定 trace_id 到日志上下文（贯穿整个工作流生命周期）
    trace_id_var.set(ticket_id)

    return TicketState(
        ticket_id=ticket_id,
        content=content,
        category=None,
        priority=None,
        processing_result=None,
        review_score=None,
        retry_count=0,
        status="received",
        messages=[],
        error=None,
    )


# ============================================================
# 节点函数
# ============================================================

# 模块级 Agent 引用（由 build_ticket_graph 注入）
_classifier_agent: "ClassifierAgent | None" = None
_processor_agent: "ProcessorAgent | None" = None
_reviewer_agent: "ReviewerAgent | None" = None


async def receive(state: TicketState) -> dict:
    """初始化工单状态，设置 status 为 received。"""
    with log_context(agent="receive"):
        return {
            "status": "received",
            "messages": state.get("messages", [])
            + [{"role": "system", "content": f"工单 {state['ticket_id']} 已接收"}],
        }


async def classify(state: TicketState) -> dict:
    """分类节点：优先使用 ClassifierAgent，不可用时降级到关键词匹配。

    Agent 内部的重试和降级由 @with_retry 装饰器统一处理，
    此处仅保留 Agent 实例不可用时的占位实现。
    """
    start = time.perf_counter()
    try:
        with log_context(agent="classifier"):
            content = state["content"]

            # Agent 可用时，直接调用（重试/降级由装饰器处理）
            if _classifier_agent is not None:
                result = await _classifier_agent.classify(content)
                category = result["category"]
                priority = result["priority"]
                reason = result.get("reason", "")
                return {
                    "category": category,
                    "priority": priority,
                    "status": "classifying",
                    "messages": state["messages"]
                    + [
                        {
                            "role": "classifier",
                            "content": f"分类结果: {category}, 优先级: {priority}, 理由: {reason}",
                        }
                    ],
                }

            # 占位分类：关键词匹配
            for keyword, (category, priority) in _CLASSIFY_RULES.items():
                if keyword in content:
                    return {
                        "category": category,
                        "priority": priority,
                        "status": "classifying",
                        "messages": state["messages"]
                        + [
                            {
                                "role": "classifier",
                                "content": f"分类结果: {category}, 优先级: {priority}",
                            }
                        ],
                    }

            # 默认分类为咨询，优先级 P3
            return {
                "category": TicketCategory.INQUIRY.value,
                "priority": TicketPriority.P3.value,
                "status": "classifying",
                "messages": state["messages"]
                + [
                    {
                        "role": "classifier",
                        "content": f"分类结果: {TicketCategory.INQUIRY.value}, 优先级: {TicketPriority.P3.value}（默认）",
                    }
                ],
            }
    except Exception:
        AGENT_EXECUTION_TOTAL.labels(agent_name="classifier", status="error").inc()
        raise
    else:
        AGENT_EXECUTION_TOTAL.labels(agent_name="classifier", status="success").inc()
    finally:
        AGENT_EXECUTION_DURATION.labels(agent_name="classifier").observe(time.perf_counter() - start)


async def route(state: TicketState) -> dict:
    """路由节点：根据分类和优先级决定后续路径。

    本节点不做状态修改，仅作为条件路由的汇聚点。
    """
    with log_context(agent="router"):
        return {}


async def process(state: TicketState) -> dict:
    """处理节点：优先使用 ProcessorAgent，不可用时降级到占位实现。

    Agent 内部的重试和降级由 @with_retry 装饰器统一处理，
    此处仅保留 Agent 实例不可用时的占位实现。
    """
    start = time.perf_counter()
    try:
        with log_context(agent="processor"):
            category = state.get("category", "")
            priority = state.get("priority", "P3")
            content = state["content"]

            # Agent 可用时，直接调用（重试/降级由装饰器处理）
            if _processor_agent is not None:
                result = await _processor_agent.process(content, category, priority)
                processing_result = result["result"]
                return {
                    "processing_result": processing_result,
                    "status": "processing",
                    "messages": state["messages"]
                    + [{"role": "processor", "content": processing_result}],
                }

            # 占位处理：根据分类生成模拟结果
            result_map = {
                TicketCategory.TECHNICAL.value: f"已排查技术问题，生成解决方案（优先级: {priority}）",
                TicketCategory.BILLING.value: f"已核实账单信息，生成处理方案（优先级: {priority}）",
            }
            processing_result = result_map.get(
                category, f"已处理工单（分类: {category}, 优先级: {priority}）"
            )

            return {
                "processing_result": processing_result,
                "status": "processing",
                "messages": state["messages"]
                + [{"role": "processor", "content": processing_result}],
            }
    except Exception:
        AGENT_EXECUTION_TOTAL.labels(agent_name="processor", status="error").inc()
        raise
    else:
        AGENT_EXECUTION_TOTAL.labels(agent_name="processor", status="success").inc()
    finally:
        AGENT_EXECUTION_DURATION.labels(agent_name="processor").observe(time.perf_counter() - start)


async def review(state: TicketState) -> dict:
    """审核节点：优先使用 ReviewerAgent，不可用时降级到占位评分。

    Agent 内部的重试和降级由 @with_retry 装饰器统一处理，
    此处仅保留 Agent 实例不可用时的占位实现。
    """
    start = time.perf_counter()
    try:
        with log_context(agent="reviewer"):
            retry_count = state.get("retry_count", 0)
            content = state["content"]
            processing_result = state.get("processing_result", "")
            category = state.get("category", "")

            # Agent 可用时，直接调用（重试/降级由装饰器处理）
            if _reviewer_agent is not None:
                result = await _reviewer_agent.review(content, processing_result, category)
                score = result["score"]
                return {
                    "review_score": score,
                    "status": "reviewing",
                    "messages": state["messages"]
                    + [
                        {
                            "role": "reviewer",
                            "content": f"审核评分: {score:.2f}, 反馈: {result.get('feedback', '')}",
                        }
                    ],
                }

            # 占位审核：重试次数越多，评分越低
            base_score = 0.85
            score = max(0.3, base_score - retry_count * 0.15)

            return {
                "review_score": score,
                "status": "reviewing",
                "messages": state["messages"]
                + [{"role": "reviewer", "content": f"审核评分: {score:.2f}"}],
            }
    except Exception:
        AGENT_EXECUTION_TOTAL.labels(agent_name="reviewer", status="error").inc()
        raise
    else:
        AGENT_EXECUTION_TOTAL.labels(agent_name="reviewer", status="success").inc()
    finally:
        AGENT_EXECUTION_DURATION.labels(agent_name="reviewer").observe(time.perf_counter() - start)


async def auto_reply(state: TicketState) -> dict:
    """咨询类工单直接生成回复。"""
    with log_context(agent="auto_reply"):
        reply = f"感谢您的咨询。关于「{state['content'][:50]}」，已为您生成自动回复。"
        return {
            "processing_result": reply,
            "status": "processing",
            "messages": state["messages"] + [{"role": "auto_reply", "content": reply}],
        }


async def escalate(state: TicketState) -> dict:
    """升级节点：P0 或投诉类工单标记需要人工处理。"""
    with log_context(agent="escalation"):
        category = state.get("category", "")
        priority = state.get("priority", "P3")

        reason = (
            "P0 紧急工单"
            if priority == TicketPriority.P0.value
            else f"投诉类工单（分类: {category}）"
        )
        escalation_msg = f"已升级至人工处理，原因: {reason}"

        return {
            "processing_result": escalation_msg,
            "status": "processing",
            "messages": state["messages"]
            + [{"role": "escalator", "content": escalation_msg}],
        }


async def notify(state: TicketState) -> dict:
    """发送处理结果通知。"""
    with log_context(agent="notification"):
        result = state.get("processing_result", "无处理结果")
        notification = f"通知: 工单 {state['ticket_id']} 处理完成 - {result}"

        return {
            "messages": state["messages"] + [{"role": "notifier", "content": notification}],
        }


async def complete(state: TicketState) -> dict:
    """归档节点：标记工单状态为已完成。"""
    with log_context(agent="complete"):
        return {
            "status": "completed",
            "messages": state["messages"]
            + [{"role": "system", "content": f"工单 {state['ticket_id']} 已归档完成"}],
        }


async def handle_failure(state: TicketState) -> dict:
    """失败处理节点：标记工单状态为失败。"""
    with log_context(agent="failure_handler"):
        error_msg = f"工单处理失败，已达最大重试次数({_get_settings().max_retries}次)"
        AGENT_EXECUTION_TOTAL.labels(agent_name="failure_handler", status="error").inc()
        return {
            "status": "failed",
            "error": error_msg,
            "messages": state["messages"] + [{"role": "system", "content": error_msg}],
        }


# ============================================================
# 条件边函数
# ============================================================


def route_decision(state: TicketState) -> Literal["auto_reply", "escalate", "process"]:
    """路由决策：根据分类和优先级选择处理路径。

    - 咨询类 -> auto_reply
    - 投诉类 -> escalate
    - P0 优先级 -> escalate
    - 其他 -> process
    """
    category = state.get("category", "")
    priority = state.get("priority", "P3")

    if category == TicketCategory.INQUIRY.value:
        return "auto_reply"
    if category == TicketCategory.COMPLAINT.value:
        return "escalate"
    if priority == TicketPriority.P0.value:
        return "escalate"
    return "process"


def review_decision(state: TicketState) -> Literal["notify", "retry_check"]:
    """审核决策：根据评分决定是否通过。

    - score >= 阈值 -> notify（通过）
    - score < 阈值 -> retry_check（重试检查）
    """
    score = state.get("review_score", 0.0)
    if score >= _get_settings().review_threshold:
        return "notify"
    return "retry_check"


def retry_decision(state: TicketState) -> Literal["process", "handle_failure"]:
    """重试决策：检查重试次数是否已达上限。

    - retry_count < 3 -> process（重试）
    - retry_count >= 3 -> handle_failure（放弃）
    """
    retry_count = state.get("retry_count", 0)
    if retry_count < _get_settings().max_retries:
        return "process"
    return "handle_failure"


# ============================================================
# retry_check 节点（递增 retry_count 后进入条件边）
# ============================================================


async def retry_check(state: TicketState) -> dict:
    """重试检查节点：递增重试计数。"""
    with log_context(agent="retry_check"):
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "review_score": None,  # 重置评分，等待重新审核
        }


# ============================================================
# 图构建
# ============================================================


def build_ticket_graph(
    settings: Settings | None = None,
    agents: dict | None = None,
) -> StateGraph:
    """构建工单处理状态图。

    Args:
        settings: 系统配置（预留，当前未使用）
        agents: Agent 实例字典，支持以下键：
            - "classifier": ClassifierAgent 实例
            - "processor": ProcessorAgent 实例
            - "reviewer": ReviewerAgent 实例
            为 None 时使用占位实现（向后兼容）

    Returns:
        已编译的 CompiledStateGraph，可直接调用 invoke/ainvoke
    """
    # 注入 Agent 到模块级变量
    global _classifier_agent, _processor_agent, _reviewer_agent  # noqa: PLW0603

    if agents is not None:
        _classifier_agent = agents.get("classifier")
        _processor_agent = agents.get("processor")
        _reviewer_agent = agents.get("reviewer")
    else:
        _classifier_agent = None
        _processor_agent = None
        _reviewer_agent = None

    graph = StateGraph(TicketState)

    # 添加所有节点
    graph.add_node("receive", receive)
    graph.add_node("classify", classify)
    graph.add_node("route", route)
    graph.add_node("process", process)
    graph.add_node("review", review)
    graph.add_node("auto_reply", auto_reply)
    graph.add_node("escalate", escalate)
    graph.add_node("notify", notify)
    graph.add_node("complete", complete)
    graph.add_node("handle_failure", handle_failure)
    graph.add_node("retry_check", retry_check)

    # 定义边：线性流程
    graph.add_edge(START, "receive")
    graph.add_edge("receive", "classify")
    graph.add_edge("classify", "route")

    # 条件路由：route -> process | auto_reply | escalate
    graph.add_conditional_edges("route", route_decision)

    # 处理路径：process -> review
    graph.add_edge("process", "review")

    # 审核决策：review -> notify | retry_check
    graph.add_conditional_edges("review", review_decision)

    # 重试决策：retry_check -> process | handle_failure
    graph.add_conditional_edges("retry_check", retry_decision)

    # 各路径汇聚到 notify -> complete -> END
    graph.add_edge("auto_reply", "notify")
    graph.add_edge("escalate", "notify")
    graph.add_edge("notify", "complete")
    graph.add_edge("complete", END)
    graph.add_edge("handle_failure", END)

    return graph.compile()
