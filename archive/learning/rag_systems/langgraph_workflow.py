from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from loguru import logger


class WorkflowState(TypedDict):
    document: str
    doc_type: Optional[str]
    processing_result: Optional[str]
    review_score: int
    iteration: int
    final_output: Optional[str]


MAX_ITERATIONS = 3
MIN_REVIEW_SCORE = 7


def ingest_node(state: WorkflowState) -> dict:
    """接收文档，提取文本内容"""
    document = state.get("document", "")
    text = document.strip()
    logger.info(f"Ingest: 接收到文档，长度 {len(text)}")
    return {"document": text, "iteration": 0, "review_score": 0}


def classify_node(state: WorkflowState) -> dict:
    """分类文档类型"""
    document = state.get("document", "")
    text_lower = document.lower()

    if "faq" in text_lower or "问答" in text_lower or "?" in document or "？" in document:
        doc_type = "faq"
    elif "```" in document or "def " in document or "class " in document or "function" in text_lower:
        doc_type = "technical"
    else:
        doc_type = "general"

    logger.info(f"Classify: 文档类型 -> {doc_type}")
    return {"doc_type": doc_type}


def route_by_type(state: WorkflowState) -> str:
    """根据文档类型路由到不同处理节点"""
    return state.get("doc_type", "general")


def process_faq_node(state: WorkflowState) -> dict:
    """处理FAQ类型文档：提取问答对"""
    document = state.get("document", "")
    lines = document.split("\n")
    qa_pairs = []
    current_q = None

    for line in lines:
        line = line.strip()
        # 检查行内是否包含问号分隔的问答（如 "什么是AI? 人工智能"）
        q_match = None
        for sep in ("?", "？"):
            if sep in line:
                parts = line.split(sep, 1)
                if len(parts) == 2 and parts[1].strip():
                    q_match = (parts[0].strip() + sep, parts[1].strip())
                    break
        if q_match:
            qa_pairs.append(f"Q: {q_match[0]}\nA: {q_match[1]}")
        elif line.endswith("?") or line.endswith("？"):
            current_q = line
        elif current_q and line:
            qa_pairs.append(f"Q: {current_q}\nA: {line}")
            current_q = None

    result = "\n\n".join(qa_pairs) if qa_pairs else "未找到问答对"
    logger.info(f"Process FAQ: 提取到 {len(qa_pairs)} 个问答对")
    return {"processing_result": result, "iteration": state.get("iteration", 0) + 1}


def process_technical_node(state: WorkflowState) -> dict:
    """处理技术文档：提取代码块"""
    document = state.get("document", "")
    lines = document.split("\n")
    code_blocks = []
    in_code = False
    current_block = []
    lang = ""

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                code_blocks.append(f"[{lang}]\n" + "\n".join(current_block))
                current_block = []
                in_code = False
            else:
                lang = line.strip()[3:].strip() or "code"
                in_code = True
        elif in_code:
            current_block.append(line)

    if not code_blocks:
        for line in lines:
            if line.startswith("    ") or line.startswith("\t"):
                code_blocks.append(line.strip())

    result = "\n---\n".join(code_blocks) if code_blocks else "未找到代码块"
    logger.info(f"Process Technical: 提取到 {len(code_blocks)} 个代码块")
    return {"processing_result": result, "iteration": state.get("iteration", 0) + 1}


def process_general_node(state: WorkflowState) -> dict:
    """处理通用文档：生成摘要"""
    document = state.get("document", "")
    sentences = [s.strip() for s in document.replace("。", "。\n").replace(".", ".\n").split("\n") if s.strip()]

    summary_sentences = sentences[:3]
    result = "摘要: " + "".join(summary_sentences) if summary_sentences else "文档为空"

    logger.info(f"Process General: 生成摘要，{len(summary_sentences)} 句")
    return {"processing_result": result, "iteration": state.get("iteration", 0) + 1}


def review_node(state: WorkflowState) -> dict:
    """审查处理结果，决定是否需要重新处理"""
    result = state.get("processing_result", "")
    iteration = state.get("iteration", 0)

    score = 5
    if result and len(result) > 10:
        score += 2
    if "未找到" not in result:
        score += 2
    if iteration > 1:
        score = min(score + 1, 10)

    score = min(score, 10)
    logger.info(f"Review: 评分 {score}/10 (迭代 {iteration})")
    return {"review_score": score}


def should_continue(state: WorkflowState) -> str:
    """决定是否继续循环"""
    if state.get("review_score", 0) >= MIN_REVIEW_SCORE:
        return "output"
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "output"
    return "reprocess"


def output_node(state: WorkflowState) -> dict:
    """格式化并输出最终结果"""
    doc_type = state.get("doc_type", "unknown")
    result = state.get("processing_result", "")
    score = state.get("review_score", 0)
    iteration = state.get("iteration", 0)

    output = f"类型: {doc_type}\n评分: {score}/10\n迭代次数: {iteration}\n\n{result}"
    logger.info("Output: 最终输出完成")
    return {"final_output": output}


def build_workflow() -> StateGraph:
    """构建文档处理工作流"""
    graph = StateGraph(WorkflowState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("classify", classify_node)
    graph.add_node("process_faq", process_faq_node)
    graph.add_node("process_technical", process_technical_node)
    graph.add_node("process_general", process_general_node)
    graph.add_node("review", review_node)
    graph.add_node("output", output_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "classify")
    graph.add_conditional_edges(
        "classify",
        route_by_type,
        {
            "faq": "process_faq",
            "technical": "process_technical",
            "general": "process_general",
        }
    )
    graph.add_edge("process_faq", "review")
    graph.add_edge("process_technical", "review")
    graph.add_edge("process_general", "review")
    graph.add_conditional_edges(
        "review",
        should_continue,
        {
            "output": "output",
            "reprocess": "classify",
        }
    )
    graph.add_edge("output", END)

    return graph


workflow = build_workflow()
app = workflow.compile()


def run_workflow(document: str) -> str:
    """运行文档处理工作流

    Args:
        document: 输入文档文本
    Returns:
        处理结果字符串
    """
    result = app.invoke({"document": document})
    return result.get("final_output", "处理失败")
