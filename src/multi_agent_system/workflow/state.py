"""工单处理工作流状态定义。"""

from typing import TypedDict

__all__ = ["TicketState"]


class TicketState(TypedDict):
    """LangGraph 工单处理状态机的全局状态。

    Attributes:
        ticket_id: 工单唯一标识
        content: 工单内容文本
        category: 分类结果（technical/billing/complaint/inquiry）
        priority: 优先级（P0/P1/P2/P3）
        processing_result: 处理Agent的输出结果
        references: 处理过程中使用的知识库引用
        review_score: 审核评分，范围 0-1
        review_should_retry: Reviewer 是否建议返工
        review_retry_suppressed: Reviewer 判断该问题无法通过重试修复
        review_issue_type: Reviewer 问题类型（fixable/knowledge_gap/needs_clarification/out_of_scope）
        clarification_request: 面向用户的补充信息请求
        auto_finalized_review_failure: 低风险咨询质检失败后是否已自动安全归档
        conversation_context: 用户补充信息与审核员沟通上下文；存在时知识盲区不再重复追问
        retry_count: 重试次数，默认 0，上限 3
        status: 当前状态（received/classifying/processing/reviewing/completed/failed）
        messages: Agent 间通信上下文列表
        error: 错误信息
        trigger_type: 人工审核触发类型（escalate/review_failed/error_fallback/user_request）
        trigger_reason: 触发原因描述
        risk_level: 风险等级（low/medium/high/critical）
        requires_human_review: 是否需要人工审核
        risk_reason: 风险原因
        __human_decision__: 人工决策信息（仅 resume_from_human_decision 时注入）
        __review_requested__: 标记需广播 review_requested 事件
        __review_decided__: 标记需广播 review_decided 事件
    """

    ticket_id: str
    content: str
    category: str | None
    priority: str | None
    processing_result: str | None
    references: list[str]
    review_score: float | None
    review_should_retry: bool | None
    review_retry_suppressed: bool | None
    review_issue_type: str | None
    clarification_request: str | None
    auto_finalized_review_failure: bool | None
    retry_count: int
    status: str
    messages: list[dict]
    error: str | None

    # Memory fields
    thought_chain: list[dict]           # ReAct 推理链
    tool_history: list[dict]            # 工具调用历史
    user_context: dict                  # 用户画像上下文
    checkpoint_ref: str | None          # 检查点 ID（避免与 LangGraph 保留字冲突）
    user_id: str | None                 # 用户 ID
    __trace_id__: str | None            # 执行追踪 ID（跨节点传播）

    # 人工审核相关字段（全部 Optional，向后兼容）
    trigger_type: str | None            # 触发类型，由调用方预设
    trigger_reason: str | None          # 触发原因描述
    risk_level: str | None              # 风险等级
    requires_human_review: bool | None  # 是否需要人工审核
    risk_reason: str | None             # 风险原因
    __human_decision__: dict | None     # 人工决策信息（仅 resume 时注入）
    __review_requested__: bool | None   # 标记需广播 review_requested 事件
    __review_decided__: bool | None     # 标记需广播 review_decided 事件
    conversation_context: str | None    # 多轮补充信息上下文
