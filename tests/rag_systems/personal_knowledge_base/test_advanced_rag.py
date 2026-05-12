"""高级RAG优化测试"""

import pytest

from src.rag_systems.personal_knowledge_base.advanced_rag import (
    Reranker,
    HybridSearcher,
    ContextCompressor,
)


class TestReranker:
    def test_rerank_empty(self):
        reranker = Reranker()
        assert reranker.rerank("test", []) == []

    def test_rerank_with_results(self):
        reranker = Reranker()
        results = [
            ({"content": "Python is a programming language"}, 0.8),
            ({"content": "Java is also popular"}, 0.6),
        ]
        reranked = reranker.rerank("Python programming", results, top_k=2)
        assert len(reranked) == 2
        # Python相关文档应该排第一
        assert "Python" in reranked[0][0]["content"]

    def test_rerank_top_k(self):
        reranker = Reranker()
        results = [({"content": f"doc{i}"}, 0.5) for i in range(10)]
        reranked = reranker.rerank("test", results, top_k=3)
        assert len(reranked) == 3


class TestHybridSearcher:
    def test_keyword_search(self):
        searcher = HybridSearcher()
        docs = [
            {"content": "Python is a great language for AI"},
            {"content": "Java is used in enterprise"},
            {"content": "Python machine learning libraries"},
        ]
        results = searcher.keyword_search("Python AI", docs, top_k=2)
        assert len(results) <= 2
        assert "Python" in results[0][0]["content"]

    def test_hybrid_search(self):
        searcher = HybridSearcher()
        vector_results = [({"content": "Python programming"}, 0.9)]
        keyword_results = [({"content": "Python data science"}, 0.8)]
        results = searcher.search(
            "Python", vector_results, keyword_results, top_k=2
        )
        assert len(results) <= 2


class TestContextCompressor:
    def test_compress_short_context(self):
        compressor = ContextCompressor()
        result = compressor.compress("test", "Short text.", max_sentences=5)
        assert result == "Short text."

    def test_compress_long_context(self):
        compressor = ContextCompressor()
        context = (
            "Python is great. Java is popular. Go is fast. "
            "Rust is safe. C is old. Ruby is fun. PHP is web."
        )
        result = compressor.compress("Python programming", context, max_sentences=3)
        assert len(result) < len(context)

    def test_compress_empty(self):
        compressor = ContextCompressor()
        assert compressor.compress("test", "") == ""
        assert compressor.compress("test", "   ") == ""
