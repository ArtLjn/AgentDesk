from datetime import datetime, timedelta

import pytest

from src.multi_agent_system.core.database import DatabaseManager
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture
async def db():
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()
    yield manager
    await manager.close()


@pytest.mark.asyncio
async def test_database_initializes_tables():
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()

    async with manager.connection() as conn:
        cursor = await conn.execute(
            "SELECT TABLE_NAME FROM information_schema.tables "
            "WHERE TABLE_SCHEMA = DATABASE()"
        )
        tables = {row[0] for row in await cursor.fetchall()}

    assert "tickets" in tables
    assert "users" in tables
    assert "checkpoints" in tables
    assert "patterns" in tables

    await manager.close()


@pytest.mark.asyncio
async def test_ticket_crud():
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()

    ticket = {
        "ticket_id": "TK-001",
        "user_id": "U001",
        "content": "无法登录",
        "category": "technical",
        "priority": "P1",
        "status": "received",
    }
    await manager.save_ticket(ticket)

    retrieved = await manager.get_ticket("TK-001")
    assert retrieved is not None
    assert retrieved["content"] == "无法登录"
    assert retrieved["category"] == "technical"

    await manager.close()


@pytest.mark.asyncio
async def test_save_ticket_keeps_existing_references_when_update_omits_them():
    """后续节点做增量保存时，不能把处理节点写入的知识库引用清空。"""
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()

    await manager.save_ticket({
        "ticket_id": "TK-REF-001",
        "content": "ERR-5001 无法登录",
        "status": "processing",
        "references": ["登录故障手册"],
    })
    await manager.save_ticket({
        "ticket_id": "TK-REF-001",
        "content": "ERR-5001 无法登录",
        "status": "completed",
    })

    retrieved = await manager.get_ticket("TK-REF-001")
    assert retrieved is not None
    assert retrieved["references_json"] == '["登录故障手册"]'
    assert retrieved["status"] == "completed"

    await manager.close()


@pytest.mark.asyncio
async def test_checkpoint_save_and_restore():
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()

    state = {"ticket_id": "TK-002", "content": "退款申请", "status": "processing"}
    expires = (datetime.now() + timedelta(hours=24)).isoformat()

    await manager.save_checkpoint("cp-001", "TK-002", state, expires)

    restored = await manager.get_checkpoint("TK-002")
    assert restored is not None
    assert restored["state"]["content"] == "退款申请"

    await manager.close()


# ============================================================
# Human Review schema & CRUD smoke tests
# ============================================================


@pytest.mark.asyncio
async def test_human_reviews_table_and_indexes_created():
    """human_reviews 表、4 个常规索引应被创建。"""
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()

    async with manager.connection() as conn:
        cursor = await conn.execute(
            "SELECT TABLE_NAME FROM information_schema.tables "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'human_reviews'"
        )
        tables = {row[0] for row in await cursor.fetchall()}
        assert "human_reviews" in tables

        cursor = await conn.execute(
            "SELECT DISTINCT INDEX_NAME FROM information_schema.statistics "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'human_reviews'"
        )
        indexes = {row[0] for row in await cursor.fetchall()}
        assert {"idx_hr_status", "idx_hr_ticket", "idx_hr_trigger", "idx_hr_reviewer"} <= indexes

        cursor = await conn.execute(
            "SELECT DISTINCT INDEX_NAME FROM information_schema.statistics "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tickets'"
        )
        tickets_indexes = {row[0] for row in await cursor.fetchall()}
        assert {"idx_tickets_user", "idx_tickets_status", "idx_tickets_category",
                "idx_tickets_status_created"} <= tickets_indexes

    await manager.close()


@pytest.mark.asyncio
async def test_human_review_full_crud_flow():
    """审核单全流程：创建待审 -> 按 ticket 查 -> 更新决策 -> 列表/统计。"""
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()

    ai_suggestion = {
        "recommended_decision": "approve",
        "confidence": 0.8,
        "reasoning": "结果完整",
        "key_concerns": ["无"],
    }
    await manager.create_pending_review({
        "review_id": "HR-001",
        "ticket_id": "TK-001",
        "trigger_type": "escalate",
        "trigger_reason": "VIP 升级",
        "ai_suggestion": ai_suggestion,
        "created_at": datetime.now().isoformat(),
    })

    fetched = await manager.get_pending_review_by_ticket("TK-001")
    assert fetched is not None
    assert fetched["review_id"] == "HR-001"
    assert fetched["status"] == "pending"
    assert fetched["trigger_type"] == "escalate"
    import json as _json
    assert _json.loads(fetched["ai_suggestion"])["confidence"] == 0.8

    await manager.update_review_decision("HR-001", {
        "decision": "rewrite",
        "decision_reason": "需要补全退款步骤",
        "rewritten_result": "已重写回复",
        "reviewer_id": "R001",
        "status": "decided",
        "decided_at": datetime.now().isoformat(),
    })

    fetched2 = await manager.get_pending_review_by_ticket("TK-001")
    assert fetched2["decision"] == "rewrite"
    assert fetched2["reviewer_id"] == "R001"
    assert fetched2["status"] == "decided"

    await manager.create_pending_review({
        "review_id": "HR-002",
        "ticket_id": "TK-002",
        "trigger_type": "review_failed",
        "trigger_reason": "score<0.6 多次",
        "created_at": datetime.now().isoformat(),
    })

    pending_list = await manager.list_pending_reviews(status="pending")
    assert len(pending_list) == 1
    assert pending_list[0]["review_id"] == "HR-002"

    by_ticket = await manager.list_reviews_by_ticket("TK-001")
    assert len(by_ticket) == 1
    assert by_ticket[0]["review_id"] == "HR-001"

    stats = await manager.get_review_stats()
    assert stats["total"] == 2
    assert stats["pending"] == 1
    assert stats["decided"] == 1
    assert stats["by_decision"].get("rewrite") == 1
    assert stats["by_trigger"].get("escalate") == 1
    assert stats["by_trigger"].get("review_failed") == 1

    await manager.close()


@pytest.mark.asyncio
async def test_update_review_decision_warns_on_unknown_keys(caplog):
    """update_review_decision 收到未知键时应记录 warning 但不报错。"""
    import logging

    from loguru import logger as loguru_logger

    def _sink(message):
        record = message.record
        logging.getLogger(record["name"]).log(
            record["level"].no,
            record["message"],
        )

    handler_id = loguru_logger.add(_sink, level="WARNING")

    try:
        manager = DatabaseManager(database_url=TEST_DATABASE_URL)
        await manager.initialize()
        await manager.truncate_all()

        await manager.create_pending_review({
            "review_id": "HR-U1",
            "ticket_id": "TK-U1",
            "trigger_type": "escalate",
            "trigger_reason": "VIP",
            "created_at": datetime.now().isoformat(),
        })

        caplog.set_level(logging.WARNING)

        await manager.update_review_decision("HR-U1", {
            "decision_reazon": "拼写错误",  # 未知键
            "decision": "approve",  # 合法
        })

        messages = [r.getMessage() for r in caplog.records]
        unknown_warnings = [m for m in messages if "未知字段" in m]
        assert unknown_warnings, (
            f"期望 warning 日志包含 '未知字段'，实际 records: {messages}"
        )
        assert "decision_reazon" in unknown_warnings[0]

        fetched = await manager.get_pending_review_by_ticket("TK-U1")
        assert fetched["decision"] == "approve"
        assert "decision_reazon" not in fetched

        await manager.close()
    finally:
        loguru_logger.remove(handler_id)


@pytest.mark.asyncio
async def test_update_review_decision_warns_on_no_valid_fields(caplog):
    """update_review_decision 全部键都非法时记录 warning 并返回 None。"""
    import logging

    from loguru import logger as loguru_logger

    def _sink(message):
        record = message.record
        logging.getLogger(record["name"]).log(
            record["level"].no,
            record["message"],
        )

    handler_id = loguru_logger.add(_sink, level="WARNING")

    try:
        manager = DatabaseManager(database_url=TEST_DATABASE_URL)
        await manager.initialize()
        await manager.truncate_all()

        await manager.create_pending_review({
            "review_id": "HR-N1",
            "ticket_id": "TK-N1",
            "trigger_type": "escalate",
            "trigger_reason": "VIP",
            "created_at": datetime.now().isoformat(),
        })

        caplog.set_level(logging.WARNING)

        result = await manager.update_review_decision("HR-N1", {
            "foo": "bar",
            "baz": "qux",
        })

        assert result is None

        messages = [r.getMessage() for r in caplog.records]
        no_valid_warnings = [m for m in messages if "无有效更新字段" in m]
        assert no_valid_warnings, (
            f"期望 warning 日志包含 '无有效更新字段'，实际: {messages}"
        )

        await manager.close()
    finally:
        loguru_logger.remove(handler_id)
