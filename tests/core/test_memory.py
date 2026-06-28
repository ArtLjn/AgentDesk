import pytest
import pytest_asyncio

from src.multi_agent_system.core.database import DatabaseManager
from src.multi_agent_system.core.memory import MemoryManager
from tests.conftest import TEST_DATABASE_URL


@pytest_asyncio.fixture
async def memory_manager():
    db_manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await db_manager.initialize()
    await db_manager.truncate_all()

    memory = MemoryManager(db_manager=db_manager)
    yield memory

    await db_manager.close()


@pytest.mark.asyncio
async def test_working_memory_tracks_react_steps(memory_manager):
    memory = memory_manager

    memory.add_thought("Need to check user history")
    memory.add_action("search_user", {"user_id": "U001"})
    memory.add_observation("User is VIP level 3")

    assert len(memory.thought_chain) == 1
    assert len(memory.tool_history) == 1
    assert memory.tool_history[0]["tool"] == "search_user"


@pytest.mark.asyncio
async def test_checkpoint_save_and_restore(memory_manager):
    memory = memory_manager

    state = {
        "ticket_id": "TK-004",
        "content": "测试",
        "status": "processing",
    }

    memory.add_thought("Analyzing ticket")
    memory.add_action("search", {"query": "test"})
    memory.add_observation("Found 3 results")

    cp_id = await memory.save_checkpoint("TK-004", state)
    assert cp_id.startswith("cp-")

    # Clear working memory
    memory.clear_working_memory()
    assert len(memory.thought_chain) == 0

    # Restore
    restored = await memory.load_checkpoint("TK-004")
    assert restored is not None
    assert len(memory.thought_chain) == 1
    assert memory.tool_history[0]["tool"] == "search"
