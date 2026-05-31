"""
VCW Scraper 包
Provider + Pipeline 架构入口。

原 trend_scraper.py 中 2000+ 行的 God Object 已被拆分为：
  - 5 个 Provider（RSS / HTML / Playwright / GoogleNews / BaiduHot）
  - 3 个 Pipeline（Filter / Dedupe / Normalize）
  - 1 个共享工具层（utils.py）

TrendScraper 作为 Facade，保持 fetch_all() 对外接口完全不变。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import HttpClient
from .pipelines import FilterPipeline, DedupePipeline, NormalizePipeline
from .providers.rss_provider import RssProvider
from .providers.html_provider import HtmlProvider
from .providers.google_news_provider import GoogleNewsProvider
from .providers.baidu_hot_provider import BaiduHotProvider
from .providers.playwright_provider import SogouWechatProvider


class TrendScraper:
    """
    多数据源热点爬虫 Facade
    内部通过 Provider + Pipeline 架构实现，对外保持与原 TrendScraper 完全一致的接口。
    """

    def __init__(self, cache_path: str = "data/trend_cache.json", proxies: list = None):
        self.cache_path = Path(cache_path)
        self.cache = self._load_cache()
        self.http = HttpClient(proxies=proxies)

        # Providers（每个拥有独立的 timeout/retry 配置）
        self._providers = [
            RssProvider(self.http),
            HtmlProvider(self.http),
            GoogleNewsProvider(self.http),
            BaiduHotProvider(self.http),
            SogouWechatProvider(self.http),
        ]

    # ------------------ 缓存管理 ------------------

    def _load_cache(self) -> Dict:
        if self.cache_path.exists():
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"last_fetch": None, "trends": []}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    # ------------------ 主入口 ------------------

    def fetch_all(self, force: bool = False, on_progress=None,
                  include_expired: bool = False) -> List[Dict]:
        """
        聚合所有数据源并行爬取热点。
        与原 TrendScraper.fetch_all() 接口完全一致。
        """
        if not force and self.cache.get("last_fetch"):
            try:
                last = datetime.fromisoformat(self.cache["last_fetch"])
                cached_include_expired = self.cache.get("include_expired", False)
                if (datetime.now() - last).total_seconds() < 600 and cached_include_expired == include_expired:
                    print("[Scraper] 使用缓存数据（10分钟内已爬取过）")
                    return self.cache.get("trends", [])
            except (ValueError, TypeError, KeyError):
                pass

        rss_provider = self._providers[0]
        html_provider = self._providers[1]
        google_provider = self._providers[2]
        baidu_provider = self._providers[3]
        wechat_provider = self._providers[4]

        all_trends = []
        source_fns = [
            ("新闻网站", lambda: rss_provider.fetch_news() + html_provider.fetch_news()),  # type: ignore[attr-defined]
            ("Google News", lambda: google_provider.fetch()),
            ("RSS", lambda: rss_provider.fetch_rss_sources()),  # type: ignore[attr-defined]
            ("百度热搜", lambda: baidu_provider.fetch()),
            ("培训机构官网", lambda: html_provider.fetch_edu()),  # type: ignore[attr-defined]
            ("微信公众号", lambda: wechat_provider.fetch()),
        ]

        if on_progress:
            on_progress(0, len(source_fns), "启动多源并行爬取...")

        with ThreadPoolExecutor(max_workers=len(source_fns)) as executor:
            futures = {executor.submit(fn): name for name, fn in source_fns}
            for i, future in enumerate(as_completed(futures)):
                name = futures[future]
                try:
                    results = future.result(timeout=60)
                    print(f"[Scraper] {name} 获取 {len(results)} 条")
                    all_trends.extend(results)
                except Exception as e:
                    print(f"[Scraper] {name} 爬取失败: {e}")
                if on_progress:
                    on_progress(i + 1, len(source_fns), f"{name} 完成...")

        # --- Pipeline 处理 ---

        # 1. Normalize：补充时间 + 时效评分 + 排序
        if all_trends:
            normalize_pipeline = NormalizePipeline(max_workers=10)
            all_trends = normalize_pipeline.run(all_trends)

        # 2. Dedupe：URL 去重 + 标题相似度去重
        dedupe_pipeline = DedupePipeline(threshold=0.85)
        unique_trends = dedupe_pipeline.run(all_trends)

        # 3. Filter：教育过滤 + 过期过滤
        filter_pipeline = FilterPipeline(include_expired=include_expired)
        unique_trends = filter_pipeline.run(unique_trends)

        # 缓存
        self.cache["last_fetch"] = datetime.now().isoformat()
        self.cache["include_expired"] = include_expired
        self.cache["trends"] = unique_trends
        self._save_cache()

        if on_progress:
            on_progress(len(source_fns), len(source_fns), f"完成！共 {len(unique_trends)} 条有效热点")
        print(f"[Scraper] 爬取完成，共 {len(unique_trends)} 条有效热点")
        return unique_trends

    # ------------------ 便捷方法 ------------------

    def get_cached_trends(self) -> List[Dict]:
        """获取缓存的热点（含时效性评分）"""
        trends = self.cache.get("trends", [])
        normalize_pipeline = NormalizePipeline()
        return normalize_pipeline._sort_by_timeliness(trends)

    def add_manual_trend(self, title: str, summary: str = "", url: str = "",
                         published_at: str = "") -> Dict:
        """手动添加热点（绕过爬虫，直接录入）"""
        trend = {
            "title": title,
            "summary": summary[:200],
            "source": "手动录入",
            "url": url,
            "published_at": published_at,
            "fetched_at": datetime.now().isoformat(),
            "keyword": "",
            "relevance_score": 0,
            "_time_source": "manual" if published_at else "manual_pending",
            "is_manual": True,
        }
        self.cache["trends"] = [trend] + self.cache.get("trends", [])
        self._save_cache()
        return trend

    def fetch_url_directly(self, article_url: str) -> Optional[Dict]:
        """直接抓取单个URL的文章标题和内容"""
        html_provider = HtmlProvider(self.http)
        return html_provider.fetch_url_directly(article_url)


def fetch_trends(force: bool = False, include_expired: bool = False) -> List[Dict]:
    """便捷函数"""
    scraper = TrendScraper()
    return scraper.fetch_all(force=force, include_expired=include_expired)
