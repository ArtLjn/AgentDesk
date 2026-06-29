"""工单意图理解 Agent 测试。"""

from src.multi_agent_system.agents.ticket_intent import TicketIntentAgent


def test_fallback_extracts_billing_refund_intent() -> None:
    """本地兜底能从自然语言中提取账务退款工单。"""
    result = TicketIntentAgent.extract_by_fallback(
        "上个月账单多扣了 200 元，请帮我退款，联系方式 finance@example.com"
    )

    assert result["category"] == "billing"
    assert result["priority"] == "P1"
    assert result["title"] == "上个月账单多扣了 200 元"
    assert result["contact"] == "finance@example.com"
    assert "【原始描述】" in result["content"]


def test_fallback_marks_core_outage_as_p0() -> None:
    """核心业务不可用会被兜底为 P0 技术工单。"""
    result = TicketIntentAgent.extract_by_fallback(
        "今天上午 10:15 开始系统完全不可用，后台一直 504，全部用户无法登录"
    )

    assert result["category"] == "technical"
    assert result["priority"] == "P0"
    assert result["impact"] == "全部用户受影响"


def test_fallback_marks_security_report_as_p1_technical() -> None:
    """漏洞/安全风险上报应被兜底为 P1 技术工单。"""
    result = TicketIntentAgent.extract_by_fallback(
        "我发现你们支付功能有漏洞，支付之后跳转到一个不知名网页，疑似被劫持"
    )

    assert result["category"] == "technical"
    assert result["priority"] == "P1"
    assert "漏洞" in result["content"]
