import pytest
import pytest_asyncio
from pathlib import Path

from src.multi_agent_system.core.database import DatabaseManager
from src.multi_agent_system.core.evaluation import EvaluationCollector


@pytest_asyncio.fixture
async def eval_collector():
    db_path = Path("tests/data/test_eval.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    db_manager = DatabaseManager(db_path=str(db_path))
    await db_manager.initialize()

    collector = EvaluationCollector(db_manager=db_manager)
    yield collector

    await db_manager.close()
    if db_path.exists():
        db_path.unlink()


@pytest.mark.asyncio
async def test_record_ticket_metrics(eval_collector):
    # Arrange: create a ticket first
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-006",
        "content": "测试工单",
        "status": "received",
    })

    # Act: record completion metrics
    await eval_collector.record_ticket_completion(
        ticket_id="TK-006",
        status="completed",
        review_score=0.85,
        token_count=1500,
        tool_call_count=3,
        duration_seconds=12.5,
    )

    # Assert
    stats = await eval_collector.get_resolution_stats()
    assert stats["total"] == 1
    assert stats["completed"] == 1
    assert stats["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_record_ticket_completion_preserves_existing_data(eval_collector):
    # Arrange
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-007",
        "content": "保留数据测试",
        "user_id": "U001",
        "category": "technical",
        "priority": "P1",
        "status": "received",
    })

    # Act
    await eval_collector.record_ticket_completion(
        ticket_id="TK-007",
        status="completed",
        review_score=0.9,
    )

    # Assert: verify existing data is preserved
    ticket = await eval_collector._db.get_ticket("TK-007")
    assert ticket["content"] == "保留数据测试"
    assert ticket["user_id"] == "U001"
    assert ticket["category"] == "technical"
    assert ticket["priority"] == "P1"
    assert ticket["status"] == "completed"
    assert ticket["review_score"] == 0.9


@pytest.mark.asyncio
async def test_record_ticket_completion_missing_ticket_logs_warning(eval_collector):
    # Act: try to record metrics for non-existent ticket
    await eval_collector.record_ticket_completion(
        ticket_id="TK-NOT-EXIST",
        status="completed",
    )

    # Assert: stats should be empty
    stats = await eval_collector.get_resolution_stats()
    assert stats["total"] == 0


@pytest.mark.asyncio
async def test_record_user_feedback_updates_ticket(eval_collector):
    # Arrange
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-008",
        "content": "反馈测试",
        "status": "completed",
    })

    # Act
    await eval_collector.record_user_feedback("TK-008", satisfied=True)

    # Assert
    ticket = await eval_collector._db.get_ticket("TK-008")
    assert ticket["satisfied"] == 1


@pytest.mark.asyncio
async def test_record_user_feedback_missing_ticket_raises_error(eval_collector):
    with pytest.raises(ValueError, match="not found"):
        await eval_collector.record_user_feedback("TK-NOT-EXIST", satisfied=True)


@pytest.mark.asyncio
async def test_record_user_feedback_updates_user_stats(eval_collector):
    # Arrange
    await eval_collector._db.save_user({
        "user_id": "U002",
        "name": "测试用户",
        "total_tickets": 2,
        "avg_satisfaction": 0.5,
    })
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-009",
        "content": "用户反馈测试",
        "user_id": "U002",
        "status": "completed",
    })

    # Act
    await eval_collector.record_user_feedback("TK-009", satisfied=True)

    # Assert: avg_satisfaction should be recalculated
    user = await eval_collector._db.get_user("U002")
    expected_avg = (0.5 * (2 - 1) + 1.0) / 2
    assert user["avg_satisfaction"] == expected_avg


@pytest.mark.asyncio
async def test_get_efficiency_stats(eval_collector):
    # Arrange
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-010",
        "content": "效率测试1",
        "status": "completed",
        "token_count": 1000,
        "tool_call_count": 2,
        "total_duration": 10.0,
    })
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-011",
        "content": "效率测试2",
        "status": "completed",
        "token_count": 2000,
        "tool_call_count": 4,
        "total_duration": 20.0,
    })

    # Act
    stats = await eval_collector.get_efficiency_stats()

    # Assert
    assert stats["avg_tokens_per_ticket"] == 1500
    assert stats["avg_duration_seconds"] == 15.0
    assert stats["avg_tool_calls"] == 3.0


@pytest.mark.asyncio
async def test_get_evaluation_summary(eval_collector):
    # Arrange
    await eval_collector._db.save_ticket({
        "ticket_id": "TK-012",
        "content": "评估摘要测试",
        "status": "completed",
        "review_score": 0.8,
        "token_count": 1000,
        "total_duration": 10.0,
        "satisfied": 1,
    })

    # Act
    summary = await eval_collector.get_evaluation_summary()

    # Assert
    assert summary["total"] == 1
    assert summary["completed"] == 1
    assert summary["avg_review_score"] == 0.8
    assert summary["satisfaction_rate"] == 1.0
    assert summary["total_feedback"] == 1
    assert summary["avg_tokens_per_ticket"] == 1000
