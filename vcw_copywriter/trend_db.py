"""
热点数据库模块 v3.0 — PostgreSQL Repository Pattern 适配器

对外接口与 v2.0 完全一致，内部通过 TrendRepository 操作 SQLAlchemy ORM。
JSON 文件保留作为本地缓存/备份，启动时若数据库为空则自动从 JSON 迁移。
"""
import json
import uuid
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import List, Dict, Optional


class TrendDatabase:
    """热点话题数据库（含时效性管理）— Repository 适配器"""

    ARCHIVE_DAYS = 90
    EXPIRED_DAYS = 365

    def __init__(self, db_path: str = "data/trend_db.json"):
        self.db_path = Path(db_path)
        # 初始化数据库表
        from .db.session import init_db, get_session
        from .db.repositories.trend_repository import TrendRepository
        init_db()
        self._repo = TrendRepository(get_session())
        # 加载数据（优先数据库，回退 JSON）
        self.data = self._load()
        self._ensure_structure()
        self._auto_archive()

    # ------------------ 加载 / 保存 ------------------

    def _load(self) -> Dict:
        # 优先从数据库加载
        from .db.models import Trend
        trends_orm = self._repo.session.query(Trend).filter_by(is_archived=False).all()
        archived_orm = self._repo.session.query(Trend).filter_by(is_archived=True).all()

        if trends_orm or archived_orm:
            # 数据库已有数据，直接使用
            trends = [t.to_dict() for t in trends_orm]
            archived = [t.to_dict() for t in archived_orm]
            return {
                "trends": trends,
                "archived": archived,
                "categories": self._build_categories(trends),
                "tags_index": self._build_tags_index(trends),
            }

        # 数据库为空，从 JSON 回退
        if self.db_path.exists():
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 同步到数据库（一次性迁移）
            self._sync_json_to_db(data)
            return data

        return {
            "trends": [],
            "archived": [],
            "categories": {},
            "tags_index": {},
        }

    def _save(self):
        """保存到 JSON 并同步到数据库（Thread-safe）"""
        from filelock import FileLock
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(self.db_path) + ".lock")
        with lock:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        self._sync_to_db()

    def _sync_json_to_db(self, data: Dict):
        """一次性将 JSON 数据全量导入数据库（用于首次迁移）"""
        from .db.models import Trend
        trends = []
        for t_dict in data.get("trends", []):
            trend = Trend.from_dict(t_dict)
            trend.is_archived = False  # type: ignore[assignment]
            trends.append(trend)
        for t_dict in data.get("archived", []):
            trend = Trend.from_dict(t_dict)
            trend.is_archived = True  # type: ignore[assignment]
            trends.append(trend)
        if trends:
            self._repo.session.bulk_save_objects(trends)
            self._repo.session.commit()
        print(f"[TrendDB] JSON → 数据库迁移完成: {len(trends)} 条活跃 + {len(data.get('archived', []))} 条归档")

    def _sync_to_db(self):
        """增量同步内存数据到数据库"""
        from .db.models import Trend
        existing = {t.id: t for t in self._repo.session.query(Trend).all()}
        current_ids = set()

        for t_dict in self.data.get("trends", []):
            tid = t_dict.get("id")
            current_ids.add(tid)
            if tid in existing:
                self._update_orm_from_dict(existing[tid], t_dict)
                existing[tid].is_archived = False
            else:
                trend = Trend.from_dict(t_dict)
                trend.is_archived = False
                self._repo.session.add(trend)

        for t_dict in self.data.get("archived", []):
            tid = t_dict.get("id")
            current_ids.add(tid)
            if tid in existing:
                self._update_orm_from_dict(existing[tid], t_dict)
                existing[tid].is_archived = True
            else:
                trend = Trend.from_dict(t_dict)
                trend.is_archived = True
                self._repo.session.add(trend)

        # 删除数据库中已不存在的记录
        for tid, t_orm in existing.items():
            if tid not in current_ids:
                self._repo.session.delete(t_orm)

        self._repo.session.commit()

    @staticmethod
    def _update_orm_from_dict(trend_orm, t_dict: Dict):
        """用字典更新 ORM 实例字段（不覆盖 id/created_at）"""
        from .scraper.utils import TimeParser
        trend_orm.title = t_dict.get("title", "")
        trend_orm.summary = t_dict.get("summary", "")
        trend_orm.source = t_dict.get("source", "")
        trend_orm.url = t_dict.get("url", "")
        trend_orm.category = t_dict.get("category", "未分类")
        trend_orm.tags = t_dict.get("tags") or []
        trend_orm.relevance_score = t_dict.get("relevance_score", 50)
        trend_orm.click_count = t_dict.get("click_count", 0)
        trend_orm.is_selected = bool(t_dict.get("is_selected"))
        trend_orm.is_manual = bool(t_dict.get("is_manual"))
        trend_orm.time_source = t_dict.get("_time_source", "")
        trend_orm.keyword = t_dict.get("keyword", "")
        pa = t_dict.get("published_at", "")
        trend_orm.published_at = TimeParser.parse_datetime(pa) if pa else None
        fa = t_dict.get("fetched_at", "")
        trend_orm.fetched_at = TimeParser.parse_datetime(fa) if fa else None
        ua = t_dict.get("updated_at", "")
        trend_orm.updated_at = TimeParser.parse_datetime(ua) if ua else datetime.utcnow()

    def _build_categories(self, trends: List[Dict]) -> Dict:
        cats: Dict[str, List[str]] = {}
        for t in trends:
            cat = t.get("category", "未分类")
            if cat not in cats:
                cats[cat] = []
            cats[cat].append(t["id"])
        return cats

    def _build_tags_index(self, trends: List[Dict]) -> Dict:
        idx: Dict[str, List[str]] = {}
        for t in trends:
            for tag in t.get("tags", []):
                if tag not in idx:
                    idx[tag] = []
                idx[tag].append(t["id"])
        return idx

    def _ensure_structure(self):
        if "archived" not in self.data:
            self.data["archived"] = []
        if "categories" not in self.data:
            self.data["categories"] = {}
        if "tags_index" not in self.data:
            self.data["tags_index"] = {}
        self._repair_time_sources()

    def _repair_time_sources(self):
        repaired = 0
        for t in self.data.get("trends", []):
            if t.get("_time_source"):
                continue
            pa = t.get("published_at", "")
            fa = t.get("fetched_at", "") or t.get("created_at", "")
            if not pa:
                t["_time_source"] = "pending"
            elif fa and pa[:10] == fa[:10]:
                t["_time_source"] = "today"
            else:
                t["_time_source"] = "unknown"
            repaired += 1
        if repaired > 0:
            self._save()
            print(f"[TrendDB] 修复 {repaired} 条旧数据的时间来源标记")

    # ------------------ 时效性工具 ------------------

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
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

    def _calc_timeliness_score(self, trend: Dict) -> int:
        published_at = trend.get("published_at", "")
        dt = self._parse_date(published_at)
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

    def _is_expired(self, trend: Dict) -> bool:
        published_at = trend.get("published_at", "")
        dt = self._parse_date(published_at)
        if not dt:
            return False
        return (datetime.now() - dt).days > self.EXPIRED_DAYS

    def _is_stale(self, trend: Dict) -> bool:
        published_at = trend.get("published_at", "")
        dt = self._parse_date(published_at)
        if not dt:
            return False
        return (datetime.now() - dt).days > self.ARCHIVE_DAYS

    # ------------------ CRUD ------------------

    def add(self, title: str, summary: str = "", source: str = "", url: str = "",
            category: str = "未分类", tags: List[str] = None,
            relevance_score: int = 50, click_count: int = 0,
            published_at: str = "", is_manual: bool = False,
            **extra_fields) -> str:
        trend_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        trend = {
            "id": trend_id,
            "title": title,
            "summary": summary,
            "source": source,
            "url": url,
            "category": category,
            "tags": tags or [],
            "relevance_score": relevance_score,
            "click_count": click_count,
            "is_selected": False,
            "published_at": published_at,
            "created_at": now,
            "updated_at": now,
            "is_manual": is_manual,
            **extra_fields,
        }
        self.data["trends"].append(trend)
        self._update_index(trend)
        self._save()
        return trend_id

    def add_manual(self, title: str, summary: str = "", url: str = "",
                   published_at: str = "", relevance_score: int = 80) -> str:
        return self.add(
            title=title, summary=summary, source="手动录入", url=url,
            relevance_score=relevance_score, published_at=published_at,
            is_manual=True, _time_source="manual" if published_at else "manual_pending",
        )

    def import_from_scraper(self, scraper_trends: List[Dict]):
        import re
        deleted_old = self.delete_expired()
        if deleted_old > 0:
            print(f"[TrendDB] 清理旧数据：删除 {deleted_old} 条过期热点")

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
            for t in self.data["trends"]:
                if st_url and _normalize_url(t.get("url", "")) == st_url:
                    existing_by_url = t
                    break
                if t.get("title") == st_title:
                    existing_by_title = t
                    break

            if existing_by_url:
                existing_by_url["title"] = st_title
                existing_by_url["summary"] = st.get("summary", "")
                existing_by_url["source"] = st.get("source", "")
                existing_by_url["relevance_score"] = st.get("relevance_score", 50)
                existing_by_url["published_at"] = published_at
                existing_by_url["_time_source"] = st.get("_time_source", "")
                existing_by_url["fetched_at"] = st.get("fetched_at", "")
                existing_by_url["keyword"] = st.get("keyword", "")
                existing_by_url["category"] = st.get("category", "未分类")
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

        self._save()
        print(f"[TrendDB] 导入完成：新增 {added} 条，更新 {updated} 条，跳过 {skipped} 条")
        return added, skipped

    def _update_index(self, trend: Dict):
        cat = trend.get("category", "未分类")
        if cat not in self.data["categories"]:
            self.data["categories"][cat] = []
        self.data["categories"][cat].append(trend["id"])
        for tag in trend.get("tags", []):
            if tag not in self.data["tags_index"]:
                self.data["tags_index"][tag] = []
            self.data["tags_index"][tag].append(trend["id"])

    # ------------------ 查询 ------------------

    def get_all(self, limit: int = 100, offset: int = 0,
                time_filter: str = "all", sort_by: str = "composite",
                category_filter: str = "all") -> tuple:
        trends = self.data["trends"].copy()

        if category_filter != "all":
            trends = [t for t in trends if t.get("category", "未分类") == category_filter]

        now = datetime.now()
        if time_filter != "all":
            if time_filter == "today":
                cutoff = now - timedelta(days=1)
            elif time_filter == "week":
                cutoff = now - timedelta(days=7)
            elif time_filter == "month":
                cutoff = now - timedelta(days=30)
            elif time_filter == "stale":
                cutoff = now - timedelta(days=self.ARCHIVE_DAYS)
                trends = [t for t in trends if self._is_stale(t)]
            else:
                cutoff = None

            if time_filter != "stale" and cutoff:
                filtered = []
                for t in trends:
                    pa = t.get("published_at", "")
                    if pa:
                        try:
                            dt = datetime.strptime(pa[:10], "%Y-%m-%d")
                            if dt >= cutoff:
                                filtered.append(t)
                        except ValueError:
                            pass
                    elif t.get("fetched_at"):
                        try:
                            dt = datetime.fromisoformat(t["fetched_at"])
                            if dt >= cutoff:
                                filtered.append(t)
                        except ValueError:
                            pass
                trends = filtered

        for t in trends:
            relevance = t.get("relevance_score", 50)
            timeliness = self._calc_timeliness_score(t)
            if t.get("is_manual"):
                timeliness = max(timeliness, 85)
            t["timeliness_score"] = timeliness
            t["composite_score"] = relevance * 0.55 + timeliness * 0.45

        if sort_by == "time":
            trends.sort(key=lambda x: x.get("published_at", "") or x.get("fetched_at", ""), reverse=True)
        elif sort_by == "relevance":
            trends.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        else:
            def _sort_key(t):
                score = t.get("composite_score", 0)
                time_bonus = 5 if t.get("_time_source") in ("rss", "google_news", "article_page", "url_date") else 0
                return score + time_bonus
            trends.sort(key=_sort_key, reverse=True)

        total = len(trends)
        return trends[offset:offset + limit], total

    def get_recommended(self, limit: int = 10) -> List[Dict]:
        trends = self.data["trends"].copy()
        for t in trends:
            relevance = t.get("relevance_score", 50)
            timeliness = self._calc_timeliness_score(t)
            click_bonus = min(t.get("click_count", 0) * 3, 20)
            manual_bonus = 15 if t.get("is_manual") else 0
            t["composite_score"] = relevance * 0.4 + timeliness * 0.4 + click_bonus + manual_bonus
            t["timeliness_score"] = timeliness
        trends.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        return trends[:limit]

    def get_fresh_hotspots(self, limit: int = 5) -> List[Dict]:
        trends = self.data["trends"].copy()
        fresh = []
        for t in trends:
            timeliness = self._calc_timeliness_score(t)
            if timeliness >= 80:
                t["timeliness_score"] = timeliness
                fresh.append(t)
        fresh.sort(key=lambda x: x.get("timeliness_score", 0), reverse=True)
        return fresh[:limit]

    def get_by_id(self, trend_id: str) -> Optional[Dict]:
        for t in self.data["trends"]:
            if t.get("id") == trend_id:
                return t
        return None

    def select(self, trend_id: str):
        for t in self.data["trends"]:
            if t.get("id") == trend_id:
                t["is_selected"] = True
                t["click_count"] = t.get("click_count", 0) + 1
                t["updated_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def delete(self, trend_id: str):
        self.data["trends"] = [t for t in self.data["trends"] if t.get("id") != trend_id]
        self._rebuild_index()
        self._save()

    def delete_expired(self) -> int:
        before = len(self.data["trends"])
        self.data["trends"] = [t for t in self.data["trends"] if not self._is_expired(t)]
        after = len(self.data["trends"])
        deleted = before - after
        if deleted > 0:
            self._rebuild_index()
            self._save()
            print(f"[TrendDB] 清理过期热点：删除 {deleted} 条")
        return deleted

    def delete_stale(self) -> int:
        stale = [t for t in self.data["trends"] if self._is_stale(t)]
        if not stale:
            return 0
        self.data["archived"].extend(stale)
        self.data["archived"] = self.data["archived"][-500:]
        stale_ids = {t["id"] for t in stale}
        self.data["trends"] = [t for t in self.data["trends"] if t.get("id") not in stale_ids]
        self._rebuild_index()
        self._save()
        print(f"[TrendDB] 归档陈旧热点：{len(stale)} 条移入归档区")
        return len(stale)

    def _auto_archive(self):
        stale_count = sum(1 for t in self.data["trends"] if self._is_stale(t))
        if stale_count > 0:
            archived = self.delete_stale()
            print(f"[TrendDB] 自动归档：{archived} 条陈旧热点（超过{self.ARCHIVE_DAYS}天）")

    def _rebuild_index(self):
        self.data["categories"] = {}
        self.data["tags_index"] = {}
        for t in self.data["trends"]:
            self._update_index(t)

    # ------------------ 统计报告 ------------------

    def generate_report(self) -> str:
        total = len(self.data["trends"])
        archived = len(self.data.get("archived", []))
        selected = sum(1 for t in self.data["trends"] if t.get("is_selected"))
        manual = sum(1 for t in self.data["trends"] if t.get("is_manual"))
        fresh = sum(1 for t in self.data["trends"] if self._calc_timeliness_score(t) >= 80)
        stale = sum(1 for t in self.data["trends"] if self._is_stale(t))
        expired = sum(1 for t in self.data["trends"] if self._is_expired(t))
        categories = self.data.get("categories", {})
        lines = [
            "=== 热点数据库统计 ===",
            f"活跃热点: {total} | 归档: {archived}",
            f"已选用: {selected} | 手动录入: {manual}",
            f"24h内新鲜: {fresh} | 陈旧(>90天): {stale} | 过期(>180天): {expired}",
            "",
            "分类分布:",
        ]
        for cat, ids in sorted(categories.items(), key=lambda x: -len(x[1])):
            lines.append(f"  - {cat}: {len(ids)}条")
        return "\n".join(lines)
