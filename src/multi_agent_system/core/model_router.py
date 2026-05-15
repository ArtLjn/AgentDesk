"""模型路由器：根据任务类型选择合适的 LLM 模型。

按任务复杂度分级路由：
- 低复杂度（classify）→ 轻量模型（如 qwen3:4b）
- 中复杂度（process/review）→ 标准模型（如 qwen3:8b）
- 高复杂度（report）→ 强模型（如 qwen3:14b）
"""

from typing import Any

from loguru import logger

__all__ = ["ModelRouter", "get_model_router", "reset_model_router"]


class ModelRouter:
    """模型路由器，根据任务类型选择合适的模型。"""

    def __init__(self, routes: dict[str, str], fallback_model: str) -> None:
        self.routes = routes
        self.fallback_model = fallback_model

    def get_model(self, task_type: str) -> str:
        """根据任务类型获取模型名称。

        Args:
            task_type: 任务类型，如 classify、process、review、report

        Returns:
            对应的模型名称，未匹配时返回降级模型
        """
        model = self.routes.get(task_type.lower())
        if model is None:
            logger.warning(
                f"[ModelRouter] 未知任务类型 {task_type}，"
                f"使用降级模型 {self.fallback_model}"
            )
            return self.fallback_model

        logger.debug(f"[ModelRouter] 任务 {task_type} 路由到模型 {model}")
        return model

    def get_stats(self) -> dict[str, Any]:
        """获取路由配置统计。"""
        return {
            "routes": dict(self.routes),
            "fallback_model": self.fallback_model,
        }


# 全局单例（延迟初始化）
_model_router_instance: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """获取全局模型路由器实例。"""
    global _model_router_instance
    if _model_router_instance is None:
        from src.multi_agent_system.config import Settings

        settings = Settings()
        _model_router_instance = ModelRouter(
            routes=settings.model_routes,
            fallback_model=settings.fallback_model,
        )
    return _model_router_instance


def reset_model_router() -> None:
    """重置模型路由器实例（用于测试）。"""
    global _model_router_instance
    _model_router_instance = None
