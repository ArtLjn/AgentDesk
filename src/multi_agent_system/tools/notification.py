"""通知发送工具，模拟通知发送（打印日志 + 记录状态）。"""

from datetime import datetime
from typing import Any

from loguru import logger

__all__ = ["NotificationTool"]

# 支持的通知渠道
_VALID_CHANNELS = {"email", "sms", "webhook"}


class NotificationTool:
    """通知发送工具（模拟）。

    模拟通知发送行为，将通知记录保存到内存列表。
    支持多种通知渠道：email、sms、webhook。
    """

    def __init__(self) -> None:
        self._notifications: list[dict[str, Any]] = []

    def send(
        self,
        ticket_id: str,
        message: str,
        channel: str = "email",
    ) -> dict[str, Any]:
        """发送通知并记录发送结果。

        Args:
            ticket_id: 关联的工单 ID
            message: 通知内容
            channel: 通知渠道，支持 email / sms / webhook

        Returns:
            发送结果字典，包含 status、ticket_id、channel、timestamp
        """
        # 校验渠道类型
        if channel not in _VALID_CHANNELS:
            logger.warning(f"不支持的通知渠道: {channel}，将使用默认 email")
            channel = "email"

        timestamp = datetime.now().isoformat()

        notification = {
            "status": "sent",
            "ticket_id": ticket_id,
            "channel": channel,
            "message": message,
            "timestamp": timestamp,
        }
        self._notifications.append(notification)

        logger.info(
            f"通知已发送 | 工单: {ticket_id} | 渠道: {channel} | 内容: {message[:50]}"
        )
        return {
            "status": "sent",
            "ticket_id": ticket_id,
            "channel": channel,
            "timestamp": timestamp,
        }

    def get_history(self, ticket_id: str | None = None) -> list[dict[str, Any]]:
        """获取通知发送历史。

        Args:
            ticket_id: 可选，按工单 ID 过滤。为 None 时返回全部通知记录

        Returns:
            通知记录列表
        """
        if ticket_id is None:
            return list(self._notifications)

        return [n for n in self._notifications if n.get("ticket_id") == ticket_id]
