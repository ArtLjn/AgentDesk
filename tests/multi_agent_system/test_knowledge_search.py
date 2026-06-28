"""知识库向量检索工具测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.multi_agent_system.tools.knowledge_search import KnowledgeSearchTool


def test_search_uses_query_points_for_new_qdrant_client():
    """新版 qdrant-client 移除 search 后，应使用 query_points 完成检索。"""
    tool = KnowledgeSearchTool(
        qdrant_url="http://qdrant:6333",
        collection_name="knowledge_base",
        embedding_base_url="http://ollama:11434",
        embedding_model="qwen3-embedding:4b",
        embedding_dim=3,
    )
    tool.ensure_collection = MagicMock()
    tool._get_embedding = MagicMock(return_value=[0.1, 0.2, 0.3])

    client = MagicMock()
    client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                score=0.91,
                payload={
                    "content": "ERR-5001 需要清理浏览器缓存并检查认证服务。",
                    "title": "登录故障手册",
                    "category": "technical",
                },
            )
        ]
    )
    del client.search
    tool._client = client

    results = tool.search("ERR-5001 无法登录", top_k=2, score_threshold=0.5)

    client.query_points.assert_called_once_with(
        collection_name="knowledge_base",
        query=[0.1, 0.2, 0.3],
        limit=2,
        score_threshold=0.5,
        with_payload=True,
    )
    assert results == [
        {
            "content": "ERR-5001 需要清理浏览器缓存并检查认证服务。",
            "score": 0.91,
            "metadata": {
                "title": "登录故障手册",
                "category": "technical",
            },
        }
    ]


def test_search_falls_back_to_keyword_scan_when_embedding_fails():
    """embedding 服务异常时，应从 Qdrant payload 兜底检索知识片段。"""
    tool = KnowledgeSearchTool(
        qdrant_url="http://qdrant:6333",
        collection_name="knowledge_base",
        embedding_base_url="http://embedding",
        embedding_model="embedding-model",
        embedding_dim=3,
    )
    tool.ensure_collection = MagicMock()
    tool._get_embedding = MagicMock(side_effect=RuntimeError("embedding 400"))

    client = MagicMock()
    client.scroll.return_value = (
        [
            SimpleNamespace(
                id="coupon-point",
                payload={
                    "document_id": "coupon-doc",
                    "title": "优惠券使用规则",
                    "category": "billing-coupon",
                    "content": "优惠券需在结算页选择，部分商品不可叠加使用。",
                    "chunk_index": 0,
                },
            ),
            SimpleNamespace(
                id="login-point",
                payload={
                    "document_id": "login-doc",
                    "title": "登录故障手册",
                    "category": "technical",
                    "content": "无法登录时检查账号状态。",
                    "chunk_index": 0,
                },
            ),
        ],
        None,
    )
    tool._client = client

    results = tool.search("咨询一下平台优惠卷如何使用", top_k=1)

    client.scroll.assert_called_once_with(
        collection_name="knowledge_base",
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    assert len(results) == 1
    assert results[0]["metadata"]["title"] == "优惠券使用规则"
    assert "结算页选择" in results[0]["content"]


def test_list_documents_groups_qdrant_chunks_by_document():
    """知识库列表应把 Qdrant 分块聚合回文档视角。"""
    tool = KnowledgeSearchTool(
        qdrant_url="http://qdrant:6333",
        collection_name="knowledge_base",
        embedding_base_url="http://ollama:11434",
        embedding_model="qwen3-embedding:4b",
        embedding_dim=3,
    )
    tool.ensure_collection = MagicMock()

    client = MagicMock()
    client.scroll.return_value = (
        [
            SimpleNamespace(
                id="point-2",
                payload={
                    "document_id": "doc-1",
                    "title": "登录故障手册",
                    "category": "technical",
                    "content": "第二段",
                    "chunk_index": 1,
                },
            ),
            SimpleNamespace(
                id="point-1",
                payload={
                    "document_id": "doc-1",
                    "title": "登录故障手册",
                    "category": "technical",
                    "content": "第一段",
                    "chunk_index": 0,
                },
            ),
        ],
        "next-page",
    )
    tool._client = client

    result = tool.list_documents(limit=20)

    client.scroll.assert_called_once_with(
        collection_name="knowledge_base",
        limit=20,
        offset=None,
        with_payload=True,
        with_vectors=False,
    )
    assert result["count"] == 1
    assert result["next_offset"] == "next-page"
    assert result["documents"][0]["id"] == "doc-1"
    assert result["documents"][0]["chunk_count"] == 2
    assert result["documents"][0]["content"] == "第一段\n第二段"
