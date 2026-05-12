"""VectorStore 测试"""

import numpy as np
import pytest
from unittest.mock import patch

from src.rag_systems.personal_knowledge_base.document_processor import Chunk
from src.rag_systems.personal_knowledge_base.vector_store import VectorStore


class TestVectorStore:
    """VectorStore 测试"""

    def test_initialization(self):
        store = VectorStore(embedding_dim=128)
        assert store.size == 0
        assert store.embedding_dim == 128

    @patch.object(VectorStore, "_get_embeddings_batch")
    def test_add_documents(self, mock_batch):
        mock_batch.return_value = np.random.randn(2, 128).tolist()
        store = VectorStore(embedding_dim=128)
        chunks = [
            Chunk(content="doc1", metadata={"source": "a"}, doc_id="1", chunk_index=0),
            Chunk(content="doc2", metadata={"source": "b"}, doc_id="2", chunk_index=0),
        ]
        count = store.add_documents(chunks)
        assert count == 2
        assert store.size == 2

    @patch.object(VectorStore, "_get_embedding")
    def test_search_empty(self, mock_embed):
        store = VectorStore(embedding_dim=128)
        results = store.search("test")
        assert results == []

    @patch.object(VectorStore, "_get_embedding")
    @patch.object(VectorStore, "_get_embeddings_batch")
    def test_search_with_docs(self, mock_batch, mock_embed):
        mock_batch.return_value = np.random.randn(2, 128).tolist()
        mock_embed.return_value = np.random.randn(128).tolist()

        store = VectorStore(embedding_dim=128)
        chunks = [
            Chunk(
                content="Python编程", metadata={"source": "a"}, doc_id="1", chunk_index=0
            ),
            Chunk(
                content="Java编程", metadata={"source": "b"}, doc_id="2", chunk_index=0
            ),
        ]
        store.add_documents(chunks)
        results = store.search("编程语言", top_k=2)
        assert len(results) <= 2
        assert len(results) > 0

    @patch.object(VectorStore, "_get_embeddings_batch")
    def test_clear(self, mock_batch):
        mock_batch.return_value = np.random.randn(1, 128).tolist()
        store = VectorStore(embedding_dim=128)
        chunks = [Chunk(content="test", metadata={}, doc_id="1", chunk_index=0)]
        store.add_documents(chunks)
        assert store.size == 1
        store.clear()
        assert store.size == 0
