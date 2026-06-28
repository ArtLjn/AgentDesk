"""知识库向量检索工具，基于 Qdrant + Ollama Embedding 实现语义搜索。"""

import uuid
from typing import Any

import requests
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.multi_agent_system.config import Settings

__all__ = ["KnowledgeSearchTool"]

# 文档分块参数（默认值，可被 config.yaml 覆盖）
_settings = Settings()
_CHUNK_SIZE = _settings.chunk_size
_CHUNK_OVERLAP = _settings.chunk_overlap


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
        embedding_base_url: str,
        embedding_model: str,
        embedding_dim: int,
        qdrant_api_key: str = "",
        embedding_api_key: str = "",
    ) -> None:
        client_kwargs: dict[str, Any] = {
            "url": qdrant_url,
            "check_compatibility": False,
            # 不读系统代理：Qdrant 通常部署在同机房/公网直连，HTTP 代理反而会干扰 TLS 握手
            "trust_env": False,
        }
        if qdrant_api_key:
            client_kwargs["api_key"] = qdrant_api_key
        self._client = QdrantClient(**client_kwargs)
        self._collection_name = collection_name
        self._embedding_base_url = embedding_base_url.rstrip("/")
        self._embedding_model = embedding_model
        self._embedding_dim = embedding_dim
        self._embedding_api_key = embedding_api_key

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
        """调用 Google Gemini API 获取文本 embedding。

        Args:
            text: 需要编码的文本

        Returns:
            embedding 向量列表

        Raises:
            RuntimeError: API 调用失败时抛出
        """
        url = f"{self._embedding_base_url}/models/{self._embedding_model}:embedContent"
        headers = {"x-goog-api-key": self._embedding_api_key}
        payload = {
            "model": f"models/{self._embedding_model}",
            "content": {"parts": [{"text": text}]},
        }

        logger.debug(f"🔢 [Embedding] 调用模型: {self._embedding_model}, 服务: {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=_settings.http_timeout)
        response.raise_for_status()
        embedding = response.json()["embedding"]["values"]
        logger.debug(f"🔢 [Embedding] 成功生成向量，维度: {len(embedding)}")
        return embedding

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
            # 分批 upsert
            batch_size = _settings.qdrant_batch_size
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
        try:
            query_vector = self._get_embedding(query)
        except Exception as e:
            logger.warning(f"向量检索前生成 embedding 失败，改用关键词兜底检索: {e}")
            return self._keyword_search_fallback(query, top_k=top_k)

        if hasattr(self._client, "query_points"):
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
            results = response.points
        else:
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

    def _keyword_search_fallback(self, query: str, top_k: int = 3) -> list[dict]:
        """embedding 不可用时从 Qdrant payload 做轻量关键词兜底检索。"""
        records, _ = self._client.scroll(
            collection_name=self._collection_name,
            limit=max(100, top_k * 20),
            with_payload=True,
            with_vectors=False,
        )
        query_terms = self._extract_query_terms(query)
        matched: list[dict[str, Any]] = []
        for record in records:
            payload = record.payload or {}
            text = f"{payload.get('title', '')} {payload.get('category', '')} {payload.get('content', '')}"
            score = self._keyword_score(query_terms, text)
            if score <= 0:
                continue
            matched.append({
                "content": payload.get("content", ""),
                "score": score,
                "metadata": {
                    k: v for k, v in payload.items() if k not in ("content",)
                },
            })

        matched.sort(key=lambda item: item["score"], reverse=True)
        logger.info(f"关键词兜底检索匹配到 {len(matched[:top_k])} 条结果")
        return matched[:top_k]

    def _extract_query_terms(self, query: str) -> list[str]:
        """基于字符 n-gram 提取通用中文短查询检索特征。"""
        normalized = "".join(ch for ch in query if not ch.isspace())
        terms: list[str] = [normalized] if len(normalized) >= 2 else []
        for size in (4, 3, 2):
            for start in range(0, max(0, len(normalized) - size + 1)):
                terms.append(normalized[start:start + size])
        return list(dict.fromkeys(terms))

    def _keyword_score(self, terms: list[str], text: str) -> float:
        """根据 n-gram 命中强度计算 0~1 的兜底相关度。"""
        if not terms:
            return 0.0
        weighted_hits = sum(len(term) for term in terms if term and term in text)
        total_weight = sum(len(term) for term in terms)
        if weighted_hits == 0 or total_weight == 0:
            return 0.0
        return min(1.0, weighted_hits / total_weight)

    def list_documents(
        self,
        limit: int = 50,
        offset: int | str | None = None,
    ) -> dict[str, Any]:
        """按文档维度列出知识库内容。

        Qdrant 中实际保存的是分块 point，这里根据 document_id 聚合，
        供管理页面查看已上传文档和完整内容。
        """
        self.ensure_collection()
        records, next_offset = self._client.scroll(
            collection_name=self._collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        grouped: dict[str, dict[str, Any]] = {}
        for record in records:
            payload = record.payload or {}
            doc_id = str(payload.get("document_id") or record.id)
            doc = grouped.setdefault(
                doc_id,
                {
                    "id": doc_id,
                    "title": payload.get("title") or "未命名文档",
                    "category": payload.get("category") or "未分类",
                    "source": payload.get("source") or "",
                    "chunk_count": 0,
                    "_chunks": [],
                },
            )
            doc["chunk_count"] += 1
            doc["_chunks"].append(
                {
                    "index": payload.get("chunk_index", 0),
                    "content": payload.get("content", ""),
                    "point_id": str(record.id),
                }
            )

        documents: list[dict[str, Any]] = []
        for doc in grouped.values():
            chunks = sorted(doc.pop("_chunks"), key=lambda item: item["index"])
            content = "\n".join(chunk["content"] for chunk in chunks if chunk["content"])
            doc["content"] = content
            doc["preview"] = content[:180]
            doc["chunks"] = chunks
            documents.append(doc)

        documents.sort(key=lambda item: item["title"])
        return {
            "documents": documents,
            "count": len(documents),
            "next_offset": str(next_offset) if next_offset is not None else None,
        }

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
            embedding_base_url=settings.embedding_base_url,
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
            qdrant_api_key=settings.qdrant_api_key,
            embedding_api_key=settings.embedding_api_key,
        )
