"""多论文查询测试"""

import pytest

from src.rag_systems.paper_reader_agent.multi_paper_query import MultiPaperQuery


class TestMultiPaperQuery:
    def setup_method(self):
        self.engine = MultiPaperQuery()
        self.paper1 = """
Transformer Architecture

Abstract
We propose the Transformer architecture based on attention mechanisms.

1. Introduction
The Transformer model replaces recurrence with attention.

References
[1] Vaswani et al., 2017.
"""
        self.paper2 = """
BERT Language Model

Abstract
We introduce BERT, a bidirectional language representation model.

1. Introduction
BERT pre-trains deep bidirectional representations.

References
[1] Devlin et al., 2018.
"""

    def test_add_paper(self):
        paper = self.engine.add_paper(self.paper1, "paper1.txt")
        assert paper.title != "未知标题"
        assert len(self.engine.papers) == 1

    def test_search_papers(self):
        self.engine.add_paper(self.paper1)
        self.engine.add_paper(self.paper2)
        results = self.engine.search_papers("attention mechanism", top_k=2)
        assert len(results) <= 2

    def test_compare_papers(self):
        self.engine.add_paper(self.paper1)
        self.engine.add_paper(self.paper2)
        result = self.engine.compare_papers("language model")
        assert "papers" in result
        assert result["paper_count"] == 2

    def test_compare_papers_insufficient(self):
        self.engine.add_paper(self.paper1)
        result = self.engine.compare_papers("test")
        assert "error" in result

    def test_get_summary(self):
        self.engine.add_paper(self.paper1)
        self.engine.add_paper(self.paper2)
        summary = self.engine.get_summary()
        assert summary["total_papers"] == 2
        assert len(summary["papers"]) == 2
