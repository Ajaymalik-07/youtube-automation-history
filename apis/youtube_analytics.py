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
EVALUATION_WINDOW_DAYS = getattr(config, "EVALUATION_WINDOW_DAYS", 30)

ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_analytics_capabilities_and_limitations() -> Dict[str, Any]:
    """
    Audits OAuth permissions and explicitly reports what owner analytics
    are accessible vs limited by OAuth scopes or YouTube Analytics API v2 constraints.
    """
    audit = audit_token_scopes()
    granted = audit.get("granted_scopes", [])
    has_analytics_scope = "https://www.googleapis.com/auth/yt-analytics.readonly" in granted
    has_readonly_scope = (
        "https://www.googleapis.com/auth/youtube.readonly" in granted
        or "https://www.googleapis.com/auth/youtube" in granted
    )
    has_api_key = bool(getattr(config, "YOUTUBE_API_KEY", "")) and bool(getattr(config, "YOUTUBE_CHANNEL_ID", ""))

    limitations = []
    if not audit.get("exists"):
        limitations.append("OAuth token file (youtube_token.pickle) not found; private owner YouTube Analytics v2 is unavailable.")
    else:
        if not has_analytics_scope:
            limitations.append(
                "OAuth token lacks 'https://www.googleapis.com/auth/yt-analytics.readonly': "
                "watch time, AVD, APV, subscribers gained, and traffic sources cannot be retrieved from YouTube Analytics v2 until reauthorized."
            )
        if not has_readonly_scope:
            limitations.append(
                "OAuth token lacks 'https://www.googleapis.com/auth/youtube.readonly': "
                "authenticated channel uploads listing (channels.list mine=true) is blocked; falling back to public Data API v3 where configured."
            )

    limitations.extend([
        "YouTube Analytics API v2 standard reports.query does not expose thumbnail impressions or impressions CTR without Studio reach-report access.",
        "YouTube Analytics API v2 has a ~48-hour processing latency for newly published videos.",
        "Granular second-by-second audience retention curves and Shorts 'Viewed vs Swiped Away' ratios are not exposed in standard v2 dimensions.",
        "Returning viewers metric is only available when supported by YouTube Analytics API v2 channel-level audience dimensions; unavailable per-video.",
    ])

    return {
        "oauth_token_exists": audit.get("exists", False),
        "oauth_valid": audit.get("valid", False),
        "has_analytics_scope": has_analytics_scope,
        "has_youtube_readonly_scope": has_readonly_scope,
        "has_public_data_api_fallback": has_api_key,
        "missing_scopes": audit.get("missing_scopes", []),
        "owner_analytics_connected": has_analytics_scope and (audit.get("valid", False) or audit.get("has_refresh_token", False)),
        "limitations": limitations,
    }


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


def _median(vals: List[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return round((s[mid - 1] + s[mid]) / 2.0, 2)


def _parse_iso8601_duration(dur_str: str) -> float:
    """Parses ISO-8601 YouTube duration (e.g. 'PT52S', 'PT10M12S') to seconds."""
    import re
    if not dur_str:
        return 0.0
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", str(dur_str).strip())
    if not m:
        return 0.0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    sec = int(m.group(3) or 0)
    return float(h * 3600 + mins * 60 + sec)


def get_video_analytics(
    video_id: str,
    days_back: int = EVALUATION_WINDOW_DAYS,
    is_shorts: bool = False,
    channel_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetches real video-level analytics from YouTube Analytics API v2.
    Uses a rolling 30-day evaluation window by default (configurable via days_back).
    Stores results in the canonical snapshot format with channel ID, video ID,
    date range, metric, value, and retrieval timestamp.
    Falls back gracefully if Analytics OAuth permission is missing and explicitly reports limitations.
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
                "impressions": None,
                "impressionClickThroughRate": None,
                "returningViewers": None,
            }
            limitations = [
                "impressions and impressionClickThroughRate are not exposed by standard YouTube Analytics API v2 reports.query.",
                "returningViewers is not exposed per-video in standard YouTube Analytics API v2 queries.",
            ]

            traffic_sources = get_traffic_sources(video_id, start_date=start_date, end_date=end_date)

            structured_record = {
                "ok": True,
                "video_id": video_id,
                "channel_id": actual_channel_id,
                "is_shorts": is_shorts,
                "source": "youtube_analytics_api_v2",
                "owner_analytics_available": True,
                "date_range": {"start_date": start_date, "end_date": end_date},
                "metrics": metrics_dict,
                "traffic_sources": traffic_sources,
                "metrics_retrieved": [
                    "views", "estimatedMinutesWatched", "averageViewDuration",
                    "averageViewPercentage", "likes", "comments", "subscribersGained", "trafficSources",
                ],
                "metrics_unavailable_at_video_level": [
                    "impressions", "impressionClickThroughRate", "returningViewers",
                ],
                "metrics_delayed": [],
                "analytics_limitations": limitations,
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
                    channel_id=actual_channel_id,
                    video_format="short" if is_shorts else "longform",
                    topic=structured_record.get("topic", "Historical Topic"),
                    content_pillar=structured_record.get("pillar_name", "General History"),
                    publication_timestamp=structured_record.get("published_at", ""),
                    video_duration=float(structured_record.get("duration_seconds", 0.0) or 0.0),
                    title=structured_record.get("title", f"Video {video_id}"),
                    views=int(metrics_dict.get("views", 0) or 0),
                    engaged_views=None,
                    watch_time_minutes=float(metrics_dict.get("estimatedMinutesWatched", 0.0) or 0.0),
                    average_view_duration_seconds=float(metrics_dict.get("averageViewDuration", 0.0) or 0.0),
                    average_percentage_viewed=float(metrics_dict.get("averageViewPercentage", 0.0) or 0.0),
                    impressions=None,
                    ctr=None,
                    likes=int(metrics_dict.get("likes", 0) or 0),
                    comments=int(metrics_dict.get("comments", 0) or 0),
                    subscribers_gained=int(metrics_dict.get("subscribersGained", 0) or 0),
                    returning_viewers=None,
                    traffic_sources=traffic_sources,
                    checkpoint="live_analytics_query",
                    observation_period=f"{start_date}..{end_date}",
                    owner_analytics_available=True,
                )
            except Exception:
                pass

            return structured_record

        # Empty response (e.g. newly published video within 48h reporting latency)
        return {
            "ok": True,
            "video_id": video_id,
            "channel_id": actual_channel_id,
            "is_shorts": is_shorts,
            "source": "youtube_analytics_api_v2",
            "owner_analytics_available": False,
            "date_range": {"start_date": start_date, "end_date": end_date},
            "metrics": {
                "views": 0,
                "estimatedMinutesWatched": 0.0,
                "averageViewDuration": 0.0,
                "averageViewPercentage": 0.0,
                "likes": 0,
                "comments": 0,
                "subscribersGained": 0,
                "impressions": None,
                "impressionClickThroughRate": None,
                "returningViewers": None,
            },
            "traffic_sources": [],
            "metrics_retrieved": [],
            "metrics_delayed": [
                "views", "estimatedMinutesWatched", "averageViewDuration",
                "averageViewPercentage", "subscribersGained",
            ],
            "metrics_unavailable_at_video_level": [
                "impressions", "impressionClickThroughRate", "returningViewers",
            ],
            "analytics_limitations": [
                "No view data recorded within the date range (may reflect YouTube's ~48h analytics processing latency).",
            ],
            "retrieval_timestamp": retrieval_ts,
            "is_live_analytics": True,
            "note": "No view data recorded within the date range.",
        }

    # OAuth Analytics v2 unavailable: never substitute another video's stats or treat public counts as private owner analytics
    public_views = None
    public_likes = None
    public_comments = None
    api_key = getattr(config, "YOUTUBE_API_KEY", "")
    if api_key and not str(api_key).startswith("YOUR_"):
        try:
            yt_pub = build("youtube", "v3", developerKey=api_key)
            v_resp = yt_pub.videos().list(id=video_id, part="statistics").execute()
            v_items = v_resp.get("items", [])
            if v_items:
                st = v_items[0].get("statistics", {})
                public_views = int(st.get("viewCount", 0) or 0)
                public_likes = int(st.get("likeCount", 0) or 0)
                public_comments = int(st.get("commentCount", 0) or 0)
        except Exception:
            pass

    return {
        "ok": False,
        "video_id": video_id,
        "channel_id": actual_channel_id,
        "is_shorts": is_shorts,
        "source": "youtube_data_api_fallback" if public_views is not None else "none",
        "owner_analytics_available": False,
        "date_range": {"start_date": start_date, "end_date": end_date},
        "metrics": {
            "views": public_views,
            "estimatedMinutesWatched": None,
            "averageViewDuration": None,
            "averageViewPercentage": None,
            "likes": public_likes,
            "comments": public_comments,
            "subscribersGained": None,
            "impressions": None,
            "impressionClickThroughRate": None,
            "returningViewers": None,
        },
        "traffic_sources": [],
        "metrics_retrieved": ["public_views", "public_likes", "public_comments"] if public_views is not None else [],
        "metrics_unavailable": [
            "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
            "subscribersGained", "trafficSources", "impressions", "impressionClickThroughRate", "returningViewers",
        ],
        "analytics_limitations": [
            query_res.get("message", "Detailed retention, watch time, impressions, CTR, and returning viewers require yt-analytics.readonly OAuth scope."),
        ],
        "retrieval_timestamp": retrieval_ts,
        "is_live_analytics": False,
        "note": query_res.get("message", "Detailed retention metrics require yt-analytics.readonly scope."),
    }


def sync_owner_channel_analytics(
    days_back: int = EVALUATION_WINDOW_DAYS,
    max_videos: int = 50,
    db_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Connects to actual owner channel data over a rolling `days_back` window (default 30 days):
    - Verifies channel ownership against config.YOUTUBE_CHANNEL_ID.
    - Uses YouTube Data API v3 (OAuth youtube.readonly or API key fallback) to list recent uploads.
    - Uses YouTube Analytics API v2 (OAuth yt-analytics.readonly) where permitted to pull
      watch time, AVD, APV, subscribers gained, and traffic sources.
    - Marks unavailable private owner metrics as None (never 0) when Analytics v2 scope is missing or delayed.
    - Never substitutes public Data API stats as private owner analytics.
    """
    from apis.growth_database import get_performance_db
    from agents.growth_analyst import classify_content_pillar

    caps = get_analytics_capabilities_and_limitations()
    db = db_override or get_performance_db()
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=days_back)
    start_date = cutoff.date().isoformat()
    end_date = today.date().isoformat()
    obs_period = f"{start_date}..{end_date}"

    synced_videos = []
    owner_analytics_videos = []
    delayed_videos = []
    source_used = "none"
    errors = []

    expected_cid = getattr(config, "YOUTUBE_CHANNEL_ID", "").strip()
    yt_client = None
    channel_id = expected_cid
    channel_verified = False
    uploads_playlist_id = None

    if caps["has_youtube_readonly_scope"]:
        try:
            from uploader.youtube import _get_service
            yt_client = _get_service()
            ch_resp = yt_client.channels().list(mine=True, part="contentDetails,snippet").execute()
            items = ch_resp.get("items", [])
            if items:
                discovered_cid = items[0]["id"]
                if expected_cid.startswith("UC") and discovered_cid != expected_cid:
                    return {
                        "ok": False,
                        "channel_id": discovered_cid,
                        "expected_channel_id": expected_cid,
                        "channel_verified": False,
                        "error": f"Channel ownership mismatch: OAuth returned {discovered_cid}, expected {expected_cid}.",
                        "videos_synced": 0,
                        "capabilities": caps,
                        "limitations": caps["limitations"],
                    }
                channel_id = discovered_cid
                channel_verified = True
                uploads_playlist_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                source_used = "youtube_oauth"
        except Exception as e:
            errors.append(f"OAuth channels.list failed: {e}")
            yt_client = None

    if not uploads_playlist_id and caps["has_public_data_api_fallback"]:
        try:
            yt_client = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
            ch_params = {"part": "contentDetails,snippet"}
            if channel_id.startswith("@"):
                ch_params["forHandle"] = channel_id
            else:
                ch_params["id"] = channel_id
            ch_resp = yt_client.channels().list(**ch_params).execute()
            items = ch_resp.get("items", [])
            if items:
                channel_id = items[0]["id"]
                channel_verified = (not expected_cid.startswith("UC")) or (channel_id == expected_cid)
                uploads_playlist_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                source_used = "youtube_data_api_key_fallback"
        except Exception as e:
            errors.append(f"Data API channels.list failed: {e}")

    # Step 2: Query video details and (if OAuth analytics scope exists) owner Analytics v2 metrics
    if yt_client and uploads_playlist_id:
        try:
            pl_resp = yt_client.playlistItems().list(
                playlistId=uploads_playlist_id,
                part="contentDetails,snippet",
                maxResults=min(50, max_videos),
            ).execute()
            video_ids = [
                item.get("contentDetails", {}).get("videoId")
                for item in pl_resp.get("items", [])
                if item.get("contentDetails", {}).get("videoId")
            ]

            if video_ids:
                v_resp = yt_client.videos().list(
                    id=",".join(video_ids[:50]),
                    part="snippet,statistics,contentDetails",
                ).execute()
                for v in v_resp.get("items", []):
                    vid = v["id"]
                    snippet = v.get("snippet", {})
                    stats = v.get("statistics", {})
                    cd = v.get("contentDetails", {})
                    pub_ts = snippet.get("publishedAt", "")
                    title = snippet.get("title", vid)
                    dur_sec = _parse_iso8601_duration(cd.get("duration", ""))
                    is_short = (0 < dur_sec <= 65.0) or ("#short" in title.lower())
                    v_fmt = "short" if is_short else "longform"

                    is_recent_48h = False
                    if pub_ts:
                        try:
                            pub_dt = datetime.fromisoformat(pub_ts.replace("Z", "+00:00"))
                            if pub_dt < cutoff:
                                continue
                            is_recent_48h = (today - pub_dt).total_seconds() < 48 * 3600
                        except Exception:
                            pass

                    views = int(stats.get("viewCount", 0) or 0)
                    likes = int(stats.get("likeCount", 0) or 0)
                    comments = int(stats.get("commentCount", 0) or 0)
                    watch_min = None
                    avd = None
                    apv = None
                    subs_gained = None
                    traffic_sources = []
                    has_owner_row = False

                    if caps["has_analytics_scope"]:
                        q_res = query_analytics_report(
                            ids="channel==MINE",
                            start_date=start_date,
                            end_date=end_date,
                            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained",
                            filters=f"video=={vid}",
                        )
                        if q_res.get("ok") and q_res.get("rows"):
                            row = q_res["rows"][0]
                            views = int(row[0])
                            watch_min = round(float(row[1]), 2)
                            avd = round(float(row[2]), 1)
                            apv = round(float(row[3]), 2)
                            likes = int(row[4])
                            comments = int(row[5])
                            subs_gained = int(row[6])
                            traffic_sources = get_traffic_sources(vid, start_date=start_date, end_date=end_date)
                            has_owner_row = True
                            source_used = "youtube_analytics_api_v2"
                            owner_analytics_videos.append(vid)
                        elif q_res.get("ok") and is_recent_48h:
                            delayed_videos.append(vid)

                    db.record_snapshot(
                        video_id=vid,
                        channel_id=channel_id,
                        video_format=v_fmt,
                        topic=title,
                        content_pillar=classify_content_pillar(title, title),
                        publication_timestamp=pub_ts,
                        video_duration=dur_sec,
                        title=title,
                        views=views,
                        engaged_views=None,
                        watch_time_minutes=watch_min,
                        average_view_duration_seconds=avd,
                        average_percentage_viewed=apv,
                        impressions=None,
                        ctr=None,
                        likes=likes,
                        comments=comments,
                        subscribers_gained=subs_gained,
                        returning_viewers=None,
                        traffic_sources=traffic_sources,
                        checkpoint="owner_sync_30d",
                        observation_period=obs_period,
                        owner_analytics_available=has_owner_row,
                        metadata_extras={"analytics_source": "youtube_analytics_api_v2" if has_owner_row else source_used},
                    )
                    synced_videos.append(vid)
        except Exception as e:
            errors.append(f"Owner video sync error: {e}")

    metrics_retrieved = (
        ["views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "likes", "comments", "subscribersGained", "trafficSources"]
        if owner_analytics_videos
        else (["public_views", "public_likes", "public_comments"] if synced_videos else [])
    )
    metrics_unavailable = (
        []
        if owner_analytics_videos
        else ["estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "subscribersGained", "trafficSources"]
    )
    metrics_unavailable_at_video_level = ["impressions", "impressionClickThroughRate", "returningViewers"]

    return {
        "ok": len(synced_videos) > 0 or len(errors) == 0,
        "channel_id": channel_id,
        "channel_verified": channel_verified,
        "evaluation_window_days": days_back,
        "date_range": {"start_date": start_date, "end_date": end_date},
        "source": source_used,
        "videos_synced": len(synced_videos),
        "owner_analytics_videos_count": len(owner_analytics_videos),
        "delayed_videos": delayed_videos,
        "video_ids": synced_videos,
        "metrics_retrieved": metrics_retrieved,
        "metrics_unavailable": metrics_unavailable,
        "metrics_unavailable_at_video_level": metrics_unavailable_at_video_level,
        "capabilities": caps,
        "limitations": caps["limitations"],
        "errors": errors,
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
    days_back: int = EVALUATION_WINDOW_DAYS,
) -> Dict[str, Any]:
    """
    Generates a separated weekly report for Shorts and Long-form videos over a rolling evaluation period
    (default 30 days):
    - Never compares raw view counts directly without accounting for format length.
    - Computes median views, watch time, AVD, APV, subscriber conversion per 1,000 views, and returning viewers (where available).
    - Identifies strong vs weak topics.
    - Evaluates retention thresholds (Long-form target: >= 45%, Shorts target: >= 70%).
    - Explicitly reports analytics limitations.
    - Generates actionable future experiments.
    """
    data = snapshots if snapshots is not None else load_snapshots()
    now_str = datetime.now(timezone.utc).isoformat()
    caps = get_analytics_capabilities_and_limitations()

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
            "average_view_duration_seconds": m.get("averageViewDuration") or 0.0,
            "average_percentage_viewed": m.get("averageViewPercentage") or 0.0,
            "subscribers_gained": m.get("subscribersGained") or 0,
            "impressions": m.get("impressions") or 0,
            "ctr": m.get("impressionClickThroughRate") or 0.0,
            "returning_viewers": m.get("returningViewers"),
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
                "median_views": 0.0,
                "total_watch_time_minutes": 0.0,
                "avg_view_duration_seconds": 0.0,
                "avg_percentage_viewed": 0.0,
                "total_subscribers_gained": 0,
                "sub_conversion_per_1k": 0.0,
                "returning_viewers": {"available": False, "total": None},
                "best_performer": None,
                "strong_topics": [],
                "weak_topics": [],
                "retention_weaknesses": [],
            }

        total_v = sum(i["views"] for i in items)
        median_v = _median([float(i["views"]) for i in items])
        total_wt = round(sum(i["watch_time_minutes"] for i in items), 2)
        avd_list = [i["average_view_duration_seconds"] for i in items if i["average_view_duration_seconds"] > 0]
        avg_avd = round(sum(avd_list) / len(avd_list), 1) if avd_list else 0.0
        total_subs = sum(i["subscribers_gained"] for i in items)
        pct_list = [i["average_percentage_viewed"] for i in items if i["average_percentage_viewed"] > 0]
        avg_pct = round(sum(pct_list) / len(pct_list), 2) if pct_list else 0.0
        sub_conv = round((total_subs / total_v * 1000), 2) if total_v > 0 else 0.0
        ret_vals = [i["returning_viewers"] for i in items if i.get("returning_viewers") is not None]
        ret_info = (
            {"available": True, "total": sum(ret_vals)}
            if ret_vals
            else {"available": False, "total": None, "note": "Returning viewers not exposed in per-video Analytics v2 query."}
        )

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

        result_group = {
            "video_count": len(items),
            "total_views": total_v,
            "median_views": median_v,
            "total_watch_time_minutes": total_wt,
            "avg_view_duration_seconds": avg_avd,
            "avg_percentage_viewed": avg_pct,
            "total_subscribers_gained": total_subs,
            "sub_conversion_per_1k": sub_conv,
            "returning_viewers": ret_info,
            "best_performer": best,
            "strong_topics": strong,
            "weak_topics": weak,
            "retention_weaknesses": retention_issues,
        }
        if not is_shorts:
            total_impr = sum(i["impressions"] for i in items)
            ctr_vals = [i["ctr"] for i in items if i["ctr"] > 0]
            result_group["total_impressions"] = total_impr
            result_group["avg_ctr"] = round(sum(ctr_vals) / len(ctr_vals), 4) if ctr_vals else 0.0
        return result_group

    lf_analysis = analyze_format_group(longform_videos, is_shorts=False)
    sh_analysis = analyze_format_group(shorts_videos, is_shorts=True)

    # Formulate recommendations
    recommendations = []
    if sh_analysis["retention_weaknesses"]:
        recommendations.append("Shorts hook optimization: Replace narrative preamble with high-intensity visual paradox in the first 2.5 seconds.")
    if lf_analysis["retention_weaknesses"]:
        recommendations.append("Long-form pacing: Introduce evidence-grounded visual reveals (artifacts, maps, diagrams) aligned with the topic.")
    if sh_analysis["total_views"] > lf_analysis["total_views"] * 2:
        recommendations.append("Topic crossover: Expand top-performing Shorts topics into 10-minute long-form investigative documentaries.")
    if not recommendations:
        recommendations.append("Pacing test: Experiment with 3-part archaeological micro-series for top-performing ancient dynasty topics.")

    report = {
        "report_generated_at": now_str,
        "evaluation_period_days": days_back,
        "longform_analytics": lf_analysis,
        "shorts_analytics": sh_analysis,
        "analytics_capabilities": caps,
        "analytics_limitations": caps["limitations"],
        "recommended_future_experiments": recommendations,
    }

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(WEEKLY_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report
