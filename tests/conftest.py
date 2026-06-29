"""pytest 共享 fixture。

测试默认使用独立的 ``*_test`` 数据库，禁止直接复用业务库。
每个测试 fixture setup 时调 truncate_all() 保证用例间数据隔离。
"""

import os
from pathlib import Path

import pytest_asyncio

from src.multi_agent_system.core.database import DatabaseManager


# 测试库 URL：默认使用本地 SQLite 测试库，可用 TEST_DATABASE_URL 覆盖
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///tests/.tmp/ai_agent_learning_test.db",
)
Path("tests/.tmp").mkdir(parents=True, exist_ok=True)


@pytest_asyncio.fixture
async def db_manager():
    """每个测试函数独立的 DatabaseManager + 自动 TRUNCATE 所有表。"""
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()
    yield manager
    await manager.close()
