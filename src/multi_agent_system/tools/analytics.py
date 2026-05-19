"""统计分析工具，基于 SQLite 数据计算工单处理统计指标。"""

from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.multi_agent_system.core.database import DatabaseManager, get_db_manager

__all__ = ["AnalyticsTool"]


class AnalyticsTool:
    """统计分析工具。

    基于 SQLite 数据库中的工单数据，计算分类分布、优先级分布、
    处理统计和每日趋势等指标。

    Args:
        db_manager: 数据库管理器实例，为 None 时自动获取全局实例
    """

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self._db = db_manager

    async def _get_db(self) -> DatabaseManager:
        if self._db is not None:
            return self._db
        return await get_db_manager()

    async def get_category_distribution(self) -> dict[str, int]:
        db = await self._get_db()
        result = await db.get_category_distribution()
        logger.debug(f"分类分布: {result}")
        return result

    async def get_priority_distribution(self) -> dict[str, int]:
        db = await self._get_db()
        result = await db.get_priority_distribution()
        logger.debug(f"优先级分布: {result}")
        return result

    async def get_resolution_stats(self) -> dict[str, Any]:
        db = await self._get_db()
        result = await db.get_resolution_stats()
        logger.debug(f"处理统计: {result}")
        return result

    async def get_daily_stats(self, days: int = 7) -> list[dict[str, Any]]:
        db = await self._get_db()
        # Query raw ticket data and aggregate in Python
        tickets = await db.list_tickets(limit=10000)
        now = datetime.now()

        daily_buckets: dict[str, dict[str, int]] = {}
        for i in range(days):
            date_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_buckets[date_str] = {"created": 0, "completed": 0, "failed": 0}

        for ticket in tickets:
            created_at = ticket.get("created_at", "")
            status = ticket.get("status", "")
            date_key = created_at[:10] if len(created_at) >= 10 else ""

            if date_key in daily_buckets:
                daily_buckets[date_key]["created"] += 1
                if status == "completed":
                    daily_buckets[date_key]["completed"] += 1
                elif status == "failed":
                    daily_buckets[date_key]["failed"] += 1

        result = [
            {"date": date, **stats} for date, stats in sorted(daily_buckets.items())
        ]
        logger.debug(f"每日统计（{days}天）: {len(result)} 条记录")
        return result
