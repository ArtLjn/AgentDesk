"""上下文窗口管理：滑动窗口、摘要压缩、关键信息提取。"""

from typing import Any

from loguru import logger

__all__ = ["ContextManager"]


class ContextManager:
    """上下文管理器。

    提供三层策略管理对话上下文：
    1. 滑动窗口：保留最近 N 轮消息
    2. 摘要压缩：丢弃的消息生成摘要
    3. 关键信息提取：重要事实存入独立字段

    Args:
        max_messages: 最大保留消息数（含系统消息），默认 20
        summary_max_tokens: 摘要最大长度，默认 200 字符
    """

    def __init__(self, max_messages: int = 20, summary_max_tokens: int = 200) -> None:
        self.max_messages = max_messages
        self.summary_max_tokens = summary_max_tokens

    def trim_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """应用滑动窗口，保留系统消息 + 最近 N 轮。

        Args:
            messages: 原始消息列表

        Returns:
            裁剪后的消息列表
        """
        if len(messages) <= self.max_messages:
            return messages

        # Separate system messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # Keep most recent messages
        keep_count = self.max_messages - len(system_msgs)
        if keep_count < 2:
            keep_count = 2  # At least keep something

        recent = non_system[-keep_count:]
        dropped = non_system[:-keep_count]

        # Generate summary of dropped messages
        summary = self._summarize_dropped(dropped)

        result = system_msgs.copy()
        if summary:
            result.append({
                "role": "system",
                "content": f"【前文摘要】{summary}",
            })
        result.extend(recent)

        logger.debug(f"[ContextManager] Trimmed {len(messages)} -> {len(result)} messages")
        return result

    def _summarize_dropped(self, dropped: list[dict[str, Any]]) -> str:
        """生成丢弃消息的摘要（轻量级，不调用 LLM）。

        提取关键事实：用户问题、分类、工具调用结果等。
        """
        if not dropped:
            return ""

        facts: list[str] = []

        for msg in dropped:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and len(content) > 5:
                facts.append(f"用户问题: {content[:80]}")
            elif role == "assistant" and "Thought:" in content:
                thought = content.split("Thought:")[1].split("\n")[0][:80]
                facts.append(f"推理: {thought}")
            elif role == "assistant" and "Final Answer:" in content:
                facts.append("已生成初步结论")

        summary = "; ".join(facts[:3])
        if len(summary) > self.summary_max_tokens:
            summary = summary[: self.summary_max_tokens - 3] + "..."

        return summary

    def extract_critical_info(self, state: dict[str, Any]) -> dict[str, Any]:
        """从状态中抽取关键信息到独立字段。

        Args:
            state: 当前 TicketState

        Returns:
            关键信息字典
        """
        return {
            "ticket_id": state.get("ticket_id", ""),
            "user_id": state.get("user_id", ""),
            "category": state.get("category", ""),
            "priority": state.get("priority", ""),
            "content_preview": state.get("content", "")[:200],
            "review_score": state.get("review_score"),
            "retry_count": state.get("retry_count", 0),
        }

    def build_system_context(self, critical_info: dict[str, Any], user_context: dict[str, Any]) -> str:
        """构建系统提示中的上下文信息。

        Args:
            critical_info: 关键信息字典
            user_context: 用户上下文

        Returns:
            格式化的上下文文本
        """
        parts: list[str] = []

        parts.append(f"工单ID: {critical_info['ticket_id']}")
        parts.append(f"分类: {critical_info['category'] or '待分类'}")
        parts.append(f"优先级: {critical_info['priority'] or '待确定'}")

        if user_context.get("vip_level", 0) > 0:
            parts.append(f"用户VIP等级: {user_context['vip_level']}")

        if user_context.get("total_tickets", 0) > 0:
            parts.append(f"用户历史工单数: {user_context['total_tickets']}")

        if user_context.get("recent_tickets"):
            parts.append("近期工单:")
            for t in user_context["recent_tickets"][:2]:
                parts.append(f"  - {t['ticket_id']} ({t['category']}): {t['content'][:50]}")

        return "\n".join(parts)
