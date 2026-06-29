import pytest

pytestmark = pytest.mark.asyncio


async def test_ticket_message_round_trip(db_manager):
    await db_manager.save_ticket({
        "ticket_id": "TK-msg-1",
        "content": "退款没有到账",
        "status": "waiting_user_input",
    })

    await db_manager.create_ticket_message({
        "message_id": "TM-1",
        "ticket_id": "TK-msg-1",
        "sender_type": "reviewer",
        "sender_id": "reviewer-001",
        "content": "请补充订单号",
        "metadata": {"source": "request_info"},
    })
    await db_manager.create_ticket_message({
        "message_id": "TM-2",
        "ticket_id": "TK-msg-1",
        "sender_type": "user",
        "sender_id": "user-001",
        "content": "订单号是 123456",
    })

    rows = await db_manager.list_ticket_messages("TK-msg-1")

    assert [row["message_id"] for row in rows] == ["TM-1", "TM-2"]
    assert rows[0]["metadata"] == {"source": "request_info"}
    assert rows[1]["content"] == "订单号是 123456"
