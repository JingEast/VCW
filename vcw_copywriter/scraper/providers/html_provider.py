"""
HTML Provider
处理 NEWS_SITES 中的 HTML 源 + EDU_SITES 培训机构官网 + 单个 URL 直接抓取。
包含所有站点专用解析器。
"""
import re
import urllib.parse
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from ..base import BaseProvider
from ..config import NEWS_SITES, EDU_SITES
from ..utils import TimeParser, RelevanceCalculator, classify_category


class HtmlProvider(BaseProvider):
    """HTML 页面抓取 Provider"""

    @property
    def name(self) -> str:
        return "HTML"

    def fetch(self) -> List[Dict]:
        """抓取所有 HTML 源（新闻网站 + 培训机构官网）"""
        return self.fetch_news() + self.fetch_edu()

    def fetch_news(self) -> List[Dict]:
        """抓取 NEWS_SITES 中的 HTML 源"""
        return self._fetch_news_sites()

    def fetch_edu(self) -> List[Dict]:
        """抓取 EDU_SITES 培训机构官网"""
        return self._fetch_edu_sites()

    # ------------------ 新闻网站 HTML ------------------

    def _fetch_news_sites(self, max_per_site: int = 15) -> List[Dict]:
        """并行抓取 NEWS_SITES 中的 HTML 类型站点"""
        html_sites = [s for s in NEWS_SITES if s.get("type") == "html"]  # type: ignore[attr-defined]
        if not html_sites:
            return []

        all_trends = []

        def _fetch_one(site: Dict) -> List[Dict]:
            try:
                parser_name = site.get("parser", "generic")
                parser_method = getattr(self, f"_parse_{parser_name}", self._parse_generic)
                trends = parser_method(site["url"], site["name"], max_per_site)
                for t in trends:
                    t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))
                print(f"[HtmlProvider] {site['name']} HTML获取 {len(trends)} 条")
                return trends
            except Exception as e:
                print(f"[HtmlProvider] {site['name']} 抓取失败: {e}")
                return []

        with ThreadPoolExecutor(max_workers=min(len(html_sites), 6)) as executor:
            results = list(executor.map(_fetch_one, html_sites))
            for r in results:
                all_trends.extend(r)

        print(f"[HtmlProvider] 新闻网站HTML共获取 {len(all_trends)} 条")
        return all_trends

    # ------------------ 培训机构官网 ------------------

    def _fetch_edu_sites(self, max_per_site: int = 5) -> List[Dict]:
        """并行抓取教育培训机构官网"""
        all_trends = []

        def _fetch_one(site: Dict) -> List[Dict]:
            try:
                html = self.http.fetch(site["url"], timeout=15)
                if not html:
                    return []
                trends = self._extract_from_html(html, site["name"], site["url"])
                before = len(trends)
                trends = [t for t in trends if RelevanceCalculator.is_education_related(t.get("title", ""))]
                if before > len(trends):
                    print(f"[HtmlProvider] {site['name']} 过滤非教育内容: {before} -> {len(trends)}")
                for t in trends:
                    t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))
                return trends
            except Exception as e:
                print(f"[HtmlProvider] {site['name']} 抓取失败: {e}")
                return []

        with ThreadPoolExecutor(max_workers=min(len(EDU_SITES), 5)) as executor:
            results = list(executor.map(_fetch_one, EDU_SITES))
            for r in results:
                all_trends.extend(r)

        print(f"[HtmlProvider] 培训机构官网共获取 {len(all_trends)} 条")
        return all_trends

    # ------------------ 通用 HTML 提取 ------------------

    def _extract_from_html(self, html: str, source_name: str, base_url: str) -> List[Dict]:
        """从 HTML 页面中提取新闻标题（通用 fallback）"""
        trends = []
        try:
            patterns = [
                r'<a[^>]*href="([^"]*)"[^>]*>([^<]{10,80})</a>',
                r'<h[23][^>]*>(.*?)</h[23]>',
                r'<div[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</div>',
            ]

            seen = set()
            for pattern in patterns:
                matches = re.findall(pattern, html, re.DOTALL)
                for match in matches:
                    if isinstance(match, tuple):
                        url, title = match
                        url = urllib.parse.urljoin(base_url, url)
                    else:
                        title = match
                        url = base_url

                    title = re.sub(r'<[^>]+>', '', title).strip()
                    if title and 10 < len(title) < 100 and title not in seen:
                        seen.add(title)
                        inferred = TimeParser.infer_date_from_text(title)
                        published_at = inferred.strftime("%Y-%m-%d %H:%M") if inferred else ""

                        trends.append({
                            "title": title,
                            "summary": "",
                            "source": source_name,
                            "url": url,
                            "published_at": published_at,
                            "fetched_at": datetime.now().isoformat(),
                            "keyword": "",
                            "relevance_score": RelevanceCalculator.calc_relevance(title, ""),
                            "_time_source": "title_inference",
                        })

                        if len(trends) >= 10:
                            break
                if len(trends) >= 10:
                    break
        except Exception as e:
            print(f"[HtmlProvider] HTML提取失败 {base_url}: {e}")

        return trends

    # ------------------ 站点专用解析器 ------------------

    def _parse_mingpao(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析明报教育版"""
        trends: List[Dict] = []
        html = self.http.fetch(url, timeout=15)
        if not html:
            return trends
        seen = set()
        patterns = [
            r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>',
            r'<a[^>]*href="(/pns/%E6%95%99%E8%82%B2/article/[^"]+)"[^>]*>.*?<h[23][^>]*>(.*?)</h[23]>',
            r'<div[^>]*class="[^"]*listing[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    href, title = match
                else:
                    continue
                title = re.sub(r'<[^>]+>', '', title).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title or len(title) < 10 or title in seen or len(title) > 120:
                    continue
                seen.add(title)
                if href.startswith('/'):
                    href = 'https://news.mingpao.com' + href
                elif not href.startswith('http'):
                    href = urllib.parse.urljoin(url, href)
                date_match = re.search(r'/article/(\d{8})/', href)
                published_at = ""
                time_source = "pending"
                if date_match:
                    d = date_match.group(1)
                    try:
                        dt = datetime(int(d[:4]), int(d[4:6]), int(d[6:8]))
                        published_at = dt.strftime("%Y-%m-%d %H:%M")
                        time_source = "url_date"
                    except ValueError:
                        pass
                trends.append({
                    "title": title, "summary": "", "source": source_name,
                    "url": href, "published_at": published_at,
                    "fetched_at": datetime.now().isoformat(), "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, ""),
                    "_time_source": time_source,
                })
                if len(trends) >= max_items:
                    break
            if len(trends) >= max_items:
                break
        return trends

    def _parse_mingpao_ins(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析明报即时教育版"""
        return self._parse_mingpao(url, source_name, max_items)

    def _parse_stheadline(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析星岛日报教育版"""
        trends: List[Dict] = []
        html = self.http.fetch(url, timeout=15)
        if not html:
            return trends
        seen = set()
        patterns = [
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*news-title[^"]*"[^>]*>(.*?)</a>',
            r'<div[^>]*class="[^"]*news-title[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            r'<h[23][^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h[23]>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    href, title = match[0], match[1]
                else:
                    continue
                title = re.sub(r'<[^>]+>', '', title).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title or len(title) < 10 or title in seen or len(title) > 120:
                    continue
                seen.add(title)
                if not href.startswith('http'):
                    href = urllib.parse.urljoin(url, href)
                trends.append({
                    "title": title, "summary": "", "source": source_name,
                    "url": href, "published_at": "",
                    "fetched_at": datetime.now().isoformat(), "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, ""),
                    "_time_source": "pending",
                })
                if len(trends) >= max_items:
                    break
            if len(trends) >= max_items:
                break
        return trends

    def _parse_hk01(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析香港01教育版"""
        trends: List[Dict] = []
        html = self.http.fetch(url, timeout=15)
        if not html:
            return trends
        seen = set()
        patterns = [
            r'<article[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?<h[234][^>]*>(.*?)</h[234]>.*?</article>',
            r'<a[^>]*href="(/article/[^"]+)"[^>]*>.*?<h[234][^>]*>(.*?)</h[234]>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    href, title = match[0], match[1]
                else:
                    continue
                title = re.sub(r'<[^>]+>', '', title).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title or len(title) < 10 or title in seen or len(title) > 120:
                    continue
                seen.add(title)
                if href.startswith('/'):
                    href = 'https://www.hk01.com' + href
                elif not href.startswith('http'):
                    href = urllib.parse.urljoin(url, href)
                trends.append({
                    "title": title, "summary": "", "source": source_name,
                    "url": href, "published_at": "",
                    "fetched_at": datetime.now().isoformat(), "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, ""),
                    "_time_source": "pending",
                })
                if len(trends) >= max_items:
                    break
            if len(trends) >= max_items:
                break
        return trends

    def _parse_tkww(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析大公文汇教育版"""
        trends: List[Dict] = []
        html = self.http.fetch(url, timeout=15)
        if not html:
            return trends
        seen = set()
        patterns = [
            r'<a[^>]*href="([^"]+)"[^>]*>.*?<h[234][^>]*>(.*?)</h[234]>.*?</a>',
            r'<div[^>]*class="[^"]*news-item[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    href, title = match[0], match[1]
                else:
                    continue
                title = re.sub(r'<[^>]+>', '', title).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title or len(title) < 10 or title in seen or len(title) > 120:
                    continue
                seen.add(title)
                if not href.startswith('http'):
                    href = urllib.parse.urljoin(url, href)
                trends.append({
                    "title": title, "summary": "", "source": source_name,
                    "url": href, "published_at": "",
                    "fetched_at": datetime.now().isoformat(), "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, ""),
                    "_time_source": "pending",
                })
                if len(trends) >= max_items:
                    break
            if len(trends) >= max_items:
                break
        return trends

    def _parse_wenweipo(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析文汇报教育版"""
        trends: List[Dict] = []
        html = self.http.fetch(url, timeout=15)
        if not html:
            return trends
        seen = set()

        patterns = [
            r'<a[^>]*href="(https://www\.wenweipo\.com/a/[^"]+)"[^>]*>([^<]{10,120})</a>',
            r'<a[^>]*href="(https://www\.wenweipo\.com/a/[^"]+)"[^>]*>.*?<span[^>]*>([^<]{10,120})</span>.*?</a>',
            r'<a[^>]*href="(https://www\.wenweipo\.com/a/[^"]+)"[^>]*>.*?</a>',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    href, title = match[0], match[1]
                elif isinstance(match, str):
                    href = match
                    idx = html.find(href)
                    nearby = html[max(0, idx-300):min(len(html), idx+300)]
                    title_match = re.search(r'>([^<]{15,100})<', nearby)
                    title = title_match.group(1) if title_match else ""
                else:
                    continue

                title = re.sub(r'<[^>]+>', '', title).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title or len(title) < 10 or title in seen or len(title) > 150:
                    continue
                seen.add(title)
                if not href.startswith('http'):
                    href = urllib.parse.urljoin(url, href)

                published_at = ""
                _time_source = "pending"
                date_match = re.search(r'/a/(\d{4})(\d{2})/(\d{2})/', href)
                if date_match:
                    try:
                        y, m, d = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                        published_at = f"{y:04d}-{m:02d}-{d:02d} 00:00"
                        _time_source = "url_date"
                    except ValueError:
                        pass

                summary = ""
                idx = html.find(href)
                if idx > 0:
                    nearby = html[max(0, idx-500):min(len(html), idx+500)]
                    desc_match = re.search(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>(.*?)</p>', nearby, re.DOTALL | re.IGNORECASE)
                    if desc_match:
                        summary = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()[:200]

                trends.append({
                    "title": title,
                    "summary": summary,
                    "source": source_name,
                    "url": href,
                    "published_at": published_at,
                    "fetched_at": datetime.now().isoformat(),
                    "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, summary),
                    "_time_source": _time_source,
                })
                if len(trends) >= max_items:
                    break
            if len(trends) >= max_items:
                break
        return trends

    def _parse_dotdotnews(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """解析点新闻教育版"""
        trends: List[Dict] = []
        html = self.http.fetch(url, timeout=15)
        if not html:
            return trends
        seen = set()

        patterns = [
            r'<a[^>]*href="(https://www\.dotdotnews\.com/a/[^"]+)"[^>]*>([^<]{10,120})</a>',
            r'<a[^>]*href="(https://www\.dotdotnews\.com/a/[^"]+)"[^>]*>.*?<h[234][^>]*>(.*?)</h[234]>.*?</a>',
            r'<a[^>]*href="(/a/[^"]+)"[^>]*>([^<]{10,120})</a>',
            r'<a[^>]*href="(/a/[^"]+)"[^>]*>.*?<h[234][^>]*>(.*?)</h[234]>.*?</a>',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    href, title = match[0], match[1]
                else:
                    continue
                title = re.sub(r'<[^>]+>', '', title).strip()
                title = re.sub(r'\s+', ' ', title)
                if not title or len(title) < 10 or title in seen or len(title) > 150:
                    continue
                seen.add(title)
                if not href.startswith('http'):
                    href = urllib.parse.urljoin(url, href)

                published_at = ""
                _time_source = "pending"
                date_match = re.search(r'/a/(\d{4})(\d{2})/(\d{2})/', href)
                if date_match:
                    try:
                        y, m, d = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                        published_at = f"{y:04d}-{m:02d}-{d:02d} 00:00"
                        _time_source = "url_date"
                    except ValueError:
                        pass

                summary = ""
                idx = html.find(href)
                if idx > 0:
                    nearby = html[max(0, idx-400):min(len(html), idx+400)]
                    desc_match = re.search(r'<p[^>]*>([^<]{20,300})</p>', nearby, re.DOTALL)
                    if desc_match:
                        summary = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()[:200]

                trends.append({
                    "title": title,
                    "summary": summary,
                    "source": source_name,
                    "url": href,
                    "published_at": published_at,
                    "fetched_at": datetime.now().isoformat(),
                    "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, summary),
                    "_time_source": _time_source,
                })
                if len(trends) >= max_items:
                    break
            if len(trends) >= max_items:
                break
        return trends

    def _parse_generic(self, url: str, source_name: str, max_items: int) -> List[Dict]:
        """通用新闻页面解析（fallback）"""
        return self._extract_from_html(self.http.fetch(url, timeout=15) or "", source_name, url)

    # ------------------ 单个 URL 直接抓取 ------------------

    def fetch_url_directly(self, article_url: str) -> Optional[Dict]:
        """直接抓取单个URL的文章标题和内容"""
        try:
            html = self.http.fetch(article_url, timeout=15)
            if not html:
                return None

            title = ""
            title_patterns = [
                r'<title[^>]*>(.*?)</title>',
                r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"',
                r'<meta[^>]*name="title"[^>]*content="([^"]+)"',
                r'<h1[^>]*>(.*?)</h1>',
            ]
            for pattern in title_patterns:
                m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                if m:
                    title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                    title = re.sub(r'\s+', ' ', title)
                    if title and len(title) > 5:
                        break

            summary = ""
            desc_patterns = [
                r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"',
                r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
            ]
            for pattern in desc_patterns:
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    summary = m.group(1).strip()
                    if summary:
                        break

            published_at = ""
            pub_patterns = [
                r'<meta[^>]*property="article:published_time"[^>]*content="([^"]+)"',
                r'<meta[^>]*name="publishdate"[^>]*content="([^"]+)"',
                r'<time[^>]*datetime="([^"]+)"',
            ]
            for pattern in pub_patterns:
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    dt = TimeParser.parse_datetime(m.group(1))
                    if dt:
                        published_at = dt.strftime("%Y-%m-%d %H:%M")
                        break
            domain = urllib.parse.urlparse(article_url).netloc

            if title:
                return {
                    "title": title, "summary": summary[:200], "source": domain,
                    "url": article_url, "published_at": published_at,
                    "fetched_at": datetime.now().isoformat(), "keyword": "",
                    "relevance_score": RelevanceCalculator.calc_relevance(title, summary),
                    "_time_source": "direct_url",
                }
        except Exception as e:
            print(f"[HtmlProvider] URL直接抓取失败 {article_url}: {e}")
        return None
