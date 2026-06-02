"""
RSS Provider
处理 NEWS_SITES 中的 RSS 源 + RSS_SOURCES 独立订阅源。
"""

import re
import defusedxml.ElementTree as ET
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

from ..base import BaseProvider
from ..config import NEWS_SITES, RSS_SOURCES
from ..utils import TimeParser, RelevanceCalculator, classify_category


class RssProvider(BaseProvider):
    """RSS 订阅源 Provider"""

    @property
    def name(self) -> str:
        return "RSS"

    def fetch(self) -> List[Dict]:
        """抓取所有 RSS 源并返回热点列表"""
        return self.fetch_news() + self.fetch_rss_sources()

    def fetch_news(self) -> List[Dict]:
        """抓取 NEWS_SITES 中的 RSS 源"""
        all_results = []
        news_rss = [s for s in NEWS_SITES if s.get("type") == "rss"]  # type: ignore[attr-defined]
        for site in news_rss:
            trends = self._fetch_rss(site["url"], site["name"], max_items=15)  # type: ignore[index]
            if site.get("filter_edu"):  # type: ignore[attr-defined]
                before = len(trends)
                trends = [
                    t
                    for t in trends
                    if RelevanceCalculator.is_education_related(t.get("title", "") + " " + t.get("summary", ""))
                ]
                if before > len(trends):
                    print(f"[RssProvider] {site['name']} 过滤非教育内容: {before} -> {len(trends)}")  # type: ignore[index]
            for t in trends:
                t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))
            print(f"[RssProvider] {site['name']} RSS获取 {len(trends)} 条")  # type: ignore[index]
            all_results.extend(trends)
        return all_results

    def _fetch_rss(self, rss_url: str, source_name: str = "RSS", max_items: int = 10) -> List[Dict]:
        """抓取单个 RSS 订阅源"""
        trends: List[Dict] = []
        try:
            if "mingpao.com" in rss_url:
                raw = self.http.fetch_raw(rss_url, timeout=20)
                if raw:
                    rss_content = raw.decode("utf-8", errors="ignore")
                    rss_content = rss_content.replace("]></", "]]></")
                else:
                    return trends
            else:
                rss_content = self.http.fetch(rss_url, timeout=20)  # type: ignore[assignment]
            if not rss_content:
                return trends

            cleaned = rss_content
            for entity in [
                "&nbsp;",
                "&copy;",
                "&reg;",
                "&trade;",
                "&mdash;",
                "&ndash;",
                "&hellip;",
                "&laquo;",
                "&raquo;",
            ]:
                cleaned = cleaned.replace(entity, "")
            cleaned = re.sub(r"&#\d+;", "", cleaned)
            cleaned = re.sub(r"&#[xX][0-9a-fA-F]+;", "", cleaned)

            try:
                root = ET.fromstring(cleaned)
            except ET.ParseError:
                # nosec B112: fallback to HTML extraction
                return self._extract_from_html(rss_content, source_name, rss_url)

            items = []
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            if root.tag == "rss":
                channel = root.find("channel")
                if channel is not None:
                    items = channel.findall("item")
            elif root.tag.endswith("feed") or root.tag == "{http://www.w3.org/2005/Atom}feed":
                items = root.findall("atom:entry", ns)
                if not items:
                    items = root.findall("entry")

            for item in items[:max_items]:
                title_elem = item.find("title")
                title = title_elem.text if title_elem is not None and title_elem.text else ""
                if not title and title_elem is not None:
                    title = "".join(title_elem.itertext())
                if rss_url and "mingpao.com" in rss_url:
                    title = title.rstrip("]")

                desc_elem = item.find("description")
                if desc_elem is None:
                    desc_elem = item.find("summary")
                summary = ""
                if desc_elem is not None:
                    if desc_elem.text:
                        summary = desc_elem.text
                    else:
                        summary = "".join(desc_elem.itertext())

                url = ""
                link_elem = item.find("link")
                if link_elem is not None:
                    url = link_elem.get("href", "")
                    if not url and link_elem.text:
                        url = link_elem.text.strip()

                published_at = ""
                pubdate_elem = item.find("pubDate")
                if pubdate_elem is None:
                    pubdate_elem = item.find("published")
                if pubdate_elem is not None and pubdate_elem.text:
                    dt = TimeParser.parse_datetime(pubdate_elem.text)
                    if dt:
                        published_at = dt.strftime("%Y-%m-%d %H:%M")

                source_elem = item.find("source")
                item_source = source_name
                if source_elem is not None and source_elem.text:
                    item_source = source_elem.text

                if title and len(title) > 5:
                    time_source = "rss" if (pubdate_elem is not None and published_at) else "title_inference"
                    if not published_at:
                        inferred = TimeParser.infer_date_from_text(title + " " + summary)
                        if inferred:
                            published_at = inferred.strftime("%Y-%m-%d %H:%M")

                    trends.append(
                        {
                            "title": title.strip(),
                            "summary": summary[:200],
                            "source": item_source,
                            "url": url,
                            "published_at": published_at,
                            "fetched_at": datetime.now().isoformat(),
                            "keyword": "",
                            "relevance_score": RelevanceCalculator.calc_relevance(title, summary),
                            "_time_source": time_source,
                        }
                    )
        except Exception as e:
            print(f"[RssProvider] RSS 抓取失败 {rss_url}: {e}")

        return trends

    def fetch_rss_sources(self) -> List[Dict]:
        """并行抓取 RSS_SOURCES"""
        all_results = []

        def _fetch_one(rss: Dict) -> List[Dict]:
            try:
                r = self._fetch_rss(rss["url"], rss["name"], max_items=5)
                if rss.get("filter_edu"):
                    before = len(r)
                    r = [
                        t
                        for t in r
                        if RelevanceCalculator.is_education_related(t.get("title", "") + " " + t.get("summary", ""))
                    ]
                    if before > len(r):
                        print(f"[RssProvider] {rss['name']} 过滤非教育内容: {before} -> {len(r)}")
                for t in r:
                    t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))
                return r
            except Exception as e:
                print(f"[RssProvider] RSS 抓取失败 {rss['name']}: {e}")
                return []

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(_fetch_one, RSS_SOURCES))
            for r in results:
                all_results.extend(r)

        return all_results

    def _extract_from_html(self, html: str, source_name: str, base_url: str) -> List[Dict]:
        """从 HTML 页面中提取新闻标题（作为 RSS 的 fallback）"""
        trends = []
        try:
            patterns = [
                r'<a[^>]*href="([^"]*)"[^>]*>([^<]{10,80})</a>',
                r"<h[23][^>]*>(.*?)</h[23]>",
                r'<div[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</div>',
            ]

            seen = set()
            for pattern in patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                for match in matches:
                    if isinstance(match, tuple):
                        url, title = match
                        url = __import__("urllib.parse", fromlist=["urljoin"]).urljoin(base_url, url)
                    else:
                        title = match
                        url = base_url

                    title = re.sub(r"<[^>]+>", "", title).strip()
                    if title and 10 < len(title) < 100 and title not in seen:
                        seen.add(title)
                        inferred = TimeParser.infer_date_from_text(title)
                        published_at = inferred.strftime("%Y-%m-%d %H:%M") if inferred else ""

                        trends.append(
                            {
                                "title": title,
                                "summary": "",
                                "source": source_name,
                                "url": url,
                                "published_at": published_at,
                                "fetched_at": datetime.now().isoformat(),
                                "keyword": "",
                                "relevance_score": RelevanceCalculator.calc_relevance(title, ""),
                                "_time_source": "title_inference",
                            }
                        )

                        if len(trends) >= 10:
                            break
                if len(trends) >= 10:
                    break
        except Exception as e:
            print(f"[RssProvider] HTML提取失败 {base_url}: {e}")

        return trends
