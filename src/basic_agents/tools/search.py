"""DuckDuckGo 搜索工具，无需 API Key"""

import requests
from bs4 import BeautifulSoup
from loguru import logger

__all__ = ["search"]


def search(query: str) -> str:
    """搜索工具，使用DuckDuckGo搜索并返回前5条结果摘要

    Args:
        query: 搜索关键词
    Returns:
        搜索结果摘要字符串
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={query}"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for i, result in enumerate(soup.select(".result")[:5]):
            title_elem = result.select_one(".result__title")
            snippet_elem = result.select_one(".result__snippet")

            title = title_elem.get_text(strip=True) if title_elem else "无标题"
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else "无摘要"
            results.append(f"{i + 1}. {title}\n   {snippet}")

        if not results:
            return f"未找到与 '{query}' 相关的结果"

        return "\n\n".join(results)
    except requests.RequestException as e:
        logger.error(f"搜索请求失败: {e}")
        return f"搜索失败: {str(e)}"
    except Exception as e:
        logger.error(f"搜索解析失败: {e}")
        return f"搜索失败: {str(e)}"
