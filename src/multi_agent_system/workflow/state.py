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
        review_score: 审核评分，范围 0-1
        retry_count: 重试次数，默认 0，上限 3
        status: 当前状态（received/classifying/processing/reviewing/completed/failed）
        messages: Agent 间通信上下文列表
        error: 错误信息
    """

    ticket_id: str
    content: str
    category: str | None
    priority: str | None
    processing_result: str | None
    review_score: float | None
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
