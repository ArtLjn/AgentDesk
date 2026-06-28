"""Trace 数据库 CRUD 和 TraceManager 单元测试。"""

import json
import time

import pytest

from src.multi_agent_system.core.database import DatabaseManager
from src.multi_agent_system.core.trace import TraceManager
from tests.conftest import TEST_DATABASE_URL


class TestTraceDatabase:
    """trace 和 span 表 CRUD 测试。"""

    @pytest.mark.asyncio
    async def test_save_and_get_trace(self):
        """保存 trace 并按 ticket_id 查询。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        trace_data = {
            "trace_id": "tr-001",
            "ticket_id": "TK-001",
            "status": "running",
            "start_time": time.time(),
        }
        await db.save_trace(trace_data)
        result = await db.get_trace_by_ticket("TK-001")
        assert result is not None
        assert result["trace_id"] == "tr-001"
        assert result["status"] == "running"
        await db.close()

    @pytest.mark.asyncio
    async def test_list_traces_with_filter(self):
        """按 status 过滤 trace 列表。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        now = time.time()
        await db.save_trace({"trace_id": "tr-1", "ticket_id": "TK-1", "status": "completed", "start_time": now - 1})
        await db.save_trace({"trace_id": "tr-2", "ticket_id": "TK-2", "status": "running", "start_time": now})
        result = await db.list_traces(status="completed")
        assert len(result) == 1
        assert result[0]["trace_id"] == "tr-1"
        await db.close()

    @pytest.mark.asyncio
    async def test_save_and_get_spans(self):
        """保存 span 并查询。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        await db.save_trace({"trace_id": "tr-001", "ticket_id": "TK-001", "status": "running", "start_time": time.time()})
        await db.save_span({
            "span_id": "sp-1", "trace_id": "tr-001", "parent_span_id": None,
            "span_type": "node", "name": "classify", "status": "ok",
            "start_time": time.time(), "duration": 0.1,
        })
        spans = await db.get_spans_by_trace("tr-001")
        assert len(spans) == 1
        assert spans[0]["name"] == "classify"
        await db.close()

    @pytest.mark.asyncio
    async def test_update_span(self):
        """更新 span 的 end_time 和 duration。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        await db.save_trace({"trace_id": "tr-001", "ticket_id": "TK-001", "status": "running", "start_time": time.time()})
        await db.save_span({
            "span_id": "sp-1", "trace_id": "tr-001", "parent_span_id": None,
            "span_type": "node", "name": "classify", "status": "ok",
            "start_time": time.time(),
        })
        await db.update_span("sp-1", {"end_time": time.time(), "duration": 0.5, "status": "ok"})
        spans = await db.get_spans_by_trace("tr-001")
        assert spans[0]["duration"] == 0.5
        await db.close()

    @pytest.mark.asyncio
    async def test_nested_spans(self):
        """嵌套 span 的 parent_span_id 关系正确。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        await db.save_trace({"trace_id": "tr-001", "ticket_id": "TK-001", "status": "running", "start_time": time.time()})
        await db.save_span({
            "span_id": "sp-1", "trace_id": "tr-001", "parent_span_id": None,
            "span_type": "node", "name": "process", "status": "ok",
            "start_time": time.time(),
        })
        await db.save_span({
            "span_id": "sp-2", "trace_id": "tr-001", "parent_span_id": "sp-1",
            "span_type": "tool_call", "name": "knowledge_search", "status": "ok",
            "start_time": time.time(),
        })
        spans = await db.get_spans_by_trace("tr-001")
        child = [s for s in spans if s["span_id"] == "sp-2"][0]
        assert child["parent_span_id"] == "sp-1"
        await db.close()

    @pytest.mark.asyncio
    async def test_get_trace_stats(self):
        """trace 耗时统计按 span_type 聚合。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        now = time.time()
        await db.save_trace({
            "trace_id": "tr-001", "ticket_id": "TK-001", "status": "completed",
            "start_time": now - 1, "end_time": now, "duration": 1.0,
        })
        await db.save_span({
            "span_id": "sp-1", "trace_id": "tr-001", "parent_span_id": None,
            "span_type": "node", "name": "process", "status": "ok",
            "start_time": now - 0.5, "end_time": now, "duration": 0.5,
        })
        await db.save_span({
            "span_id": "sp-2", "trace_id": "tr-001", "parent_span_id": None,
            "span_type": "llm_call", "name": "chat_completions", "status": "ok",
            "start_time": now - 0.3, "end_time": now, "duration": 0.3,
        })
        stats = await db.get_trace_stats("tr-001")
        assert stats is not None
        assert "node" in stats["by_type"]
        assert stats["by_type"]["node"]["count"] == 1
        assert len(stats["slowest_spans"]) == 2
        await db.close()


class TestTraceManager:
    """TraceManager 生命周期和 span 嵌套测试。"""

    @pytest.mark.asyncio
    async def test_start_and_finish_trace(self):
        """trace 完整生命周期。"""
        from src.multi_agent_system.core.trace import current_trace_id

        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        manager = TraceManager(db)
        trace_id = await manager.start_trace("TK-001")
        assert trace_id.startswith("trace-")
        assert current_trace_id.get() == trace_id

        await manager.finish_trace(trace_id, "completed")
        assert current_trace_id.get() is None

        trace = await db.get_trace_by_ticket("TK-001")
        assert trace["status"] == "completed"
        assert trace["duration"] is not None
        assert trace["duration"] > 0
        await db.close()

    @pytest.mark.asyncio
    async def test_span_context_manager(self):
        """span 自动记录耗时。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        manager = TraceManager(db)
        trace_id = await manager.start_trace("TK-001")

        async with manager.start_span("classify", "node") as span:
            span.set_output({"category": "technical"})

        spans = await db.get_spans_by_trace(trace_id)
        assert len(spans) == 1
        assert spans[0]["name"] == "classify"
        assert spans[0]["duration"] is not None
        assert spans[0]["duration"] > 0

        await manager.finish_trace(trace_id, "completed")
        await db.close()

    @pytest.mark.asyncio
    async def test_nested_spans(self):
        """嵌套 span 的 parent 关系正确。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        manager = TraceManager(db)
        trace_id = await manager.start_trace("TK-001")

        async with manager.start_span("process", "node") as parent:
            async with manager.start_span("react_iter", "react_iter") as child:
                child.set_metadata({"iteration": 1})

        spans = await db.get_spans_by_trace(trace_id)
        assert len(spans) == 2
        parent_span = [s for s in spans if s["name"] == "process"][0]
        child_span = [s for s in spans if s["name"] == "react_iter"][0]
        assert child_span["parent_span_id"] == parent_span["span_id"]

        await manager.finish_trace(trace_id, "completed")
        await db.close()

    @pytest.mark.asyncio
    async def test_span_captures_exception(self):
        """span 内异常自动标记 error。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        manager = TraceManager(db)
        trace_id = await manager.start_trace("TK-001")

        with pytest.raises(ValueError):
            async with manager.start_span("failing_node", "node") as span:
                raise ValueError("test error")

        spans = await db.get_spans_by_trace(trace_id)
        assert spans[0]["status"] == "error"
        metadata = json.loads(spans[0]["metadata"])
        assert "test error" in metadata["error"]

        await manager.finish_trace(trace_id, "failed", error="test error")
        await db.close()

    @pytest.mark.asyncio
    async def test_noop_span_when_no_trace(self):
        """无活跃 trace 时返回 no-op span，不报错。"""
        from src.multi_agent_system.core.trace import current_trace_id

        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        manager = TraceManager(db)
        current_trace_id.set(None)

        async with manager.start_span("classify", "node") as span:
            span.set_output({"category": "technical"})

        # 不应写入任何 span
        traces = await db.list_traces()
        assert len(traces) == 0
        await db.close()

    @pytest.mark.asyncio
    async def test_node_and_tool_count(self):
        """node_count 和 total_tool_calls 自动递增。"""
        db = DatabaseManager(database_url=TEST_DATABASE_URL)
        await db.initialize()
        await db.truncate_all()

        manager = TraceManager(db)
        trace_id = await manager.start_trace("TK-001")

        async with manager.start_span("classify", "node"):
            pass
        async with manager.start_span("process", "node"):
            async with manager.start_span("knowledge_search", "tool_call"):
                pass

        await manager.finish_trace(trace_id, "completed")

        trace = await db.get_trace_by_ticket("TK-001")
        assert trace["node_count"] == 2
        assert trace["total_tool_calls"] == 1
        await db.close()
