"""网页抓取工具测试"""

from unittest.mock import MagicMock, patch

import pytest

from archive.learning.basic_agents.tools.web_scraper import web_scraper


class TestWebScraper:
    """网页抓取工具测试"""

    @patch("archive.learning.basic_agents.tools.web_scraper.requests.get")
    def test_scrape_success(self, mock_get: MagicMock) -> None:
        """正常抓取网页内容"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        result = web_scraper("https://example.com")
        assert "Hello World" in result

    @patch("archive.learning.basic_agents.tools.web_scraper.requests.get")
    def test_scrape_removes_script_style(self, mock_get: MagicMock) -> None:
        """抓取时移除 script 和 style 标签"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "<html><body>"
            "<script>var x=1</script>"
            "<style>.a{}</style>"
            "<p>Content</p>"
            "</body></html>"
        )
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        result = web_scraper("https://example.com")
        assert "Content" in result
        assert "var x" not in result
        assert ".a{}" not in result

    @patch("archive.learning.basic_agents.tools.web_scraper.requests.get")
    def test_scrape_truncates_long_content(self, mock_get: MagicMock) -> None:
        """过长内容自动截断"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f"<html><body><p>{'A' * 3000}</p></body></html>"
        mock_response.apparent_encoding = "utf-8"
        mock_get.return_value = mock_response

        result = web_scraper("https://example.com")
        assert "截断" in result

    @patch("archive.learning.basic_agents.tools.web_scraper.requests.get")
    def test_scrape_network_error(self, mock_get: MagicMock) -> None:
        """网络异常时返回错误提示"""
        mock_get.side_effect = Exception("Connection refused")
        result = web_scraper("https://bad-url.com")
        assert "抓取失败" in result

    def test_scraper_has_docstring(self) -> None:
        """函数有文档字符串"""
        assert web_scraper.__doc__ is not None
        assert "网页" in web_scraper.__doc__
