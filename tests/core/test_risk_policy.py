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


def test_attack_threat_requires_human_review() -> None:
    """直接表达攻击意图时，即使被标成咨询也必须人工审核。"""
    assessment = assess_ticket_risk(
        "我发现你们系统的 bug 了，我要攻击你们系统了",
        category="inquiry",
        priority="P3",
    )

    assert assessment.requires_human_review is True
    assert assessment.risk_level == "high"
    assert assessment.trigger_type == "escalate"
    assert "攻击" in assessment.reason


def test_billing_knowledge_question_does_not_require_human_review() -> None:
    """账务规则咨询不应因为出现退款字样就转人工审核。"""
    assessment = assess_ticket_risk(
        "退款一般多久到账，平台规则是什么",
        category="billing",
        priority="P3",
    )

    assert assessment.requires_human_review is False
    assert assessment.risk_level == "low"


def test_billing_business_action_requires_human_review() -> None:
    """真实业务动作由结构化契约驱动人工闭环，而不是靠词库命中。"""
    assessment = assess_ticket_risk(
        "用户描述了一件账务问题",
        category="billing",
        priority="P1",
        agent_risk={
            "risk_level": "medium",
            "requires_human_review": False,
            "risk_reason": "涉及真实账务处理，需要人工核查订单和支付流水",
            "requires_business_operation": True,
            "can_auto_resolve": False,
            "required_fields": ["order_id", "payment_record"],
        },
    )

    assert assessment.requires_human_review is True
    assert assessment.risk_level == "medium"
    assert assessment.trigger_type == "escalate"
    assert "账务处理" in assessment.reason


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
