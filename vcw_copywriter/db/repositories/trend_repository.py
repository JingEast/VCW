"""
Trend Repository
热点话题数据访问层，封装所有 SQLAlchemy 查询逻辑。
与原 TrendDatabase 的公共方法一一对应。
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from .base import BaseRepository
from ..models import Trend


class TrendRepository(BaseRepository):
    """热点话题 Repository"""

    ARCHIVE_DAYS = 90
    EXPIRED_DAYS = 365

    def __init__(self, session: Session):
        super().__init__(session, Trend)

    # ---------- 内部工具 ----------

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            pass
        formats = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip()[:len(fmt)], fmt)
            except ValueError:
                continue
        return None

    def _calc_timeliness_score(self, trend: Trend) -> int:
        published_at = trend.published_at
        if not published_at:
            return 30
        now = datetime.now()
        delta = now - published_at
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

    def _is_expired(self, trend: Trend) -> bool:
        if not trend.published_at:
            return False
        return (datetime.now() - trend.published_at).days > self.EXPIRED_DAYS

    def _is_stale(self, trend: Trend) -> bool:
        if not trend.published_at:
            return False
        return (datetime.now() - trend.published_at).days > self.ARCHIVE_DAYS

    # ---------- CRUD ----------

    def add(self, title: str, summary: str = "", source: str = "", url: str = "",  # type: ignore[override]
            category: str = "未分类", tags: List[str] = None,
            relevance_score: int = 50, click_count: int = 0,
            published_at: str = "", is_manual: bool = False,
            **extra_fields) -> Trend:
        import uuid
        trend = Trend(
            id=str(uuid.uuid4())[:8],
            title=title,
            summary=summary,
            source=source,
            url=url,
            category=category,
            tags=tags or [],
            relevance_score=relevance_score,
            click_count=click_count,
            is_manual=is_manual,
            published_at=self._parse_date(published_at),
            time_source=extra_fields.get("_time_source", ""),
            keyword=extra_fields.get("keyword", ""),
            fetched_at=self._parse_date(extra_fields.get("fetched_at", "")),
        )
        self.session.add(trend)
        self.session.commit()
        self.session.refresh(trend)
        return trend

    def add_manual(self, title: str, summary: str = "", url: str = "",
                   published_at: str = "", relevance_score: int = 80) -> Trend:
        return self.add(
            title=title, summary=summary, source="手动录入", url=url,
            relevance_score=relevance_score, published_at=published_at,
            is_manual=True, _time_source="manual" if published_at else "manual_pending",
        )

    def import_from_scraper(self, scraper_trends: List[Dict]) -> Tuple[int, int]:
        """从爬虫结果批量导入。返回 (added, skipped)"""
        deleted_old = self.delete_expired()
        if deleted_old > 0:
            print(f"[TrendRepository] 清理旧数据：删除 {deleted_old} 条过期热点")

        added = 0
        updated = 0
        skipped = 0

        def _normalize_url(url: str) -> str:
            if not url:
                return ""
            url = re.sub(r'[?&](utm_|fbclid|gclid|ref|source)=([^&]*)', '', url)
            return url.rstrip('?')

        for st in scraper_trends:
            st_url = _normalize_url(st.get("url", ""))
            st_title = st.get("title", "")
            published_at = st.get("published_at", "")
            dt = self._parse_date(published_at)
            if dt and (datetime.now() - dt).days > self.EXPIRED_DAYS:
                skipped += 1
                continue

            existing_by_url = None
            existing_by_title = None
            if st_url:
                existing_by_url = self.session.query(Trend).filter(
                    Trend.url.like(f"%{st_url}%")
                ).first()
            if not existing_by_url:
                existing_by_title = self.session.query(Trend).filter_by(title=st_title).first()

            if existing_by_url:
                existing_by_url.title = st_title
                existing_by_url.summary = st.get("summary", "")
                existing_by_url.source = st.get("source", "")
                existing_by_url.relevance_score = st.get("relevance_score", 50)
                existing_by_url.published_at = dt  # type: ignore[assignment]
                existing_by_url.time_source = st.get("_time_source", "")
                existing_by_url.fetched_at = self._parse_date(st.get("fetched_at", ""))  # type: ignore[assignment]
                existing_by_url.keyword = st.get("keyword", "")
                existing_by_url.category = st.get("category", "未分类")
                updated += 1
            elif existing_by_title:
                skipped += 1
            else:
                self.add(
                    title=st_title, summary=st.get("summary", ""),
                    source=st.get("source", ""), url=st.get("url", ""),
                    relevance_score=st.get("relevance_score", 50),
                    published_at=published_at,
                    _time_source=st.get("_time_source", ""),
                    fetched_at=st.get("fetched_at", ""),
                    keyword=st.get("keyword", ""),
                    category=st.get("category", "未分类"),
                )
                added += 1

        self.session.commit()
        print(f"[TrendRepository] 导入完成：新增 {added} 条，更新 {updated} 条，跳过 {skipped} 条")
        return added, skipped

    # ---------- 查询 ----------

    def get_all(self, limit: int = 100, offset: int = 0,  # type: ignore[override]
                time_filter: str = "all", sort_by: str = "composite",
                category_filter: str = "all") -> Tuple[List[Trend], int]:
        query = self.session.query(Trend).filter(~Trend.is_archived)

        if category_filter != "all":
            query = query.filter_by(category=category_filter)

        now = datetime.now()
        if time_filter != "all":
            if time_filter == "today":
                cutoff = now - timedelta(days=1)
                query = query.filter(
                    ((Trend.published_at >= cutoff) | (Trend.fetched_at >= cutoff))
                )
            elif time_filter == "week":
                cutoff = now - timedelta(days=7)
                query = query.filter(
                    ((Trend.published_at >= cutoff) | (Trend.fetched_at >= cutoff))
                )
            elif time_filter == "month":
                cutoff = now - timedelta(days=30)
                query = query.filter(
                    ((Trend.published_at >= cutoff) | (Trend.fetched_at >= cutoff))
                )
            elif time_filter == "stale":
                stale_cutoff = now - timedelta(days=self.ARCHIVE_DAYS)
                query = query.filter(Trend.published_at <= stale_cutoff)

        trends = query.all()

        # 计算运行时字段
        for t in trends:
            t.timeliness_score = self._calc_timeliness_score(t)  # type: ignore[assignment]
            if t.is_manual:
                t.timeliness_score = max(t.timeliness_score or 0, 85)  # type: ignore[arg-type]
            t.composite_score = (t.relevance_score or 0) * 0.55 + (t.timeliness_score or 0) * 0.45  # type: ignore[assignment]

        if sort_by == "time":
            trends.sort(key=lambda x: x.published_at or x.fetched_at or datetime.min, reverse=True)
        elif sort_by == "relevance":
            trends.sort(key=lambda x: x.relevance_score or 0, reverse=True)
        else:
            def _sort_key(t):
                score = t.composite_score or 0
                time_bonus = 5 if (t.time_source in ("rss", "google_news", "article_page", "url_date")) else 0
                return score + time_bonus
            trends.sort(key=_sort_key, reverse=True)

        total = len(trends)
        return trends[offset:offset + limit], total

    def get_recommended(self, limit: int = 10) -> List[Trend]:
        trends = self.session.query(Trend).filter(~Trend.is_archived).all()
        for t in trends:
            timeliness = self._calc_timeliness_score(t)
            click_bonus = min((t.click_count or 0) * 3, 20)
            manual_bonus = 15 if t.is_manual else 0
            t.composite_score = (t.relevance_score or 0) * 0.4 + timeliness * 0.4 + click_bonus + manual_bonus  # type: ignore[assignment]
            t.timeliness_score = timeliness  # type: ignore[assignment]
        trends.sort(key=lambda x: x.composite_score or 0, reverse=True)
        return trends[:limit]

    def get_fresh_hotspots(self, limit: int = 5) -> List[Trend]:
        trends = self.session.query(Trend).filter(~Trend.is_archived).all()
        fresh = []
        for t in trends:
            timeliness = self._calc_timeliness_score(t)
            if timeliness >= 80:
                t.timeliness_score = timeliness  # type: ignore[assignment]
                fresh.append(t)
        fresh.sort(key=lambda x: x.timeliness_score or 0, reverse=True)
        return fresh[:limit]

    def get_by_id(self, trend_id: str) -> Optional[Trend]:
        return self.session.query(Trend).filter_by(id=trend_id, is_archived=False).first()

    def select(self, trend_id: str) -> bool:
        trend = self.get_by_id(trend_id)
        if trend:
            trend.is_selected = True  # type: ignore[assignment]
            trend.click_count = (trend.click_count or 0) + 1  # type: ignore[assignment]
            trend.updated_at = datetime.now()  # type: ignore[assignment]
            self.session.commit()
            return True
        return False

    def delete(self, trend_id: str) -> bool:
        trend = self.get_by_id(trend_id)
        if trend:
            self.session.delete(trend)
            self.session.commit()
            return True
        return False

    def delete_expired(self) -> int:
        trends = self.session.query(Trend).filter(~Trend.is_archived).all()
        expired = [t for t in trends if self._is_expired(t)]
        for t in expired:
            self.session.delete(t)
        self.session.commit()
        if expired:
            print(f"[TrendRepository] 清理过期热点：删除 {len(expired)} 条")
        return len(expired)

    def delete_stale(self) -> int:
        trends = self.session.query(Trend).filter(~Trend.is_archived).all()
        stale = [t for t in trends if self._is_stale(t)]
        for t in stale:
            t.is_archived = True  # type: ignore[assignment]
        self.session.commit()
        if stale:
            print(f"[TrendRepository] 归档陈旧热点：{len(stale)} 条移入归档区")
        return len(stale)

    def auto_archive(self) -> int:
        return self.delete_stale()

    # ---------- 统计 ----------

    def generate_report(self) -> str:
        total = self.session.query(Trend).filter(~Trend.is_archived).count()
        archived = self.session.query(Trend).filter(Trend.is_archived).count()
        selected = self.session.query(Trend).filter(Trend.is_selected, ~Trend.is_archived).count()
        manual = self.session.query(Trend).filter(Trend.is_manual, ~Trend.is_archived).count()

        cat_counts = self.session.query(Trend.category, func.count(Trend.id)).filter(
            ~Trend.is_archived
        ).group_by(Trend.category).all()

        lines = [
            "=== 热点数据库统计 ===",
            f"活跃热点: {total} | 归档: {archived}",
            f"已选用: {selected} | 手动录入: {manual}",
            "",
            "分类分布:",
        ]
        for cat, cnt in sorted(cat_counts, key=lambda x: -x[1]):
            lines.append(f"  - {cat}: {cnt}条")
        return "\n".join(lines)
