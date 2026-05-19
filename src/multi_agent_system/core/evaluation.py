"""Agent 评估框架：客观指标收集、用户反馈、统计分析。"""

from datetime import datetime
from typing import Any

from loguru import logger

from src.multi_agent_system.core.database import DatabaseManager

__all__ = ["EvaluationCollector"]


class EvaluationCollector:
    """评估收集器。

    收集客观指标（解决率、Token 消耗、耗时等）和用户满意度反馈，
    提供统计分析接口。

    Args:
        db_manager: 数据库管理器实例
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db = db_manager

    async def record_ticket_completion(
        self,
        ticket_id: str,
        status: str,
        review_score: float | None = None,
        token_count: int = 0,
        tool_call_count: int = 0,
        duration_seconds: float = 0.0,
    ) -> None:
        """记录工单完成指标。

        Args:
            ticket_id: 工单 ID
            status: 最终状态（completed/failed）
            review_score: 审核评分
            token_count: Token 消耗数
            tool_call_count: 工具调用次数
            duration_seconds: 总处理耗时
        """
        ticket = await self._db.get_ticket(ticket_id)
        if ticket is None:
            logger.warning(f"[Evaluation] Ticket {ticket_id} not found for metric recording")
            return

        update_data = {
            **ticket,
            "ticket_id": ticket_id,
            "status": status,
            "review_score": review_score,
            "token_count": token_count,
            "tool_call_count": tool_call_count,
            "total_duration": duration_seconds,
            "resolved_at": datetime.now().isoformat(),
        }

        await self._db.save_ticket(update_data)
        logger.info(f"[Evaluation] Recorded metrics for {ticket_id}: status={status}, score={review_score}")

    async def record_user_feedback(
        self,
        ticket_id: str,
        satisfied: bool,
    ) -> None:
        """记录用户满意度反馈。

        Args:
            ticket_id: 工单 ID
            satisfied: 是否满意
        """
        ticket = await self._db.get_ticket(ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id} not found")

        await self._db.save_ticket({
            **ticket,
            "ticket_id": ticket_id,
            "satisfied": 1 if satisfied else 0,
        })

        # Update user stats
        user_id = ticket.get("user_id")
        if user_id:
            user = await self._db.get_user(user_id)
            if user:
                total = user.get("total_tickets", 0)
                current_avg = user.get("avg_satisfaction", 0.0) or 0.0
                new_avg = (current_avg * (total - 1) + (1.0 if satisfied else 0.0)) / total if total > 0 else (1.0 if satisfied else 0.0)
                await self._db.save_user({
                    "user_id": user_id,
                    "avg_satisfaction": new_avg,
                })

        logger.info(f"[Evaluation] User feedback for {ticket_id}: satisfied={satisfied}")

    async def get_resolution_stats(self) -> dict[str, Any]:
        """获取处理统计。"""
        return await self._db.get_resolution_stats()

    async def get_efficiency_stats(self) -> dict[str, Any]:
        """获取效率指标。"""
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT AVG(token_count) as avg_tokens, AVG(total_duration) as avg_duration, "
                "AVG(tool_call_count) as avg_tools FROM tickets WHERE status = 'completed'"
            )
            row = await cursor.fetchone()

            return {
                "avg_tokens_per_ticket": round(row["avg_tokens"] or 0, 0),
                "avg_duration_seconds": round(row["avg_duration"] or 0, 2),
                "avg_tool_calls": round(row["avg_tools"] or 0, 1),
            }

    async def get_evaluation_summary(self) -> dict[str, Any]:
        """获取完整评估摘要。"""
        resolution = await self.get_resolution_stats()
        efficiency = await self.get_efficiency_stats()

        async with self._db.connection() as conn:
            cursor = await conn.execute(
                "SELECT AVG(review_score) as avg_score FROM tickets WHERE review_score IS NOT NULL"
            )
            row = await cursor.fetchone()
            avg_review_score = round(row["avg_score"] or 0, 2)

            cursor = await conn.execute(
                "SELECT COUNT(*) as count FROM tickets WHERE satisfied = 1"
            )
            satisfied_count = (await cursor.fetchone())["count"]

            cursor = await conn.execute(
                "SELECT COUNT(*) as count FROM tickets WHERE satisfied IS NOT NULL"
            )
            total_feedback = (await cursor.fetchone())["count"]

        satisfaction_rate = satisfied_count / total_feedback if total_feedback > 0 else 0.0

        return {
            **resolution,
            **efficiency,
            "avg_review_score": avg_review_score,
            "satisfaction_rate": round(satisfaction_rate, 2),
            "total_feedback": total_feedback,
        }
