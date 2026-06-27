"""人工审核相关数据模型。"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "AISuggestion",
    "HumanReview",
    "HumanReviewCreate",
    "ReviewDecision",
    "ReviewDecisionRequest",
    "ReviewStats",
    "ReviewStatus",
    "TriggerType",
]


class TriggerType(str, Enum):
    """触发人工审核的原因类型。"""

    ESCALATE = "escalate"
    REVIEW_FAILED = "review_failed"
    ERROR_FALLBACK = "error_fallback"
    USER_REQUEST = "user_request"


class ReviewDecision(str, Enum):
    """人工审核决策。"""

    APPROVE = "approve"
    REJECT = "reject"
    REWRITE = "rewrite"
    REPROCESS = "reprocess"


class ReviewStatus(str, Enum):
    """审核单状态。"""

    PENDING = "pending"
    DECIDED = "decided"


class AISuggestion(BaseModel):
    """CoordinatorAgent 给出的辅助决策建议。"""

    model_config = ConfigDict(extra="forbid")

    recommended_decision: ReviewDecision
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    key_concerns: list[str] = Field(default_factory=list)


class HumanReviewCreate(BaseModel):
    """创建待审核单的入参。

    将 create_pending_review 的字段聚合为单一对象，避免方法参数超过 5 个。
    """

    model_config = ConfigDict(extra="forbid")

    review_id: str
    ticket_id: str
    trigger_type: TriggerType
    trigger_reason: str | None = None
    ai_suggestion: AISuggestion | None = None


class HumanReview(BaseModel):
    """人工审核单完整记录。"""

    model_config = ConfigDict(extra="forbid")

    review_id: str
    ticket_id: str
    trigger_type: TriggerType
    trigger_reason: str | None = None
    ai_suggestion: AISuggestion | None = None
    decision: ReviewDecision | None = None
    decision_reason: str | None = None
    rewritten_result: str | None = None
    reviewer_id: str | None = None
    status: ReviewStatus
    created_at: datetime
    decided_at: datetime | None = None


class ReviewDecisionRequest(BaseModel):
    """提交审核决策的请求。"""

    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    decision_reason: str  # 必填
    rewritten_result: str | None = None  # decision=rewrite 时必填
    reviewer_id: str  # 必填

    @model_validator(mode="after")
    def _validate_decision_fields(self) -> "ReviewDecisionRequest":
        """跨字段校验：reason 非空白；rewrite 时 rewritten_result 必填。"""
        reason = (self.decision_reason or "").strip()
        if not reason:
            raise ValueError("DECISION_REASON_REQUIRED: decision_reason 不能为空")
        if self.decision == ReviewDecision.REWRITE:
            if not (self.rewritten_result or "").strip():
                raise ValueError(
                    "REWRITE_RESULT_REQUIRED: decision=rewrite 时必须提供 rewritten_result"
                )
        return self


class ReviewStats(BaseModel):
    """审核统计信息。"""

    model_config = ConfigDict(extra="forbid")

    total: int = 0
    pending: int = 0
    decided: int = 0
    by_decision: dict[str, int] = Field(default_factory=dict)
    by_trigger: dict[str, int] = Field(default_factory=dict)
