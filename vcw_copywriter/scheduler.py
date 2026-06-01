"""
定时任务调度器
后台线程自动执行热点爬取等任务
"""
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable


class TrendScheduler:
    """
    热点定时爬取调度器

    功能：
    1. 每小时自动爬取热点（可配置间隔）
    2. 支持手动触发/暂停/恢复
    3. 状态持久化到 JSON
    4. 记录最近爬取结果摘要
    """

    DEFAULT_INTERVAL_MINUTES = 60  # 默认每小时

    def __init__(self, state_path: str = "data/scheduler.json"):
        self.state_path = Path(state_path)
        self.state = self._load_state()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_flag = threading.Event()
        self._callback: Optional[Callable] = None  # 爬取完成的回调

    def _load_state(self) -> Dict:
        if self.state_path.exists():
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "enabled": False,
            "interval_minutes": self.DEFAULT_INTERVAL_MINUTES,
            "last_run": None,
            "next_run": None,
            "last_result": {"count": 0, "status": "never"},
            "run_history": [],  # 最近10次执行记录
        }

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def set_callback(self, callback: Callable):
        """设置爬取完成后的回调函数 callback(result_dict)"""
        self._callback = callback

    def start(self):
        """启动调度器（如果已启用）"""
        if self._running:
            return
        self._running = True
        self._stop_flag.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止调度器"""
        self._stop_flag.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _loop(self):
        """主循环：检查是否到执行时间"""
        while not self._stop_flag.is_set():
            if self.state.get("enabled", False):
                next_run_str = self.state.get("next_run")
                if next_run_str:
                    try:
                        next_run = datetime.fromisoformat(next_run_str)
                        if datetime.now() >= next_run:
                            self._do_crawl()
                    except (ValueError, TypeError):
                        pass
                else:
                    # 首次启用，立即执行一次
                    self._do_crawl()

            # 每30秒检查一次
            self._stop_flag.wait(30)

    def _do_crawl(self):
        """执行爬取任务"""
        now = datetime.now()
        self.state["last_run"] = now.isoformat()

        try:
            from .trend_scraper import TrendScraper
            from .trend_db import TrendDatabase

            scraper = TrendScraper()
            trends = scraper.fetch_all(force=True)

            db = TrendDatabase("data/trend_db.json")
            db.import_from_scraper(trends)

            result = {
                "time": now.isoformat(),
                "count": len(trends),
                "status": "success"
            }
            self.state["last_result"] = result

            # 记录历史
            history = self.state.get("run_history", [])
            history.insert(0, result)
            self.state["run_history"] = history[:10]

            # 回调通知
            if self._callback:
                try:
                    self._callback(result)
                except (ValueError, TypeError, KeyError):
                    pass

        except Exception as e:
            result = {
                "time": now.isoformat(),
                "count": 0,
                "status": "failed",
                "error": str(e)[:200]
            }
            self.state["last_result"] = result
            history = self.state.get("run_history", [])
            history.insert(0, result)
            self.state["run_history"] = history[:10]

        # 计算下次执行时间
        interval = self.state.get("interval_minutes", self.DEFAULT_INTERVAL_MINUTES)
        next_run = now + timedelta(minutes=interval)
        self.state["next_run"] = next_run.isoformat()
        self._save_state()

    def enable(self, interval_minutes: Optional[int] = None):
        """启用定时爬取"""
        self.state["enabled"] = True
        if interval_minutes is not None:
            self.state["interval_minutes"] = max(10, interval_minutes)
        # 重置下次执行时间为现在+间隔（避免立即执行后马上又执行）
        interval = self.state.get("interval_minutes", self.DEFAULT_INTERVAL_MINUTES)
        self.state["next_run"] = (datetime.now() + timedelta(minutes=interval)).isoformat()
        self._save_state()

    def disable(self):
        """禁用定时爬取"""
        self.state["enabled"] = False
        self.state["next_run"] = None
        self._save_state()

    def trigger_now(self) -> Dict:
        """立即手动触发一次爬取（返回结果摘要）"""
        self._do_crawl()
        return self.state["last_result"]

    def get_status(self) -> Dict:
        """获取调度器状态"""
        status = dict(self.state)
        # 添加人类可读的时间
        if status.get("next_run"):
            try:
                next_dt = datetime.fromisoformat(status["next_run"])
                delta = next_dt - datetime.now()
                if delta.total_seconds() > 0:
                    hours, rem = divmod(int(delta.total_seconds()), 3600)
                    mins, secs = divmod(rem, 60)
                    if hours > 0:
                        status["next_run_human"] = f"{hours}小时{mins}分钟后"
                    else:
                        status["next_run_human"] = f"{mins}分钟{secs}秒后"
                else:
                    status["next_run_human"] = "即将执行"
            except Exception:
                status["next_run_human"] = status["next_run"]

        if status.get("last_run"):
            try:
                last_dt = datetime.fromisoformat(status["last_run"])
                status["last_run_human"] = last_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                status["last_run_human"] = status["last_run"]

        return status


# 全局调度器实例（单例）
_scheduler_instance: Optional[TrendScheduler] = None


def get_scheduler() -> TrendScheduler:
    """获取全局调度器（懒加载）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TrendScheduler()
        _scheduler_instance.start()
    return _scheduler_instance
