import pytest
import pytest_asyncio
from pathlib import Path

from src.multi_agent_system.core.database import DatabaseManager
from src.multi_agent_system.tools.db_query import DBQueryTool


@pytest_asyncio.fixture
async def db_tool():
    db_path = Path("tests/data/test_db_tool.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    db_manager = DatabaseManager(db_path=str(db_path))
    await db_manager.initialize()

    tool = DBQueryTool(db_manager=db_manager)
    yield tool

    await db_manager.close()
    if db_path.exists():
        db_path.unlink()


@pytest.mark.asyncio
async def test_db_tool_save_and_get_ticket(db_tool):
    ticket = {
        "ticket_id": "TK-003",
        "content": "测试工单",
        "status": "received",
    }
    await db_tool.save_ticket(ticket)

    retrieved = await db_tool.get_ticket("TK-003")
    assert retrieved is not None
    assert retrieved["content"] == "测试工单"
