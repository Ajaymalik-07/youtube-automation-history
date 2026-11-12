"""
YouTube Uploader & Autonomous Publishing Engine
Phase 17 Overhaul: Fully automated create -> validate -> upload -> schedule -> analytics workflow.
Removes all manual human approval dependencies and enforces automated quality gates,
idempotent duplicate prevention, and timezone-aware scheduling in Asia/Kolkata.
"""
import os
import json
import pickle
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
import config
from uploader.safety import (
    record_production_state,
    get_production_record,
    is_eligible_for_upload,
    record_quality_gate_result,
    PublishingState,
)
from uploader.quality_gates import evaluate_all_quality_gates, classify_content_disclosures

TOKEN_FILE = "youtube_token.pickle"
IST = timezone(timedelta(hours=5, minutes=30))


def is_configured() -> bool:
    """Return True if OAuth credentials and token exist and are valid."""
    config.sync_client_secret_file()
    if hasattr(config, "sync_youtube_token_file"):
        config.sync_youtube_token_file()
    secret_file = getattr(config, "YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    if not os.path.exists(secret_file):
        return False
    try:
        with open(secret_file, encoding="utf-8") as f:
            if "YOUR_CLIENT_ID" in f.read():
                return False
    except Exception:
        return False
    return os.path.exists(TOKEN_FILE)


def _get_service():
    """Return an authenticated YouTube service object with automatic token refresh."""
    if hasattr(config, "sync_youtube_token_file"):
        config.sync_youtube_token_file()
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "rb") as f:
                creds = pickle.load(f)
            if creds and not creds.valid and creds.expired and creds.refresh_token:
                from uploader.oauth_manager import safe_refresh_credentials
                if not safe_refresh_credentials(creds, TOKEN_FILE):
                    creds = None
        except Exception as e:
            print(f"   ⚠ Could not load/refresh token from {TOKEN_FILE}: {e}")
            creds = None

    if not creds or not creds.valid:
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            raise RuntimeError(
                "YouTube OAuth credentials are missing or could not be refreshed in headless CI environment. "
                "Ensure YOUTUBE_TOKEN_BASE64 in your GitHub repository secrets is up to date."
            )
        from uploader.oauth_manager import reauthorize_channel
        expected_cid = getattr(config, "YOUTUBE_CHANNEL_ID", "").strip() or None
        ok, res = reauthorize_channel(open_browser=True, timeout_seconds=180, expected_channel_id=expected_cid)
        if not ok:
            raise RuntimeError(f"YouTube OAuth authorization failed: {res.get('error', 'unknown error')}")
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    return build("youtube", "v3", credentials=creds)


def verify_category_id(youtube, category_id: str = "27", region_code: str = "IN") -> str:
    """Verifies that category_id is supported in region_code, returning verified ID or fallback."""
    try:
        resp = youtube.videoCategories().list(part="snippet", regionCode=region_code).execute()
        valid_ids = [item["id"] for item in resp.get("items", [])]
        if str(category_id) in valid_ids:
            return str(category_id)
        if "27" in valid_ids:  # Education
            return "27"
        if valid_ids:
            return valid_ids[0]
    except Exception:
        pass
    return str(category_id)


def _get_publishing_tz():
    """Return configured publishing timezone (defaults to Asia/Kolkata)."""
    tz_name = getattr(config, "PUBLISHING_TIMEZONE", "Asia/Kolkata")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        return IST


def calculate_next_scheduled_time(is_shorts: bool = False, min_lead_minutes: int = 30) -> str:
    """
    Calculates next optimal publication slot in the configured timezone (default Asia/Kolkata / IST),
    ensuring timestamp is strictly in the future.
    Reads configurable slot hours from config while preserving backward compatibility.
    Returns RFC 3339 / ISO 8601 UTC string (e.g. '2026-11-12T13:30:00Z').
    """
    tz = _get_publishing_tz()
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    min_target = now_local + timedelta(minutes=min_lead_minutes)

    if is_shorts:
        cfg = getattr(config, "SHORTS_UPLOAD_CONFIG", {})
        raw_hours = cfg.get("target_hours_ist") or getattr(config, "SHORTS_TARGET_HOURS_IST", [9, 12, 16, 19, 22])
    else:
        cfg = getattr(config, "LONGFORM_UPLOAD_CONFIG", {})
        raw_hours = cfg.get("target_hours_ist") or (
            [cfg["target_hour_ist"]] if "target_hour_ist" in cfg else getattr(config, "LONGFORM_TARGET_HOURS_IST", [19])
        )

    hours = sorted({int(h) % 24 for h in raw_hours}) if raw_hours else ([9, 12, 16, 19, 22] if is_shorts else [19])

    target_local = None
    for h in hours:
        candidate = now_local.replace(hour=h, minute=0, second=0, microsecond=0)
        if candidate > min_target:
            target_local = candidate
            break

    if target_local is None:
        # Roll over to the first slot tomorrow
        target_local = (now_local + timedelta(days=1)).replace(hour=hours[0], minute=0, second=0, microsecond=0)

    target_utc = target_local.astimezone(timezone.utc)
    return target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_upload_and_processing(youtube, video_id: str, expected_channel_id: Optional[str] = None) -> dict:
    """
    Queries videos.list with part='snippet,status,processingDetails' to inspect:
    - Channel ownership verification (ensures video belongs to authenticated channel).
    - Upload status and privacy status.
    - Processing status (processing, succeeded, failed, terminated).
    - Failure or rejection reasons if any.
    """
    try:
        res = youtube.videos().list(id=video_id, part="snippet,status,processingDetails").execute()
        items = res.get("items", [])
        if not items:
            return {
                "ok": False,
                "video_id": video_id,
                "status": "not_found",
                "is_processing_complete": False,
                "is_processing_failed": True,
                "failure_reason": "Video ID not found in YouTube Data API query.",
            }

        v = items[0]
        snippet_info = v.get("snippet", {})
        status_info = v.get("status", {})
        proc_info = v.get("processingDetails", {})

        video_channel_id = snippet_info.get("channelId", "")
        channel_verified = True
        if expected_channel_id and video_channel_id:
            channel_verified = (video_channel_id == expected_channel_id)

        upload_status = status_info.get("uploadStatus", "uploaded")
        proc_status = proc_info.get("processingStatus", "processing")
        rejection_reason = status_info.get("rejectionReason")
        failure_reason = rejection_reason or proc_info.get("processingFailureReason")

        is_failed = (
            proc_status in ("failed", "terminated")
            or upload_status in ("rejected", "failed")
            or bool(rejection_reason)
            or not channel_verified
        )

        is_complete = (proc_status == "succeeded" or upload_status == "processed") and not is_failed

        return {
            "ok": True,
            "video_id": video_id,
            "channel_id": video_channel_id,
            "channel_verified": channel_verified,
            "upload_status": upload_status,
            "privacy_status": status_info.get("privacyStatus"),
            "publish_at": status_info.get("publishAt"),
            "processing_status": proc_status,
            "is_processing_complete": is_complete,
            "is_processing_failed": is_failed,
            "failure_reason": failure_reason,
            "parts_available": proc_info.get("partsProcessed"),
        }
    except Exception as e:
        return {
            "ok": False,
            "video_id": video_id,
            "error": str(e),
            "is_processing_complete": False,
            "is_processing_failed": False,
        }



def upload_to_youtube(script: dict, video_path: str, thumb_path: str = None,
                      title: str = None, description: str = None, tags: list = None,
                      privacy: str = None, publish_at: str = None,
                      is_shorts: bool = None, upload_mode: str = None,
                      research: dict = None, skip_quality_gate: bool = False) -> str:
    """
    Fully automated upload pipeline:
    1. Idempotency Check: Prevents duplicate uploads of already published videos.
    2. Automated Quality Gates: Evaluates research, script, video, and metadata.
    3. Timezone-aware scheduling (Asia/Kolkata) with private default security.
    4. Resumable upload via official YouTube Data API v3.
    5. Post-upload processing and publication verification.
    """
    if is_shorts is None:
        is_shorts = (script.get("video_type") == "shorts" or "short" in os.path.basename(video_path).lower())

    # --- 1. Idempotent Duplicate Prevention ---
    rec = get_production_record(video_path)
    rec_meta = (rec or {}).get("metadata", {}) or {}
    existing_yt_id = rec_meta.get("youtube_id")
    is_proc_failed = rec_meta.get("error_type") == "ProcessingFailure"
    if rec and (
        rec.get("current_state") in (
            PublishingState.UPLOADED_PRIVATE.value,
            PublishingState.SCHEDULED.value,
            PublishingState.PUBLISHED.value,
            PublishingState.ANALYTICS_PENDING.value,
            PublishingState.COMPLETED.value,
        )
        or (existing_yt_id and not is_proc_failed)
    ):
        existing_url = rec_meta.get("youtube_url") or (f"https://www.youtube.com/watch?v={existing_yt_id}" if existing_yt_id else None)
        if existing_url:
            print(f"   ℹ Idempotency check: Video already published/scheduled: {existing_url}")
            return existing_url

    content_id = rec_meta.get("content_id")
    job_id = rec_meta.get("job_id")
    target_date_meta = rec_meta.get("target_date")
    slot_hour_meta = rec_meta.get("slot_hour_ist")
    slot_index_meta = rec_meta.get("index")
    intended_publish_at = rec_meta.get("intended_publish_at") or publish_at

    def _pending_manifest_path(vpath: str, content_id: Optional[str] = None) -> str:
        safe_seed = "".join(c if (c.isalnum() or c in "-_") else "_" for c in (content_id or "")) if content_id else hashlib.sha1(
            os.path.normpath(vpath).encode("utf-8", errors="ignore")
        ).hexdigest()[:10]
        return os.path.join(config.OUTPUT_DIR, "pending_uploads", f"upload_{safe_seed}_{os.path.basename(vpath)}.json")

    def _with_credits_attribution(vpath: str, desc_text: str) -> str:
        credits_path = os.path.join(os.path.dirname(vpath), "credits.json")
        if not os.path.exists(credits_path):
            return desc_text
        try:
            items = json.load(open(credits_path, encoding="utf-8"))
            if not isinstance(items, list) or not items:
                return desc_text
            seen_lines = []
            for item in items:
                src = str(item.get("source", "")).strip()
                author = str(item.get("author", "")).strip()
                lic = str(item.get("license", "")).strip()
                if src:
                    entry = f"- {src}: {author or 'Contributor'} ({lic or 'Standard License'})"
                    if entry not in seen_lines:
                        seen_lines.append(entry)
            if not seen_lines:
                return desc_text
            block = "\n\nVisual Credits:\n" + "\n".join(seen_lines[:8])
            if "Visual Credits:" not in desc_text and len(desc_text) + len(block) <= 4950:
                return desc_text + block
        except Exception:
            pass
        return desc_text

    # Optimize metadata using SEO candidate generator
    from agents.seo_optimizer import optimize_for_100_percent
    topic = script.get("topic") or script.get("title", "")
    opt = optimize_for_100_percent(
        title=title or script.get("title", "History Documentary"),
        description=description or script.get("description", ""),
        tags=tags or script.get("tags", []),
        sections=script.get("sections", []),
        topic=topic,
        is_shorts=is_shorts,
    )
    final_title = opt["title"]
    final_desc = _with_credits_attribution(video_path, opt["description"])
    final_tags = opt["tags"]

    metadata_dict = {
        "title": final_title,
        "description": final_desc,
        "tags": final_tags,
        "categoryId": getattr(config, "VIDEO_CATEGORY_ID", "27"),
        "defaultLanguage": getattr(config, "DEFAULT_LANGUAGE", "hi"),
    }

    # --- 2. Automated Quality Gates ---
    if not skip_quality_gate:
        q_report = evaluate_all_quality_gates(
            research=research,
            script=script,
            video_path=video_path,
            thumb_path=thumb_path,
            metadata=metadata_dict,
            is_shorts=is_shorts,
        )
        record_quality_gate_result(video_path, q_report)
        if not q_report.get("passed", False):
            issues = q_report.get("blocking_issues", [])
            print(f"   🚨 Video blocked by Automated Quality Gate: {len(issues)} critical issue(s)")
            for iss in issues:
                print(f"      - {iss}")
            diag_file = q_report.get("diagnostic_file", "")
            print(f"      Diagnostic report preserved at: {diag_file}")
            return f"local://blocked_quality_gate/{os.path.basename(video_path)}"

    # Transition state to UPLOAD_QUEUED
    record_production_state(video_path, PublishingState.UPLOAD_QUEUED.value, metadata={
        "title": final_title,
        "is_shorts": is_shorts,
    })

    # --- 3. Determine Upload Mode & Scheduling ---
    mode = upload_mode or getattr(config, "YOUTUBE_UPLOAD_MODE", config.UPLOAD_MODE_SCHEDULED)
    target_publish_at = publish_at

    if mode == config.UPLOAD_MODE_SCHEDULED:
        target_privacy = "private"
        if not target_publish_at:
            target_publish_at = calculate_next_scheduled_time(is_shorts=is_shorts)
        else:
            # Validate future timestamp
            try:
                # Parse ISO timestamp
                clean_ts = target_publish_at.replace("Z", "+00:00")
                parsed_dt = datetime.fromisoformat(clean_ts)
                if parsed_dt <= datetime.now(timezone.utc) + timedelta(minutes=15):
                    print("   ⚠ Scheduled publishAt timestamp is in the past or under 15 min; recalculating next IST slot…")
                    target_publish_at = calculate_next_scheduled_time(is_shorts=is_shorts)
            except Exception:
                target_publish_at = calculate_next_scheduled_time(is_shorts=is_shorts)
    elif mode == config.UPLOAD_MODE_IMMEDIATE:
        target_privacy = "public"
        target_publish_at = None
    else:  # PRIVATE_ARCHIVE
        target_privacy = "private"
        target_publish_at = None

    if privacy:
        target_privacy = privacy

    # --- 4. Offline / Unconfigured Handler ---
    if not is_configured():
        print("   ℹ YouTube OAuth credentials not linked or headless environment.")
        print(f"      Video {video_path} validated and ready for upload ({mode}).")
        os.makedirs(os.path.join(config.OUTPUT_DIR, "pending_uploads"), exist_ok=True)
        manifest_path = _pending_manifest_path(video_path, content_id=content_id)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_path": video_path,
                "thumb_path": thumb_path,
                "title": final_title,
                "description": final_desc,
                "tags": final_tags,
                "mode": mode,
                "original_mode": mode,
                "publish_at": target_publish_at,
                "original_publish_at": intended_publish_at,
                "privacy": target_privacy,
                "is_shorts": bool(is_shorts),
                "content_id": content_id,
                "job_id": job_id,
                "target_date": target_date_meta,
                "slot_hour_ist": slot_hour_meta,
                "slot_index": slot_index_meta,
                "script": script or {},
                "research": research or {},
                "retry_count": 0,
                "status": "ready_for_upload",
            }, f, indent=2)
        print(f"      Saved ready-to-publish manifest: {manifest_path}")
        return f"local://pending_upload/{os.path.basename(video_path)}"

    # --- 5. YouTube API Upload Execution ---
    youtube = _get_service()

    # Channel identity guard (non-fatal if mocked channels().list returns no real dict items)
    expected_cid = getattr(config, "YOUTUBE_CHANNEL_ID", "") or ""
    if expected_cid:
        try:
            ch_res = youtube.channels().list(part="id,snippet", mine=True).execute()
            if isinstance(ch_res, dict) and isinstance(ch_res.get("items"), list) and ch_res["items"]:
                actual_cid = ch_res["items"][0].get("id", "")
                if actual_cid and actual_cid != expected_cid:
                    err_msg = f"Authenticated channel mismatch: got '{actual_cid}', expected '{expected_cid}'."
                    print(f"   ❌ {err_msg}")
                    record_production_state(video_path, PublishingState.FAILED.value, metadata={
                        "error": err_msg,
                        "error_type": "ChannelMismatch",
                    })
                    return f"local://channel_mismatch/{os.path.basename(video_path)}"
        except Exception:
            pass

    verified_cat_id = verify_category_id(youtube, getattr(config, "VIDEO_CATEGORY_ID", "27"))
    disclosures = classify_content_disclosures(script, video_path)

    body = {
        "snippet": {
            "title":           final_title[:100],
            "description":     final_desc[:4950],
            "tags":            final_tags[:15],
            "categoryId":      verified_cat_id,
            "defaultLanguage": getattr(config, "DEFAULT_LANGUAGE", "hi"),
        },
        "status": {
            "privacyStatus":           target_privacy,
            "license":                 "youtube",
            "embeddable":              True,
            "publicStatsViewable":     True,
            "selfDeclaredMadeForKids": disclosures["selfDeclaredMadeForKids"],
            "containsSyntheticMedia":   disclosures["containsSyntheticMedia"],
        },
    }
    if target_publish_at:
        body["status"]["publishAt"] = target_publish_at

    # Notify subscribers config
    cfg_section = getattr(config, "SHORTS_UPLOAD_CONFIG" if is_shorts else "LONGFORM_UPLOAD_CONFIG", {})
    notify_sub = cfg_section.get("notify_subscribers", False if is_shorts else True)

    record_production_state(video_path, PublishingState.UPLOADING.value, metadata={
        "mode": mode,
        "privacy": target_privacy,
        "publish_at": target_publish_at,
    })

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024,
    )

    insert_req = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
        notifySubscribers=notify_sub,
    )

    sched_msg = f"scheduled for {target_publish_at} (Asia/Kolkata)" if target_publish_at else f"privacy: {target_privacy}"
    print(f"   → Uploading {os.path.basename(video_path)} [{sched_msg}]…")
    response = None
    try:
        chunk_retries = 0
        max_chunk_retries = 3
        while response is None:
            try:
                status, response = insert_req.next_chunk()
                chunk_retries = 0
                if status:
                    pct = int(status.progress() * 100)
                    print(f"   → {pct}% uploaded", end="\r")
            except HttpError as chunk_err:
                resp_status = getattr(getattr(chunk_err, "resp", None), "status", None)
                if resp_status in (500, 502, 503, 504) and chunk_retries < max_chunk_retries:
                    chunk_retries += 1
                    print(f"\n   ⚠ Transient HTTP {resp_status} during upload chunk (retry {chunk_retries}/{max_chunk_retries})…")
                    import time as _time
                    _time.sleep(2 ** chunk_retries)
                    continue
                raise

        print()
        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"   ✅ Video uploaded to YouTube: {video_url}")

        # Upload thumbnail if provided
        if thumb_path and os.path.exists(thumb_path):
            try:
                print("   → Setting video thumbnail…")
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg"),
                ).execute()
                print("   ✅ Thumbnail uploaded successfully.")
            except Exception as e:
                print(f"   ⚠ Thumbnail upload warning: {e}")

        # Post-Upload Verification
        proc_res = verify_upload_and_processing(
            youtube,
            video_id,
            expected_channel_id=expected_cid or None,
        )
        print(f"   → YouTube processing verification: {proc_res.get('processing_status', 'uploaded')}")

        if proc_res.get("is_processing_failed"):
            fail_reason = proc_res.get("failure_reason") or "YouTube processing failed or upload rejected."
            print(f"   ❌ YouTube processing failure detected: {fail_reason}")
            record_production_state(video_path, PublishingState.FAILED.value, metadata={
                "youtube_id": video_id,
                "youtube_url": video_url,
                "error": fail_reason,
                "error_type": "ProcessingFailure",
                "processing_verification": proc_res,
            })
            return f"local://failed_processing/{os.path.basename(video_path)}"

        # Determine terminal/next state
        if target_publish_at:
            next_state = PublishingState.SCHEDULED.value
        elif target_privacy == "public":
            next_state = PublishingState.PUBLISHED.value
        else:
            next_state = PublishingState.UPLOADED_PRIVATE.value

        record_production_state(video_path, next_state, metadata={
            "youtube_id": video_id,
            "youtube_url": video_url,
            "mode": mode,
            "privacy": target_privacy,
            "publish_at": target_publish_at,
            "intended_publish_at": intended_publish_at,
            "publication_status": next_state,
            "upload_completed": True,
            "youtube_processing_completed": bool(proc_res.get("is_processing_complete")),
            "actually_published": (next_state == PublishingState.PUBLISHED.value),
            "title": final_title,
            "processing_verification": proc_res,
        })

        # Transition to ANALYTICS_PENDING
        record_production_state(video_path, PublishingState.ANALYTICS_PENDING.value)

        return video_url

    except HttpError as err:
        err_str = str(err)
        is_quota = any(k in err_str.lower() for k in ("quotaexceeded", "dailylimitexceeded", "uploadlimitexceeded"))
        print(f"\n   ⚠ YouTube API Error during upload: {err}")
        record_production_state(video_path, PublishingState.FAILED.value, metadata={
            "error": err_str,
            "error_type": "QuotaExceeded" if is_quota else "HttpError",
            "intended_publish_at": intended_publish_at,
            "upload_completed": False,
            "actually_published": False,
        })
        os.makedirs(os.path.join(config.OUTPUT_DIR, "pending_uploads"), exist_ok=True)
        manifest_path = _pending_manifest_path(video_path, content_id=content_id)
        existing_retry = 0
        if os.path.exists(manifest_path):
            try:
                existing_retry = int(json.load(open(manifest_path, encoding="utf-8")).get("retry_count", 0))
            except Exception:
                existing_retry = 0
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_path": video_path,
                "thumb_path": thumb_path,
                "title": final_title,
                "description": final_desc,
                "tags": final_tags,
                "mode": mode,
                "original_mode": mode,
                "publish_at": target_publish_at,
                "original_publish_at": intended_publish_at,
                "privacy": target_privacy,
                "is_shorts": bool(is_shorts),
                "content_id": content_id,
                "job_id": job_id,
                "target_date": target_date_meta,
                "slot_hour_ist": slot_hour_meta,
                "slot_index": slot_index_meta,
                "script": script or {},
                "research": research or {},
                "retry_count": existing_retry,
                "error": err_str,
                "status": "pending_quota_reset" if is_quota else "pending_retry",
            }, f, indent=2)
        if is_quota:
            return f"local://pending_quota_reset/{os.path.basename(video_path)}"
        return f"local://failed_upload/{os.path.basename(video_path)}"
    except Exception as e:
        print(f"\n   ⚠ Unexpected upload failure: {e}")
        record_production_state(video_path, PublishingState.FAILED.value, metadata={
            "error": str(e),
            "error_type": "UnexpectedException",
        })
        return f"local://failed_upload/{os.path.basename(video_path)}"


def reconcile_channel_publications(
    output_dir: Optional[str] = None,
    max_results: int = 25,
    youtube_service=None,
) -> Dict[str, Any]:
    """
    Correlates actual channel uploads (via YouTube Data API v3 or OAuth) with local
    production_database.json and automation_schedule.json history records.
    Updates publication_status / actually_published when a scheduled video becomes public.
    """
    import requests
    from uploader.safety import load_production_db

    base_dir = output_dir or getattr(config, "OUTPUT_DIR", "output")
    expected_cid = getattr(config, "YOUTUBE_CHANNEL_ID", "") or ""
    api_key = getattr(config, "YOUTUBE_API_KEY", "") or ""

    live_items: list = []
    source = "unavailable"
    errors: list = []

    if youtube_service is not None:
        try:
            ch = youtube_service.channels().list(part="contentDetails,snippet", id=expected_cid or None, mine=(None if expected_cid else True)).execute()
            items = ch.get("items", [])
            if items:
                up_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
                pl = youtube_service.playlistItems().list(part="contentDetails", playlistId=up_pl, maxResults=min(max_results, 50)).execute()
                vids = [it["contentDetails"]["videoId"] for it in pl.get("items", []) if it.get("contentDetails", {}).get("videoId")]
                if vids:
                    vresp = youtube_service.videos().list(part="snippet,status,processingDetails,contentDetails", id=",".join(vids)).execute()
                    live_items = vresp.get("items", [])
                    source = "oauth_service"
        except Exception as e:
            errors.append(str(e))
    elif api_key and expected_cid:
        try:
            ch = requests.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "contentDetails,snippet", "id": expected_cid, "key": api_key},
                timeout=15,
            ).json()
            items = ch.get("items", [])
            if items:
                up_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
                pl = requests.get(
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    params={"part": "contentDetails", "playlistId": up_pl, "maxResults": min(max_results, 50), "key": api_key},
                    timeout=15,
                ).json()
                vids = [it["contentDetails"]["videoId"] for it in pl.get("items", []) if it.get("contentDetails", {}).get("videoId")]
                if vids:
                    vresp = requests.get(
                        "https://www.googleapis.com/youtube/v3/videos",
                        params={"part": "snippet,status,contentDetails", "id": ",".join(vids), "key": api_key},
                        timeout=15,
                    ).json()
                    live_items = vresp.get("items", [])
                    source = "youtube_data_api_key_fallback"
        except Exception as e:
            errors.append(str(e))

    prod_db = load_production_db()
    by_yt_id = {}
    for k, rec in prod_db.items():
        if isinstance(rec, dict):
            yt_id = (rec.get("metadata") or {}).get("youtube_id")
            if yt_id:
                by_yt_id[yt_id] = (k, rec)

    sched_urls = {}
    sched_path = os.path.join(base_dir, "automation_schedule.json")
    if os.path.exists(sched_path):
        try:
            sdata = json.load(open(sched_path, encoding="utf-8"))
            for r in sdata.get("history_runs", []) or []:
                url = str(r.get("url", ""))
                if "watch?v=" in url:
                    vid = url.split("watch?v=")[-1].split("&")[0]
                    sched_urls[vid] = r
        except Exception:
            pass

    reconciled = []
    untracked_on_channel = []
    ownership_mismatches = []

    for v in live_items:
        vid = v.get("id", "")
        snip = v.get("snippet", {})
        stat = v.get("status", {})
        actual_cid = snip.get("channelId", "")
        privacy_status = stat.get("privacyStatus", "unknown")
        publish_at = stat.get("publishAt")
        published_at = snip.get("publishedAt")
        if expected_cid and actual_cid and actual_cid != expected_cid:
            ownership_mismatches.append({"video_id": vid, "channel_id": actual_cid})

        matched_prod = vid in by_yt_id
        matched_sched = vid in sched_urls
        if matched_prod:
            vkey, rec = by_yt_id[vid]
            if privacy_status == "public":
                record_production_state(
                    rec.get("video_path", vkey),
                    rec.get("current_state", PublishingState.PUBLISHED.value),
                    metadata={
                        "publication_status": PublishingState.PUBLISHED.value,
                        "actually_published": True,
                        "actual_published_at": published_at,
                    },
                )
        elif not matched_sched:
            untracked_on_channel.append({
                "video_id": vid,
                "title": snip.get("title", ""),
                "published_at": published_at,
                "privacy_status": privacy_status,
            })

        reconciled.append({
            "video_id": vid,
            "channel_id": actual_cid,
            "title": snip.get("title", ""),
            "privacy_status": privacy_status,
            "scheduled_publish_at": publish_at,
            "actual_published_at": published_at,
            "matched_production_db": matched_prod,
            "matched_schedule_history": matched_sched,
        })

    return {
        "source": source,
        "expected_channel_id": expected_cid,
        "live_videos_inspected": len(live_items),
        "matched_production_db_count": sum(1 for r in reconciled if r["matched_production_db"]),
        "matched_schedule_history_count": sum(1 for r in reconciled if r["matched_schedule_history"]),
        "untracked_on_channel_count": len(untracked_on_channel),
        "untracked_on_channel": untracked_on_channel[:20],
        "ownership_mismatches": ownership_mismatches,
        "videos": reconciled,
        "errors": errors,
    }
