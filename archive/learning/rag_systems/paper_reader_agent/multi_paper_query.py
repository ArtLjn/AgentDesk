"""多论文查询引擎：支持跨论文检索和对比"""

import re
from typing import List

from loguru import logger

from archive.learning.rag_systems.paper_reader_agent.paper_processor import PaperProcessor, PaperInfo


class MultiPaperQuery:
    """多论文查询引擎，支持跨论文检索和对比"""

    def __init__(self):
        self.processor = PaperProcessor()
        self.papers: List[PaperInfo] = []
        self.paper_chunks: List[dict] = []

    def add_paper(self, text: str, source: str = "unknown") -> PaperInfo:
        """添加论文到查询引擎"""
        paper = self.processor.process(text)
        self.papers.append(paper)

        # 摘要块
        if paper.abstract:
            self.paper_chunks.append(
                {
                    "content": paper.abstract,
                    "source": source,
                    "paper_title": paper.title,
                    "section": "Abstract",
                }
            )

        # 章节块
        for section in paper.sections:
            self.paper_chunks.append(
                {
                    "content": section["content"],
                    "source": source,
                    "paper_title": paper.title,
                    "section": section["title"],
                }
            )

        logger.info(f"添加论文: {paper.title}, {len(self.paper_chunks)} 个块")
        return paper

    def search_papers(self, query: str, top_k: int = 5) -> List[dict]:
        """跨论文关键词检索"""
        query_terms = set(re.findall(r'\w+', query.lower()))

        scored = []
        for chunk in self.paper_chunks:
            content_terms = set(re.findall(r'\w+', chunk["content"].lower()))
            overlap = len(query_terms & content_terms)
            if overlap > 0:
                scored.append({**chunk, "score": overlap / max(len(query_terms), 1)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def compare_papers(self, topic: str) -> dict:
        """对比多篇论文在特定主题上的观点"""
        if len(self.papers) < 2:
            return {"error": "至少需要2篇论文才能对比"}

        results = {}
        for paper in self.papers:
            relevant = self.search_papers(topic, top_k=3)
            paper_results = [r for r in relevant if r["paper_title"] == paper.title]
            results[paper.title] = {
                "relevant_sections": paper_results,
                "key_points": self.processor.extract_key_points(paper),
            }

        return {
            "topic": topic,
            "papers": results,
            "paper_count": len(self.papers),
        }

    def get_summary(self) -> dict:
        """获取所有论文的概要"""
        return {
            "total_papers": len(self.papers),
            "papers": [
                {
                    "title": p.title,
                    "abstract_length": len(p.abstract),
                    "sections": len(p.sections),
                    "references": len(p.references),
                }
                for p in self.papers
            ],
        }
