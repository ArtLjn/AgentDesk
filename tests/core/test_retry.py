"""retry 模块单元测试。"""

import asyncio

import pytest

from src.multi_agent_system.core.exceptions import (
    FallbackExhaustedError,
    NonRetryableError,
    RetryableError,
)
from src.multi_agent_system.core.retry import with_retry


class TestWithRetrySuccess:
    """重试成功路径测试。"""

    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        """首次调用成功，不需要重试。"""
        call_count = 0

        @with_retry()
        async def ok_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await ok_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self) -> None:
        """首次失败后重试成功。"""
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01)
        async def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("临时错误")
            return "recovered"

        result = await flaky_func()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retryable_error_retried_max_times(self) -> None:
        """可重试异常在重试次数耗尽后进入降级。"""
        call_count = 0

        @with_retry(max_retries=2, backoff_base=0.01, fallback=lambda: "fallback_result")
        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise RetryableError("持续失败")

        result = await always_fail()
        assert result == "fallback_result"
        assert call_count == 3  # 首次 + 2 次重试


class TestWithRetryNonRetryable:
    """不可重试异常路径测试。"""

    @pytest.mark.asyncio
    async def test_non_retryable_skips_retry(self) -> None:
        """不可重试异常跳过重试，直接进入降级。"""
        call_count = 0

        @with_retry(max_retries=5, fallback=lambda: "fallback")
        async def bad_request() -> str:
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("参数错误")

        result = await bad_request()
        assert result == "fallback"
        assert call_count == 1  # 不重试，只调用一次

    @pytest.mark.asyncio
    async def test_unknown_exception_skips_retry(self) -> None:
        """未知异常视为不可重试，跳过重试。"""
        call_count = 0

        @with_retry(max_retries=5, fallback=lambda: "fallback")
        async def unknown_error() -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("未知错误")

        result = await unknown_error()
        assert result == "fallback"
        assert call_count == 1


class TestWithRetryFallback:
    """降级回调测试。"""

    @pytest.mark.asyncio
    async def test_sync_fallback(self) -> None:
        """同步降级函数正常工作。"""

        @with_retry(max_retries=1, backoff_base=0.01, fallback=lambda x: f"fb:{x}")
        async def fail_func(x: int) -> str:
            raise RetryableError("失败")

        result = await fail_func(42)
        assert result == "fb:42"

    @pytest.mark.asyncio
    async def test_async_fallback(self) -> None:
        """异步降级函数正常工作。"""

        async def async_fb(x: int) -> str:
            return f"async_fb:{x}"

        @with_retry(max_retries=1, backoff_base=0.01, fallback=async_fb)
        async def fail_func(x: int) -> str:
            raise RetryableError("失败")

        result = await fail_func(42)
        assert result == "async_fb:42"

    @pytest.mark.asyncio
    async def test_no_fallback_raises_exhausted(self) -> None:
        """无降级回调时重试耗尽抛出 FallbackExhaustedError。"""

        @with_retry(max_retries=1, backoff_base=0.01)
        async def fail_func() -> str:
            raise RetryableError("失败")

        with pytest.raises(FallbackExhaustedError, match="重试耗尽且无降级方案"):
            await fail_func()

    @pytest.mark.asyncio
    async def test_exhausted_error_preserves_cause(self) -> None:
        """FallbackExhaustedError 保留原始异常。"""
        original = RetryableError("原始错误")

        @with_retry(max_retries=0, backoff_base=0.01)
        async def fail_func() -> str:
            raise original

        with pytest.raises(FallbackExhaustedError) as exc_info:
            await fail_func()

        assert exc_info.value.cause is original


class TestWithRetryBackoff:
    """退避策略测试。"""

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self) -> None:
        """验证指数退避的等待时间。"""
        timestamps: list[float] = []

        @with_retry(max_retries=3, backoff_base=2.0)
        async def timed_func() -> str:
            timestamps.append(asyncio.get_event_loop().time())
            if len(timestamps) <= 3:
                raise RetryableError("重试中")
            return "done"

        result = await timed_func()
        assert result == "done"
        assert len(timestamps) == 4  # 首次 + 3 次重试

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self) -> None:
        """自定义可重试异常类型。"""

        class MyRetryable(RetryableError):
            pass

        call_count = 0

        @with_retry(
            max_retries=2,
            backoff_base=0.01,
            retryable_exceptions=MyRetryable,
            fallback=lambda: "fallback",
        )
        async def custom_retryable() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise MyRetryable("自定义重试")
            return "ok"

        result = await custom_retryable()
        assert result == "ok"
        assert call_count == 3


class TestWithRetryPreservesMetadata:
    """装饰器元数据保留测试。"""

    @pytest.mark.asyncio
    async def test_preserves_function_name(self) -> None:
        """装饰器保留原函数名。"""

        @with_retry()
        async def my_function() -> str:
            return "ok"

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_preserves_docstring(self) -> None:
        """装饰器保留原函数文档字符串。"""

        @with_retry()
        async def my_function() -> str:
            """这是我的函数。"""
            return "ok"

        assert my_function.__doc__ == "这是我的函数。"
