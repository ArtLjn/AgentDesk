"""LLM 调用结果缓存，基于 LRU 算法，支持 TTL 过期。

对相同输入（model + messages hash + temperature）的 LLM 调用结果进行缓存，
减少重复调用，降低 Token 成本。
"""

import hashlib
import json
import time
from typing import Any

from cachetools import LRUCache
from loguru import logger

__all__ = ["LLMCache", "llm_cache"]


class LLMCache:
    """LLM 调用结果缓存，基于 LRU 算法，支持 TTL 过期。"""

    def __init__(self, max_size: int = 512, ttl: int = 300) -> None:
        self.cache: LRUCache = LRUCache(maxsize=max_size)
        self.ttl = ttl
        self.hits = 0
        self.misses = 0

    def _generate_key(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """生成缓存键：对模型名称、消息内容、温度等参数做哈希。"""
        cache_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }
        serialized = json.dumps(cache_params, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def get(self, key: str) -> Any | None:
        """获取缓存，过期返回 None。"""
        entry = self.cache.get(key)
        if entry is None:
            self.misses += 1
            return None

        value, expire_at = entry
        if time.time() > expire_at:
            del self.cache[key]
            self.misses += 1
            return None

        self.hits += 1
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存，ttl 默认使用初始化参数。"""
        if ttl is None:
            ttl = self.ttl
        expire_at = time.time() + ttl
        self.cache[key] = (value, expire_at)

    def clear(self) -> None:
        """清空缓存。"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """缓存命中率。"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息。"""
        return {
            "size": len(self.cache),
            "max_size": self.cache.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "ttl": self.ttl,
        }


# 全局单例（延迟初始化）
_llm_cache_instance: LLMCache | None = None


def _get_llm_cache() -> LLMCache | None:
    """获取全局缓存实例，根据配置决定是否启用。"""
    global _llm_cache_instance
    if _llm_cache_instance is None:
        from src.multi_agent_system.config import Settings

        settings = Settings()
        if settings.cache_enabled:
            _llm_cache_instance = LLMCache(
                max_size=settings.cache_max_size,
                ttl=settings.cache_ttl,
            )
            logger.info(f"[LLMCache] 缓存已启用，max_size={settings.cache_max_size}, ttl={settings.cache_ttl}s")
        else:
            logger.info("[LLMCache] 缓存已禁用")
    return _llm_cache_instance


def reset_cache() -> None:
    """重置缓存实例（用于测试）。"""
    global _llm_cache_instance
    _llm_cache_instance = None


# 兼容属性访问
class _LLMCacheProxy:
    """延迟代理，首次访问时才初始化真正的缓存实例。"""

    def __getattr__(self, name: str) -> Any:
        cache = _get_llm_cache()
        if cache is None:
            return None
        return getattr(cache, name)

    def __bool__(self) -> bool:
        return _get_llm_cache() is not None


llm_cache = _LLMCacheProxy()
