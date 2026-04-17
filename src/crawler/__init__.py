def get_crawler():
    from .crawler import WebCrawler
    return WebCrawler()

def get_browser_crawler():
    from .crawler import BrowserCrawler
    return BrowserCrawler()
