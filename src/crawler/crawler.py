"""
Scrapling Crawler Module - Lazy import để tránh treo khi khởi động
"""
from typing import Optional


class WebCrawler:
    """Crawler sử dụng Scrapling - import lazy khi gọi"""

    def fetch(self, url: str, **kwargs) -> dict:
        try:
            from scrapling.fetchers import Fetcher
            page = Fetcher().get(url, **kwargs)
            return self._parse(url, page)
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}

    def fetch_stealth(self, url: str, **kwargs) -> dict:
        try:
            from scrapling.fetchers import StealthyFetcher
            page = StealthyFetcher.fetch(url, headless=True, **kwargs)
            return self._parse(url, page)
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}

    async def async_fetch(self, url: str, **kwargs) -> dict:
        try:
            from scrapling.fetchers import AsyncFetcher
            page = await AsyncFetcher().get(url, **kwargs)
            return self._parse(url, page)
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}

    def _parse(self, url: str, page) -> dict:
        try:
            title = page.find("title").text if page.find("title") else ""
        except Exception:
            title = ""
        try:
            text = page.get_all_text(ignore_tags=("script", "style"))
        except Exception:
            text = ""
        try:
            links = [a.attrib.get("href", "") for a in page.css("a[href]")]
        except Exception:
            links = []
        return {
            "success": True,
            "url": url,
            "status": getattr(page, "status", 200),
            "html": getattr(page, "html_content", ""),
            "text": text,
            "title": title,
            "links": [l for l in links if l],
        }

    def search_elements(self, html: str, css_selector: str) -> list:
        try:
            from scrapling import Adaptor
            page = Adaptor(html, url="http://dummy.com")
            return [el.text for el in page.css(css_selector)]
        except Exception as e:
            return [f"Error: {e}"]

    def extract_tables(self, url: str) -> list:
        result = self.fetch(url)
        if not result["success"]:
            return []
        try:
            from scrapling import Adaptor
            page = Adaptor(result["html"], url=url)
            tables = []
            for table in page.css("table"):
                headers = [th.text.strip() for th in table.css("th")]
                rows = [[td.text.strip() for td in tr.css("td")]
                        for tr in table.css("tr") if tr.css("td")]
                tables.append({"headers": headers, "rows": rows})
            return tables
        except Exception:
            return []


class BrowserCrawler:
    """Crawler dùng PlayWright để render JS"""

    def fetch_with_js(self, url: str, headless: bool = True) -> dict:
        try:
            from scrapling.fetchers import PlayWrightFetcher
            page = PlayWrightFetcher.fetch(
                url, headless=headless,
                network_idle=True, block_images=True
            )
            return {
                "success": True,
                "url": url,
                "html": getattr(page, "html_content", ""),
                "text": page.get_all_text(ignore_tags=("script", "style")),
                "title": page.find("title").text if page.find("title") else "",
            }
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}
