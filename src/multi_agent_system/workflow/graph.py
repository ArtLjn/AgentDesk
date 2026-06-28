"""LangGraph 工单处理状态机定义。

使用 StateGraph 构建完整的工单处理流程，包含分类、路由、处理、审核、
重试等节点。支持 Agent 注入模式：传入 agents 时使用 LLM Agent，
否则使用占位实现（向后兼容）。
"""

from typing import TYPE_CHECKING, Any, Literal

from langgraph.graph import END, START, StateGraph
from loguru import logger

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core.logging import generate_trace_id, log_context, trace_id_var
from src.multi_agent_system.models.ticket import TicketCategory, TicketPriority
from src.multi_agent_system.workflow.state import TicketState

if TYPE_CHECKING:
    from src.multi_agent_system.agents.classifier import ClassifierAgent
    from src.multi_agent_system.agents.coordinator import CoordinatorAgent
    from src.multi_agent_system.agents.processor import ProcessorAgent
    from src.multi_agent_system.agents.reviewer import ReviewerAgent
    from src.multi_agent_system.core.database import DatabaseManager
    from src.multi_agent_system.core.trace import TraceManager

__all__ = [
    "apply_human_decision",
    "build_ticket_graph",
    "create_initial_state",
    "human_decision_router",
    "human_review_wait",
    "resume_from_human_decision",
]


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
        references=[],
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
_coordinator_agent: "CoordinatorAgent | None" = None

# 模块级 MemoryManager 引用（由 lifespan 注入）
_memory_manager = None

# 模块级 TraceManager 引用（由 lifespan 注入）
_trace_manager = None

# 模块级 DatabaseManager 引用（人工审核节点持久化使用）
_db_manager: "DatabaseManager | None" = None

# 模块级活跃 trace_id（用于跨 task 传播，绕过 contextvar 限制）
_active_trace_id: str | None = None


class _NoOpSpanContext:
    """无活跃 trace 时的空操作 span。"""

    span_id = ""
    trace_id = ""

    def set_output(self, data: dict[str, Any]) -> None:
        pass

    def set_metadata(self, data: dict[str, Any]) -> None:
        pass

    def set_status(self, status: str) -> None:
        pass

    async def __aenter__(self) -> "_NoOpSpanContext":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _restore_trace_context(state: TicketState) -> None:
    """从 state 中恢复 trace context（用于后台 task 跨节点传播）。"""
    global _active_trace_id  # noqa: PLW0603
    trace_id = state.get("__trace_id__")
    logger.debug(f"[_restore_trace_context] trace_id from state={trace_id}, current _active_trace_id={_active_trace_id}")
    if trace_id is not None:
        from src.multi_agent_system.core.trace import current_trace_id
        current_trace_id.set(trace_id)
        _active_trace_id = trace_id
        logger.debug(f"[_restore_trace_context] set _active_trace_id={trace_id}")


def _span(name: str, span_type: str = "node", **kwargs: Any):
    """获取当前 span context manager，无 TraceManager 时返回 no-op。

    优先使用模块级 _active_trace_id（跨 task 兼容），
    其次使用 contextvar current_trace_id。
    """
    if _trace_manager is None:
        logger.debug(f"[_span] {name}: _trace_manager is None")
        return _NoOpSpanContext()

    # 优先使用模块级 trace_id（跨 task 传播）
    trace_id = _active_trace_id
    if trace_id is None:
        from src.multi_agent_system.core.trace import current_trace_id
        trace_id = current_trace_id.get()

    if trace_id is None:
        logger.debug(f"[_span] {name}: trace_id is None")
        return _NoOpSpanContext()

    logger.debug(f"[_span] {name}: using trace_id={trace_id}")
    return _trace_manager.start_span(
        name=name,
        span_type=span_type,
        trace_id=trace_id,
        **kwargs,
    )


def _build_classify_decision(
    content: str,
    category: str,
    confidence: float | None,
    reason: str,
) -> dict[str, Any]:
    """构造 classify 节点的 routing 决策记录。"""
    options = [
        {"value": c.value, "score": 0.0, "reason": "未选中"}
        for c in TicketCategory
    ]
    for opt in options:
        if opt["value"] == category:
            opt["score"] = confidence if confidence is not None else 1.0
            opt["reason"] = reason or "LLM 选择"
    return {
        "decision_type": "routing",
        "trigger": {"content_preview": content[:200]},
        "options": options,
        "selection": {
            "value": category,
            "confidence": confidence if confidence is not None else 1.0,
            "reason": reason or "LLM 选择",
        },
        "execution": {"downstream_node": "route"},
    }


def _build_review_decision(score: float, threshold: float) -> dict[str, Any]:
    """构造 review 节点的 quality_gate 决策记录。"""
    passed = score >= threshold
    confidence = min(1.0, abs(score - threshold) / max(threshold, 1e-6))
    return {
        "decision_type": "quality_gate",
        "trigger": {"review_score": round(score, 4), "threshold": threshold},
        "options": [
            {"value": "pass", "score": round(score, 4), "reason": f"score >= {threshold}"},
            {"value": "retry", "score": round(1 - score, 4), "reason": f"score < {threshold}"},
        ],
        "selection": {
            "value": "pass" if passed else "retry",
            "confidence": round(confidence, 4),
            "reason": "阈值判断",
        },
    }


async def receive(state: TicketState) -> dict:
    """初始化工单状态，加载用户长期记忆。"""
    global _active_trace_id  # noqa: PLW0603
    with log_context(agent="receive"):
        # 启动 trace，并将 trace_id 写回 state 供后续节点恢复 context
        trace_id = None
        if _trace_manager is not None:
            trace_id = await _trace_manager.start_trace(state["ticket_id"])
            from src.multi_agent_system.core.trace import current_trace_id

            current_trace_id.set(trace_id)
            _active_trace_id = trace_id

        # 恢复 trace context（从 state 中读取，兼容后台 task 场景）
        _restore_trace_context(state)

        async with _span("receive", input_data={"content": state["content"]}) as span:
            # Load user context if user_id present
            user_context = {}
            if _memory_manager and state.get("user_id"):
                async with _span(
                    "load_user_context",
                    span_type="memory_call",
                    input_data={"user_id": state["user_id"]},
                ) as mem_span:
                    user_context = await _memory_manager.load_user_context(state["user_id"])
                    await _memory_manager.ensure_user(state["user_id"])
                    mem_span.set_output({"context_keys": list(user_context.keys())})

            result = {
                "status": "received",
                "user_context": user_context,
                "messages": state.get("messages", [])
                + [{"role": "system", "content": f"工单 {state['ticket_id']} 已接收"}],
                "__trace_id__": trace_id,
            }
            span.set_output({"status": "received"})
            return result


async def classify(state: TicketState) -> dict:
    """分类节点：优先使用 ClassifierAgent，不可用时降级到关键词匹配。

    Agent 内部的重试和降级由 @with_retry 装饰器统一处理，
    此处仅保留 Agent 实例不可用时的占位实现。
    """
    _restore_trace_context(state)
    with log_context(agent="classifier"):
        async with _span("classify", input_data={"content": state["content"]}) as span:
            content = state["content"]

            # Agent 可用时，直接调用（重试/降级由装饰器处理）
            if _classifier_agent is not None:
                result = await _classifier_agent.classify(content)
                category = result["category"]
                priority = result["priority"]
                reason = result.get("reason", "")
                confidence = result.get("confidence")
                span.set_output({"category": category, "priority": priority})
                span.set_metadata({"decision": _build_classify_decision(
                    content=content,
                    category=category,
                    confidence=confidence,
                    reason=reason,
                )})
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
                    span.set_output({"category": category, "priority": priority})
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
            span.set_output({"category": TicketCategory.INQUIRY.value, "priority": TicketPriority.P3.value})
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


async def route(state: TicketState) -> dict:
    """路由节点：根据分类和优先级决定后续路径。

    本节点不做状态修改，仅作为条件路由的汇聚点。
    """
    _restore_trace_context(state)
    with log_context(agent="router"):
        return {}


async def process(state: TicketState) -> dict:
    """处理节点：优先使用 ProcessorAgent，不可用时降级到占位实现。

    Agent 内部的重试和降级由 @with_retry 装饰器统一处理，
    此处仅保留 Agent 实例不可用时的占位实现。
    """
    _restore_trace_context(state)
    with log_context(agent="processor"):
        async with _span("process", input_data={"category": state.get("category"), "priority": state.get("priority")}) as span:
            category = state.get("category", "")
            priority = state.get("priority", "P3")
            content = state["content"]

            # Agent 可用时，直接调用（重试/降级由装饰器处理）
            if _processor_agent is not None:
                result = await _processor_agent.process(content, category, priority)
                processing_result = result["result"]
                references = result.get("references", [])
                span.set_output(
                    {
                        "result_length": len(processing_result),
                        "reference_count": len(references),
                    }
                )
                return {
                    "processing_result": processing_result,
                    "references": references,
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
            span.set_output({"result": "placeholder"})

            return {
                "processing_result": processing_result,
                "status": "processing",
                "messages": state["messages"]
                + [{"role": "processor", "content": processing_result}],
            }


async def review(state: TicketState) -> dict:
    """审核节点：优先使用 ReviewerAgent，不可用时降级到占位评分。

    Agent 内部的重试和降级由 @with_retry 装饰器统一处理，
    此处仅保留 Agent 实例不可用时的占位实现。
    """
    _restore_trace_context(state)
    with log_context(agent="reviewer"):
        async with _span("review", input_data={"retry_count": state.get("retry_count", 0)}) as span:
            retry_count = state.get("retry_count", 0)
            content = state["content"]
            processing_result = state.get("processing_result", "")
            category = state.get("category", "")

            # Agent 可用时，直接调用（重试/降级由装饰器处理）
            if _reviewer_agent is not None:
                result = await _reviewer_agent.review(content, processing_result, category)
                score = result["score"]
                span.set_output({"review_score": score})
                span.set_metadata({"decision": _build_review_decision(
                    score=score,
                    threshold=_get_settings().review_threshold,
                )})
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
            span.set_output({"review_score": score})

            return {
                "review_score": score,
                "status": "reviewing",
                "messages": state["messages"]
                + [{"role": "reviewer", "content": f"审核评分: {score:.2f}"}],
            }


async def auto_reply(state: TicketState) -> dict:
    """咨询类工单直接生成回复。"""
    _restore_trace_context(state)
    with log_context(agent="auto_reply"):
        async with _span("auto_reply", input_data={"category": state.get("category")}) as span:
            reply = f"感谢您的咨询。关于「{state['content'][:50]}」，已为您生成自动回复。"
            span.set_output({"reply_length": len(reply)})
            return {
                "processing_result": reply,
                "status": "processing",
                "messages": state["messages"] + [{"role": "auto_reply", "content": reply}],
            }


async def escalate(state: TicketState) -> dict:
    """升级节点：P0 或投诉类工单标记需要人工处理。"""
    _restore_trace_context(state)
    with log_context(agent="escalation"):
        async with _span("escalate", input_data={"category": state.get("category"), "priority": state.get("priority")}) as span:
            category = state.get("category", "")
            priority = state.get("priority", "P3")

            reason = (
                "P0 紧急工单"
                if priority == TicketPriority.P0.value
                else f"投诉类工单（分类: {category}）"
            )
            escalation_msg = f"已升级至人工处理，原因: {reason}"
            span.set_output({"reason": reason})

            return {
                "processing_result": escalation_msg,
                "status": "processing",
                "trigger_type": state.get("trigger_type") or "escalate",
                "trigger_reason": state.get("trigger_reason") or reason,
                "messages": state["messages"]
                + [{"role": "escalator", "content": escalation_msg}],
            }


async def notify(state: TicketState) -> dict:
    """发送处理结果通知。"""
    _restore_trace_context(state)
    with log_context(agent="notification"):
        async with _span("notify", input_data={"has_result": bool(state.get("processing_result"))}) as span:
            result = state.get("processing_result", "无处理结果")
            notification = f"通知: 工单 {state['ticket_id']} 处理完成 - {result}"
            span.set_output({"notification_length": len(notification)})

            return {
                "messages": state["messages"] + [{"role": "notifier", "content": notification}],
            }


async def complete(state: TicketState) -> dict:
    """归档节点：标记工单状态为已完成。"""
    _restore_trace_context(state)
    with log_context(agent="complete"):
        async with _span("complete") as span:
            if _trace_manager is not None:
                from src.multi_agent_system.core.trace import current_trace_id

                tid = current_trace_id.get()
                if tid:
                    await _trace_manager.finish_trace(tid, "completed")
            span.set_output({"status": "completed"})
            return {
                "status": "completed",
                "messages": state["messages"]
                + [{"role": "system", "content": f"工单 {state['ticket_id']} 已归档完成"}],
            }


async def handle_failure(state: TicketState) -> dict:
    """失败处理节点：标记工单状态为失败。"""
    _restore_trace_context(state)
    with log_context(agent="failure_handler"):
        async with _span("handle_failure", input_data={"error": state.get("error")}) as span:
            error_msg = state.get("error", f"工单处理失败，已达最大重试次数({_get_settings().max_retries}次)")
            if _trace_manager is not None:
                from src.multi_agent_system.core.trace import current_trace_id

                tid = current_trace_id.get()
                if tid:
                    await _trace_manager.finish_trace(tid, "failed", error=error_msg)
            span.set_output({"status": "failed"})
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

    - 投诉类 -> escalate
    - P0 优先级 -> escalate
    - 其他（含咨询）-> process
    """
    category = state.get("category", "")
    priority = state.get("priority", "P3")

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


def retry_decision(state: TicketState) -> Literal["process", "human_review_wait"]:
    """重试决策：检查重试次数是否已达上限。

    - retry_count < max_retries -> process（重试）
    - retry_count >= max_retries -> human_review_wait（转人工审核）
    """
    retry_count = state.get("retry_count", 0)
    if retry_count < _get_settings().max_retries:
        return "process"
    return "human_review_wait"


# ============================================================
# retry_check 节点（递增 retry_count 后进入条件边）
# ============================================================


async def retry_check(state: TicketState) -> dict:
    """重试检查节点：递增重试计数，并记录决策点。

    若 retry_count 已达上限（即将进入 human_review_wait），
    预置 trigger_type=review_failed 供人工审核节点使用。
    """
    _restore_trace_context(state)
    with log_context(agent="retry_check"):
        new_retry = state.get("retry_count", 0) + 1
        max_retries = _get_settings().max_retries
        will_escalate = new_retry >= max_retries
        result: dict[str, Any] = {
            "retry_count": new_retry,
            "review_score": None,  # 重置评分，等待重新审核
        }
        if will_escalate:
            result["trigger_type"] = state.get("trigger_type") or "review_failed"
            result["trigger_reason"] = (
                state.get("trigger_reason")
                or f"AI 多次审核未通过（retry_count={new_retry}）"
            )

        # 决策点埋点：retry vs escalate 的边界判断
        async with _span(
            "retry_check",
            input_data={"retry_count": new_retry, "max_retries": max_retries},
        ) as span:
            span.set_output({"will_escalate": will_escalate})
            span.set_metadata({"decision": {
                "decision_type": "boundary",
                "trigger": {
                    "retry_count": new_retry,
                    "max_retries": max_retries,
                    "review_score": state.get("review_score"),
                },
                "options": [
                    {
                        "value": "retry",
                        "score": 0.0 if will_escalate else 1.0,
                        "reason": f"retry_count={new_retry} < max={max_retries}",
                    },
                    {
                        "value": "escalate",
                        "score": 1.0 if will_escalate else 0.0,
                        "reason": f"retry_count={new_retry} >= max={max_retries}",
                    },
                ],
                "selection": {
                    "value": "escalate" if will_escalate else "retry",
                    "confidence": 1.0,
                    "reason": "硬阈值",
                },
            }})
        return result


# ============================================================
# 人工审核节点
# ============================================================


def _build_trigger_reason(state: TicketState, default: str = "") -> str:
    """根据触发类型构造默认 trigger_reason（调用方未提供时使用）。"""
    existing = state.get("trigger_reason")
    if existing:
        return existing
    trigger_type = state.get("trigger_type", "")
    if trigger_type == "escalate":
        return "升级工单，需人工审核"
    if trigger_type == "review_failed":
        return f"AI 多次审核未通过（retry_count={state.get('retry_count', 0)}）"
    if trigger_type == "error_fallback":
        return state.get("error") or default or "工作流执行异常"
    if trigger_type == "user_request":
        return "用户主动申请人工审核"
    return default


async def _generate_ai_suggestion(state: TicketState) -> dict | None:
    """调用 CoordinatorAgent 生成 AI 辅助决策建议，失败时返回 None。"""
    if _coordinator_agent is None:
        return None
    try:
        return await _coordinator_agent.suggest_decision(
            state["ticket_id"],
            state.get("trigger_type", ""),
            state.get("trigger_reason") or "",
            state.get("processing_result"),
            state.get("review_score"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"suggest_decision 失败，跳过 AI 建议: {e}")
        return None


async def human_review_wait(state: TicketState) -> dict:
    """人工审核暂停节点。

    副作用：
    1. 调用 CoordinatorAgent.suggest_decision 生成 AI 建议
    2. 写入 human_reviews 行（status=pending）
    3. 更新 tickets.status = pending_human_review（由调用方在 _run_workflow 处理）
    4. 创建 human_decision span（pending 状态）
    5. 返回结束标记（不阻塞等待，由 _run_workflow 检测后广播 review_requested）
    """
    _restore_trace_context(state)
    with log_context(agent="human_review_wait"):
        trigger_type = state.get("trigger_type", "user_request")
        trigger_reason = _build_trigger_reason(state)

        # 1. 生成 AI 建议（可选，失败不阻塞）
        ai_suggestion = await _generate_ai_suggestion(state)

        # 2. 写入 human_reviews pending 记录
        review_id = f"HR-{generate_trace_id()}"
        from datetime import datetime
        created_at = datetime.now().isoformat()
        if _db_manager is not None:
            await _db_manager.create_pending_review({
                "review_id": review_id,
                "ticket_id": state["ticket_id"],
                "trigger_type": trigger_type,
                "trigger_reason": trigger_reason,
                "ai_suggestion": ai_suggestion,
                "created_at": created_at,
            })

        # 3. 创建 pending span（span_type=human_decision，不计入 node_count）
        async with _span(
            "human_review_wait",
            span_type="human_decision",
            input_data={
                "trigger_type": trigger_type,
                "trigger_reason": trigger_reason,
                "review_id": review_id,
            },
        ) as span:
            span.set_output({
                "status": "pending",
                "review_id": review_id,
                "ai_suggestion": ai_suggestion,
            })

        # 4. 标记需广播 review_requested，更新工单状态
        return {
            "status": "pending_human_review",
            "__review_requested__": True,
            "messages": state["messages"]
            + [{
                "role": "human_review_wait",
                "content": f"工单已转入人工审核（trigger={trigger_type}, review_id={review_id}）",
            }],
        }


def _compute_ai_adopted(
    decision: str, ai_suggestion_raw: str | dict | None
) -> bool | None:
    """比较人工决策与 AI 建议，计算 ai_adopted。

    Returns:
        True 表示采纳、False 表示未采纳、None 表示无 AI 建议可比对。
    """
    if ai_suggestion_raw is None:
        return None
    if isinstance(ai_suggestion_raw, str):
        if not ai_suggestion_raw:
            return None
        import json
        try:
            ai_suggestion_raw = json.loads(ai_suggestion_raw)
        except json.JSONDecodeError:
            return None
    recommended = ai_suggestion_raw.get("recommended_decision") if isinstance(
        ai_suggestion_raw, dict
    ) else None
    if not recommended:
        return None
    return decision == recommended


async def apply_human_decision(state: TicketState) -> dict:
    """人工决策恢复节点。

    按决策矩阵路由（实际下一节点由 human_decision_router 条件边决定）：
    - approve → 沿用原 processing_result
    - rewrite → 用 rewritten_result 覆盖 processing_result
    - reprocess → 清空 processing_result + retry_count
    - reject → 标记 processing_result 为已驳回
    """
    _restore_trace_context(state)
    with log_context(agent="apply_human_decision"):
        decision_info = state.get("__human_decision__") or {}
        decision = decision_info.get("decision")
        decision_reason = decision_info.get("decision_reason")
        rewritten_result = decision_info.get("rewritten_result")
        reviewer_id = decision_info.get("reviewer_id")

        result: dict[str, Any] = {
            "messages": state["messages"]
            + [{
                "role": "apply_human_decision",
                "content": f"人工决策: {decision}（reviewer={reviewer_id}）",
            }],
            "__review_decided__": True,
        }

        result.update(
            _apply_decision_to_state(decision, state, rewritten_result)
        )

        await _persist_review_decision(
            state, decision_info, decision, decision_reason,
            rewritten_result, reviewer_id,
        )

        return result


def _apply_decision_to_state(
    decision: str | None,
    state: TicketState,
    rewritten_result: str | None,
) -> dict[str, Any]:
    """根据决策更新 state 中的 processing_result / retry_count 字段。"""
    current_result = state.get("processing_result")
    if decision == "approve":
        return {}  # 沿用原结果
    if decision == "rewrite":
        return {"processing_result": rewritten_result or current_result}
    if decision == "reprocess":
        return {"processing_result": None, "retry_count": 0}
    if decision == "reject":
        mark = "(已驳回) 原结果: "
        return {"processing_result": f"{mark}{current_result or '无'}"}
    return {}


async def _persist_review_decision(
    state: TicketState,
    decision_info: dict,
    decision: str | None,
    decision_reason: str | None,
    rewritten_result: str | None,
    reviewer_id: str | None,
) -> None:
    """更新 human_reviews 行、计算 ai_adopted、完成 span。"""
    if _db_manager is None:
        return
    from datetime import datetime
    decided_at = datetime.now().isoformat()

    pending = await _db_manager.get_pending_review_by_ticket(state["ticket_id"])
    if pending is None:
        logger.warning(
            f"apply_human_decision: 未找到 {state['ticket_id']} 的 pending 审核单"
        )
        return

    ai_adopted = _compute_ai_adopted(decision, pending.get("ai_suggestion"))

    await _db_manager.update_review_decision(
        pending["review_id"],
        {
            "decision": decision,
            "decision_reason": decision_reason,
            "rewritten_result": rewritten_result,
            "reviewer_id": reviewer_id,
            "status": "decided",
            "decided_at": decided_at,
        },
    )

    # 写入 decided span（span_type=human_decision，包含 decision/reviewer_id/ai_adopted）
    async with _span(
        "apply_human_decision",
        span_type="human_decision",
        input_data={"review_id": pending["review_id"], "decision": decision},
    ) as span:
        span.set_output({
            "status": "decided",
            "decision": decision,
            "reviewer_id": reviewer_id,
            "ai_adopted": ai_adopted,
        })
        span.set_metadata({
            "decision_reason": decision_reason,
            "rewritten_result": rewritten_result,
        })


def human_decision_router(
    state: TicketState,
) -> Literal["notify", "process", "complete"]:
    """根据人工决策结果路由到下一节点。"""
    decision_info = state.get("__human_decision__") or {}
    decision = decision_info.get("decision")
    if decision in ("approve", "rewrite"):
        return "notify"
    if decision == "reprocess":
        return "process"
    if decision == "reject":
        return "complete"
    return "notify"  # 默认走 notify（理论上不会到达）


# ============================================================
# 图构建
# ============================================================


def build_ticket_graph(
    settings: Settings | None = None,
    agents: dict | None = None,
    trace_manager: "TraceManager | None" = None,
    db_manager: "DatabaseManager | None" = None,
) -> StateGraph:
    """构建工单处理状态图。

    Args:
        settings: 系统配置（预留，当前未使用）
        agents: Agent 实例字典，支持以下键：
            - "classifier": ClassifierAgent 实例
            - "processor": ProcessorAgent 实例
            - "reviewer": ReviewerAgent 实例
            - "coordinator": CoordinatorAgent 实例（人工审核节点必需）
            为 None 时使用占位实现（向后兼容）
        trace_manager: Trace 实例（可选）
        db_manager: DatabaseManager 实例（人工审核节点持久化使用）

    Returns:
        已编译的 CompiledStateGraph，可直接调用 invoke/ainvoke
    """
    # 注入 Agent 和 TraceManager 到模块级变量
    global _classifier_agent, _processor_agent, _reviewer_agent  # noqa: PLW0603
    global _coordinator_agent, _trace_manager, _db_manager  # noqa: PLW0603

    if agents is not None:
        _classifier_agent = agents.get("classifier")
        _processor_agent = agents.get("processor")
        _reviewer_agent = agents.get("reviewer")
        _coordinator_agent = agents.get("coordinator")
    else:
        _classifier_agent = None
        _processor_agent = None
        _reviewer_agent = None
        _coordinator_agent = None

    _trace_manager = trace_manager
    _db_manager = db_manager

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
    graph.add_node("human_review_wait", human_review_wait)
    graph.add_node("apply_human_decision", apply_human_decision)

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

    # 重试决策：retry_check -> process | human_review_wait
    graph.add_conditional_edges("retry_check", retry_decision)

    # escalate 直接转入人工审核
    graph.add_edge("escalate", "human_review_wait")

    # 人工审核等待节点终止本次执行（审核恢复后由子图/单独入口处理）
    graph.add_edge("human_review_wait", END)

    # 人工决策恢复节点：按决策路由到 notify | process | complete
    graph.add_conditional_edges("apply_human_decision", human_decision_router)

    # 各路径汇聚到 notify -> complete -> END
    graph.add_edge("auto_reply", "notify")
    graph.add_edge("notify", "complete")
    graph.add_edge("complete", END)
    graph.add_edge("handle_failure", END)

    return graph.compile()


def _build_resume_subgraph() -> Any:
    """构造从 apply_human_decision 开始的恢复子图。

    子图节点：apply_human_decision → notify | process | complete → END
    LangGraph 0.2.x 不支持 start_node 参数，故通过独立子图实现恢复。
    """
    graph = StateGraph(TicketState)
    graph.add_node("apply_human_decision", apply_human_decision)
    graph.add_node("process", process)
    graph.add_node("review", review)
    graph.add_node("notify", notify)
    graph.add_node("complete", complete)
    graph.add_edge(START, "apply_human_decision")
    graph.add_conditional_edges("apply_human_decision", human_decision_router)
    graph.add_edge("process", "review")
    graph.add_conditional_edges("review", review_decision)
    graph.add_conditional_edges("retry_check", retry_decision)
    graph.add_node("retry_check", retry_check)
    graph.add_node("human_review_wait", human_review_wait)
    graph.add_edge("human_review_wait", END)
    graph.add_edge("notify", "complete")
    graph.add_edge("complete", END)
    return graph.compile()


def _build_resume_state(
    ticket: dict[str, Any], decision_info: dict[str, Any]
) -> TicketState:
    """从 DB 工单快照构造 resume 子图的初始 state。"""
    return TicketState(
        ticket_id=ticket.get("ticket_id", ""),
        content=ticket.get("content", ""),
        category=ticket.get("category"),
        priority=ticket.get("priority"),
        processing_result=ticket.get("processing_result"),
        references=ticket.get("references") or [],
        review_score=ticket.get("review_score"),
        retry_count=ticket.get("retry_count", 0) or 0,
        status=ticket.get("status", "pending_human_review"),
        messages=[],
        error=ticket.get("error"),
        __trace_id__=ticket.get("trace_id"),
        __human_decision__=decision_info,
    )


async def resume_from_human_decision(
    app: Any,
    ticket_id: str,
    decision: str,
    decision_reason: str,
    rewritten_result: str | None,
    reviewer_id: str,
) -> dict[str, Any]:
    """从人工决策节点恢复工作流执行。

    1. 从 DB 加载工单当前快照
    2. 构造含 __human_decision__ 的初始 state
    3. 调用恢复子图（从 apply_human_decision 开始）
    4. 流式处理后返回 next_node 与 workflow_resumed 标记

    Args:
        app: FastAPI app 实例（用于读取 app.state）
        ticket_id: 工单 ID
        decision: 人工决策（approve/reject/rewrite/reprocess）
        decision_reason: 决策原因
        rewritten_result: 改写后的处理结果（decision=rewrite 时使用）
        reviewer_id: 审核员 ID

    Returns:
        dict 含 ticket_id / status / next_node / workflow_resumed
    """
    db_tool = app.state.db_tool
    existing = await db_tool.get_ticket(ticket_id) or {}

    decision_info = {
        "decision": decision,
        "decision_reason": decision_reason,
        "rewritten_result": rewritten_result,
        "reviewer_id": reviewer_id,
    }
    initial_state = _build_resume_state(existing, decision_info)

    # 恢复 trace context
    trace_id = initial_state.get("__trace_id__")
    if trace_id:
        from src.multi_agent_system.core.trace import current_trace_id
        current_trace_id.set(trace_id)

    subgraph = _build_resume_subgraph()

    next_node: str | None = None
    final_status = initial_state.get("status", "processing")
    # 累积更新：每次迭代基于上一次的状态叠加 node_output，避免后续节点
    # 未返回某字段时被 initial existing 快照回写覆盖（rewrite 后被旧值覆盖等场景）
    current_snapshot: dict[str, Any] = dict(existing)
    async for event in subgraph.astream(initial_state):
        for node_name, node_output in event.items():
            if not isinstance(node_output, dict):
                continue
            next_node = node_name
            current_snapshot.update(node_output)
            if "status" in node_output:
                final_status = node_output["status"]

            # 同步工单快照到 DB（与 _run_workflow 行为对齐）
            merged = {**current_snapshot, "ticket_id": ticket_id}
            await db_tool.save_ticket(merged)

    return {
        "ticket_id": ticket_id,
        "status": final_status,
        "next_node": next_node,
        "workflow_resumed": True,
    }
