"""
Provider 基类与 HTTP 客户端
"""

import time
import urllib.request
import urllib.parse
from typing import List, Dict, Optional


class HttpClient:
    """共享 HTTP 客户端，封装重试、代理、编码等逻辑。"""

    def __init__(self, proxies: list = None):
        self.proxies = proxies or []
        self._proxy_index = 0
        self._stop_requested = False
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh-HK;q=0.9,en;q=0.8",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    def _get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self._proxy_index]
        self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
        return proxy

    def fetch_with_retry(
        self, url: str, timeout: int = 15, max_retries: int = 3, headers: dict = None
    ) -> Optional[str]:
        """发送 HTTP GET 请求（支持代理和重试），返回 UTF-8 文本。"""
        if self._stop_requested:
            return None

        try:
            url.encode("ascii")
        except UnicodeEncodeError:
            parsed = urllib.parse.urlparse(url)
            safe_path = urllib.parse.quote(parsed.path, safe="/")
            safe_query = urllib.parse.quote(parsed.query, safe="&=")
            safe_fragment = urllib.parse.quote(parsed.fragment, safe="")
            url = urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, safe_path, parsed.params, safe_query, safe_fragment)
            )

        last_error = ""
        req_headers = headers or self.headers

        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=req_headers)
                proxy = self._get_proxy()
                if proxy:
                    proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                    opener = urllib.request.build_opener(proxy_handler)
                else:
                    opener = urllib.request.build_opener()

                with opener.open(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        return resp.read().decode("utf-8", errors="ignore")
                    elif resp.status in (403, 429):
                        wait = 2 ** (attempt + 2)
                        print(f"[HttpClient] 状态码 {resp.status}，{wait}秒后重试...")
                        time.sleep(wait)
                        continue
                    else:
                        return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    print(f"[HttpClient] 请求失败（{e}），{wait}秒后重试...")
                    time.sleep(wait)
                continue

        print(f"[HttpClient] 请求失败（重试{max_retries}次）{url}: {last_error}")
        return None

    def fetch(self, url: str, timeout: int = 15) -> Optional[str]:
        return self.fetch_with_retry(url, timeout=timeout, max_retries=3)

    def fetch_raw(self, url: str, timeout: int = 15, max_retries: int = 3) -> Optional[bytes]:
        """获取原始字节（用于需要自定义解码的场景）"""
        if self._stop_requested:
            return None
        last_error = ""
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                proxy = self._get_proxy()
                if proxy:
                    proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                    opener = urllib.request.build_opener(proxy_handler)
                else:
                    opener = urllib.request.build_opener()
                with opener.open(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        return resp.read()
                    elif resp.status in (403, 429):
                        wait = 2 ** (attempt + 2)
                        print(f"[HttpClient] 状态码 {resp.status}，{wait}秒后重试...")
                        time.sleep(wait)
                        continue
                    else:
                        return resp.read()
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait = 2**attempt
                    print(f"[HttpClient] 请求失败（{e}），{wait}秒后重试...")
                    time.sleep(wait)
                continue
        print(f"[HttpClient] 请求失败（重试{max_retries}次）{url}: {last_error}")
        return None

    def request_stop(self):
        self._stop_requested = True


class BaseProvider:
    """
    数据源 Provider 基类。
    子类只需实现 name 属性和 fetch() 方法。
    """

    def __init__(self, http_client: HttpClient = None):
        self.http = http_client or HttpClient()

    @property
    def name(self) -> str:
        raise NotImplementedError

    def fetch(self) -> List[Dict]:
        """获取热点列表。子类必须实现。"""
        raise NotImplementedError
