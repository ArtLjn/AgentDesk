"""Async SQLite database manager with schema migrations."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import aiosqlite
from loguru import logger

__all__ = ["DatabaseManager", "get_db_manager", "reset_db_manager"]

# Schema definition
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    user_id TEXT,
    content TEXT NOT NULL,
    category TEXT,
    priority TEXT,
    processing_result TEXT,
    references_json TEXT,
    review_score REAL,
    retry_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'received',
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    satisfied INTEGER,
    token_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    total_duration REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    vip_level INTEGER DEFAULT 0,
    preferred_category TEXT,
    avg_satisfaction REAL,
    total_tickets INTEGER DEFAULT 0,
    last_contact TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL UNIQUE,
    state_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS patterns (
    pattern_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    keywords TEXT,
    solution_template TEXT NOT NULL,
    success_rate REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_checkpoints_expires ON checkpoints(expires_at);

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    start_time REAL NOT NULL,
    end_time REAL,
    duration REAL,
    total_tokens INTEGER DEFAULT 0,
    total_tool_calls INTEGER DEFAULT 0,
    node_count INTEGER DEFAULT 0,
    error TEXT
);

CREATE TABLE IF NOT EXISTS spans (
    span_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_span_id TEXT,
    span_type TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    input_data TEXT,
    output_data TEXT,
    start_time REAL NOT NULL,
    end_time REAL,
    duration REAL,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(parent_span_id);
CREATE INDEX IF NOT EXISTS idx_spans_type ON spans(span_type);
CREATE INDEX IF NOT EXISTS idx_traces_ticket ON traces(ticket_id);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);

CREATE TABLE IF NOT EXISTS human_reviews (
    review_id        TEXT PRIMARY KEY,
    ticket_id        TEXT NOT NULL,
    trigger_type     TEXT NOT NULL,
    trigger_reason   TEXT,
    ai_suggestion    TEXT,
    decision         TEXT,
    decision_reason  TEXT,
    rewritten_result TEXT,
    reviewer_id      TEXT,
    status           TEXT NOT NULL,
    created_at       TIMESTAMP,
    decided_at       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hr_status   ON human_reviews(status);
CREATE INDEX IF NOT EXISTS idx_hr_ticket   ON human_reviews(ticket_id);
CREATE INDEX IF NOT EXISTS idx_hr_trigger  ON human_reviews(trigger_type);
CREATE INDEX IF NOT EXISTS idx_hr_reviewer ON human_reviews(reviewer_id);

-- 部分索引：加速待审核工单查询。SQLite 3.8.0+ 支持。
CREATE INDEX IF NOT EXISTS idx_tickets_pending
    ON tickets(created_at) WHERE status = 'pending_human_review';
"""


class DatabaseManager:
    """Async SQLite connection manager with connection pooling."""

    def __init__(self, db_path: str = "data/app.db") -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create database file, run schema migrations."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(_SCHEMA_SQL)
        await self._ensure_column("tickets", "references_json", "TEXT")
        await self._connection.commit()
        logger.info(f"[Database] Initialized: {self._db_path}")

    async def _ensure_column(self, table: str, column: str, definition: str) -> None:
        """为旧数据库补充新增字段。"""
        if self._connection is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        cursor = await self._connection.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        if column in {row["name"] for row in rows}:
            return
        await self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Yield the singleton connection."""
        if self._connection is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        yield self._connection

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("[Database] Connection closed")

    # Ticket operations
    async def save_ticket(self, ticket_data: dict[str, Any]) -> None:
        """保存或更新工单记录。"""
        async with self.connection() as conn:
            references = ticket_data.get("references")
            if "references" not in ticket_data:
                cursor = await conn.execute(
                    "SELECT references_json FROM tickets WHERE ticket_id = ?",
                    (ticket_data.get("ticket_id"),),
                )
                row = await cursor.fetchone()
                references_json = row["references_json"] if row else None
            else:
                references_json = json.dumps(references or [], ensure_ascii=False)

            await conn.execute(
                """INSERT OR REPLACE INTO tickets (
                    ticket_id, user_id, content, category, priority,
                    processing_result, references_json, review_score, retry_count, status,
                    error, resolved_at, satisfied, token_count,
                    tool_call_count, total_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket_data.get("ticket_id"),
                    ticket_data.get("user_id"),
                    ticket_data.get("content"),
                    ticket_data.get("category"),
                    ticket_data.get("priority"),
                    ticket_data.get("processing_result"),
                    references_json,
                    ticket_data.get("review_score"),
                    ticket_data.get("retry_count", 0),
                    ticket_data.get("status", "received"),
                    ticket_data.get("error"),
                    ticket_data.get("resolved_at"),
                    ticket_data.get("satisfied"),
                    ticket_data.get("token_count", 0),
                    ticket_data.get("tool_call_count", 0),
                    ticket_data.get("total_duration", 0.0),
                ),
            )
            await conn.commit()

    async def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        """根据工单ID查询工单记录。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_tickets(
        self,
        status: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """分页查询工单列表，可按状态和分类筛选。"""
        async with self.connection() as conn:
            query = "SELECT * FROM tickets WHERE 1=1"
            params: list[Any] = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if category:
                query += " AND category = ?"
                params.append(category)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # User operations
    async def get_user(self, user_id: str) -> dict[str, Any] | None:
        """根据用户ID查询用户信息。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def save_user(self, user_data: dict[str, Any]) -> None:
        """保存或更新用户信息。"""
        async with self.connection() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO users (
                    user_id, name, vip_level, preferred_category,
                    avg_satisfaction, total_tickets, last_contact
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_data.get("user_id"),
                    user_data.get("name"),
                    user_data.get("vip_level", 0),
                    user_data.get("preferred_category"),
                    user_data.get("avg_satisfaction"),
                    user_data.get("total_tickets", 0),
                    user_data.get("last_contact"),
                ),
            )
            await conn.commit()

    async def get_user_tickets(
        self, user_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """查询指定用户的最近工单列表。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Checkpoint operations
    async def save_checkpoint(
        self, checkpoint_id: str, ticket_id: str, state: dict[str, Any], expires_at: str
    ) -> None:
        """保存或更新检查点状态。"""
        async with self.connection() as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO checkpoints (checkpoint_id, ticket_id, state_json, expires_at) VALUES (?, ?, ?, ?)",
                (
                    checkpoint_id,
                    ticket_id,
                    json.dumps(state, ensure_ascii=False),
                    expires_at,
                ),
            )
            await conn.commit()

    async def get_checkpoint(self, ticket_id: str) -> dict[str, Any] | None:
        """根据工单ID查询未过期的检查点。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM checkpoints WHERE ticket_id = ? AND expires_at > datetime('now')",
                (ticket_id,),
            )
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                result["state"] = json.loads(result["state_json"])
                return result
            return None

    async def list_active_checkpoints(self) -> list[dict[str, Any]]:
        """查询所有未过期的检查点列表。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM checkpoints WHERE expires_at > datetime('now')"
            )
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["state"] = json.loads(item["state_json"])
                result.append(item)
            return result

    async def delete_checkpoint(self, ticket_id: str) -> None:
        """根据工单ID删除检查点。"""
        async with self.connection() as conn:
            await conn.execute(
                "DELETE FROM checkpoints WHERE ticket_id = ?", (ticket_id,)
            )
            await conn.commit()

    async def cleanup_expired_checkpoints(self) -> int:
        """清理已过期的检查点，返回删除数量。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM checkpoints WHERE expires_at <= datetime('now')"
            )
            await conn.commit()
            return cursor.rowcount

    # Pattern operations
    async def get_pattern(self, category: str) -> dict[str, Any] | None:
        """根据分类查询使用次数最多的匹配模式。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM patterns WHERE category = ? ORDER BY usage_count DESC LIMIT 1",
                (category,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def save_pattern(self, pattern_data: dict[str, Any]) -> None:
        """保存或更新匹配模式记录。"""
        async with self.connection() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO patterns (
                    pattern_id, category, keywords, solution_template,
                    success_rate, usage_count
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    pattern_data.get("pattern_id"),
                    pattern_data.get("category"),
                    pattern_data.get("keywords"),
                    pattern_data.get("solution_template"),
                    pattern_data.get("success_rate", 0.0),
                    pattern_data.get("usage_count", 0),
                ),
            )
            await conn.commit()

    # Trace CRUD
    # ============================================================

    async def save_trace(self, trace_data: dict[str, Any]) -> None:
        """保存或更新 trace 记录。"""
        cols = [
            "trace_id", "ticket_id", "status", "start_time",
            "end_time", "duration", "total_tokens", "total_tool_calls",
            "node_count", "error",
        ]
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join(cols)
        values = [trace_data.get(c) for c in cols]
        async with self.connection() as conn:
            await conn.execute(
                f"INSERT OR REPLACE INTO traces ({col_str}) VALUES ({placeholders})",
                values,
            )
            await conn.commit()

    async def get_trace_by_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        """按 ticket_id 查询 trace。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT
                    tr.*,
                    tk.content AS ticket_content,
                    tk.category AS ticket_category,
                    tk.priority AS ticket_priority,
                    tk.processing_result AS ticket_result,
                    tk.review_score AS ticket_review_score,
                    tk.references_json AS ticket_references_json
                FROM traces tr
                LEFT JOIN tickets tk ON tk.ticket_id = tr.ticket_id
                WHERE tr.ticket_id = ?
                ORDER BY tr.start_time DESC
                LIMIT 1
                """,
                (ticket_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_traces(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询 trace 列表，按 start_time DESC 排序。"""
        query = """
            SELECT
                tr.*,
                tk.content AS ticket_content,
                tk.category AS ticket_category,
                tk.priority AS ticket_priority,
                tk.processing_result AS ticket_result,
                tk.review_score AS ticket_review_score,
                tk.references_json AS ticket_references_json
            FROM traces tr
            LEFT JOIN tickets tk ON tk.ticket_id = tr.ticket_id
        """
        params: list[Any] = []
        if status:
            query += " WHERE tr.status = ?"
            params.append(status)
        query += " ORDER BY tr.start_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def count_traces(self, status: str | None = None) -> int:
        """统计 trace 总数，用于分页。"""
        query = "SELECT COUNT(*) as total FROM traces"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            return int(row["total"]) if row else 0

    async def get_trace_stats(self, trace_id: str) -> dict[str, Any] | None:
        """获取 trace 的耗时统计。"""
        trace = None
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?",
                (trace_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            trace = dict(row)

            # 按 span_type 聚合
            cursor = await conn.execute(
                "SELECT span_type, COUNT(*) as count, "
                "AVG(duration) as avg_duration, MAX(duration) as max_duration "
                "FROM spans WHERE trace_id = ? AND duration IS NOT NULL "
                "GROUP BY span_type",
                (trace_id,),
            )
            by_type = {}
            for r in await cursor.fetchall():
                d = dict(r)
                by_type[d["span_type"]] = {
                    "count": d["count"],
                    "avg_duration": round(d["avg_duration"], 4),
                    "max_duration": round(d["max_duration"], 4),
                }
            trace["by_type"] = by_type

            # 最慢的 5 个 span
            cursor = await conn.execute(
                "SELECT name, span_type, duration FROM spans "
                "WHERE trace_id = ? AND duration IS NOT NULL "
                "ORDER BY duration DESC LIMIT 5",
                (trace_id,),
            )
            trace["slowest_spans"] = [dict(r) for r in await cursor.fetchall()]

        return trace

    async def save_span(self, span_data: dict[str, Any]) -> None:
        """保存 span 记录。"""
        cols = [
            "span_id", "trace_id", "parent_span_id", "span_type",
            "name", "status", "input_data", "output_data",
            "start_time", "end_time", "duration", "metadata",
        ]
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join(cols)
        values = [span_data.get(c) for c in cols]
        async with self.connection() as conn:
            await conn.execute(
                f"INSERT OR REPLACE INTO spans ({col_str}) VALUES ({placeholders})",
                values,
            )
            await conn.commit()

    async def update_span(self, span_id: str, updates: dict[str, Any]) -> None:
        """更新 span 记录的部分字段。"""
        set_parts = [f"{k} = ?" for k in updates]
        values = list(updates.values()) + [span_id]
        async with self.connection() as conn:
            await conn.execute(
                f"UPDATE spans SET {', '.join(set_parts)} WHERE span_id = ?",
                values,
            )
            await conn.commit()

    async def get_spans_by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """查询 trace 的所有 span，按 start_time 排序。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
                (trace_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # Human Review CRUD
    # ============================================================

    async def create_pending_review(self, review: dict[str, Any]) -> None:
        """创建待审核单。

        Args:
            review: 包含 review_id / ticket_id / trigger_type / trigger_reason /
                ai_suggestion 等字段的字典
        """
        ai_suggestion_raw = review.get("ai_suggestion")
        if isinstance(ai_suggestion_raw, dict):
            ai_suggestion_json = json.dumps(ai_suggestion_raw, ensure_ascii=False)
        elif ai_suggestion_raw is None:
            ai_suggestion_json = None
        else:
            ai_suggestion_json = str(ai_suggestion_raw)

        async with self.connection() as conn:
            await conn.execute(
                """INSERT INTO human_reviews (
                    review_id, ticket_id, trigger_type, trigger_reason,
                    ai_suggestion, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    review.get("review_id"),
                    review.get("ticket_id"),
                    review.get("trigger_type"),
                    review.get("trigger_reason"),
                    ai_suggestion_json,
                    review.get("created_at"),
                ),
            )
            await conn.commit()

    async def get_pending_review_by_ticket(
        self, ticket_id: str
    ) -> dict[str, Any] | None:
        """按工单 ID 查询最新待审核记录。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM human_reviews WHERE ticket_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (ticket_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_review_decision(
        self, review_id: str, updates: dict[str, Any]
    ) -> None:
        """更新审核单的决策信息。

        Args:
            review_id: 审核单 ID
            updates: 包含 decision / decision_reason / rewritten_result /
                reviewer_id / status / decided_at 等字段的字典
        """
        allowed = {
            "decision", "decision_reason", "rewritten_result",
            "reviewer_id", "status", "decided_at",
        }
        set_parts = [f"{k} = ?" for k in updates if k in allowed]
        values = [v for k, v in updates.items() if k in allowed]
        if not set_parts:
            return
        values.append(review_id)
        async with self.connection() as conn:
            await conn.execute(
                f"UPDATE human_reviews SET {', '.join(set_parts)} "
                "WHERE review_id = ?",
                values,
            )
            await conn.commit()

    async def list_pending_reviews(
        self,
        status: str | None = None,
        trigger_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """分页查询审核单列表，可按状态和触发类型筛选。"""
        query = "SELECT * FROM human_reviews WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if trigger_type:
            query += " AND trigger_type = ?"
            params.append(trigger_type)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def list_reviews_by_ticket(self, ticket_id: str) -> list[dict[str, Any]]:
        """查询指定工单的全部审核记录。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM human_reviews WHERE ticket_id = ? "
                "ORDER BY created_at ASC",
                (ticket_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_review_stats(self) -> dict[str, Any]:
        """统计审核单整体情况：总数、待处理、已处理及按决策/触发类型分布。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) as total FROM human_reviews"
            )
            total = (await cursor.fetchone())["total"]

            cursor = await conn.execute(
                "SELECT COUNT(*) as cnt FROM human_reviews WHERE status = 'pending'"
            )
            pending = (await cursor.fetchone())["cnt"]

            cursor = await conn.execute(
                "SELECT COUNT(*) as cnt FROM human_reviews WHERE status = 'decided'"
            )
            decided = (await cursor.fetchone())["cnt"]

            cursor = await conn.execute(
                "SELECT decision, COUNT(*) as cnt FROM human_reviews "
                "WHERE decision IS NOT NULL GROUP BY decision"
            )
            by_decision = {row["decision"]: row["cnt"] for row in await cursor.fetchall()}

            cursor = await conn.execute(
                "SELECT trigger_type, COUNT(*) as cnt FROM human_reviews "
                "GROUP BY trigger_type"
            )
            by_trigger = {row["trigger_type"]: row["cnt"] for row in await cursor.fetchall()}

        return {
            "total": total,
            "pending": pending,
            "decided": decided,
            "by_decision": by_decision,
            "by_trigger": by_trigger,
        }

    # Analytics
    async def get_category_distribution(self) -> dict[str, int]:
        """统计各分类的工单数量分布。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT category, COUNT(*) as count FROM tickets GROUP BY category"
            )
            rows = await cursor.fetchall()
            return {row["category"] or "uncategorized": row["count"] for row in rows}

    async def get_priority_distribution(self) -> dict[str, int]:
        """统计各优先级的工单数量分布。"""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT priority, COUNT(*) as count FROM tickets GROUP BY priority"
            )
            rows = await cursor.fetchall()
            return {row["priority"] or "unassigned": row["count"] for row in rows}

    async def get_resolution_stats(self) -> dict[str, Any]:
        """获取工单整体解决统计信息，包括总数、完成数、失败数、平均重试次数和成功率。"""
        async with self.connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) as total FROM tickets")
            total = (await cursor.fetchone())["total"]

            cursor = await conn.execute(
                "SELECT COUNT(*) as completed FROM tickets WHERE status = 'completed'"
            )
            completed = (await cursor.fetchone())["completed"]

            cursor = await conn.execute(
                "SELECT COUNT(*) as failed FROM tickets WHERE status = 'failed'"
            )
            failed = (await cursor.fetchone())["failed"]

            cursor = await conn.execute(
                "SELECT AVG(retry_count) as avg_retries FROM tickets"
            )
            avg_retries = (await cursor.fetchone())["avg_retries"] or 0.0

            success_rate = completed / total if total > 0 else 0.0

            return {
                "total": total,
                "completed": completed,
                "failed": failed,
                "avg_retries": round(avg_retries, 2),
                "success_rate": round(success_rate, 4),
            }


# Global singleton
_db_manager_instance: DatabaseManager | None = None


async def get_db_manager() -> DatabaseManager:
    global _db_manager_instance
    if _db_manager_instance is None:
        from src.multi_agent_system.config import Settings
        _db_manager_instance = DatabaseManager(db_path=Settings().db_path)
        await _db_manager_instance.initialize()
    return _db_manager_instance


def reset_db_manager() -> None:
    global _db_manager_instance
    _db_manager_instance = None
