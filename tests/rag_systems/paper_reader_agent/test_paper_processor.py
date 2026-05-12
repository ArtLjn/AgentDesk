"""论文处理器测试"""

import pytest

from src.rag_systems.paper_reader_agent.paper_processor import PaperProcessor, PaperInfo


class TestPaperProcessor:
    def setup_method(self):
        self.processor = PaperProcessor()
        self.sample_paper = """
Attention Is All You Need

Abstract
We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.
This paper introduces the Transformer architecture that achieves state-of-the-art results.

1. Introduction
Recurrent neural networks have been widely used for sequence modeling.
We propose a new architecture that avoids recurrence entirely.

2. Method
The Transformer uses multi-head self-attention mechanism.
It consists of an encoder and decoder stack.

3. Results
Our model achieves 28.4 BLEU on WMT translation.
The Transformer outperforms all previous models.

4. Conclusion
We presented the Transformer, a new architecture based on attention.
The Transformer achieves superior results on translation tasks.

References
[1] Vaswani et al., Attention Is All You Need, 2017.
[2] Devlin et al., BERT, 2018.
[3] Radford et al., GPT, 2018.
"""

    def test_extract_title(self):
        title = self.processor.extract_title(self.sample_paper)
        assert "Attention" in title

    def test_extract_abstract(self):
        abstract = self.processor.extract_abstract(self.sample_paper)
        assert "Transformer" in abstract
        assert len(abstract) > 10

    def test_extract_sections(self):
        sections = self.processor.extract_sections(self.sample_paper)
        assert len(sections) >= 2
        assert any("Introduction" in s["title"] for s in sections)

    def test_extract_references(self):
        refs = self.processor.extract_references(self.sample_paper)
        assert len(refs) >= 1

    def test_process_full(self):
        paper = self.processor.process(self.sample_paper)
        assert isinstance(paper, PaperInfo)
        assert paper.title != "未知标题"
        assert len(paper.sections) >= 2

    def test_extract_key_points(self):
        paper = self.processor.process(self.sample_paper)
        points = self.processor.extract_key_points(paper)
        assert len(points) >= 0

    def test_empty_paper(self):
        paper = self.processor.process("")
        assert paper.title == "未知标题"
        assert paper.abstract == ""
        assert paper.sections == []
