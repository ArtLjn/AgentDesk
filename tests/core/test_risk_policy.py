"""工单风险策略测试。"""

from src.multi_agent_system.core.risk_policy import assess_ticket_risk


def test_security_report_requires_human_review() -> None:
    """涉及敏感业务面的漏洞上报应触发人工审核。"""
    assessment = assess_ticket_risk(
        "我发现支付功能有漏洞，付款后跳转到不知名网页"
    )

    assert assessment.requires_human_review is True
    assert assessment.risk_level == "high"
    assert assessment.trigger_type == "escalate"


def test_normal_billing_issue_does_not_require_human_review() -> None:
    """普通账务问题不应因为出现支付字样就转人工审核。"""
    assessment = assess_ticket_risk(
        "支付失败了，请帮我退款",
        category="billing",
        priority="P2",
    )

    assert assessment.requires_human_review is False
    assert assessment.risk_level == "low"


def test_agent_contract_can_force_human_review() -> None:
    """Agent 输出的结构化风险契约可以直接触发人工审核。"""
    assessment = assess_ticket_risk(
        "页面异常",
        agent_risk={
            "risk_level": "high",
            "requires_human_review": True,
            "risk_reason": "疑似账号越权",
        },
    )

    assert assessment.requires_human_review is True
    assert assessment.reason == "疑似账号越权"
