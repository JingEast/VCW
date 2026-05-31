"""
Pipeline 层
filter_pipeline / dedupe_pipeline / normalize_pipeline
处理数据清洗、去重、评分、排序，与 Provider 解耦。
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Dict

from .utils import TimeParser, RelevanceCalculator, UrlUtils, classify_category
from .config import STALE_DAYS, EXPIRED_DAYS


class FilterPipeline:
    """
    过滤 Pipeline
    1. 教育相关过滤（计分制）
    2. 过期内容过滤
    3. 低相关性过滤（Google News 专用）
    """

    def __init__(self, include_expired: bool = False, min_relevance: int = 0):
        self.include_expired = include_expired
        self.min_relevance = min_relevance

    def run(self, trends: List[Dict]) -> List[Dict]:
        # 全局教育过滤
        before_edu = len(trends)
        trends = [t for t in trends if RelevanceCalculator.is_education_related(
            t.get("title", "") + " " + t.get("summary", "")
        )]
        if before_edu > len(trends):
            print(f"[FilterPipeline] 全局过滤非教育内容: {before_edu} -> {len(trends)}")

        # 低相关性过滤（如 Google News 的结果）
        if self.min_relevance > 0:
            before_rel = len(trends)
            trends = [t for t in trends if t.get("relevance_score", 0) >= self.min_relevance]
            if before_rel > len(trends):
                print(f"[FilterPipeline] 过滤低相关性: {before_rel} -> {len(trends)}")

        # 过期过滤
        if not self.include_expired:
            before = len(trends)
            trends = [t for t in trends if not self._is_expired(t)]
            if before > len(trends):
                print(f"[FilterPipeline] 过滤过期内容: {before} -> {len(trends)}")

        return trends

    @staticmethod
    def _is_expired(trend: Dict) -> bool:
        published_at = trend.get("published_at", "")
        if not published_at:
            return False
        dt = TimeParser.parse_datetime(published_at)
        if not dt:
            return False
        return (datetime.now() - dt).days > EXPIRED_DAYS


class DedupePipeline:
    """
    去重 Pipeline
    1. URL 精确去重（保留高相关性 / 可靠时间来源的版本）
    2. 标题 2-gram 相似度去重（阈值 0.85）
    """

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def run(self, trends: List[Dict]) -> List[Dict]:
        reliable_sources = ("rss", "google_news", "article_page", "url_date", "direct_url", "manual")
        unique: List[Dict] = []
        seen_urls = set()

        for t in trends:
            title = t.get("title", "")
            url = UrlUtils.normalize_url(t.get("url", ""))

            # 第一层：URL精确去重
            if url and url in seen_urls:
                for u in unique:
                    if UrlUtils.normalize_url(u.get("url", "")) == url:
                        if t.get("relevance_score", 0) > u.get("relevance_score", 0):
                            u_pa, u_ts = u.get("published_at"), u.get("_time_source")
                            u_reliable = u_ts in reliable_sources and bool(u_pa)
                            t_reliable = t.get("_time_source") in reliable_sources and bool(t.get("published_at"))
                            u.update(t)
                            if u_reliable and not t_reliable:
                                u["published_at"] = u_pa
                                u["_time_source"] = u_ts
                            elif not t.get("published_at") and u_pa:
                                u["published_at"] = u_pa
                                u["_time_source"] = u_ts
                        break
                continue

            if url:
                seen_urls.add(url)

            # 第二层：标题相似度去重
            is_duplicate = False
            for u in unique:
                sim = UrlUtils.title_similarity(title, u.get("title", ""))
                if sim >= self.threshold:
                    is_duplicate = True
                    if t.get("relevance_score", 0) > u.get("relevance_score", 0):
                        u_pa, u_ts = u.get("published_at"), u.get("_time_source")
                        u_reliable = u_ts in reliable_sources and bool(u_pa)
                        t_reliable = t.get("_time_source") in reliable_sources and bool(t.get("published_at"))
                        u.update(t)
                        if u_reliable and not t_reliable:
                            u["published_at"] = u_pa
                            u["_time_source"] = u_ts
                        elif not t.get("published_at") and u_pa:
                            u["published_at"] = u_pa
                            u["_time_source"] = u_ts
                    break
            if not is_duplicate:
                unique.append(t)

        return unique


class NormalizePipeline:
    """
    标准化 Pipeline
    1. 补充/丰富发布时间（enrich_publish_times）
    2. 计算时效性评分
    3. 标记陈旧内容
    4. 综合排序（相关度 60% + 时效性 40%）
    """

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers

    def run(self, trends: List[Dict]) -> List[Dict]:
        if not trends:
            return trends

        # 先分配 category
        for t in trends:
            if not t.get("category") or t.get("category") == "未分类":
                t["category"] = classify_category(t.get("title", ""), t.get("summary", ""))

        # 丰富发布时间
        trends = self._enrich_publish_times(trends)

        # 标记陈旧
        for t in trends:
            t["is_stale"] = self._is_stale(t)

        # 排序
        return self._sort_by_timeliness(trends)

    # ----------  enrich_publish_times  ----------

    def _enrich_publish_times(self, trends: List[Dict]) -> List[Dict]:
        def _needs_enrich(t: Dict) -> bool:
            if not t.get("published_at"):
                return True
            if t.get("_time_source") in ("today", "pending"):
                return True
            if t.get("_time_source") == "title_inference":
                return True
            if t.get("_time_source") == "url_date":
                pt = t.get("published_at", "")
                if pt.endswith(" 00:00"):
                    return True
            if not t.get("_time_source"):
                return True
            return False

        needs_enrich_list = [t for t in trends if _needs_enrich(t)]
        if not needs_enrich_list:
            return trends

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            list(executor.map(self._fetch_one, needs_enrich_list))

        return trends

    def _fetch_one(self, trend: Dict) -> Dict:
        from .base import HttpClient
        http = HttpClient()

        url = trend.get("url", "")
        if not url or not url.startswith("http"):
            inferred = TimeParser.infer_date_from_text(trend.get("title", ""), trend.get("summary", ""))
            if inferred:
                trend["published_at"] = inferred.strftime("%Y-%m-%d %H:%M")
                trend["_time_source"] = "title_inference"
            return trend

        if "duckduckgo.com/l/?" in url and "uddg=" in url:
            url = UrlUtils.extract_real_url(url)

        if "news.google.com/rss/articles/" in url:
            inferred = TimeParser.infer_date_from_text(trend.get("title", ""), trend.get("summary", ""))
            if inferred:
                trend["published_at"] = inferred.strftime("%Y-%m-%d %H:%M")
                trend["_time_source"] = "title_inference"
            return trend

        old_source = trend.get("_time_source", "")
        old_pt = trend.get("published_at", "")
        needs_precise_time = (old_source == "url_date" and old_pt.endswith(" 00:00"))

        if not needs_precise_time:
            url_date = TimeParser.extract_date_from_url(url)
            if url_date:
                trend["published_at"] = url_date.strftime("%Y-%m-%d %H:%M")
                trend["_time_source"] = "url_date"
                return trend

        try:
            html = http.fetch(url, timeout=8)
            if html:
                pt = TimeParser.extract_publish_time_from_html(html)
                if pt:
                    if old_pt:
                        try:
                            old_dt = TimeParser.parse_datetime(old_pt)
                            new_dt = TimeParser.parse_datetime(pt)
                            if needs_precise_time:
                                trend["published_at"] = pt
                                trend["_time_source"] = "article_page"
                            elif old_dt and new_dt and abs((old_dt - new_dt).days) > 1:
                                trend["published_at"] = pt
                                trend["_time_source"] = "article_page"
                        except Exception:
                            trend["published_at"] = pt
                            trend["_time_source"] = "article_page"
                    else:
                        trend["published_at"] = pt
                        trend["_time_source"] = "article_page"
                else:
                    if not old_pt:
                        url_date = TimeParser.extract_date_from_url(url)
                        if url_date:
                            trend["published_at"] = url_date.strftime("%Y-%m-%d %H:%M")
                            trend["_time_source"] = "url_date"
                        else:
                            inferred = TimeParser.infer_date_from_text(trend.get("title", ""), trend.get("summary", ""))
                            if inferred:
                                trend["published_at"] = inferred.strftime("%Y-%m-%d %H:%M")
                                trend["_time_source"] = "title_inference"
            else:
                if not old_pt:
                    url_date = TimeParser.extract_date_from_url(url)
                    if url_date:
                        trend["published_at"] = url_date.strftime("%Y-%m-%d %H:%M")
                        trend["_time_source"] = "url_date"
                    else:
                        inferred = TimeParser.infer_date_from_text(trend.get("title", ""), trend.get("summary", ""))
                        if inferred:
                            trend["published_at"] = inferred.strftime("%Y-%m-%d %H:%M")
                            trend["_time_source"] = "title_inference"
        except Exception as e:
            if not old_pt:
                url_date = TimeParser.extract_date_from_url(url)
                if url_date:
                    trend["published_at"] = url_date.strftime("%Y-%m-%d %H:%M")
                    trend["_time_source"] = "url_date"
                else:
                    inferred = TimeParser.infer_date_from_text(trend.get("title", ""), trend.get("summary", ""))
                    if inferred:
                        trend["published_at"] = inferred.strftime("%Y-%m-%d %H:%M")
                        trend["_time_source"] = "title_inference"
                    else:
                        print(f"[NormalizePipeline] 获取文章发布时间失败 {url[:60]}: {e}")
        return trend

    # ----------  stale / timeliness  ----------

    @staticmethod
    def _is_stale(trend: Dict) -> bool:
        published_at = trend.get("published_at", "")
        if not published_at:
            return False
        dt = TimeParser.parse_datetime(published_at)
        if not dt:
            return False
        return (datetime.now() - dt).days > STALE_DAYS

    @staticmethod
    def _calc_timeliness_score(trend: Dict) -> int:
        published_at = trend.get("published_at", "")
        if not published_at:
            inferred = TimeParser.infer_date_from_text(trend.get("title", ""), trend.get("summary", ""))
            if inferred:
                published_at = inferred.strftime("%Y-%m-%d %H:%M")
            else:
                return 50

        dt = TimeParser.parse_datetime(published_at)
        if not dt:
            return 30

        now = datetime.now()
        delta = now - dt

        if delta.days < 0:
            return 80
        if delta.days <= 1:
            return 100
        if delta.days <= 3:
            return 90
        if delta.days <= 7:
            return 80
        if delta.days <= 14:
            return 65
        if delta.days <= 30:
            return 50
        if delta.days <= 60:
            return 35
        if delta.days <= 90:
            return 20
        return 10

    def _sort_by_timeliness(self, trends: List[Dict]) -> List[Dict]:
        for t in trends:
            relevance = t.get("relevance_score", 50)
            timeliness = self._calc_timeliness_score(t)
            t["composite_score"] = relevance * 0.6 + timeliness * 0.4
            t["timeliness_score"] = timeliness
        trends.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        return trends
