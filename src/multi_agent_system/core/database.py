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
        await self._connection.commit()
        logger.info(f"[Database] Initialized: {self._db_path}")

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
            await conn.execute(
                """INSERT OR REPLACE INTO tickets (
                    ticket_id, user_id, content, category, priority,
                    processing_result, review_score, retry_count, status,
                    error, resolved_at, satisfied, token_count,
                    tool_call_count, total_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket_data.get("ticket_id"),
                    ticket_data.get("user_id"),
                    ticket_data.get("content"),
                    ticket_data.get("category"),
                    ticket_data.get("priority"),
                    ticket_data.get("processing_result"),
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
                "SELECT * FROM traces WHERE ticket_id = ? ORDER BY start_time DESC LIMIT 1",
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
        query = "SELECT * FROM traces"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

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
        _db_manager_instance = DatabaseManager()
        await _db_manager_instance.initialize()
    return _db_manager_instance


def reset_db_manager() -> None:
    global _db_manager_instance
    _db_manager_instance = None
