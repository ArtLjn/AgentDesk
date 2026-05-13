"""搜索工具测试"""

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from src.basic_agents.tools.search import search, _parse_sse_response


class TestParseSSEResponse:
    """SSE 响应解析测试"""

    def test_valid_sse_response(self) -> None:
        """正常 SSE 流拼接"""
        raw = 'data: {"code":0,"data":{"data":{"part":"特朗普最近"}}}\ndata: {"code":0,"data":{"data":{"part":"在参加竞选活动"}}}\n'
        result = _parse_sse_response(raw)
        assert result == "特朗普最近在参加竞选活动"

    def test_empty_sse(self) -> None:
        """空响应返回提示"""
        result = _parse_sse_response("")
        assert "未返回有效结果" in result

    def test_no_data_field(self) -> None:
        """data 为 null 时返回提示"""
        raw = 'data: {"code":0,"data":null}\n'
        result = _parse_sse_response(raw)
        assert "未返回有效结果" in result

    def test_error_code(self) -> None:
        """错误码响应返回提示"""
        raw = 'data: {"code":400,"msg":"error"}\n'
        result = _parse_sse_response(raw)
        assert "未返回有效结果" in result

    def test_part_at_top_level(self) -> None:
        """part 字段在 data 顶层"""
        raw = 'data: {"code":0,"data":{"part":"直接part字段"}}\n'
        result = _parse_sse_response(raw)
        assert result == "直接part字段"


class TestSearch:
    """百度 LLM 搜索工具测试"""

    @patch("src.basic_agents.tools.search.urlopen")
    def test_search_success(self, mock_urlopen: MagicMock) -> None:
        """正常搜索返回结果"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            'data: {"code":0,"data":{"data":{"part":"Python是编程语言"}}}\n'.encode()
        )
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = search("Python")
        assert "Python" in result

    @patch("src.basic_agents.tools.search.urlopen")
    def test_search_no_results(self, mock_urlopen: MagicMock) -> None:
        """搜索无结果时返回提示"""
        mock_resp = MagicMock()
        mock_resp.read.return_value = "".encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = search("xyzabc123")
        assert "未返回有效结果" in result

    @patch("src.basic_agents.tools.search.urlopen")
    def test_search_network_error(self, mock_urlopen: MagicMock) -> None:
        """网络异常时返回错误提示"""
        mock_urlopen.side_effect = URLError("Connection refused")
        result = search("test")
        assert "搜索失败" in result

    def test_search_has_docstring(self) -> None:
        """函数有文档字符串"""
        assert search.__doc__ is not None
        assert "搜索" in search.__doc__
