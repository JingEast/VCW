"""
Playwright Provider
通过搜狗微信搜索抓取公众号文章。
"""
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

from ..base import BaseProvider
from ..config import WECHAT_ACCOUNTS
from ..utils import RelevanceCalculator, classify_category


class SogouWechatProvider(BaseProvider):
    """搜狗微信搜索 Provider（Playwright 浏览器自动化）"""

    @property
    def name(self) -> str:
        return "微信公众号"

    def fetch(self, accounts: list = None, max_results: int = 10,
              max_pages: int = 2) -> List[Dict]:
        """通过搜狗微信搜索抓取公众号文章"""
        if not _PLAYWRIGHT_AVAILABLE:
            print("[SogouWechatProvider] Playwright未安装，跳过微信公众号抓取")
            return []

        if accounts is None:
            accounts = WECHAT_ACCOUNTS

        all_trends = []
        seen_titles = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                for account in accounts:
                    count = 0
                    encoded = urllib.parse.quote(account)

                    for pg in range(1, max_pages + 1):
                        try:
                            url = f"https://weixin.sogou.com/weixin?type=2&query={encoded}&page={pg}"
                            page.goto(url, timeout=30000)
                            page.wait_for_load_state("networkidle", timeout=30000)

                            results = page.query_selector_all('ul.news-list li')
                            if not results:
                                break

                            for result in results:
                                try:
                                    title_elem = result.query_selector('h3 a')
                                    if not title_elem:
                                        continue
                                    title = title_elem.inner_text().strip()
                                    if not title or len(title) <= 5:
                                        continue
                                    if title in seen_titles:
                                        continue
                                    seen_titles.add(title)

                                    href = title_elem.get_attribute('href') or ''
                                    if href.startswith('/'):
                                        article_url = f"https://weixin.sogou.com{href}"
                                    elif href.startswith('http'):
                                        article_url = href
                                    else:
                                        article_url = f"https://weixin.sogou.com/weixin?type=2&query={encoded}"

                                    summary_elem = result.query_selector('p.txt-info')
                                    summary = summary_elem.inner_text().strip() if summary_elem else ""

                                    time_elem = result.query_selector('.s2')
                                    pub_time = ""
                                    if time_elem:
                                        time_text = time_elem.inner_text().strip()
                                        pub_time = self._parse_sogou_time(time_text)

                                    source_elem = result.query_selector('a.account')
                                    item_source = source_elem.inner_text().strip() if source_elem else account

                                    all_trends.append({
                                        "title": title,
                                        "summary": summary[:200],
                                        "source": item_source,
                                        "url": article_url,
                                        "published_at": pub_time,
                                        "fetched_at": datetime.now().isoformat(),
                                        "keyword": account,
                                        "relevance_score": RelevanceCalculator.calc_relevance(title, summary),
                                        "_time_source": "sogou_wechat",
                                    })
                                    count += 1

                                    if count >= max_results:
                                        break
                                except (AttributeError, KeyError, IndexError):
                                    continue

                            if count >= max_results:
                                break

                        except Exception as e:
                            print(f"[SogouWechatProvider] 搜狗搜索页{pg}失败 {account}: {e}")
                            break

                    if count > 0:
                        print(f"[SogouWechatProvider] 搜狗-{account}: {count}条")

                browser.close()
        except Exception as e:
            print(f"[SogouWechatProvider] Playwright启动失败: {e}")

        for t in all_trends:
            t["category"] = classify_category(str(t.get("title", "")), str(t.get("summary", "")))

        print(f"[SogouWechatProvider] 微信公众号(搜狗)共获取 {len(all_trends)} 条")
        return all_trends

    @staticmethod
    def _parse_sogou_time(time_text: str) -> str:
        """解析搜狗搜索结果中的时间文本"""
        if not time_text:
            return ""
        m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', time_text)
        if m:
            try:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return datetime(year, month, day).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass
        now = datetime.now()
        if "今天" in time_text:
            return now.strftime("%Y-%m-%d %H:%M")
        m = re.search(r'(\d+)\s*天前', time_text)
        if m:
            days = int(m.group(1))
            return (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
        if "昨天" in time_text:
            return (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        return ""
