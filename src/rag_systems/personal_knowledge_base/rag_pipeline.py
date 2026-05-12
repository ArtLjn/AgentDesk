"""RAG检索增强生成Pipeline

完整流程：文档处理 -> 向量存储 -> 检索 -> 生成
"""

import os
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

from src.rag_systems.personal_knowledge_base.document_processor import (
    Chunk,
    DocumentProcessor,
)
from src.rag_systems.personal_knowledge_base.vector_store import VectorStore

load_dotenv()


class RAGPipeline:
    """RAG检索增强生成Pipeline

    完整流程：文档处理 -> 向量存储 -> 检索 -> 生成
    """

    def __init__(
        self,
        model: str = "deepseek-chat",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        top_k: int = 5,
    ):
        self.model = model
        self.top_k = top_k
        self.processor = DocumentProcessor(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        self.vector_store = VectorStore()
        self._api_key = os.getenv("OPENAI_API_KEY")
        self._base_url = os.getenv("OPENAI_BASE_URL")

    @property
    def client(self):
        """懒加载OpenAI客户端"""
        if not hasattr(self, "_client"):
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def add_document(self, text: str, source: str = "unknown") -> int:
        """添加文档到知识库

        Args:
            text: 文档文本
            source: 文档来源标识

        Returns:
            添加的块数
        """
        chunks = self.processor.process(text, source)
        count = self.vector_store.add_documents(chunks)
        logger.info(f"添加文档: source={source}, {count} 个块")
        return count

    def query(self, question: str) -> dict:
        """查询知识库

        Args:
            question: 用户问题

        Returns:
            包含answer和sources的字典
        """
        # 1. 检索相关文档
        results = self.vector_store.search(question, top_k=self.top_k)

        if not results:
            return {
                "answer": "知识库中没有相关文档，请先添加文档。",
                "sources": [],
                "question": question,
            }

        # 2. 构建上下文
        context_parts = []
        sources = []
        for doc, score in results:
            context_parts.append(doc["content"])
            sources.append(
                {
                    "content": doc["content"][:200],
                    "source": doc["metadata"].get("source", "unknown"),
                    "score": round(score, 4),
                    "chunk_index": doc.get("chunk_index", 0),
                }
            )

        context = "\n\n---\n\n".join(context_parts)

        # 3. 生成回答
        prompt = f"""基于以下参考文档回答用户的问题。如果参考文档中没有相关信息，请说明。

参考文档：
{context}

用户问题：{question}

请给出回答，并标注信息来源："""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            answer = f"生成回答失败: {str(e)}"

        return {
            "answer": answer,
            "sources": sources,
            "question": question,
        }

    def get_stats(self) -> dict:
        """获取知识库统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_chunks": self.vector_store.size,
            "chunk_size": self.processor.chunk_size,
            "chunk_overlap": self.processor.chunk_overlap,
            "top_k": self.top_k,
        }
