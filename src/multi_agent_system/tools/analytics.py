"""统计分析工具，基于内存数据计算工单处理统计指标。"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.multi_agent_system.tools.db_query import DBQueryTool

__all__ = ["AnalyticsTool"]


class AnalyticsTool:
    """统计分析工具。

    基于 DBQueryTool 中的内存数据，计算工单分类分布、优先级分布、
    处理统计和每日趋势等指标。

    Args:
        db_tool: 数据库查询工具实例，作为数据源
    """

    def __init__(self, db_tool: DBQueryTool) -> None:
        self._db = db_tool

    def _get_all_tickets(self) -> list[dict[str, Any]]:
        """从 db_tool 获取所有工单。"""
        return list(self._db._tickets.values())

    def get_category_distribution(self) -> dict[str, int]:
        """获取工单分类分布统计。

        Returns:
            分类名称到工单数量的映射，如 {"technical": 5, "billing": 3}
        """
        tickets = self._get_all_tickets()
        counter = Counter(t.get("category", "uncategorized") for t in tickets)
        result = dict(counter)
        logger.debug(f"分类分布: {result}")
        return result

    def get_priority_distribution(self) -> dict[str, int]:
        """获取工单优先级分布统计。

        Returns:
            优先级到工单数量的映射，如 {"P0": 2, "P1": 5, "P2": 8}
        """
        tickets = self._get_all_tickets()
        counter = Counter(t.get("priority", "unassigned") for t in tickets)
        result = dict(counter)
        logger.debug(f"优先级分布: {result}")
        return result

    def get_resolution_stats(self) -> dict[str, Any]:
        """获取工单处理统计。

        Returns:
            包含以下字段的统计字典：
            - total: 总工单数
            - completed: 已完成数
            - failed: 失败数
            - avg_retries: 平均重试次数
            - success_rate: 完成功率（0.0 ~ 1.0）
        """
        tickets = self._get_all_tickets()
        total = len(tickets)

        if total == 0:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "avg_retries": 0.0,
                "success_rate": 0.0,
            }

        completed = sum(1 for t in tickets if t.get("status") == "completed")
        failed = sum(1 for t in tickets if t.get("status") == "failed")

        retry_counts = [t.get("retry_count", 0) for t in tickets]
        avg_retries = sum(retry_counts) / total

        success_rate = completed / total

        result = {
            "total": total,
            "completed": completed,
            "failed": failed,
            "avg_retries": round(avg_retries, 2),
            "success_rate": round(success_rate, 4),
        }
        logger.debug(f"处理统计: {result}")
        return result

    def get_daily_stats(self, days: int = 7) -> list[dict[str, Any]]:
        """获取每日处理统计。

        统计最近 N 天每天的工单创建数量、完成数量和失败数量。

        Args:
            days: 统计天数，默认 7 天

        Returns:
            每日统计列表，每项包含 date、created、completed、failed 字段
        """
        tickets = self._get_all_tickets()
        now = datetime.now()

        # 初始化每日桶
        daily_buckets: dict[str, dict[str, int]] = {}
        for i in range(days):
            date_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_buckets[date_str] = {"created": 0, "completed": 0, "failed": 0}

        for ticket in tickets:
            # 解析工单创建日期
            created_at = ticket.get("created_at", "")
            status = ticket.get("status", "")

            # 提取日期部分（支持 ISO 格式和日期字符串）
            date_key = created_at[:10] if len(created_at) >= 10 else ""

            if date_key in daily_buckets:
                daily_buckets[date_key]["created"] += 1
                if status == "completed":
                    daily_buckets[date_key]["completed"] += 1
                elif status == "failed":
                    daily_buckets[date_key]["failed"] += 1

        # 按日期升序排列输出
        result = [
            {"date": date, **stats} for date, stats in sorted(daily_buckets.items())
        ]
        logger.debug(f"每日统计（{days}天）: {len(result)} 条记录")
        return result
