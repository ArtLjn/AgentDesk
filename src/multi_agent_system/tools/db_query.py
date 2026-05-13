"""模拟数据库查询工具，基于内存 dict 存储工单和用户数据。"""

from datetime import datetime
from typing import Any

from loguru import logger

__all__ = ["DBQueryTool"]


class DBQueryTool:
    """模拟数据库查询工具。

    使用内存 dict 模拟数据库表，提供工单 CRUD 和用户查询功能。
    预置了 3 个示例用户数据。
    """

    def __init__(self) -> None:
        self._tickets: dict[str, dict[str, Any]] = {}
        self._users: dict[str, dict[str, Any]] = {
            "U001": {"name": "张三", "vip": True, "ticket_count": 5},
            "U002": {"name": "李四", "vip": False, "ticket_count": 1},
            "U003": {"name": "王五", "vip": True, "ticket_count": 12},
        }

    def save_ticket(self, ticket_data: dict[str, Any]) -> None:
        """保存工单到内存数据库。

        如果 ticket_data 中包含已存在的 ticket_id，则更新已有记录。

        Args:
            ticket_data: 工单数据字典，需包含 "ticket_id" 字段
        """
        ticket_id = ticket_data.get("ticket_id")
        if not ticket_id:
            logger.warning("保存工单失败：缺少 ticket_id")
            return

        # 如果是新工单，自动添加创建时间
        if ticket_id not in self._tickets:
            ticket_data.setdefault("created_at", datetime.now().isoformat())

        self._tickets[ticket_id] = ticket_data
        logger.debug(f"已保存工单: {ticket_id}")

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        """根据 ID 获取单个工单。

        Args:
            ticket_id: 工单 ID

        Returns:
            工单数据字典，不存在时返回 None
        """
        return self._tickets.get(ticket_id)

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """根据 ID 获取用户信息。

        Args:
            user_id: 用户 ID

        Returns:
            用户数据字典，不存在时返回 None
        """
        return self._users.get(user_id)

    def get_ticket_history(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """获取指定用户的工单历史记录。

        按创建时间倒序排列，最多返回 limit 条记录。

        Args:
            user_id: 用户 ID
            limit: 最大返回条数，默认 10

        Returns:
            该用户的工单列表，按时间倒序
        """
        user_tickets = [
            t for t in self._tickets.values() if t.get("user_id") == user_id
        ]
        # 按创建时间倒序排列
        user_tickets.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return user_tickets[:limit]

    def get_similar_tickets(
        self, category: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """获取同分类的工单列表。

        按创建时间倒序排列，最多返回 limit 条记录。

        Args:
            category: 工单分类
            limit: 最大返回条数，默认 5

        Returns:
            同分类工单列表
        """
        similar = [t for t in self._tickets.values() if t.get("category") == category]
        similar.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return similar[:limit]
