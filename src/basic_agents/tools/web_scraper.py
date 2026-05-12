"""网页抓取工具，提取网页正文内容"""

import requests
from bs4 import BeautifulSoup
from loguru import logger

__all__ = ["web_scraper"]

# 网页正文最大保留字符数
_MAX_CONTENT_LENGTH = 2000


def web_scraper(url: str) -> str:
    """网页抓取工具，提取网页正文内容

    Args:
        url: 要抓取的网页URL
    Returns:
        网页正文内容字符串（最多2000字）
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(url.strip(), headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, "html.parser")

        # 移除无关标签
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # 提取正文
        text = soup.get_text(separator="\n", strip=True)

        # 清理多余空行
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        content = "\n".join(lines)

        # 截断过长内容
        if len(content) > _MAX_CONTENT_LENGTH:
            content = content[:_MAX_CONTENT_LENGTH] + "\n... (内容已截断)"

        return content
    except requests.RequestException as e:
        logger.error(f"网页请求失败: {e}")
        return f"抓取失败: {str(e)}"
    except Exception as e:
        logger.error(f"网页解析失败: {e}")
        return f"抓取失败: {str(e)}"
