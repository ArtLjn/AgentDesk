"""工单风险评估策略。

该模块集中管理是否需要人工审核的业务判断，避免在多个 Agent 或工作流节点
里散落关键词判断。策略以“风险信号 + 业务面 + Agent 契约”组合评分。
"""

from dataclasses import dataclass
from typing import Any

__all__ = ["RiskAssessment", "assess_ticket_risk"]


@dataclass(frozen=True)
class RiskAssessment:
    """工单风险评估结果。"""

    risk_level: str
    requires_human_review: bool
    reason: str
    trigger_type: str | None = None


_HIGH_RISK_LEVELS = {"high", "critical"}
_SENSITIVE_BUSINESS_SURFACES = ("支付", "付款", "账户", "账号", "登录", "订单", "资金", "账单")
_SECURITY_FINDING_SIGNALS = ("漏洞", "越权", "泄露", "劫持", "钓鱼", "注入")
_ABNORMAL_REDIRECT_SIGNALS = ("未知网页", "不知名网页", "异常跳转", "可疑跳转")
_ATTACK_THREAT_SIGNALS = ("攻击", "入侵", "攻破", "黑掉", "打爆", "搞垮")
def assess_ticket_risk(
    content: str,
    *,
    category: str | None = None,
    priority: str | None = None,
    agent_risk: dict[str, Any] | None = None,
) -> RiskAssessment:
    """评估工单是否需要人工审核。

    优先消费 Agent 输出的结构化风险契约；没有契约时用少量稳定风险维度兜底。
    兜底规则不是穷举词库，而是表达风险组合：安全发现 + 敏感业务面/异常跳转。
    """
    contract = _assessment_from_agent_contract(agent_risk)
    if contract is not None:
        return contract

    text = content.lower()
    has_attack_threat = _contains_any(text, _ATTACK_THREAT_SIGNALS)
    has_security_finding = _contains_any(text, _SECURITY_FINDING_SIGNALS)
    has_sensitive_surface = _contains_any(text, _SENSITIVE_BUSINESS_SURFACES)
    has_abnormal_redirect = _contains_any(text, _ABNORMAL_REDIRECT_SIGNALS)

    if has_attack_threat:
        return RiskAssessment(
            risk_level="high",
            requires_human_review=True,
            reason="用户表达攻击或入侵威胁，需人工审核",
            trigger_type="escalate",
        )

    if has_security_finding and (has_sensitive_surface or has_abnormal_redirect):
        return RiskAssessment(
            risk_level="high",
            requires_human_review=True,
            reason="疑似安全风险影响敏感业务面，需人工审核",
            trigger_type="escalate",
        )

    if priority == "P0":
        return RiskAssessment(
            risk_level="critical",
            requires_human_review=True,
            reason="P0 紧急工单",
            trigger_type="escalate",
        )

    if category == "complaint":
        return RiskAssessment(
            risk_level="medium",
            requires_human_review=True,
            reason="投诉类工单",
            trigger_type="escalate",
        )

    return RiskAssessment(
        risk_level="low",
        requires_human_review=False,
        reason="未触发人工审核风险策略",
    )


def _assessment_from_agent_contract(
    agent_risk: dict[str, Any] | None,
) -> RiskAssessment | None:
    """从 Agent 风险契约构造评估结果。"""
    if not agent_risk:
        return None

    has_contract = any(
        agent_risk.get(key) not in (None, "")
        for key in ("risk_level", "requires_human_review", "risk_reason")
    )
    if not has_contract:
        return None

    risk_level = str(agent_risk.get("risk_level") or "low").lower()
    requires_human_review = bool(agent_risk.get("requires_human_review"))
    reason = str(agent_risk.get("risk_reason") or agent_risk.get("reason") or "").strip()
    requires_business_operation = bool(agent_risk.get("requires_business_operation"))
    can_auto_resolve = bool(agent_risk.get("can_auto_resolve"))
    required_fields = agent_risk.get("required_fields")
    has_missing_fields = isinstance(required_fields, list) and len(required_fields) > 0

    if (
        requires_human_review
        or risk_level in _HIGH_RISK_LEVELS
        or (requires_business_operation and not can_auto_resolve)
        or has_missing_fields
    ):
        if not reason and requires_business_operation:
            reason = "工单涉及真实业务操作，需人工核查或补充关键字段"
        if not reason and has_missing_fields:
            reason = "工单缺少业务处理所需关键字段"
        return RiskAssessment(
            risk_level=risk_level if risk_level != "low" else "medium",
            requires_human_review=True,
            reason=reason or "Agent 风险评估要求人工审核",
            trigger_type="escalate",
        )

    return None


def _contains_any(text: str, signals: tuple[str, ...]) -> bool:
    """判断文本是否包含任一风险信号。"""
    return any(signal.lower() in text for signal in signals)
