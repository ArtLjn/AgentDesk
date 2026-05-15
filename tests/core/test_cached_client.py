"""CachedLLMClient 缓存客户端测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.multi_agent_system.core.cache import reset_cache
from src.multi_agent_system.core.cached_client import CachedLLMClient


def _make_mock_response(content: str) -> MagicMock:
    """构造模拟的 OpenAI API 响应对象。"""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


def _mock_settings(**overrides: object) -> MagicMock:
    """创建统一的 mock Settings 实例。"""
    defaults = {
        "llm_api_key": "test-key",
        "llm_base_url": "http://localhost:11434",
        "llm_model": "test-model",
        "cache_enabled": True,
        "cache_max_size": 512,
        "cache_ttl": 300,
    }
    defaults.update(overrides)
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture(autouse=True)
def _reset_global_cache() -> None:
    """每个测试前后重置全局缓存单例。"""
    reset_cache()
    yield
    reset_cache()


class TestCachedLLMClientHit:
    """缓存命中测试。"""

    @pytest.mark.asyncio
    async def test_repeated_call_returns_cached_result(self) -> None:
        """相同输入的重复调用返回缓存结果，API 只调用一次。"""
        messages = [{"role": "user", "content": "hello"}]
        mock_response = _make_mock_response("world")
        settings = _mock_settings()

        with patch("src.multi_agent_system.config.Settings", return_value=settings):
            client = CachedLLMClient()

            # mock 底层 AsyncOpenAI
            mock_openai_client = AsyncMock()
            mock_openai_client.chat.completions.create.return_value = mock_response
            client._client = mock_openai_client

            # 第一次调用
            result1 = await client.chat_completions_create(messages=messages, temperature=0.7)
            # 第二次调用（应命中缓存）
            result2 = await client.chat_completions_create(messages=messages, temperature=0.7)

            assert result1 is result2
            # API 只应被调用一次
            mock_openai_client.chat.completions.create.assert_called_once()


class TestCachedLLMClientMiss:
    """缓存未命中测试。"""

    @pytest.mark.asyncio
    async def test_different_input_calls_api(self) -> None:
        """不同输入触发新的 API 调用。"""
        msg_a = [{"role": "user", "content": "hello"}]
        msg_b = [{"role": "user", "content": "world"}]
        resp_a = _make_mock_response("response-a")
        resp_b = _make_mock_response("response-b")
        settings = _mock_settings()

        with patch("src.multi_agent_system.config.Settings", return_value=settings):
            client = CachedLLMClient()
            mock_openai_client = AsyncMock()
            mock_openai_client.chat.completions.create.side_effect = [resp_a, resp_b]
            client._client = mock_openai_client

            result_a = await client.chat_completions_create(messages=msg_a, temperature=0.7)
            result_b = await client.chat_completions_create(messages=msg_b, temperature=0.7)

            assert result_a is resp_a
            assert result_b is resp_b
            assert mock_openai_client.chat.completions.create.call_count == 2


class TestCachedLLMClientCacheFalse:
    """cache=False 跳过缓存测试。"""

    @pytest.mark.asyncio
    async def test_cache_false_bypasses_cache(self) -> None:
        """cache=False 时每次都调用 API。"""
        messages = [{"role": "user", "content": "hello"}]
        resp1 = _make_mock_response("response-1")
        resp2 = _make_mock_response("response-2")
        settings = _mock_settings()

        with patch("src.multi_agent_system.config.Settings", return_value=settings):
            client = CachedLLMClient()
            mock_openai_client = AsyncMock()
            mock_openai_client.chat.completions.create.side_effect = [resp1, resp2]
            client._client = mock_openai_client

            result1 = await client.chat_completions_create(messages=messages, temperature=0.7, cache=False)
            result2 = await client.chat_completions_create(messages=messages, temperature=0.7, cache=False)

            assert result1 is resp1
            assert result2 is resp2
            assert mock_openai_client.chat.completions.create.call_count == 2


class TestCachedLLMClientDifferentParams:
    """不同参数产生不同缓存键测试。"""

    @pytest.mark.asyncio
    async def test_different_temperature_different_cache(self) -> None:
        """不同 temperature 产生不同缓存键。"""
        messages = [{"role": "user", "content": "hello"}]
        resp_a = _make_mock_response("low-temp")
        resp_b = _make_mock_response("high-temp")
        settings = _mock_settings()

        with patch("src.multi_agent_system.config.Settings", return_value=settings):
            client = CachedLLMClient()
            mock_openai_client = AsyncMock()
            mock_openai_client.chat.completions.create.side_effect = [resp_a, resp_b]
            client._client = mock_openai_client

            result_a = await client.chat_completions_create(messages=messages, temperature=0.1)
            result_b = await client.chat_completions_create(messages=messages, temperature=0.9)

            assert result_a is resp_a
            assert result_b is resp_b
            assert mock_openai_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_different_model_different_cache(self) -> None:
        """不同 model 参数产生不同缓存键。"""
        messages = [{"role": "user", "content": "hello"}]
        resp_a = _make_mock_response("model-a")
        resp_b = _make_mock_response("model-b")
        settings = _mock_settings()

        with patch("src.multi_agent_system.config.Settings", return_value=settings):
            client = CachedLLMClient()
            mock_openai_client = AsyncMock()
            mock_openai_client.chat.completions.create.side_effect = [resp_a, resp_b]
            client._client = mock_openai_client

            result_a = await client.chat_completions_create(messages=messages, model="model-a", temperature=0.7)
            result_b = await client.chat_completions_create(messages=messages, model="model-b", temperature=0.7)

            assert result_a is resp_a
            assert result_b is resp_b
            assert mock_openai_client.chat.completions.create.call_count == 2


class TestCachedLLMClientCacheDisabled:
    """全局缓存禁用测试。"""

    @pytest.mark.asyncio
    async def test_cache_disabled_always_calls_api(self) -> None:
        """全局缓存禁用时每次都调用 API。"""
        messages = [{"role": "user", "content": "hello"}]
        resp1 = _make_mock_response("response-1")
        resp2 = _make_mock_response("response-2")
        settings = _mock_settings(cache_enabled=False)

        with patch("src.multi_agent_system.config.Settings", return_value=settings):
            client = CachedLLMClient()
            mock_openai_client = AsyncMock()
            mock_openai_client.chat.completions.create.side_effect = [resp1, resp2]
            client._client = mock_openai_client

            result1 = await client.chat_completions_create(messages=messages, temperature=0.7)
            result2 = await client.chat_completions_create(messages=messages, temperature=0.7)

            assert result1 is resp1
            assert result2 is resp2
            assert mock_openai_client.chat.completions.create.call_count == 2
