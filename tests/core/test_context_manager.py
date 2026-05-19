from src.multi_agent_system.core.context_manager import ContextManager


def test_sliding_window_trims_excess_messages():
    manager = ContextManager(max_messages=5)

    messages = [
        {"role": "system", "content": "You are a helper"},
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "resp1"},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "resp2"},
        {"role": "user", "content": "msg3"},
        {"role": "assistant", "content": "resp3"},
    ]

    trimmed = manager.trim_messages(messages)

    # Should keep system + last 4 messages (but max is 5, so system + 4 recent)
    assert len(trimmed) <= 5
    assert trimmed[0]["role"] == "system"
    assert trimmed[-1]["content"] == "resp3"


def test_extract_critical_info():
    manager = ContextManager()
    state = {
        "ticket_id": "TK-005",
        "user_id": "U001",
        "category": "technical",
        "priority": "P1",
        "content": "系统崩溃，无法访问",
        "review_score": 0.85,
        "retry_count": 1,
    }

    info = manager.extract_critical_info(state)
    assert info["ticket_id"] == "TK-005"
    assert info["category"] == "technical"
    assert info["priority"] == "P1"
    assert info["content_preview"] == "系统崩溃，无法访问"
