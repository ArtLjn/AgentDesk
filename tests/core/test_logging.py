"""结构化日志工具单元测试。"""

import asyncio
from unittest.mock import patch

import pytest

from src.multi_agent_system.core.logging import (
    generate_trace_id,
    get_trace_id,
    log_context,
    structured_logger,
    trace_id_var,
)


class TestGenerateTraceId:
    """generate_trace_id 函数测试。"""

    def test_returns_16_char_hex_string(self) -> None:
        trace_id = generate_trace_id()
        assert len(trace_id) == 16
        assert all(c in "0123456789abcdef" for c in trace_id)

    def test_generates_unique_ids(self) -> None:
        ids = {generate_trace_id() for _ in range(100)}
        assert len(ids) == 100


class TestGetTraceId:
    """get_trace_id 函数测试。"""

    def test_returns_none_when_not_set(self) -> None:
        # 重置上下文
        trace_id_var.set(None)
        assert get_trace_id() is None

    def test_returns_value_when_set(self) -> None:
        token = trace_id_var.set("test-trace-123")
        assert get_trace_id() == "test-trace-123"
        trace_id_var.reset(token)


class TestLogContext:
    """log_context 上下文管理器测试。"""

    def test_auto_generates_trace_id(self) -> None:
        trace_id_var.set(None)
        with log_context(agent="test"):
            trace_id = get_trace_id()
            assert trace_id is not None
            assert len(trace_id) == 16

    def test_preserves_existing_trace_id(self) -> None:
        token = trace_id_var.set("existing-id")
        try:
            with log_context(agent="test"):
                assert get_trace_id() == "existing-id"
        finally:
            trace_id_var.reset(token)

    def test_restores_trace_id_on_exit(self) -> None:
        trace_id_var.set(None)
        with log_context(agent="test"):
            inner_trace_id = get_trace_id()
        # 退出后 trace_id 应恢复为 None
        assert get_trace_id() is None
        assert inner_trace_id is not None

    def test_binds_extra_kwargs(self) -> None:
        trace_id_var.set(None)
        with log_context(agent="classifier", task="classify"):
            # 上下文管理器内部应能正常工作
            assert get_trace_id() is not None


class TestStructuredLogger:
    """structured_logger 函数测试。"""

    def test_logs_with_trace_id(self) -> None:
        token = trace_id_var.set("test-trace-456")
        try:
            # 不应抛出异常
            structured_logger("test message", level="INFO", agent="test")
        finally:
            trace_id_var.reset(token)

    def test_logs_without_trace_id(self) -> None:
        trace_id_var.set(None)
        # 不应抛出异常（trace_id 为 None 时也能正常工作）
        structured_logger("test message")
