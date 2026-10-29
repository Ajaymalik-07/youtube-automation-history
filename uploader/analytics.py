"""
YouTube Analytics & Performance Retriever
Queries YouTube Data API v3 to retrieve real-time analytics for the latest
video and overall channel metrics (views, likes, comments, subscribers).
Falls back gracefully to local schedule state if API credentials are not yet linked.
"""
import os
import sys
import json
from datetime import datetime
import config

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def get_channel_and_last_video_analytics(youtube_service=None) -> dict:
    """
    Retrieves performance metrics for the channel and the most recently published video.
    Returns a structured dictionary with views, likes, comments, and growth stats.
    """
    res = {
        "available": False,
        "video_id": "",
        "video_title": "No recent video found",
        "video_url": "",
        "published_at": "",
        "views": "0",
        "likes": "0",
        "comments": "0",
        "channel_subscribers": "N/A",
        "channel_total_views": "N/A",
        "channel_total_videos": "N/A",
        "source": "none",
    }

    # 1. Try authenticated OAuth service or create one if possible
    service = youtube_service
    if service is None:
        try:
            from uploader.youtube import is_configured, _get_service
            if is_configured():
                service = _get_service()
        except Exception:
            service = None

    # 2. If OAuth service is available, fetch live stats for "mine"
    if service:
        try:
            ch_resp = service.channels().list(mine=True, part="contentDetails,statistics,snippet").execute()
            items = ch_resp.get("items", [])
            if items:
                ch = items[0]
                stats = ch.get("statistics", {})
                res["channel_subscribers"] = f"{int(stats.get('subscriberCount', 0)):,}"
                res["channel_total_views"] = f"{int(stats.get('viewCount', 0)):,}"
                res["channel_total_videos"] = f"{int(stats.get('videoCount', 0)):,}"

                uploads_id = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                if uploads_id:
                    # Fetch latest video from uploads playlist
                    pl_resp = service.playlistItems().list(
                        playlistId=uploads_id,
                        part="snippet,contentDetails",
                        maxResults=1
                    ).execute()
                    pl_items = pl_resp.get("items", [])
                    if pl_items:
                        vid_id = pl_items[0].get("contentDetails", {}).get("videoId")
                        v_title = pl_items[0].get("snippet", {}).get("title", "")
                        v_pub = pl_items[0].get("snippet", {}).get("publishedAt", "")

                        # Fetch video statistics
                        v_resp = service.videos().list(id=vid_id, part="statistics").execute()
                        v_items = v_resp.get("items", [])
                        v_stats = v_items[0].get("statistics", {}) if v_items else {}

                        res["available"] = True
                        res["video_id"] = vid_id
                        res["video_title"] = v_title
                        res["video_url"] = f"https://www.youtube.com/watch?v={vid_id}"
                        res["published_at"] = v_pub
                        res["views"] = f"{int(v_stats.get('viewCount', 0)):,}"
                        res["likes"] = f"{int(v_stats.get('likeCount', 0)):,}"
                        res["comments"] = f"{int(v_stats.get('commentCount', 0)):,}"
                        res["source"] = "youtube_oauth"
                        return res
        except Exception as e:
            print(f"   ℹ Could not fetch live analytics via OAuth: {e}")

    # 3. Try read-only with API Key + Channel ID if available
    api_key = getattr(config, "YOUTUBE_API_KEY", "")
    channel_id = getattr(config, "YOUTUBE_CHANNEL_ID", "")
    if api_key and channel_id and not api_key.startswith("YOUR_"):
        try:
            from googleapiclient.discovery import build
            yt_public = build("youtube", "v3", developerKey=api_key)
            ch_resp = yt_public.channels().list(id=channel_id, part="contentDetails,statistics").execute()
            items = ch_resp.get("items", [])
            if items:
                ch = items[0]
                stats = ch.get("statistics", {})
                res["channel_subscribers"] = f"{int(stats.get('subscriberCount', 0)):,}"
                res["channel_total_views"] = f"{int(stats.get('viewCount', 0)):,}"
                res["channel_total_videos"] = f"{int(stats.get('videoCount', 0)):,}"

                uploads_id = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                if uploads_id:
                    pl_resp = yt_public.playlistItems().list(
                        playlistId=uploads_id,
                        part="snippet,contentDetails",
                        maxResults=1
                    ).execute()
                    pl_items = pl_resp.get("items", [])
                    if pl_items:
                        vid_id = pl_items[0].get("contentDetails", {}).get("videoId")
                        v_title = pl_items[0].get("snippet", {}).get("title", "")
                        v_pub = pl_items[0].get("snippet", {}).get("publishedAt", "")

                        v_resp = yt_public.videos().list(id=vid_id, part="statistics").execute()
                        v_items = v_resp.get("items", [])
                        v_stats = v_items[0].get("statistics", {}) if v_items else {}

                        res["available"] = True
                        res["video_id"] = vid_id
                        res["video_title"] = v_title
                        res["video_url"] = f"https://www.youtube.com/watch?v={vid_id}"
                        res["published_at"] = v_pub
                        res["views"] = f"{int(v_stats.get('viewCount', 0)):,}"
                        res["likes"] = f"{int(v_stats.get('likeCount', 0)):,}"
                        res["comments"] = f"{int(v_stats.get('commentCount', 0)):,}"
                        res["source"] = "youtube_api_key"
                        return res
        except Exception as e:
            print(f"   ℹ Could not fetch live analytics via API Key: {e}")

    # 4. Fallback to local scheduler history
    try:
        from automation import load_schedule_state
        state = load_schedule_state()
        history = state.get("history_runs", [])
        if history:
            last_run = history[-1]
            res["available"] = True
            res["video_title"] = last_run.get("title", "Last Produced Video")
            res["video_url"] = last_run.get("url", "")
            res["published_at"] = last_run.get("date_ist", "")
            res["views"] = "Recorded in Studio"
            res["likes"] = "Ready"
            res["comments"] = f"SEO Score: {last_run.get('score', 100)}/100"
            res["source"] = "local_studio_history"
            return res
    except Exception:
        pass

    return res
