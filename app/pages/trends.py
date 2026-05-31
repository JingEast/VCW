"""
热点发现路由（页面 Blueprint）
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.core.container import get_service
from domains.trend.application import (
    AddManualTrendCommand,
    ArchiveStaleCommand,
    DeleteExpiredCommand,
    DeleteTrendCommand,
    FetchTrendsCommand,
    ListTrendsQuery,
    SelectTrendCommand,
    GetFreshHotspotsQuery,
    GenerateReportQuery,
    GetTrendDetailQuery,
)
from services.scheduler_service import SchedulerError

bp = Blueprint("pages_trends", __name__)


@bp.route("/trends")
def trends_page():
    """热点发现页面（支持分页、时间筛选、板块筛选）"""
    handler = get_service("trend_handler")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    time_filter = request.args.get("time_filter", "all")
    sort_by = request.args.get("sort_by", "composite")
    category_filter = request.args.get("category", "all")

    trends, total = handler.handle_list_trends(
        ListTrendsQuery(
            page=page,
            per_page=per_page,
            time_filter=time_filter,
            sort_by=sort_by,
            category_filter=category_filter,
        )
    )

    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    fresh_hotspots = handler.handle_get_fresh_hotspots(GetFreshHotspotsQuery(limit=5))
    report = handler.handle_generate_report(GenerateReportQuery())
    return render_template(
        "trends.html",
        trends=trends,
        report=report,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        time_filter=time_filter,
        sort_by=sort_by,
        category_filter=category_filter,
        fresh_hotspots=fresh_hotspots,
    )


@bp.route("/trends/fetch", methods=["POST"])
def trends_fetch():
    """爬取热点（多数据源聚合）"""
    handler = get_service("trend_handler")
    try:
        deleted = handler.handle_delete_expired(DeleteExpiredCommand())
        if deleted > 0:
            flash(f"已清理 {deleted} 条过期热点", "info")

        added, skipped = handler.handle_fetch_trends(FetchTrendsCommand())
        flash(
            f"爬取完成！新增 {added} 条热点，跳过 {skipped} 条（重复或过期）",
            "success",
        )
    except SchedulerError as e:
        flash(f"爬取失败: {e.message}", "error")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("热点爬取失败: %s", e, exc_info=True)
        flash(f"爬取失败: {str(e)}", "error")
    return redirect(url_for("trends_page"))


@bp.route("/trend/select/<trend_id>", methods=["POST"])
def trend_select(trend_id):
    """选用热点，自动填充参数"""
    handler = get_service("trend_handler")
    try:
        trend = handler.handle_get_trend_detail(GetTrendDetailQuery(trend_id=trend_id))
        if not trend:
            flash("热点不存在", "error")
            return redirect(url_for("trends_page"))

        timeliness = handler.handle_calc_timeliness_score(trend)
        if timeliness < 35:
            flash(
                f"⚠️ 该热点已较陈旧（{timeliness}分），建议核对信息时效性",
                "warning",
            )

        auto_params = handler.handle_select_trend(SelectTrendCommand(trend_id=trend_id))
        flash(f"已选用热点: {trend['title'][:30]}...", "success")
        return redirect(url_for("index", **auto_params))
    except SchedulerError as e:
        flash(f"参数推断失败: {e.message}，已跳转至生成页面，请手动填写", "warning")
        return redirect(
            url_for("index", topic=trend.get("title", "") if trend else "")
        )
    except Exception as e:
        flash(
            f"参数推断失败: {str(e)}，已跳转至生成页面，请手动填写",
            "warning",
        )
        return redirect(url_for("index", topic=""))


@bp.route("/trend/delete/<trend_id>", methods=["POST"])
def trend_delete(trend_id):
    """删除热点"""
    handler = get_service("trend_handler")
    try:
        handler.handle_delete_trend(DeleteTrendCommand(trend_id=trend_id))
        flash("热点已删除", "success")
    except SchedulerError as e:
        flash(f"删除失败: {e.message}", "error")
    return redirect(url_for("trends_page"))


@bp.route("/trend/add_manual", methods=["POST"])
def trend_add_manual():
    """手动录入热点（绕过爬虫）"""
    handler = get_service("trend_handler")
    title = request.form.get("title", "").strip()
    summary = request.form.get("summary", "").strip()
    url = request.form.get("url", "").strip()
    published_at = request.form.get("published_at", "").strip()

    try:
        trend_id = handler.handle_add_manual_trend(
            AddManualTrendCommand(
                title=title,
                summary=summary,
                url=url,
                published_at=published_at,
            )
        )
        flash(f"手动录入成功 (ID: {trend_id})", "success")
    except SchedulerError as e:
        flash(e.message, "error")
    except Exception as e:
        flash(f"录入失败: {str(e)}", "error")

    return redirect(url_for("trends_page"))


@bp.route("/trend/delete_expired", methods=["POST"])
def trend_delete_expired():
    """一键清除所有过期热点"""
    handler = get_service("trend_handler")
    try:
        deleted = handler.handle_delete_expired(DeleteExpiredCommand())
        if deleted > 0:
            flash(f"已清理 {deleted} 条过期热点", "success")
        else:
            flash("暂无过期热点", "info")
    except SchedulerError as e:
        flash(f"清理失败: {e.message}", "error")
    except Exception as e:
        flash(f"清理失败: {str(e)}", "error")
    return redirect(url_for("trends_page"))


@bp.route("/trend/archive_stale", methods=["POST"])
def trend_archive_stale():
    """归档陈旧热点"""
    handler = get_service("trend_handler")
    try:
        archived = handler.handle_archive_stale(ArchiveStaleCommand())
        if archived > 0:
            flash(f"已归档 {archived} 条陈旧热点", "success")
        else:
            flash("暂无需要归档的陈旧热点", "info")
    except SchedulerError as e:
        flash(f"归档失败: {e.message}", "error")
    except Exception as e:
        flash(f"归档失败: {str(e)}", "error")
    return redirect(url_for("trends_page"))
