"""基于FAISS的向量存储，支持文档索引和相似度检索"""

import os
from typing import List, Optional, Tuple

import numpy as np
from loguru import logger


class VectorStore:
    """基于FAISS的向量存储，支持文档索引和相似度检索"""

    def __init__(self, embedding_dim: int = 1536):
        self.embedding_dim = embedding_dim
        self.documents: List[dict] = []  # 存储原始文档
        self.embeddings: Optional[np.ndarray] = None
        self._index = None

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本的embedding向量（使用OpenAI API或本地模型）

        Args:
            text: 待编码文本

        Returns:
            embedding向量列表
        """
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding API调用失败，使用随机向量: {e}")
            # 降级：使用简单的随机向量（仅用于测试）
            rng = np.random.RandomState(hash(text) % 2**31)
            return rng.randn(self.embedding_dim).tolist()

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """批量获取embedding

        Args:
            texts: 待编码文本列表

        Returns:
            embedding向量列表
        """
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.warning(f"批量Embedding失败，逐个降级: {e}")
            return [self._get_embedding(text) for text in texts]

    def add_documents(self, chunks: list) -> int:
        """添加文档到向量存储

        Args:
            chunks: Chunk对象列表

        Returns:
            添加的文档数量
        """
        if not chunks:
            return 0

        texts = [chunk.content for chunk in chunks]
        embeddings = self._get_embeddings_batch(texts)

        # 存储文档和向量
        for chunk, embedding in zip(chunks, embeddings):
            self.documents.append(
                {
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                    "doc_id": chunk.doc_id,
                    "chunk_index": chunk.chunk_index,
                }
            )

        # 更新FAISS索引
        new_embeddings = np.array(embeddings, dtype=np.float32)
        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])

        self._build_index()
        logger.info(f"添加 {len(chunks)} 个文档块，总计 {len(self.documents)} 个")
        return len(chunks)

    def _build_index(self):
        """构建FAISS索引"""
        try:
            import faiss

            self._index = faiss.IndexFlatIP(self.embedding_dim)
            # 归一化向量用于余弦相似度
            norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = self.embeddings / norms
            self._index.add(normalized)
        except ImportError:
            logger.warning("FAISS未安装，使用暴力搜索")
            self._index = None

    def search(self, query: str, top_k: int = 5) -> List[Tuple[dict, float]]:
        """相似度检索

        Args:
            query: 查询文本
            top_k: 返回前k个结果

        Returns:
            (文档, 分数) 列表
        """
        if not self.documents:
            return []

        query_embedding = np.array([self._get_embedding(query)], dtype=np.float32)

        if self._index is not None:
            # 归一化查询向量
            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                query_embedding = query_embedding / norm

            scores, indices = self._index.search(
                query_embedding, min(top_k, len(self.documents))
            )

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(self.documents):
                    results.append((self.documents[idx], float(score)))
            return results
        else:
            # 暴力搜索降级
            norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized = self.embeddings / norms
            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                query_embedding = query_embedding / norm

            scores = (normalized @ query_embedding.T).flatten()
            top_indices = np.argsort(scores)[::-1][:top_k]

            return [
                (self.documents[idx], float(scores[idx])) for idx in top_indices
            ]

    def clear(self):
        """清空存储"""
        self.documents = []
        self.embeddings = None
        self._index = None
        logger.info("向量存储已清空")

    @property
    def size(self) -> int:
        """当前存储的文档数量"""
        return len(self.documents)
