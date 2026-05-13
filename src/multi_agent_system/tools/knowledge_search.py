"""知识库向量检索工具，基于 Qdrant + Ollama Embedding 实现语义搜索。"""

import uuid
from typing import Any

import requests
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.multi_agent_system.config import Settings

__all__ = ["KnowledgeSearchTool"]

# 文档分块参数
_CHUNK_SIZE = 512
_CHUNK_OVERLAP = 64


class KnowledgeSearchTool:
    """知识库向量检索工具。

    通过 Ollama API 获取文本 embedding，使用 Qdrant 进行向量存储和检索，
    为工单处理提供知识库匹配能力。

    Args:
        qdrant_url: Qdrant 服务地址
        collection_name: Qdrant collection 名称
        ollama_base_url: Ollama 服务地址
        embedding_model: Embedding 模型名称
        embedding_dim: Embedding 向量维度
    """

    def __init__(
        self,
        qdrant_url: str,
        collection_name: str,
        ollama_base_url: str,
        embedding_model: str,
        embedding_dim: int,
    ) -> None:
        self._client = QdrantClient(url=qdrant_url)
        self._collection_name = collection_name
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim

    def ensure_collection(self) -> None:
        """确保 Qdrant collection 存在，不存在则创建。"""
        collections = self._client.get_collections().collections
        names = [c.name for c in collections]

        if self._collection_name not in names:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"已创建 Qdrant collection: {self._collection_name}")
        else:
            logger.debug(f"Qdrant collection 已存在: {self._collection_name}")

    def _get_embedding(self, text: str) -> list[float]:
        """调用 Ollama API 获取文本 embedding。

        Args:
            text: 需要编码的文本

        Returns:
            embedding 向量列表

        Raises:
            RuntimeError: API 调用失败时抛出
        """
        url = f"{self._ollama_base_url}/api/embeddings"
        payload = {"model": self._embedding_model, "prompt": text}

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["embedding"]

    def _split_chunks(self, text: str) -> list[str]:
        """将文本按固定大小分块，带重叠。

        Args:
            text: 原始文本

        Returns:
            文本块列表
        """
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + _CHUNK_SIZE
            chunks.append(text[start:end])
            start += _CHUNK_SIZE - _CHUNK_OVERLAP
        return chunks

    def add_documents(self, documents: list[dict]) -> int:
        """批量添加文档到知识库。

        将每篇文档按分块策略切分，获取 embedding 后 upsert 到 Qdrant。

        Args:
            documents: 文档列表，每个文档需包含 "content" 字段，
                       可选 "id"、"title"、"category"、"source" 等元数据

        Returns:
            成功添加的文档块数量
        """
        self.ensure_collection()
        points: list[PointStruct] = []
        total_chunks = 0

        for doc in documents:
            doc_id = doc.get("id", str(uuid.uuid4()))
            content = doc.get("content", "")
            metadata = {
                "title": doc.get("title", ""),
                "category": doc.get("category", ""),
                "source": doc.get("source", ""),
                "document_id": doc_id,
            }

            # 文档分块
            chunks = self._split_chunks(content)
            for idx, chunk in enumerate(chunks):
                embedding = self._get_embedding(chunk)
                point_id = str(uuid.uuid4())

                point_metadata = {**metadata, "chunk_index": idx}
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "content": chunk,
                            **point_metadata,
                        },
                    )
                )
                total_chunks += 1

            logger.debug(f"文档 {doc_id} 分为 {len(chunks)} 块")

        if points:
            # 分批 upsert，每批最多 100 个点
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                self._client.upsert(
                    collection_name=self._collection_name,
                    points=batch,
                )

        logger.info(f"已添加 {len(documents)} 篇文档，共 {total_chunks} 个块")
        return total_chunks

    def search(
        self,
        query: str,
        top_k: int = 3,
        score_threshold: float = 0.5,
    ) -> list[dict]:
        """检索与查询相关的文档块。

        Args:
            query: 查询文本
            top_k: 返回最相关的 K 个结果
            score_threshold: 相似度阈值，低于此值的结果会被过滤

        Returns:
            匹配结果列表，每项包含 content、score、metadata
        """
        self.ensure_collection()
        query_vector = self._get_embedding(query)

        results = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
        )

        matched: list[dict[str, Any]] = []
        for hit in results:
            payload = hit.payload or {}
            matched.append(
                {
                    "content": payload.get("content", ""),
                    "score": hit.score,
                    "metadata": {
                        k: v for k, v in payload.items() if k not in ("content",)
                    },
                }
            )

        logger.info(f"查询匹配到 {len(matched)} 条结果")
        return matched

    @staticmethod
    def create_from_settings() -> "KnowledgeSearchTool":
        """从 Settings 配置创建 KnowledgeSearchTool 实例。

        Returns:
            配置好的 KnowledgeSearchTool 实例
        """
        settings = Settings()
        return KnowledgeSearchTool(
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            ollama_base_url=settings.ollama_base_url,
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
        )
