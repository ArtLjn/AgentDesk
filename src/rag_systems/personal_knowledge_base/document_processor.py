"""文档处理器，负责文档加载和分块"""

import hashlib
import re
from dataclasses import dataclass
from typing import List

from loguru import logger


@dataclass
class Document:
    """文档数据类"""

    content: str
    metadata: dict

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Chunk:
    """文档分块数据类"""

    content: str
    metadata: dict
    doc_id: str
    chunk_index: int


class DocumentProcessor:
    """文档处理器，负责文档加载和分块"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_text(self, text: str, source: str = "unknown") -> Document:
        """加载文本内容为Document对象

        Args:
            text: 原始文本内容
            source: 文档来源标识

        Returns:
            Document对象
        """
        doc = Document(content=text, metadata={"source": source, "length": len(text)})
        logger.info(f"加载文档: source={source}, length={len(text)}")
        return doc

    def split_text(self, text: str) -> List[str]:
        """将文本分块，支持重叠

        按段落和句子边界分割，尽量保持语义完整。

        Args:
            text: 待分割的文本

        Returns:
            分块后的文本列表
        """
        if not text or not text.strip():
            return []

        # 先按段落分割
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            # 如果当前块+新段落不超过大小，合并
            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # 当前块已满，保存
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单段落超过chunk_size，按句子再分
                if len(para) > self.chunk_size:
                    sub_chunks = self._split_by_sentences(para)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""
                else:
                    current_chunk = para

        # 最后一块
        if current_chunk:
            chunks.append(current_chunk)

        # 添加重叠：在相邻块之间共享部分内容
        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped: List[str] = []
            for i, chunk in enumerate(chunks):
                if i > 0:
                    # 从前一个块末尾取overlap内容
                    prev_overlap = chunks[i - 1][-self.chunk_overlap :]
                    chunk = prev_overlap + chunk
                overlapped.append(chunk)
            chunks = overlapped

        logger.info(f"文本分块: {len(chunks)} 个块")
        return chunks

    def _split_by_sentences(self, text: str) -> List[str]:
        """按句子边界分割长文本

        Args:
            text: 超长文本

        Returns:
            按句子聚合后的文本块列表
        """
        # 按中英文句号、问号、感叹号分割
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks: List[str] = []
        current = ""

        for sent in sentences:
            if len(current) + len(sent) + 1 <= self.chunk_size:
                current = (current + " " + sent).strip() if current else sent
            else:
                if current:
                    chunks.append(current)
                current = sent

        if current:
            chunks.append(current)

        return chunks if chunks else [text[: self.chunk_size]]

    def process(self, text: str, source: str = "unknown") -> List[Chunk]:
        """完整处理流程：加载 -> 分块

        Args:
            text: 原始文本
            source: 文档来源标识

        Returns:
            Chunk对象列表
        """
        doc = self.load_text(text, source)
        text_chunks = self.split_text(doc.content)

        doc_id = hashlib.md5(doc.content.encode()).hexdigest()[:8]

        chunks = []
        for i, content in enumerate(text_chunks):
            chunk = Chunk(
                content=content,
                metadata={**doc.metadata, "chunk_index": i},
                doc_id=doc_id,
                chunk_index=i,
            )
            chunks.append(chunk)

        logger.info(f"处理完成: doc_id={doc_id}, {len(chunks)} 个分块")
        return chunks
