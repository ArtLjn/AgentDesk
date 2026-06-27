"""个人知识库文本处理工具。"""

__all__ = ["sanitize_text"]


def sanitize_text(text: str) -> str:
    """清洗输入文本中的 UTF-8 代理字符，避免编码错误。"""
    return text.encode("utf-8", errors="surrogatepass").decode(
        "utf-8", errors="replace"
    )
