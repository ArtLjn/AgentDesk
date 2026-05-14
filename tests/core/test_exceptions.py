"""exceptions 模块单元测试。"""

import pytest

from src.multi_agent_system.core.exceptions import (
    FallbackExhaustedError,
    NonRetryableError,
    RetryableError,
)


class TestRetryableError:
    """可重试异常测试。"""

    def test_default_message_is_empty(self) -> None:
        err = RetryableError()
        assert str(err) == ""

    def test_custom_message(self) -> None:
        err = RetryableError("网络超时")
        assert str(err) == "网络超时"

    def test_cause_chaining(self) -> None:
        original = TimeoutError("connection timeout")
        err = RetryableError(cause=original)
        assert err.cause is original
        assert str(err) == "connection timeout"

    def test_custom_message_with_cause(self) -> None:
        original = ConnectionError("refused")
        err = RetryableError("服务不可用", cause=original)
        assert err.cause is original
        assert str(err) == "服务不可用"

    def test_is_exception(self) -> None:
        assert issubclass(RetryableError, Exception)

    def test_raise_and_catch(self) -> None:
        with pytest.raises(RetryableError, match="超时"):
            raise RetryableError("超时")


class TestNonRetryableError:
    """不可重试异常测试。"""

    def test_default_message_is_empty(self) -> None:
        err = NonRetryableError()
        assert str(err) == ""

    def test_custom_message(self) -> None:
        err = NonRetryableError("参数校验失败")
        assert str(err) == "参数校验失败"

    def test_cause_chaining(self) -> None:
        original = ValueError("invalid json")
        err = NonRetryableError(cause=original)
        assert err.cause is original
        assert str(err) == "invalid json"

    def test_custom_message_with_cause(self) -> None:
        original = TypeError("wrong type")
        err = NonRetryableError("类型错误", cause=original)
        assert err.cause is original
        assert str(err) == "类型错误"

    def test_is_exception(self) -> None:
        assert issubclass(NonRetryableError, Exception)

    def test_not_retryable_distinct_from_retryable(self) -> None:
        """不可重试异常与可重试异常是独立类型。"""
        assert not issubclass(NonRetryableError, RetryableError)
        assert not issubclass(RetryableError, NonRetryableError)


class TestFallbackExhaustedError:
    """降级耗尽异常测试。"""

    def test_default_message_is_empty(self) -> None:
        err = FallbackExhaustedError()
        assert str(err) == ""

    def test_custom_message(self) -> None:
        err = FallbackExhaustedError("所有降级方案已耗尽")
        assert str(err) == "所有降级方案已耗尽"

    def test_cause_chaining(self) -> None:
        original = RuntimeError("service down")
        err = FallbackExhaustedError(cause=original)
        assert err.cause is original
        assert str(err) == "service down"

    def test_custom_message_with_cause(self) -> None:
        original = RuntimeError("service down")
        err = FallbackExhaustedError("降级失败", cause=original)
        assert err.cause is original
        assert str(err) == "降级失败"

    def test_is_exception(self) -> None:
        assert issubclass(FallbackExhaustedError, Exception)

    def test_distinct_from_others(self) -> None:
        """降级耗尽异常独立于其他两种异常。"""
        assert not issubclass(FallbackExhaustedError, RetryableError)
        assert not issubclass(FallbackExhaustedError, NonRetryableError)
