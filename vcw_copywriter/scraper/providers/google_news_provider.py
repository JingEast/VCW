"""
Google News Provider
通过 Google News RSS 搜索获取教育新闻。
"""
import re
import urllib.parse
import defusedxml.ElementTree as ET
from datetime import datetime
from typing import List, Dict

from ..base import BaseProvider
from ..utils import TimeParser, RelevanceCalculator, classify_category


class GoogleNewsProvider(BaseProvider):
    """Google News RSS 搜索 Provider"""

    @property
    def name(self) -> str:
        return "Google News"

    def fetch(self, queries: list = None, max_results: int = 20) -> List[Dict]:
        """通过 Google News RSS 搜索获取教育新闻"""
        if queries is None:
            queries = [
                "DSE 香港 放榜 分数线 2026",
                "JUPAS 联招 港八大 录取 改选",
                "港澳台联考 报名 录取分数线",
                "香港中小学 插班 学位 派位",
                "港籍生 内地升学 政策 985",
                "港生 英国 澳洲 留学 升学",
                "考评局 教育局 公告 最新",
                "副学士 升读 港八大 港校",
                "香港 大学 排名 面试 招生",
                "DSE 选科 公民科 备考 2026",
                "港澳子弟学校 内地 政策",
                "直资学校 插班 Band1 中学",
            ]

        all_trends = []
        seen_urls = set()
        consecutive_failures = 0

        for q in queries:
            try:
                if consecutive_failures >= 2:
                    print(f"[GoogleNewsProvider] 连续失败{consecutive_failures}次，跳过剩余查询（网络不可达）")
                    break

                encoded = urllib.parse.quote(q)
                url = f"https://news.google.com/rss/search?q={encoded}&hl=zh-HK&gl=HK&ceid=HK:zh-Hant"

                rss_content = self.http.fetch(url, timeout=8)
                if not rss_content:
                    consecutive_failures += 1
                    continue
                consecutive_failures = 0

                cleaned = rss_content
                for entity in ["&nbsp;", "&copy;", "&reg;", "&trade;", "&mdash;", "&ndash;", "&hellip;"]:
                    cleaned = cleaned.replace(entity, "")
                cleaned = re.sub(r'&#\d+;', '', cleaned)
                cleaned = re.sub(r'&#[xX][0-9a-fA-F]+;', '', cleaned)

                try:
                    root = ET.fromstring(cleaned)
                except ET.ParseError:
                    continue  # nosec B112: RSS parse error is safe to skip

                items = []
                if root.tag == "rss":
                    channel = root.find("channel")
                    if channel is not None:
                        items = channel.findall("item")

                for item in items[:max_results]:
                    title_elem = item.find("title")
                    title = title_elem.text if title_elem is not None and title_elem.text else ""

                    desc_elem = item.find("description")
                    summary = ""
                    if desc_elem is not None:
                        summary = desc_elem.text or ""

                    link_elem = item.find("link")
                    url_val = ""
                    if link_elem is not None:
                        url_val = link_elem.get("href", "")
                        if not url_val and link_elem.text:
                            url_val = link_elem.text.strip()

                    pub_elem = item.find("pubDate")
                    published_at = ""
                    if pub_elem is not None and pub_elem.text:
                        dt = TimeParser.parse_datetime(pub_elem.text)
                        if dt:
                            published_at = dt.strftime("%Y-%m-%d %H:%M")

                    source_elem = item.find("source")
                    source_name = ""
                    if source_elem is not None:
                        source_name = source_elem.text or ""
                    if not source_name:
                        source_name = urllib.parse.urlparse(url_val).netloc

                    title = re.sub(r'<[^>]+>', '', title).strip()
                    summary = re.sub(r'<[^>]+>', '', summary).strip()

                    if not title or len(title) < 10 or url_val in seen_urls:
                        continue
                    if "news.google.com" in url_val and not source_name:
                        continue
                    seen_urls.add(url_val)

                    all_trends.append({
                        "title": title,
                        "summary": summary[:200],
                        "source": source_name,
                        "url": url_val,
                        "published_at": published_at,
                        "fetched_at": datetime.now().isoformat(),
                        "keyword": q,
                        "relevance_score": RelevanceCalculator.calc_relevance(title, summary),
                        "_time_source": "google_news",
                    })

            except Exception as e:
                print(f"[GoogleNewsProvider] 查询失败 '{q}': {e}")

        # 过滤低相关性
        before_filter = len(all_trends)
        all_trends = [t for t in all_trends if t.get("relevance_score", 0) >= 30]
        if before_filter > len(all_trends):
            print(f"[GoogleNewsProvider] 过滤低相关性: {before_filter} -> {len(all_trends)}")

        for t in all_trends:
            t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))
        print(f"[GoogleNewsProvider] 共获取 {len(all_trends)} 条")
        return all_trends
