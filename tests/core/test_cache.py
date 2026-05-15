"""LLMCache 缓存层测试。"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.multi_agent_system.core.cache import LLMCache, _get_llm_cache, reset_cache


class TestLLMCache:
    """LLMCache 核心功能测试。"""

    def setup_method(self) -> None:
        """每个测试方法前创建全新的缓存实例。"""
        self.cache = LLMCache(max_size=10, ttl=5)

    def test_set_and_get_returns_cached_value(self) -> None:
        """缓存命中：相同 key 返回已缓存的值。"""
        self.cache.set("key1", "value1")
        result = self.cache.get("key1")
        assert result == "value1"

    def test_get_missing_key_returns_none(self) -> None:
        """缓存未命中：不存在的 key 返回 None。"""
        result = self.cache.get("nonexistent")
        assert result is None

    def test_different_keys_are_independent(self) -> None:
        """不同 key 的缓存互不影响。"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        assert self.cache.get("key1") == "value1"
        assert self.cache.get("key2") == "value2"

    def test_ttl_expiration_returns_none(self) -> None:
        """TTL 过期后缓存返回 None。"""
        self.cache.set("key1", "value1", ttl=0)
        # ttl=0 已过期
        result = self.cache.get("key1")
        assert result is None

    def test_ttl_expiration_after_delay(self) -> None:
        """TTL 在短时间后过期。"""
        self.cache.set("key1", "value1", ttl=1)
        assert self.cache.get("key1") == "value1"
        time.sleep(1.1)
        result = self.cache.get("key1")
        assert result is None

    def test_overwrite_existing_key(self) -> None:
        """覆盖已有 key 的缓存值。"""
        self.cache.set("key1", "value1")
        self.cache.set("key1", "value2")
        assert self.cache.get("key1") == "value2"

    def test_lru_eviction_when_full(self) -> None:
        """缓存满时淘汰最久未使用的条目。"""
        cache = LLMCache(max_size=3, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # 插入第 4 个，应淘汰 "a"
        cache.set("d", 4)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4


class TestLLMCacheGenerateKey:
    """缓存键生成测试。"""

    def setup_method(self) -> None:
        self.cache = LLMCache()

    def test_same_inputs_same_key(self) -> None:
        """相同输入生成相同的缓存键。"""
        messages = [{"role": "user", "content": "hello"}]
        key1 = self.cache._generate_key("model-a", messages, 0.7)
        key2 = self.cache._generate_key("model-a", messages, 0.7)
        assert key1 == key2

    def test_different_model_different_key(self) -> None:
        """不同模型生成不同的缓存键。"""
        messages = [{"role": "user", "content": "hello"}]
        key1 = self.cache._generate_key("model-a", messages, 0.7)
        key2 = self.cache._generate_key("model-b", messages, 0.7)
        assert key1 != key2

    def test_different_temperature_different_key(self) -> None:
        """不同温度生成不同的缓存键。"""
        messages = [{"role": "user", "content": "hello"}]
        key1 = self.cache._generate_key("model-a", messages, 0.7)
        key2 = self.cache._generate_key("model-a", messages, 0.3)
        assert key1 != key2

    def test_different_messages_different_key(self) -> None:
        """不同消息内容生成不同的缓存键。"""
        msg_a = [{"role": "user", "content": "hello"}]
        msg_b = [{"role": "user", "content": "world"}]
        key1 = self.cache._generate_key("model-a", msg_a, 0.7)
        key2 = self.cache._generate_key("model-a", msg_b, 0.7)
        assert key1 != key2

    def test_extra_kwargs_affect_key(self) -> None:
        """额外的 kwargs 影响缓存键。"""
        messages = [{"role": "user", "content": "hello"}]
        key1 = self.cache._generate_key("model-a", messages, 0.7)
        key2 = self.cache._generate_key("model-a", messages, 0.7, response_format={"type": "json_object"})
        assert key1 != key2


class TestLLMCacheStats:
    """缓存统计测试。"""

    def setup_method(self) -> None:
        self.cache = LLMCache(max_size=10, ttl=5)

    def test_hit_rate_zero_when_empty(self) -> None:
        """无访问时命中率为 0。"""
        assert self.cache.hit_rate == 0.0

    def test_hit_rate_all_misses(self) -> None:
        """全部未命中时命中率为 0。"""
        self.cache.get("nonexistent")
        assert self.cache.hit_rate == 0.0

    def test_hit_rate_all_hits(self) -> None:
        """全部命中时命中率为 1。"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.get("key1")
        assert self.cache.hit_rate == 1.0

    def test_hit_rate_mixed(self) -> None:
        """混合命中/未命中的命中率计算。"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")    # hit
        self.cache.get("key1")    # hit
        self.cache.get("miss")    # miss
        # 2 hits, 1 miss = 2/3
        assert abs(self.cache.hit_rate - 2 / 3) < 0.01

    def test_get_stats_returns_correct_fields(self) -> None:
        """get_stats 返回正确的字段。"""
        self.cache.set("key1", "value1")
        stats = self.cache.get_stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 10
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["ttl"] == 5

    def test_get_stats_after_operations(self) -> None:
        """操作后统计数据正确更新。"""
        self.cache.set("key1", "value1")
        self.cache.get("key1")    # hit
        self.cache.get("miss")    # miss
        stats = self.cache.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestLLMCacheClear:
    """缓存清理测试。"""

    def test_clear_resets_cache_and_stats(self) -> None:
        """clear() 清空缓存并重置统计。"""
        cache = LLMCache(max_size=10, ttl=5)
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("miss")

        cache.clear()

        # clear 后 hits/misses 已重置，再 get 会产生新的 miss
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.get("key1") is None


class TestGlobalCache:
    """全局缓存单例测试。"""

    def teardown_method(self) -> None:
        """每个测试方法后重置全局缓存。"""
        reset_cache()

    @patch("src.multi_agent_system.config.Settings")
    def test_get_llm_cache_enabled(self, mock_settings_cls: MagicMock) -> None:
        """缓存启用时返回 LLMCache 实例。"""
        mock_settings = MagicMock()
        mock_settings.cache_enabled = True
        mock_settings.cache_max_size = 256
        mock_settings.cache_ttl = 120
        mock_settings_cls.return_value = mock_settings

        cache = _get_llm_cache()
        assert cache is not None
        assert isinstance(cache, LLMCache)
        assert cache.ttl == 120

    @patch("src.multi_agent_system.config.Settings")
    def test_get_llm_cache_disabled(self, mock_settings_cls: MagicMock) -> None:
        """缓存禁用时返回 None。"""
        mock_settings = MagicMock()
        mock_settings.cache_enabled = False
        mock_settings_cls.return_value = mock_settings

        cache = _get_llm_cache()
        assert cache is None

    @patch("src.multi_agent_system.config.Settings")
    def test_reset_cache_clears_singleton(self, mock_settings_cls: MagicMock) -> None:
        """reset_cache() 重置全局单例。"""
        mock_settings = MagicMock()
        mock_settings.cache_enabled = True
        mock_settings.cache_max_size = 512
        mock_settings.cache_ttl = 300
        mock_settings_cls.return_value = mock_settings

        _get_llm_cache()
        reset_cache()
        # 重置后再次获取会创建新实例
        cache = _get_llm_cache()
        assert cache is not None
