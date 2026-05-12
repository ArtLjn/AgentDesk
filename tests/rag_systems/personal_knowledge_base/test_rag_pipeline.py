"""RAGPipeline 测试"""

from unittest.mock import MagicMock, patch

import pytest

from src.rag_systems.personal_knowledge_base.rag_pipeline import RAGPipeline


class TestRAGPipeline:
    """RAGPipeline 测试"""

    def test_initialization(self):
        pipeline = RAGPipeline(model="test-model", chunk_size=200, top_k=3)
        assert pipeline.model == "test-model"
        assert pipeline.top_k == 3
        assert pipeline.processor.chunk_size == 200

    def test_add_document(self):
        pipeline = RAGPipeline(model="test", chunk_size=200)
        with patch.object(pipeline.vector_store, "add_documents", return_value=3):
            count = pipeline.add_document("测试文档内容", "test.txt")
            assert count == 3

    def test_query_empty_knowledge_base(self):
        pipeline = RAGPipeline(model="test")
        result = pipeline.query("什么是Python?")
        assert "没有" in result["answer"] or "请先添加" in result["answer"]
        assert result["sources"] == []

    def test_get_stats(self):
        pipeline = RAGPipeline(model="test", chunk_size=300, top_k=5)
        stats = pipeline.get_stats()
        assert stats["chunk_size"] == 300
        assert stats["top_k"] == 5
        assert stats["total_chunks"] == 0
