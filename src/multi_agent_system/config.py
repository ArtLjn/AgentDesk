"""全局配置模块，基于 Pydantic Settings 从环境变量和 .env 文件加载配置。"""

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings"]


class Settings(BaseSettings):
    """多 Agent 工单处理系统统一配置。

    所有字段均可通过同名环境变量或 .env 文件覆盖。
    """

    # LLM (Chat) & Embedding 都用 HomeUbuntu 本地 Ollama
    llm_base_url: str = "http://172.16.58.68:11434"
    llm_api_key: str = "ollama"
    embedding_base_url: str = "http://172.16.58.68:11434"

    # Qdrant 向量数据库配置
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "knowledge_base"

    # LLM 模型配置
    llm_model: str = "qwen3:8b"
    embedding_model: str = "qwen3-embedding:4b"
    embedding_dim: int = 2560

    # 缓存配置
    cache_enabled: bool = True
    cache_max_size: int = 512
    cache_ttl: int = 300  # 秒

    # 处理策略
    max_retries: int = 3
    review_threshold: float = 0.7

    # 并发配置
    max_concurrency: int = 5

    # 模型路由配置
    model_routes: dict[str, str] = {
        "classify": "qwen3:4b",
        "process": "qwen3:8b",
        "review": "qwen3:8b",
        "report": "qwen3:14b",
        "default": "qwen3:8b",
    }
    fallback_model: str = "qwen3:8b"

    # API 服务配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
