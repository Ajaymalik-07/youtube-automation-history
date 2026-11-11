"""
Official YouTube Analytics API Integration Module
Queries the YouTube Analytics API (v2) using authorized OAuth credentials.
Collects:
- Watch time (estimatedMinutesWatched)
- Average View Duration (averageViewDuration in seconds)
- Average Percentage Viewed (averageViewPercentage)
- Audience retention and traffic sources
- Performance checkpoints at 24h, 48h, 7d, and 28d intervals.

Falls back gracefully to YouTube Data API v3 public stats if Analytics OAuth scope is pending.
"""
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import config

SNAPSHOT_FILE = os.path.join(config.OUTPUT_DIR, "analytics_snapshots.json")
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
        json.dump(snapshots, f, indent=2)


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

    snaps[video_id]["checkpoints"][cp] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
    }
    save_snapshots(snaps)
    return snaps[video_id]


def _get_analytics_service():
    """
    Initializes YouTube Analytics API v2 client using authenticated OAuth credentials.
    Returns (service, None) if successful, or (None, error_str).
    """
    token_file = "youtube_token.pickle"
    if not os.path.exists(token_file):
        return None, "youtube_token.pickle not found; OAuth authorization required."

    try:
        import pickle
        from googleapiclient.discovery import build
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                with open(token_file, "wb") as f:
                    pickle.dump(creds, f)
            else:
                return None, "OAuth credentials expired and cannot be refreshed."

        service = build("youtubeAnalytics", "v2", credentials=creds)
        return service, None
    except Exception as e:
        return None, str(e)


def get_video_analytics(video_id: str, days_back: int = 28) -> Dict[str, Any]:
    """
    Fetches official YouTube Analytics metrics for a specific video.
    Returns:
      - views
      - estimatedMinutesWatched
      - averageViewDuration
      - averageViewPercentage
      - likes, comments, subscribersGained
      - source ("youtube_analytics_api" | "youtube_data_api_fallback")
    """
    service, err = _get_analytics_service()
    
    if service:
        try:
            today = datetime.now(timezone.utc).date()
            start_date = (today - timedelta(days=days_back)).isoformat()
            end_date = today.isoformat()

            resp = service.reports().query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained",
                filters=f"video=={video_id}",
            ).execute()

            rows = resp.get("rows", [])
            if rows and len(rows[0]) >= 7:
                row = rows[0]
                return {
                    "ok": True,
                    "video_id": video_id,
                    "source": "youtube_analytics_api",
                    "views": int(row[0]),
                    "watch_time_minutes": round(float(row[1]), 2),
                    "average_view_duration_seconds": round(float(row[2]), 1),
                    "average_percentage_viewed": round(float(row[3]), 2),
                    "likes": int(row[4]),
                    "comments": int(row[5]),
                    "subscribers_gained": int(row[6]),
                    "is_live_analytics": True,
                }
        except Exception as api_err:
            print(f"   ℹ YouTube Analytics query note: {api_err}")

    # Graceful fallback to YouTube Data API v3 public stats
    try:
        from uploader.analytics import get_channel_and_last_video_analytics
        data_stats = get_channel_and_last_video_analytics()
        return {
            "ok": data_stats.get("available", False),
            "video_id": video_id,
            "source": "youtube_data_api_fallback",
            "views": int(str(data_stats.get("views", 0)).replace(",", "") or 0),
            "watch_time_minutes": None,
            "average_view_duration_seconds": None,
            "average_percentage_viewed": None,
            "likes": int(str(data_stats.get("likes", 0)).replace(",", "") or 0),
            "comments": int(str(data_stats.get("comments", 0)).replace(",", "") or 0),
            "subscribers_gained": None,
            "is_live_analytics": False,
            "note": "Detailed retention metrics require yt-analytics.readonly OAuth permission.",
        }
    except Exception as fallback_err:
        return {
            "ok": False,
            "video_id": video_id,
            "error": str(fallback_err),
            "source": "none",
        }


def get_traffic_sources(video_id: str) -> List[Dict[str, Any]]:
    """
    Fetches discovery traffic source breakdown (Search, Suggested, External, Shorts feed).
    """
    service, _ = _get_analytics_service()
    if not service:
        return []

    try:
        today = datetime.now(timezone.utc).date()
        start_date = (today - timedelta(days=28)).isoformat()
        end_date = today.isoformat()

        resp = service.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            dimensions="insightTrafficSourceType",
            metrics="views,estimatedMinutesWatched",
            filters=f"video=={video_id}",
            sort="-views",
        ).execute()

        sources = []
        for row in resp.get("rows", []):
            sources.append({
                "traffic_source": str(row[0]),
                "views": int(row[1]),
                "watch_time_minutes": round(float(row[2]), 2),
            })
        return sources
    except Exception:
        return []
