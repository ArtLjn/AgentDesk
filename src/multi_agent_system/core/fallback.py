"""降级注册表：管理多级降级链。

提供 FallbackRegistry 类，支持按名称注册多个降级函数，
按优先级依次执行，返回首个成功结果。
"""

import asyncio
from typing import Any, Callable

from loguru import logger

__all__ = ["FallbackRegistry"]

# 降级结果中的固定标记字段
_FALLBACK_MARKER = "fallback"


class FallbackRegistry:
    """降级注册表：按名称管理多级降级函数链。

    支持为同一个名称注册多个降级函数（多级降级链），
    执行时按注册顺序依次尝试，返回首个成功结果。
    降级函数可以是同步或异步函数。

    所有的降级返回结果会自动附加 ``"fallback": True`` 字段。
    """

    def __init__(self) -> None:
        self._registry: dict[str, list[Callable[..., Any]]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """注册降级函数。

        同一个名称可以注册多个降级函数，按注册顺序组成降级链。

        Args:
            name: 降级名称（通常对应被降级的函数/服务名）
            fn: 降级函数（同步或异步）
        """
        if name not in self._registry:
            self._registry[name] = []
        self._registry[name].append(fn)
        logger.debug(f"[FallbackRegistry] 注册降级函数: {name} -> {fn.__name__}")

    def get(self, name: str) -> list[Callable[..., Any]]:
        """获取指定名称的降级函数列表。

        Args:
            name: 降级名称

        Returns:
            降级函数列表，按注册顺序排列；未注册时返回空列表
        """
        return self._registry.get(name, [])

    async def execute(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """执行降级链，依次尝试每个降级函数直到成功。

        Args:
            name: 降级名称
            *args: 传递给降级函数的位置参数
            **kwargs: 传递给降级函数的关键字参数

        Returns:
            首个成功的降级函数返回值（自动附加 ``"fallback": True``），
            如果所有降级函数均失败或无注册，返回通用错误字典
        """
        fallbacks = self.get(name)

        if not fallbacks:
            logger.warning(f"[FallbackRegistry] 无降级函数: {name}")
            return {"error": "no fallback available", _FALLBACK_MARKER: True}

        for i, fn in enumerate(fallbacks):
            try:
                result = fn(*args, **kwargs)
                # 支持异步降级函数
                if asyncio.iscoroutine(result):
                    result = await result
                # 如果结果是字典，附加 fallback 标记
                if isinstance(result, dict):
                    result[_FALLBACK_MARKER] = True
                return result
            except Exception as e:
                logger.warning(
                    f"[FallbackRegistry] 降级函数 {fn.__name__} "
                    f"（{name} 第 {i + 1}/{len(fallbacks)} 级）失败: {e}"
                )
                continue

        # 所有降级函数均失败
        logger.error(f"[FallbackRegistry] 所有降级函数均失败: {name}")
        return {"error": "no fallback available", _FALLBACK_MARKER: True}
