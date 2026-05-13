"""多 Agent 工单处理系统 - Streamlit 前端应用。

调用 FastAPI 后端 API 实现工单提交、查询和统计展示。
API 地址从环境变量 API_URL 读取，默认 http://localhost:8000。
"""

import os
from typing import Any

import requests
import streamlit as st

# API 基础地址
API_URL = os.environ.get("API_URL", "http://localhost:8000")


# ============================================================
# API 请求封装
# ============================================================


def submit_ticket(content: str, user_id: str) -> dict[str, Any]:
    """提交新工单到后端。

    Args:
        content: 工单内容。
        user_id: 用户 ID。

    Returns:
        后端返回的响应字典。
    """
    resp = requests.post(
        f"{API_URL}/api/tickets",
        json={"content": content, "user_id": user_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_tickets(
    status: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """从后端获取工单列表。

    Args:
        status: 按状态过滤，可选。
        category: 按分类过滤，可选。

    Returns:
        工单列表。
    """
    params: dict[str, str] = {}
    if status:
        params["status"] = status
    if category:
        params["category"] = category

    resp = requests.get(
        f"{API_URL}/api/tickets",
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_ticket_detail(ticket_id: str) -> dict[str, Any]:
    """查询单个工单详情。

    Args:
        ticket_id: 工单 ID。

    Returns:
        工单详情字典。
    """
    resp = requests.get(
        f"{API_URL}/api/tickets/{ticket_id}",
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_analytics() -> dict[str, Any]:
    """获取统计面板数据。

    Returns:
        包含分类分布、优先级分布、处理统计的字典。
    """
    resp = requests.get(f"{API_URL}/api/analytics", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ============================================================
# 辅助函数
# ============================================================


def status_badge(status: str) -> str:
    """将工单状态转为带颜色的标记文本。

    Args:
        status: 工单状态字符串。

    Returns:
        格式化后的状态标记。
    """
    color_map: dict[str, str] = {
        "received": "blue",
        "classifying": "orange",
        "processing": "orange",
        "reviewing": "yellow",
        "completed": "green",
        "failed": "red",
    }
    color = color_map.get(status, "gray")
    label_map: dict[str, str] = {
        "received": "已接收",
        "classifying": "分类中",
        "processing": "处理中",
        "reviewing": "审核中",
        "completed": "已完成",
        "failed": "失败",
    }
    label = label_map.get(status, status)
    return f":{color}[**{label}**]"


def priority_badge(priority: str | None) -> str:
    """将优先级转为带颜色的标记。

    Args:
        priority: 优先级字符串。

    Returns:
        格式化后的优先级标记。
    """
    if not priority:
        return "-"
    color_map: dict[str, str] = {
        "P0": "red",
        "P1": "orange",
        "P2": "yellow",
        "P3": "green",
    }
    color = color_map.get(priority, "gray")
    return f":{color}[**{priority}**]"


def category_label(category: str | None) -> str:
    """将分类英文名转为中文。

    Args:
        category: 分类英文字符串。

    Returns:
        中文分类名。
    """
    label_map: dict[str, str] = {
        "technical": "技术支持",
        "billing": "账务问题",
        "complaint": "投诉建议",
        "inquiry": "咨询问询",
    }
    if not category:
        return "-"
    return label_map.get(category, category)


# ============================================================
# 页面组件
# ============================================================


def render_sidebar() -> None:
    """渲染左侧边栏：工单提交表单 + 工单列表（带过滤）。"""
    with st.sidebar:
        st.header("提交工单")

        # 工单提交表单
        with st.form("submit_ticket_form"):
            user_id = st.text_input("用户 ID", value="U001", max_chars=10)
            content = st.text_area("工单内容", placeholder="请描述您遇到的问题...", height=100)
            submitted = st.form_submit_button("提交工单", use_container_width=True)

            if submitted:
                if not content.strip():
                    st.error("工单内容不能为空")
                else:
                    try:
                        result = submit_ticket(content.strip(), user_id.strip())
                        st.success(f"工单已提交！工单 ID: `{result['ticket_id']}`")
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"提交失败: {e}")

        st.divider()

        # 过滤器
        st.header("工单列表")
        col_s, col_c = st.columns(2)
        with col_s:
            filter_status = st.selectbox(
                "状态",
                options=["全部", "received", "classifying", "processing", "reviewing", "completed", "failed"],
                format_func=lambda x: {
                    "全部": "全部",
                    "received": "已接收",
                    "classifying": "分类中",
                    "processing": "处理中",
                    "reviewing": "审核中",
                    "completed": "已完成",
                    "failed": "失败",
                }.get(x, x),
            )
        with col_c:
            filter_category = st.selectbox(
                "分类",
                options=["全部", "technical", "billing", "complaint", "inquiry"],
                format_func=lambda x: {
                    "全部": "全部",
                    "technical": "技术支持",
                    "billing": "账务问题",
                    "complaint": "投诉建议",
                    "inquiry": "咨询问询",
                }.get(x, x),
            )

        # 获取工单列表
        try:
            status_param = None if filter_status == "全部" else filter_status
            category_param = None if filter_category == "全部" else filter_category
            tickets = fetch_tickets(status=status_param, category=category_param)
        except requests.RequestException:
            tickets = []
            st.warning("无法连接后端服务")

        # 展示工单卡片列表
        if not tickets:
            st.info("暂无工单记录")
        else:
            for ticket in tickets:
                tid = ticket.get("ticket_id", "")
                t_status = ticket.get("status", "received")
                t_category = ticket.get("category")
                t_priority = ticket.get("priority")
                t_content = ticket.get("content", "")

                # 截断过长的工单内容
                display_content = t_content[:40] + "..." if len(t_content) > 40 else t_content

                # 每个工单以按钮形式展示，点击后在右侧显示详情
                if st.button(
                    f"{status_badge(t_status)} | {display_content}",
                    key=f"ticket_btn_{tid}",
                    use_container_width=True,
                ):
                    st.session_state["selected_ticket_id"] = tid


def render_ticket_detail() -> None:
    """渲染右侧工单详情区域。"""
    st.header("工单详情")

    selected_id = st.session_state.get("selected_ticket_id")
    if not selected_id:
        st.info("请在左侧工单列表中选择一个工单查看详情")
        return

    try:
        ticket = fetch_ticket_detail(selected_id)
    except requests.RequestException as e:
        st.error(f"获取工单详情失败: {e}")
        return

    # 基本信息卡片
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**工单 ID:** `{ticket.get('ticket_id', '')}`")
        st.markdown(f"**状态:** {status_badge(ticket.get('status', ''))}")
    with col_b:
        st.markdown(f"**分类:** {category_label(ticket.get('category'))}")
        st.markdown(f"**优先级:** {priority_badge(ticket.get('priority'))}")

    st.markdown(f"**创建时间:** {ticket.get('created_at', '-')}")

    st.divider()

    # 工单内容
    st.subheader("工单内容")
    st.text(ticket.get("content", ""))

    # 处理结果
    processing_result = ticket.get("processing_result")
    if processing_result:
        st.subheader("处理结果")
        st.markdown(processing_result)

    # 审核评分
    review_score = ticket.get("review_score")
    if review_score is not None:
        st.subheader("审核评分")
        score_pct = int(review_score * 100)
        st.progress(score_pct, text=f"评分: {score_pct}/100")

    # 错误信息
    error = ticket.get("error")
    if error:
        st.subheader("错误信息")
        st.error(error)

    # 重试次数
    retry_count = ticket.get("retry_count", 0)
    if retry_count > 0:
        st.caption(f"重试次数: {retry_count}")


def render_analytics_panel() -> None:
    """渲染底部统计面板：分类分布、优先级分布、处理统计。"""
    st.divider()
    st.header("统计面板")

    try:
        analytics = fetch_analytics()
    except requests.RequestException as e:
        st.warning(f"无法获取统计数据: {e}")
        return

    col_cat, col_pri, col_stats = st.columns(3)

    # 分类分布
    with col_cat:
        st.subheader("分类分布")
        cat_dist = analytics.get("category_distribution", {})
        if cat_dist:
            # 将英文分类名转为中文
            cat_labels: dict[str, str] = {
                "technical": "技术支持",
                "billing": "账务问题",
                "complaint": "投诉建议",
                "inquiry": "咨询问询",
            }
            display_cat = {
                cat_labels.get(k, k): v for k, v in cat_dist.items()
            }
            st.bar_chart(display_cat)
        else:
            st.info("暂无数据")

    # 优先级分布
    with col_pri:
        st.subheader("优先级分布")
        pri_dist = analytics.get("priority_distribution", {})
        if pri_dist:
            st.bar_chart(pri_dist)
        else:
            st.info("暂无数据")

    # 处理统计
    with col_stats:
        st.subheader("处理统计")
        res_stats = analytics.get("resolution_stats", {})
        if res_stats:
            total = res_stats.get("total", 0)
            completed = res_stats.get("completed", 0)
            failed = res_stats.get("failed", 0)
            avg_time = res_stats.get("avg_resolution_time", "-")

            st.metric("工单总数", total)
            st.metric("已完成", completed)
            st.metric("失败", failed)
            st.metric("平均处理时间", avg_time)
        else:
            st.info("暂无数据")


# ============================================================
# 主入口
# ============================================================


def main() -> None:
    """Streamlit 应用主入口。"""
    st.set_page_config(
        page_title="多Agent工单处理系统",
        page_icon="📋",
        layout="wide",
    )

    st.title("多Agent工单处理系统")

    # 左侧边栏
    render_sidebar()

    # 右侧主区域：工单详情
    render_ticket_detail()

    # 底部统计面板
    render_analytics_panel()


if __name__ == "__main__":
    main()
