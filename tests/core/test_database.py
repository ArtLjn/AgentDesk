from datetime import datetime, timedelta

import pytest
from pathlib import Path

from src.multi_agent_system.core.database import DatabaseManager


@pytest.fixture
async def db():
    db_path = Path("tests/data/test.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    manager = DatabaseManager(db_path=str(db_path))
    await manager.initialize()
    yield manager
    await manager.close()
    if db_path.exists():
        db_path.unlink()


@pytest.mark.asyncio
async def test_database_initializes_tables():
    db_path = Path("tests/data/test_init.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseManager(db_path=str(db_path))
    await manager.initialize()

    async with manager.connection() as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}

    assert "tickets" in tables
    assert "users" in tables
    assert "checkpoints" in tables
    assert "patterns" in tables

    await manager.close()
    db_path.unlink()


@pytest.mark.asyncio
async def test_ticket_crud():
    db_path = Path("tests/data/test_crud.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseManager(db_path=str(db_path))
    await manager.initialize()

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
    db_path.unlink()


@pytest.mark.asyncio
async def test_checkpoint_save_and_restore():
    db_path = Path("tests/data/test_checkpoint.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseManager(db_path=str(db_path))
    await manager.initialize()

    state = {"ticket_id": "TK-002", "content": "退款申请", "status": "processing"}
    expires = (datetime.now() + timedelta(hours=24)).isoformat()

    await manager.save_checkpoint("cp-001", "TK-002", state, expires)

    restored = await manager.get_checkpoint("TK-002")
    assert restored is not None
    assert restored["state"]["content"] == "退款申请"

    await manager.close()
    db_path.unlink()
