"""ModelRouter 单元测试。"""

from unittest.mock import MagicMock, patch

import pytest

from src.multi_agent_system.core.model_router import (
    ModelRouter,
    get_model_router,
    reset_model_router,
)

# 默认路由配置（与 Settings 默认值一致）
DEFAULT_ROUTES = {
    "classify": "qwen3:4b",
    "process": "qwen3:8b",
    "review": "qwen3:8b",
    "report": "qwen3:14b",
    "default": "qwen3:8b",
}
DEFAULT_FALLBACK = "qwen3:8b"


@pytest.fixture(autouse=True)
def _reset_singleton():
    """每个测试前后重置全局单例，避免测试间互相影响。"""
    reset_model_router()
    yield
    reset_model_router()


class TestModelRouterGetModel:
    """测试 ModelRouter.get_model 方法。"""

    def test_classify_route(self):
        """classify 任务路由到 qwen3:4b。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        assert router.get_model("classify") == "qwen3:4b"

    def test_process_route(self):
        """process 任务路由到 qwen3:8b。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        assert router.get_model("process") == "qwen3:8b"

    def test_review_route(self):
        """review 任务路由到 qwen3:8b。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        assert router.get_model("review") == "qwen3:8b"

    def test_report_route(self):
        """report 任务路由到 qwen3:14b。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        assert router.get_model("report") == "qwen3:14b"

    def test_unknown_task_type_returns_fallback(self):
        """未知任务类型返回降级模型。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        assert router.get_model("unknown_task") == DEFAULT_FALLBACK

    def test_case_insensitive(self):
        """任务类型大小写不敏感。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        assert router.get_model("CLASSIFY") == "qwen3:4b"
        assert router.get_model("Classify") == "qwen3:4b"
        assert router.get_model("REPORT") == "qwen3:14b"

    def test_custom_routes(self):
        """自定义路由配置正常工作。"""
        custom_routes = {
            "simple": "tiny-model",
            "complex": "big-model",
        }
        router = ModelRouter(routes=custom_routes, fallback_model="medium-model")
        assert router.get_model("simple") == "tiny-model"
        assert router.get_model("complex") == "big-model"
        assert router.get_model("nonexistent") == "medium-model"


class TestModelRouterGetStats:
    """测试 ModelRouter.get_stats 方法。"""

    def test_get_stats_returns_correct_info(self):
        """get_stats 返回正确的路由配置信息。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        stats = router.get_stats()

        assert stats["routes"] == DEFAULT_ROUTES
        assert stats["fallback_model"] == DEFAULT_FALLBACK

    def test_get_stats_returns_copy(self):
        """get_stats 返回的是路由表的副本，修改不影响原始数据。"""
        router = ModelRouter(routes=DEFAULT_ROUTES, fallback_model=DEFAULT_FALLBACK)
        stats = router.get_stats()
        stats["routes"]["classify"] = "modified"

        assert router.routes["classify"] == "qwen3:4b"


class TestGlobalSingleton:
    """测试全局单例函数。"""

    def test_reset_clears_singleton(self):
        """reset_model_router 重置单例后，下次获取会创建新实例。"""
        router1 = get_model_router()
        reset_model_router()
        router2 = get_model_router()

        assert router1 is not router2

    def test_get_model_router_returns_same_instance(self):
        """多次调用 get_model_router 返回同一实例。"""
        router1 = get_model_router()
        router2 = get_model_router()

        assert router1 is router2

    @patch("src.multi_agent_system.config.Settings")
    def test_get_model_router_creates_from_settings(self, mock_settings_cls):
        """get_model_router 从 Settings 创建实例并使用正确的配置。"""
        mock_settings = MagicMock()
        mock_settings.model_routes = {"test": "test-model"}
        mock_settings.fallback_model = "fallback-test"
        mock_settings_cls.return_value = mock_settings

        reset_model_router()
        router = get_model_router()

        assert router.routes == {"test": "test-model"}
        assert router.fallback_model == "fallback-test"
