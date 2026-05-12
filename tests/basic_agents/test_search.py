"""搜索工具测试"""

from unittest.mock import MagicMock, patch

import pytest

from src.basic_agents.tools.search import search


class TestSearch:
    """DuckDuckGo 搜索工具测试"""

    @patch("src.basic_agents.tools.search.requests.get")
    def test_search_success(self, mock_get: MagicMock) -> None:
        """正常搜索返回结果"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <div class="result">
            <div class="result__title">Python教程</div>
            <div class="result__snippet">Python是一种编程语言</div>
        </div>
        """
        mock_get.return_value = mock_response

        result = search("Python")
        assert "Python教程" in result
        assert "编程语言" in result

    @patch("src.basic_agents.tools.search.requests.get")
    def test_search_no_results(self, mock_get: MagicMock) -> None:
        """搜索无结果时返回提示"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body></body></html>"
        mock_get.return_value = mock_response

        result = search("xyzabc123")
        assert "未找到" in result

    @patch("src.basic_agents.tools.search.requests.get")
    def test_search_network_error(self, mock_get: MagicMock) -> None:
        """网络异常时返回错误提示"""
        mock_get.side_effect = Exception("Network error")
        result = search("test")
        assert "搜索失败" in result

    def test_search_has_docstring(self) -> None:
        """函数有文档字符串"""
        assert search.__doc__ is not None
        assert "搜索" in search.__doc__
