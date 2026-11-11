"""
Official YouTube Analytics API Integration Module
Phase 18.1 Overhaul: Real Owner Analytics, Format-Separated Reporting, and Topic Diagnostics.

Queries YouTube Analytics API (v2) using authorized OAuth credentials:
- Views
- Watch time (estimatedMinutesWatched)
- Average View Duration (averageViewDuration in seconds)
- Average Percentage Viewed (averageViewPercentage)
- Traffic sources breakdown (insightTrafficSourceType)
- Subscriber gains (subscribersGained)
- Independent Long-form vs Shorts evaluation
- Structured persistence of actual metrics with channel ID, video ID, date range, metric, value, and timestamp.
"""
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import config
from uploader.oauth_manager import audit_token_scopes, safe_refresh_credentials, REQUIRED_SCOPES

SNAPSHOT_FILE = os.path.join(config.OUTPUT_DIR, "analytics_snapshots.json")
WEEKLY_REPORT_FILE = os.path.join(config.OUTPUT_DIR, "weekly_analytics_report.json")

ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def load_snapshots() -> dict:
    """Load persisted historical performance snapshots."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_snapshots(snapshots: dict) -> None:
    """Persist performance snapshots to disk."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2, ensure_ascii=False)


def record_performance_checkpoint(video_id: str, checkpoint: str, metrics: dict) -> dict:
    """
    Stores an analytics checkpoint for a video (e.g. '24h', '48h', '7d', '28d').
    """
    valid_checkpoints = ("24h", "48h", "7d", "28d", "initial")
    cp = checkpoint if checkpoint in valid_checkpoints else "ad_hoc"

    snaps = load_snapshots()
    if video_id not in snaps:
        snaps[video_id] = {
            "video_id": video_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "checkpoints": {},
        }
    elif "checkpoints" not in snaps[video_id]:
        snaps[video_id]["checkpoints"] = {}

    snaps[video_id]["checkpoints"][cp] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
    }
    save_snapshots(snaps)
    return snaps[video_id]



def _get_analytics_service():
    """
    Initializes YouTube Analytics API v2 client using authenticated OAuth credentials.
    Returns (service, None) if successful, or (None, error_dict).
    """
    token_file = "youtube_token.pickle"
    audit = audit_token_scopes(token_file)

    if not audit["exists"]:
        return None, {
            "error": "token_not_found",
            "message": "youtube_token.pickle not found; OAuth authorization required.",
        }

    # Verify analytics scope
    granted = audit.get("granted_scopes", [])
    if "https://www.googleapis.com/auth/yt-analytics.readonly" not in granted:
        return None, {
            "error": "insufficient_scope",
            "message": "Token lacks 'https://www.googleapis.com/auth/yt-analytics.readonly' permission.",
            "missing_scope": "https://www.googleapis.com/auth/yt-analytics.readonly",
        }

    try:
        import pickle
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                refreshed = safe_refresh_credentials(creds, token_file)
                if not refreshed:
                    return None, {
                        "error": "refresh_failed",
                        "message": "OAuth credentials expired and could not be refreshed.",
                    }
            else:
                return None, {
                    "error": "token_invalid",
                    "message": "OAuth credentials are invalid or expired without refresh token.",
                }

        service = build("youtubeAnalytics", "v2", credentials=creds)
        return service, None
    except Exception as e:
        return None, {"error": "initialization_error", "message": str(e)}


def query_analytics_report(
    ids: str = "channel==MINE",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    metrics: str = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained",
    dimensions: Optional[str] = None,
    filters: Optional[str] = None,
    sort: Optional[str] = None,
    max_results: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Executes a direct query to the YouTube Analytics API v2 reports endpoint.
    Handles dates, quotas, and structured responses cleanly.
    """
    service, err = _get_analytics_service()
    if err:
        return {"ok": False, "error_type": err.get("error"), "message": err.get("message")}

    today = datetime.now(timezone.utc).date()
    # YouTube Analytics data usually has a 2-day processing latency
    s_date = start_date or (today - timedelta(days=28)).isoformat()
    e_date = end_date or today.isoformat()

    kwargs = {
        "ids": ids,
        "startDate": s_date,
        "endDate": e_date,
        "metrics": metrics,
    }
    if dimensions:
        kwargs["dimensions"] = dimensions
    if filters:
        kwargs["filters"] = filters
    if sort:
        kwargs["sort"] = sort
    if max_results:
        kwargs["maxResults"] = max_results

    try:
        resp = service.reports().query(**kwargs).execute()
        return {
            "ok": True,
            "columnHeaders": resp.get("columnHeaders", []),
            "rows": resp.get("rows", []),
            "startDate": s_date,
            "endDate": e_date,
        }
    except HttpError as http_err:
        content_str = http_err.content.decode("utf-8", errors="replace") if hasattr(http_err, "content") and http_err.content else ""
        err_msg = f"{http_err} {content_str}"
        quota_exceeded = "quotaExceeded" in err_msg or "dailyLimitExceeded" in err_msg
        return {
            "ok": False,
            "error_type": "quota_error" if quota_exceeded else "api_http_error",
            "message": err_msg,
            "status_code": http_err.resp.status if hasattr(http_err, "resp") else 500,
        }
    except Exception as e:
        return {"ok": False, "error_type": "unknown_error", "message": str(e)}


def get_video_analytics(
    video_id: str,
    days_back: int = 28,
    is_shorts: bool = False,
    channel_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetches real video-level analytics from YouTube Analytics API v2.
    Stores results in the canonical snapshot format with channel ID, video ID,
    date range, metric, value, and retrieval timestamp.
    Falls back gracefully if Analytics OAuth permission is missing.
    """
    today = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=days_back)).isoformat()
    end_date = today.isoformat()
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    actual_channel_id = channel_id or getattr(config, "YOUTUBE_CHANNEL_ID", "Stories_Malik_Owner")

    query_res = query_analytics_report(
        ids="channel==MINE",
        start_date=start_date,
        end_date=end_date,
        metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained",
        filters=f"video=={video_id}",
    )

    if query_res.get("ok"):
        rows = query_res.get("rows", [])
        if rows and len(rows[0]) >= 7:
            row = rows[0]
            metrics_dict = {
                "views": int(row[0]),
                "estimatedMinutesWatched": round(float(row[1]), 2),
                "averageViewDuration": round(float(row[2]), 1),
                "averageViewPercentage": round(float(row[3]), 2),
                "likes": int(row[4]),
                "comments": int(row[5]),
                "subscribersGained": int(row[6]),
            }

            traffic_sources = get_traffic_sources(video_id, start_date=start_date, end_date=end_date)

            structured_record = {
                "ok": True,
                "video_id": video_id,
                "channel_id": actual_channel_id,
                "is_shorts": is_shorts,
                "source": "youtube_analytics_api_v2",
                "date_range": {"start_date": start_date, "end_date": end_date},
                "metrics": metrics_dict,
                "traffic_sources": traffic_sources,
                "retrieval_timestamp": retrieval_ts,
                "is_live_analytics": True,
            }

            # Store structured result in snapshot store
            snaps = load_snapshots()
            snaps[video_id] = structured_record
            save_snapshots(snaps)

            # Also persist versioned checkpoint into HistoricalPerformanceDB
            try:
                from apis.growth_database import get_performance_db
                get_performance_db().record_snapshot(
                    video_id=video_id,
                    video_format="short" if is_shorts else "longform",
                    topic=structured_record.get("topic", "Historical Topic"),
                    content_pillar=structured_record.get("pillar_name", "General History"),
                    publication_timestamp=structured_record.get("published_at", ""),
                    video_duration=float(structured_record.get("duration_seconds", 0.0) or 0.0),
                    title=structured_record.get("title", f"Video {video_id}"),
                    views=int(metrics_dict.get("views", 0) or 0),
                    engaged_views=int(metrics_dict.get("engagedViews", 0) or 0),
                    watch_time_minutes=float(metrics_dict.get("estimatedMinutesWatched", 0.0) or 0.0),
                    average_view_duration_seconds=float(metrics_dict.get("averageViewDuration", 0.0) or 0.0),
                    average_percentage_viewed=float(metrics_dict.get("averageViewPercentage", 0.0) or 0.0),
                    impressions=int(metrics_dict.get("impressions", 0) or 0),
                    ctr=float(metrics_dict.get("impressionClickThroughRate", 0.0) or 0.0),
                    likes=int(metrics_dict.get("likes", 0) or 0),
                    comments=int(metrics_dict.get("comments", 0) or 0),
                    subscribers_gained=int(metrics_dict.get("subscribersGained", 0) or 0),
                    traffic_sources=traffic_sources,
                    checkpoint="live_analytics_query",
                )
            except Exception:
                pass

            return structured_record

        # Empty response (e.g. newly published video with no view history yet)
        return {
            "ok": True,
            "video_id": video_id,
            "channel_id": actual_channel_id,
            "is_shorts": is_shorts,
            "source": "youtube_analytics_api_v2",
            "date_range": {"start_date": start_date, "end_date": end_date},
            "metrics": {
                "views": 0,
                "estimatedMinutesWatched": 0.0,
                "averageViewDuration": 0.0,
                "averageViewPercentage": 0.0,
                "likes": 0,
                "comments": 0,
                "subscribersGained": 0,
            },
            "traffic_sources": [],
            "retrieval_timestamp": retrieval_ts,
            "is_live_analytics": True,
            "note": "No view data recorded within the date range.",
        }

    # Fallback to public Data API v3 statistics when Analytics OAuth scope is pending
    try:
        from uploader.analytics import get_channel_and_last_video_analytics
        data_stats = get_channel_and_last_video_analytics()
        views = int(str(data_stats.get("views", 0)).replace(",", "") or 0)
        likes = int(str(data_stats.get("likes", 0)).replace(",", "") or 0)
        comments = int(str(data_stats.get("comments", 0)).replace(",", "") or 0)

        fallback_record = {
            "ok": data_stats.get("available", False),
            "video_id": video_id,
            "channel_id": actual_channel_id,
            "is_shorts": is_shorts,
            "source": "youtube_data_api_fallback",
            "date_range": {"start_date": start_date, "end_date": end_date},
            "metrics": {
                "views": views,
                "estimatedMinutesWatched": None,
                "averageViewDuration": None,
                "averageViewPercentage": None,
                "likes": likes,
                "comments": comments,
                "subscribersGained": None,
            },
            "traffic_sources": [],
            "retrieval_timestamp": retrieval_ts,
            "is_live_analytics": False,
            "note": query_res.get("message", "Detailed retention metrics require yt-analytics.readonly scope."),
        }
        return fallback_record
    except Exception as fallback_err:
        return {
            "ok": False,
            "video_id": video_id,
            "channel_id": actual_channel_id,
            "error": str(fallback_err),
            "source": "none",
        }


def get_traffic_sources(
    video_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches discovery traffic source breakdown (Search, Suggested, External, Shorts feed).
    """
    res = query_analytics_report(
        ids="channel==MINE",
        start_date=start_date,
        end_date=end_date,
        dimensions="insightTrafficSourceType",
        metrics="views,estimatedMinutesWatched",
        filters=f"video=={video_id}",
        sort="-views",
    )
    if not res.get("ok"):
        return []

    sources = []
    for row in res.get("rows", []):
        sources.append({
            "traffic_source": str(row[0]),
            "views": int(row[1]),
            "watch_time_minutes": round(float(row[2]), 2),
        })
    return sources


def generate_weekly_format_report(
    snapshots: Optional[dict] = None,
    days_back: int = 7,
) -> Dict[str, Any]:
    """
    Generates a separated weekly report for Shorts and Long-form videos:
    - Never compares raw view counts directly without accounting for format length.
    - Identifies strong vs weak topics.
    - Evaluates retention thresholds (Long-form target: >= 45%, Shorts target: >= 70%).
    - Evaluates subscriber conversion per 1,000 views.
    - Generates actionable future experiments.
    """
    data = snapshots if snapshots is not None else load_snapshots()
    now_str = datetime.now(timezone.utc).isoformat()

    longform_videos = []
    shorts_videos = []

    for vid, rec in data.items():
        if not isinstance(rec, dict):
            continue
        m = rec.get("metrics", {})
        entry = {
            "video_id": vid,
            "title": rec.get("title", vid),
            "topic": rec.get("topic", rec.get("title", "Historical Topic")),
            "views": m.get("views", 0) or 0,
            "watch_time_minutes": m.get("estimatedMinutesWatched") or 0.0,
            "average_percentage_viewed": m.get("averageViewPercentage") or 0.0,
            "subscribers_gained": m.get("subscribersGained") or 0,
        }
        if rec.get("is_shorts"):
            shorts_videos.append(entry)
        else:
            longform_videos.append(entry)

    def analyze_format_group(items: list, is_shorts: bool) -> dict:
        if not items:
            return {
                "video_count": 0,
                "total_views": 0,
                "avg_percentage_viewed": 0.0,
                "total_subscribers_gained": 0,
                "sub_conversion_per_1k": 0.0,
                "best_performer": None,
                "strong_topics": [],
                "weak_topics": [],
                "retention_weaknesses": [],
            }

        total_v = sum(i["views"] for i in items)
        total_subs = sum(i["subscribers_gained"] for i in items)
        pct_list = [i["average_percentage_viewed"] for i in items if i["average_percentage_viewed"] > 0]
        avg_pct = round(sum(pct_list) / len(pct_list), 2) if pct_list else 0.0
        sub_conv = round((total_subs / total_v * 1000), 2) if total_v > 0 else 0.0

        sorted_by_views = sorted(items, key=lambda x: x["views"], reverse=True)
        best = sorted_by_views[0] if sorted_by_views else None

        # Thresholds: Longform benchmark 45%, Shorts benchmark 70%
        retention_bench = 70.0 if is_shorts else 45.0
        retention_issues = [
            f"{i['topic']} ({i['average_percentage_viewed']}% < {retention_bench}%)"
            for i in items if i["average_percentage_viewed"] > 0 and i["average_percentage_viewed"] < retention_bench
        ]

        strong = [i["topic"] for i in sorted_by_views[:2] if i["views"] > 0]
        weak = [i["topic"] for i in sorted_by_views[-2:] if len(sorted_by_views) >= 2]

        return {
            "video_count": len(items),
            "total_views": total_v,
            "avg_percentage_viewed": avg_pct,
            "total_subscribers_gained": total_subs,
            "sub_conversion_per_1k": sub_conv,
            "best_performer": best,
            "strong_topics": strong,
            "weak_topics": weak,
            "retention_weaknesses": retention_issues,
        }

    lf_analysis = analyze_format_group(longform_videos, is_shorts=False)
    sh_analysis = analyze_format_group(shorts_videos, is_shorts=True)

    # Formulate recommendations
    recommendations = []
    if sh_analysis["retention_weaknesses"]:
        recommendations.append("Shorts hook optimization: Replace narrative preamble with high-intensity visual paradox in the first 2.5 seconds.")
    if lf_analysis["retention_weaknesses"]:
        recommendations.append("Long-form pacing: Introduce tactical maps and animated timeline anchors at the 3-minute and 7-minute mark.")
    if sh_analysis["total_views"] > lf_analysis["total_views"] * 2:
        recommendations.append("Topic crossover: Expand top-performing Shorts topics into 10-minute long-form investigative documentaries.")
    if not recommendations:
        recommendations.append("Pacing test: Experiment with 3-part archaeological micro-series for top-performing ancient dynasty topics.")

    report = {
        "report_generated_at": now_str,
        "evaluation_period_days": days_back,
        "longform_analytics": lf_analysis,
        "shorts_analytics": sh_analysis,
        "recommended_future_experiments": recommendations,
    }

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(WEEKLY_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report
