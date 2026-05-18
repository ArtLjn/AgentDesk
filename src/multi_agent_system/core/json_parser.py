"""LLM 响应 JSON 解析工具。

从 LLM 原始响应中提取 JSON，兼容 markdown 代码块包裹和控制字符。
"""

import json
import re

__all__ = ["parse_json_response"]


def parse_json_response(raw: str) -> dict:
    """从 LLM 响应中提取 JSON。

    兼容以下情况：
    - 响应被 ```json ... ``` 包裹
    - JSON 中含换行、制表符等控制字符

    Args:
        raw: LLM 原始响应文本

    Returns:
        解析后的字典

    Raises:
        json.JSONDecodeError: JSON 解析失败
    """
    # 尝试提取 ```json ... ``` 或 ``` ... ``` 中的内容
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    text = match.group(1).strip() if match else raw.strip()
    # 严格模式解析，自动处理控制字符（\n \t 等）
    return json.loads(text, strict=False)
