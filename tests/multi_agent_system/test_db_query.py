import pytest
import pytest_asyncio

from src.multi_agent_system.core.database import DatabaseManager
from src.multi_agent_system.tools.db_query import DBQueryTool
from tests.conftest import TEST_DATABASE_URL


@pytest_asyncio.fixture
async def db_tool():
    db_manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await db_manager.initialize()
    await db_manager.truncate_all()

    tool = DBQueryTool(db_manager=db_manager)
    yield tool

    await db_manager.close()


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
