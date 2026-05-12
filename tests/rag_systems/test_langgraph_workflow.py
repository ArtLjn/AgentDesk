import pytest
from src.rag_systems.langgraph_workflow import (
    ingest_node, classify_node, process_faq_node, process_technical_node,
    process_general_node, review_node, output_node, should_continue,
    route_by_type, run_workflow, build_workflow, WorkflowState
)


class TestIngestNode:
    def test_basic_ingest(self):
        state = {"document": "  Hello World  ", "review_score": 0, "iteration": 0}
        result = ingest_node(state)
        assert result["document"] == "Hello World"
        assert result["iteration"] == 0

    def test_empty_document(self):
        state = {"document": "", "review_score": 0, "iteration": 0}
        result = ingest_node(state)
        assert result["document"] == ""


class TestClassifyNode:
    def test_classify_faq(self):
        state = {"document": "什么是Python? Python是一种编程语言"}
        result = classify_node(state)
        assert result["doc_type"] == "faq"

    def test_classify_technical(self):
        state = {"document": "def hello():\n    print('hello')"}
        result = classify_node(state)
        assert result["doc_type"] == "technical"

    def test_classify_general(self):
        state = {"document": "这是一篇普通的文章"}
        result = classify_node(state)
        assert result["doc_type"] == "general"


class TestProcessNodes:
    def test_process_faq(self):
        state = {"document": "什么是AI? 人工智能", "iteration": 0}
        result = process_faq_node(state)
        assert "Q:" in result["processing_result"]
        assert "A:" in result["processing_result"]

    def test_process_technical(self):
        state = {"document": "代码如下\n```python\nprint('hello')\n```\n结束", "iteration": 0}
        result = process_technical_node(state)
        assert "python" in result["processing_result"]

    def test_process_general(self):
        state = {"document": "这是第一句话。这是第二句话。这是第三句话。这是第四句话。", "iteration": 0}
        result = process_general_node(state)
        assert "摘要" in result["processing_result"]


class TestReviewNode:
    def test_review_good_result(self):
        state = {"processing_result": "这是一段较长的良好处理结果内容", "iteration": 1}
        result = review_node(state)
        assert result["review_score"] >= 7

    def test_review_poor_result(self):
        state = {"processing_result": "未找到", "iteration": 1}
        result = review_node(state)
        assert result["review_score"] < 7


class TestShouldContinue:
    def test_continue_on_low_score(self):
        state = {"review_score": 4, "iteration": 1}
        assert should_continue(state) == "reprocess"

    def test_stop_on_high_score(self):
        state = {"review_score": 8, "iteration": 1}
        assert should_continue(state) == "output"

    def test_stop_on_max_iterations(self):
        state = {"review_score": 4, "iteration": 3}
        assert should_continue(state) == "output"


class TestRouteByType:
    def test_route_faq(self):
        state = {"doc_type": "faq"}
        assert route_by_type(state) == "faq"

    def test_route_technical(self):
        state = {"doc_type": "technical"}
        assert route_by_type(state) == "technical"

    def test_route_general(self):
        state = {"doc_type": "general"}
        assert route_by_type(state) == "general"


class TestWorkflow:
    def test_build_workflow(self):
        graph = build_workflow()
        assert graph is not None

    def test_run_workflow_faq(self):
        result = run_workflow("什么是Python? 一种编程语言")
        assert "faq" in result.lower() or "类型" in result

    def test_run_workflow_technical(self):
        result = run_workflow("```python\nprint('hello')\n```")
        assert "technical" in result.lower() or "类型" in result

    def test_run_workflow_general(self):
        result = run_workflow("今天天气不错，适合出去散步。公园里花都开了。阳光明媚。")
        assert "general" in result.lower() or "类型" in result

    def test_run_workflow_empty(self):
        result = run_workflow("")
        assert result is not None
