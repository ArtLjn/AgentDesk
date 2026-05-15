"""统一异常层次定义。

提供可重试异常、不可重试异常和降级耗尽异常三个层次，
用于 retry/fallback 机制中的异常分类和传递。
"""

__all__ = ["RetryableError", "NonRetryableError", "FallbackExhaustedError"]


class RetryableError(Exception):
    """可重试异常：临时性错误，应触发重试。

    典型场景：网络超时、服务端 5xx 错误、连接池耗尽等。

    Args:
        message: 错误描述信息
        cause: 原始异常（可选），用于异常链追踪
    """

    def __init__(self, message: str = "", *, cause: Exception | None = None) -> None:
        self.cause = cause
        if cause and not message:
            message = str(cause)
        super().__init__(message)


class NonRetryableError(Exception):
    """不可重试异常：业务/参数错误，应跳过重试直接进入降级。

    典型场景：客户端 4xx 错误、JSON 解析失败、参数校验不通过等。

    Args:
        message: 错误描述信息
        cause: 原始异常（可选），用于异常链追踪
    """

    def __init__(self, message: str = "", *, cause: Exception | None = None) -> None:
        self.cause = cause
        if cause and not message:
            message = str(cause)
        super().__init__(message)


class FallbackExhaustedError(Exception):
    """降级耗尽异常：重试和降级均失败后的最终异常。

    当重试次数用尽且没有可用的降级方案（或降级方案全部失败）时抛出，
    表示系统已无法继续处理该请求。

    Args:
        message: 错误描述信息
        cause: 原始异常（可选），用于异常链追踪
    """

    def __init__(self, message: str = "", *, cause: Exception | None = None) -> None:
        self.cause = cause
        if cause and not message:
            message = str(cause)
        super().__init__(message)
