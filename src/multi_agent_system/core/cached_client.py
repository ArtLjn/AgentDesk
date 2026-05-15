"""带缓存的 OpenAI 客户端封装。

自动缓存 chat.completions 调用结果，减少重复 Token 消耗。
"""

from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from src.multi_agent_system.config import Settings

__all__ = ["CachedLLMClient"]


class CachedLLMClient:
    """带缓存的 OpenAI 客户端封装，自动缓存 chat.completions 调用结果。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = Settings()
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        """延迟初始化 OpenAI 异步客户端。"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    async def chat_completions_create(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        cache: bool = True,
        task_type: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """调用 chat.completions.create，支持缓存和模型路由。

        Args:
            messages: 消息列表
            model: 模型名称（手动指定时优先级最高）
            temperature: 温度参数
            cache: 是否使用缓存（默认 True），设置为 False 跳过缓存
            task_type: 任务类型（如 classify/process/review/report），用于模型路由
            **kwargs: 其他传递给 API 的参数
        """
        from src.multi_agent_system.core.cache import _get_llm_cache

        # 模型选择优先级：手动指定 > task_type 路由 > 默认模型
        if model is not None:
            use_model = model
        elif task_type is not None:
            from src.multi_agent_system.core.model_router import get_model_router

            use_model = get_model_router().get_model(task_type)
        else:
            use_model = self.model
        llm_cache = _get_llm_cache()

        # 缓存未启用或显式禁用缓存，直接调用
        if llm_cache is None or not cache:
            logger.debug(f"[CachedLLMClient] 跳过缓存，直接调用 {use_model}")
            return await self.client.chat.completions.create(
                model=use_model,
                messages=messages,
                temperature=temperature,
                **kwargs,
            )

        # 生成缓存键
        cache_key = llm_cache._generate_key(
            model=use_model,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )

        # 尝试从缓存获取
        cached_result = llm_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"[CachedLLMClient] 缓存命中 {use_model}")
            return cached_result

        # 缓存未命中，调用 API
        logger.debug(f"[CachedLLMClient] 缓存未命中，调用 {use_model}")
        result = await self.client.chat.completions.create(
            model=use_model,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )

        # 缓存结果
        llm_cache.set(cache_key, result)
        return result
