"""DocumentProcessor 测试"""

import pytest

from src.rag_systems.personal_knowledge_base.document_processor import (
    Chunk,
    Document,
    DocumentProcessor,
)


class TestDocument:
    """Document 数据类测试"""

    def test_create_document(self):
        doc = Document(content="test", metadata={"source": "test.txt"})
        assert doc.content == "test"
        assert doc.metadata["source"] == "test.txt"

    def test_document_default_metadata(self):
        doc = Document(content="test", metadata=None)
        assert doc.metadata == {}


class TestDocumentProcessor:
    """DocumentProcessor 测试"""

    def test_load_text(self):
        processor = DocumentProcessor()
        doc = processor.load_text("Hello World", "test.txt")
        assert doc.content == "Hello World"
        assert doc.metadata["source"] == "test.txt"

    def test_split_text_short(self):
        processor = DocumentProcessor(chunk_size=1000)
        chunks = processor.split_text("Short text")
        assert len(chunks) == 1
        assert chunks[0] == "Short text"

    def test_split_text_long(self):
        processor = DocumentProcessor(chunk_size=50, chunk_overlap=10)
        text = "这是第一段内容。" * 20 + "\n\n" + "这是第二段内容。" * 20
        chunks = processor.split_text(text)
        assert len(chunks) >= 2

    def test_split_text_empty(self):
        processor = DocumentProcessor()
        chunks = processor.split_text("")
        assert chunks == []

    def test_split_text_whitespace_only(self):
        processor = DocumentProcessor()
        chunks = processor.split_text("   \n\n   ")
        assert chunks == []

    def test_process_full_pipeline(self):
        processor = DocumentProcessor(chunk_size=200)
        chunks = processor.process("这是测试文档内容。", "test.txt")
        assert len(chunks) >= 1
        assert isinstance(chunks[0], Chunk)
        assert chunks[0].doc_id != ""
        assert chunks[0].chunk_index == 0

    def test_chunk_size_configurable(self):
        processor = DocumentProcessor(chunk_size=100, chunk_overlap=20)
        assert processor.chunk_size == 100
        assert processor.chunk_overlap == 20
