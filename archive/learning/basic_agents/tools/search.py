"""百度 LLM 搜索工具，国内网络可用"""

import json
import os
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from loguru import logger

__all__ = ["search"]

# 百度 LLM 配置（通过环境变量注入）
_BASE_URL = os.getenv(
    "BAIDU_LLM_BASE_URL",
    "https://openapi-iot.baidu.com/inside-api/resource/llm",
)
_APPID = os.getenv("BAIDU_LLM_APPID", "speech2")
_DIRECT_AUTH = os.getenv(
    "BAIDU_LLM_AUTH",
    "2fdcf365887b20318c53b8d3b907a25b:1763975200763",
)
_REQUEST_TIMEOUT = int(os.getenv("BAIDU_LLM_TIMEOUT", "30"))
_QUERY_PREFIX = "请用80字以内简洁回答以下问题："


def _extract_part(data: Any) -> str:
    """从响应 data 字段中提取 part 文本"""
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict):
            return str(inner.get("part", ""))
        if "part" in data:
            return str(data["part"])
    return ""


def _parse_sse_response(raw: str) -> str:
    """解析 SSE 流式响应，拼接所有 part 片段"""
    parts: list[str] = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("data"):
            continue
        json_str = line[5:] if line.startswith("data:") else line[4:]
        json_str = json_str.strip()
        if not json_str:
            continue
        try:
            body = json.loads(json_str)
        except json.JSONDecodeError:
            continue
        if body.get("code") == 0 and body.get("data") is not None:
            part = _extract_part(body["data"])
            if part:
                parts.append(part)
    return "".join(parts) if parts else "百度搜索未返回有效结果"


def _call_baidu_llm(query: str) -> str:
    """调用百度 LLM 接口（带 web_search），返回回答文本"""
    if not _DIRECT_AUTH:
        return "百度搜索不可用：未配置凭证"

    prompt = _QUERY_PREFIX + query
    messages = [{"role": "user", "content": prompt}]
    body = json.dumps(
        {
            "stream": True,
            "messages": messages,
            "temperature": 0.7,
            "web_search": {"enable": True},
        },
        ensure_ascii=False,
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": _DIRECT_AUTH,
        "APPID": _APPID,
    }

    logger.debug(f"百度LLM请求: query={query[:50]}...")

    start_time = time.time()
    try:
        req = Request(_BASE_URL, data=body.encode("utf-8"), headers=headers)
        with urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
    except (URLError, OSError) as e:
        elapsed = time.time() - start_time
        logger.error(f"百度LLM请求失败: elapsed={elapsed:.2f}s, error={e}")
        return f"搜索失败: {e}"

    elapsed = time.time() - start_time
    logger.debug(f"百度LLM响应: elapsed={elapsed:.2f}s, length={len(raw)}")

    return _parse_sse_response(raw)


def search(query: str) -> str:
    """搜索工具，调用百度 LLM（带联网搜索）获取实时信息

    Args:
        query: 搜索关键词
    Returns:
        搜索结果字符串
    """
    try:
        result = _call_baidu_llm(query)
        logger.info(f"搜索结果: {result[:100]}...")
        return result
    except Exception as e:
        logger.error(f"搜索异常: {e}")
        return f"搜索失败: {str(e)}"
