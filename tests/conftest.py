"""pytest 共享 fixture。

所有测试连同一个 MySQL 测试库（生产环境共用 ai_agent_learning），
每个测试 fixture setup 时调 truncate_all() 保证用例间数据隔离。
"""

import os

import pytest_asyncio

from src.multi_agent_system.config import Settings
from src.multi_agent_system.core.database import DatabaseManager

# 测试库 URL：默认读 config.yaml 的 database_url，可用 TEST_DATABASE_URL 环境变量覆盖
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", Settings().database_url)


@pytest_asyncio.fixture
async def db_manager():
    """每个测试函数独立的 DatabaseManager + 自动 TRUNCATE 所有表。"""
    manager = DatabaseManager(database_url=TEST_DATABASE_URL)
    await manager.initialize()
    await manager.truncate_all()
    yield manager
    await manager.close()
