"""分层记忆系统：工作记忆、短期记忆、长期记忆管理。"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from src.multi_agent_system.core.database import DatabaseManager

__all__ = ["MemoryManager"]


class MemoryManager:
    """分层记忆管理器。

    管理四层记忆：
    - 工作记忆：当前 ReAct 循环的推理状态（内存）
    - 短期记忆：工单级上下文，支持 checkpoint 恢复
    - 长期记忆：用户画像、历史工单（SQLite）
    - 语义记忆：知识库（Qdrant，外部管理）

    Args:
        db_manager: 数据库管理器实例
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db = db_manager

        # Working memory (in-memory only)
        self.thought_chain: list[dict] = []
        self.tool_history: list[dict] = []

    # ========== Working Memory ==========

    def add_thought(self, thought: str, iteration: int = 0) -> None:
        """记录推理步骤。"""
        self.thought_chain.append({
            "iteration": iteration,
            "thought": thought,
            "timestamp": datetime.now().isoformat(),
        })

    def add_action(self, tool: str, params: dict[str, Any], iteration: int = 0) -> None:
        """记录工具调用。"""
        self.tool_history.append({
            "iteration": iteration,
            "tool": tool,
            "params": params,
            "timestamp": datetime.now().isoformat(),
        })

    def add_observation(self, observation: str, iteration: int = 0) -> None:
        """记录工具返回结果。"""
        if self.tool_history:
            self.tool_history[-1]["observation"] = observation
            self.tool_history[-1]["iteration"] = iteration

    def get_react_context(self) -> str:
        """格式化 ReAct 历史为上下文文本。"""
        parts: list[str] = []
        for t in self.thought_chain:
            parts.append(f"Thought: {t['thought']}")
        for h in self.tool_history:
            parts.append(f"Action: {h['tool']}({h.get('params', {})})")
            if "observation" in h:
                parts.append(f"Observation: {h['observation']}")
        return "\n".join(parts)

    def clear_working_memory(self) -> None:
        """清空工作记忆。"""
        self.thought_chain = []
        self.tool_history = []

    # ========== Short-term Memory (Checkpoint) ==========

    async def save_checkpoint(self, ticket_id: str, state: dict[str, Any]) -> str:
        """保存状态检查点。

        Args:
            ticket_id: 工单 ID
            state: 当前状态字典

        Returns:
            checkpoint_id
        """
        checkpoint_id = f"cp-{uuid.uuid4().hex[:8]}"
        expires_at = (datetime.now() + timedelta(hours=24)).isoformat()

        # Merge working memory into state
        state["thought_chain"] = self.thought_chain
        state["tool_history"] = self.tool_history

        await self._db.save_checkpoint(checkpoint_id, ticket_id, state, expires_at)
        logger.info(f"[Memory] Checkpoint saved: {checkpoint_id} for ticket {ticket_id}")
        return checkpoint_id

    async def load_checkpoint(self, ticket_id: str) -> dict[str, Any] | None:
        """加载未过期的检查点。

        Args:
            ticket_id: 工单 ID

        Returns:
            状态字典，或 None（无有效检查点）
        """
        checkpoint = await self._db.get_checkpoint(ticket_id)
        if checkpoint is None:
            return None

        state = checkpoint["state"]
        self.thought_chain = state.get("thought_chain", [])
        self.tool_history = state.get("tool_history", [])
        logger.info(f"[Memory] Checkpoint restored for ticket {ticket_id}")
        return state

    async def delete_checkpoint(self, ticket_id: str) -> None:
        """删除检查点（工单完成后清理）。"""
        await self._db.delete_checkpoint(ticket_id)

    # ========== Long-term Memory ==========

    async def load_user_context(self, user_id: str | None) -> dict[str, Any]:
        """加载用户长期记忆为上下文。

        Args:
            user_id: 用户 ID

        Returns:
            用户上下文字典
        """
        if not user_id:
            return {}

        user = await self._db.get_user(user_id)
        if user is None:
            return {}

        # Load recent ticket history
        history = await self._db.get_user_tickets(user_id, limit=3)

        return {
            "user_id": user_id,
            "vip_level": user.get("vip_level", 0),
            "total_tickets": user.get("total_tickets", 0),
            "preferred_category": user.get("preferred_category", ""),
            "recent_tickets": [
                {
                    "ticket_id": t["ticket_id"],
                    "category": t.get("category", ""),
                    "status": t.get("status", ""),
                    "content": t["content"][:100] if t.get("content") else "",
                }
                for t in history
            ],
        }

    async def ensure_user(self, user_id: str, name: str = "") -> dict[str, Any]:
        """确保用户存在，不存在则创建默认档案。"""
        user = await self._db.get_user(user_id)
        if user is None:
            user = {
                "user_id": user_id,
                "name": name,
                "vip_level": 0,
                "total_tickets": 0,
            }
            await self._db.save_user(user)
            logger.info(f"[Memory] Created user profile: {user_id}")
        return user

    async def update_user_after_ticket(
        self,
        user_id: str | None,
        category: str | None,
        satisfied: bool | None = None,
    ) -> None:
        """工单完成后更新用户档案。"""
        if not user_id:
            return

        user = await self._db.get_user(user_id)
        if user is None:
            user = {"user_id": user_id, "name": "", "vip_level": 0, "total_tickets": 0}

        total = user.get("total_tickets", 0) + 1
        user["total_tickets"] = total
        user["last_contact"] = datetime.now().isoformat()

        if category:
            user["preferred_category"] = category

        if satisfied is not None:
            current_avg = user.get("avg_satisfaction", 0.0) or 0.0
            user["avg_satisfaction"] = (current_avg * (total - 1) + (1.0 if satisfied else 0.0)) / total

        await self._db.save_user(user)

    async def get_pattern(self, category: str) -> dict[str, Any] | None:
        """获取某分类的解决方案模板。"""
        return await self._db.get_pattern(category)

    async def cleanup_expired_checkpoints(self) -> int:
        """清理过期检查点。"""
        count = await self._db.cleanup_expired_checkpoints()
        if count > 0:
            logger.info(f"[Memory] Cleaned up {count} expired checkpoints")
        return count
