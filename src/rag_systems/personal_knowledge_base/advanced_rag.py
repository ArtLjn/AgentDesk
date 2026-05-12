"""高级RAG优化模块：重排序、混合检索、上下文压缩"""

from typing import List, Tuple
import re
from loguru import logger


class Reranker:
    """重排序器：基于关键词匹配和长度对检索结果重排序"""

    def rerank(
        self, query: str, results: List[Tuple[dict, float]], top_k: int = 5
    ) -> List[Tuple[dict, float]]:
        """对检索结果重排序

        结合原始分数和关键词匹配分数进行重排序
        """
        if not results:
            return []

        query_terms = set(re.findall(r'\w+', query.lower()))

        scored = []
        for doc, original_score in results:
            content = doc.get("content", "").lower()
            # 关键词匹配度
            content_terms = set(re.findall(r'\w+', content))
            keyword_overlap = len(query_terms & content_terms) / max(
                len(query_terms), 1
            )

            # 长度惩罚：过短的内容可能信息不足
            length_factor = min(len(content) / 200, 1.0)

            # 综合分数：原始分数 * 0.5 + 关键词匹配 * 0.3 + 长度因子 * 0.2
            combined_score = (
                original_score * 0.5 + keyword_overlap * 0.3 + length_factor * 0.2
            )
            scored.append((doc, combined_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


class HybridSearcher:
    """混合检索器：结合向量检索和关键词检索"""

    def search(
        self,
        query: str,
        vector_results: List[Tuple[dict, float]],
        keyword_results: List[Tuple[dict, float]],
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        top_k: int = 5,
    ) -> List[Tuple[dict, float]]:
        """混合检索：融合向量检索和关键词检索结果

        使用Reciprocal Rank Fusion (RRF)算法合并结果
        """
        # 计算RRF分数
        rrf_scores = {}
        k = 60  # RRF常数

        for rank, (doc, _score) in enumerate(vector_results):
            doc_key = doc.get("content", "")[:100]
            if doc_key not in rrf_scores:
                rrf_scores[doc_key] = 0.0
            rrf_scores[doc_key] += vector_weight / (k + rank + 1)
            rrf_scores[doc_key + "_doc"] = doc

        for rank, (doc, _score) in enumerate(keyword_results):
            doc_key = doc.get("content", "")[:100]
            if doc_key not in rrf_scores:
                rrf_scores[doc_key] = 0.0
            rrf_scores[doc_key] += keyword_weight / (k + rank + 1)
            rrf_scores[doc_key + "_doc"] = doc

        # 排序
        results = []
        for key, score in rrf_scores.items():
            if not key.endswith("_doc"):
                doc = rrf_scores.get(key + "_doc")
                if doc:
                    results.append((doc, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def keyword_search(
        self, query: str, documents: List[dict], top_k: int = 5
    ) -> List[Tuple[dict, float]]:
        """简单的关键词检索

        基于BM25-like的词频匹配
        """
        query_terms = set(re.findall(r'\w+', query.lower()))

        scored = []
        for doc in documents:
            content = doc.get("content", "").lower()
            content_terms = re.findall(r'\w+', content)

            if not content_terms:
                scored.append((doc, 0.0))
                continue

            # 计算词频
            term_freq = sum(1 for t in content_terms if t in query_terms)
            # TF归一化
            tf = term_freq / len(content_terms)
            scored.append((doc, tf))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


class ContextCompressor:
    """上下文压缩器：提取与查询最相关的句子"""

    def compress(
        self, query: str, context: str, max_sentences: int = 5
    ) -> str:
        """压缩上下文，只保留与查询最相关的句子

        Args:
            query: 用户查询
            context: 原始上下文
            max_sentences: 最多保留的句子数

        Returns:
            压缩后的上下文
        """
        if not context or not context.strip():
            return ""

        # 分句
        sentences = re.split(r'(?<=[。！？.!?])\s*', context)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= max_sentences:
            return context

        query_terms = set(re.findall(r'\w+', query.lower()))

        # 每个句子计算与查询的相关性
        scored_sentences = []
        for i, sent in enumerate(sentences):
            sent_terms = set(re.findall(r'\w+', sent.lower()))
            overlap = len(query_terms & sent_terms)
            # 位置权重：前面的句子更重要
            position_weight = 1.0 - (i / len(sentences)) * 0.3
            score = overlap * position_weight
            scored_sentences.append((i, sent, score))

        # 按分数排序，取top句子
        scored_sentences.sort(key=lambda x: x[2], reverse=True)
        top_indices = sorted([x[0] for x in scored_sentences[:max_sentences]])

        # 按原文顺序重组
        compressed = " ".join(sentences[i] for i in top_indices)
        logger.info(f"上下文压缩: {len(sentences)} 句 -> {len(top_indices)} 句")
        return compressed
