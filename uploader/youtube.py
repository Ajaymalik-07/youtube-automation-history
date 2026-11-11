"""
YouTube Uploader & Autonomous Publishing Engine
Phase 17 Overhaul: Fully automated create -> validate -> upload -> schedule -> analytics workflow.
Removes all manual human approval dependencies and enforces automated quality gates,
idempotent duplicate prevention, and timezone-aware scheduling in Asia/Kolkata.
"""
import os
import json
import pickle
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
from uploader.quality_gates import evaluate_all_quality_gates

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
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                with open(TOKEN_FILE, "wb") as f:
                    pickle.dump(creds, f)
        except Exception as e:
            print(f"   ⚠ Could not load/refresh token from {TOKEN_FILE}: {e}")
            creds = None

    if not creds or not creds.valid:
        if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
            raise RuntimeError(
                "YouTube OAuth credentials are missing or could not be refreshed in headless CI environment. "
                "Ensure YOUTUBE_TOKEN_BASE64 in your GitHub repository secrets is up to date."
            )
        secret_file = getattr(config, "YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
        if not os.path.exists(secret_file):
            raise FileNotFoundError(
                f"YouTube OAuth file not found: {secret_file}\n"
                "Follow the setup guide to create it in Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            secret_file, config.YOUTUBE_SCOPES
        )
        flow.redirect_uri = "http://localhost:8080/"
        creds = flow.run_local_server(bind_addr="0.0.0.0", port=8080, open_browser=True, timeout_seconds=180)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

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


def calculate_next_scheduled_time(is_shorts: bool = False, min_lead_minutes: int = 30) -> str:
    """
    Calculates next optimal publication slot in Asia/Kolkata (IST),
    ensuring timestamp is strictly in the future.
    Returns RFC 3339 / ISO 8601 UTC string (e.g. '2026-11-12T13:30:00Z').
    """
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    if is_shorts:
        # Slots at 10:00 AM IST and 6:00 PM (18:00) IST
        candidate_today_10 = now_ist.replace(hour=10, minute=0, second=0, microsecond=0)
        candidate_today_18 = now_ist.replace(hour=18, minute=0, second=0, microsecond=0)

        if candidate_today_10 > now_ist + timedelta(minutes=min_lead_minutes):
            target_ist = candidate_today_10
        elif candidate_today_18 > now_ist + timedelta(minutes=min_lead_minutes):
            target_ist = candidate_today_18
        else:
            # Tomorrow at 10:00 AM IST
            target_ist = (now_ist + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    else:
        # Long-form slot at 7:00 PM (19:00) IST
        candidate_today_19 = now_ist.replace(hour=19, minute=0, second=0, microsecond=0)
        if candidate_today_19 > now_ist + timedelta(minutes=min_lead_minutes):
            target_ist = candidate_today_19
        else:
            # Tomorrow at 19:00 IST
            target_ist = (now_ist + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)

    target_utc = target_ist.astimezone(timezone.utc)
    return target_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_upload_and_processing(youtube, video_id: str) -> dict:
    """
    Queries videos.list to inspect upload and processing status.
    Returns processing details and detected failure status if any.
    """
    try:
        res = youtube.videos().list(id=video_id, part="snippet,status,processingDetails").execute()
        items = res.get("items", [])
        if not items:
            return {"ok": False, "status": "not_found", "details": None}

        v = items[0]
        status_info = v.get("status", {})
        proc_info = v.get("processingDetails", {})

        return {
            "ok": True,
            "upload_status": status_info.get("uploadStatus"),
            "privacy_status": status_info.get("privacyStatus"),
            "publish_at": status_info.get("publishAt"),
            "processing_status": proc_info.get("processingStatus", "processing"),
            "rejection_reason": status_info.get("rejectionReason"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
    if rec and rec.get("current_state") in (
        PublishingState.SCHEDULED.value,
        PublishingState.PUBLISHED.value,
        PublishingState.COMPLETED.value,
    ):
        existing_url = rec.get("metadata", {}).get("youtube_url")
        if existing_url:
            print(f"   ℹ Idempotency check: Video already published/scheduled: {existing_url}")
            return existing_url

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
    final_desc = opt["description"]
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
        manifest_path = os.path.join(config.OUTPUT_DIR, "pending_uploads", f"upload_{os.path.basename(video_path)}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_path": video_path,
                "thumb_path": thumb_path,
                "title": final_title,
                "description": final_desc,
                "tags": final_tags,
                "mode": mode,
                "publish_at": target_publish_at,
                "privacy": target_privacy,
                "status": "ready_for_upload",
            }, f, indent=2)
        print(f"      Saved ready-to-publish manifest: {manifest_path}")
        return f"local://pending_upload/{os.path.basename(video_path)}"

    # --- 5. YouTube API Upload Execution ---
    youtube = _get_service()
    verified_cat_id = verify_category_id(youtube, getattr(config, "VIDEO_CATEGORY_ID", "27"))

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
            "selfDeclaredMadeForKids": getattr(config, "MADE_FOR_KIDS", False),
            "containsSyntheticMedia":   getattr(config, "CONTAINS_SYNTHETIC_MEDIA", True),
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
        while response is None:
            status, response = insert_req.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"   → {pct}% uploaded", end="\r")

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
        proc_res = verify_upload_and_processing(youtube, video_id)
        print(f"   → YouTube processing verification: {proc_res.get('processing_status', 'uploaded')}")

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
            "title": final_title,
            "processing_verification": proc_res,
        })

        # Transition to ANALYTICS_PENDING
        record_production_state(video_path, PublishingState.ANALYTICS_PENDING.value)

        return video_url

    except HttpError as err:
        err_str = str(err)
        print(f"\n   ⚠ YouTube API Error during upload: {err}")
        record_production_state(video_path, PublishingState.FAILED.value, metadata={
            "error": err_str,
            "error_type": "HttpError",
        })
        os.makedirs(os.path.join(config.OUTPUT_DIR, "pending_uploads"), exist_ok=True)
        manifest_path = os.path.join(config.OUTPUT_DIR, "pending_uploads", f"upload_{os.path.basename(video_path)}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_path": video_path,
                "thumb_path": thumb_path,
                "title": final_title,
                "description": final_desc,
                "tags": final_tags,
                "error": err_str,
                "status": "pending_retry",
            }, f, indent=2)
        return f"local://failed_upload/{os.path.basename(video_path)}"
    except Exception as e:
        print(f"\n   ⚠ Unexpected upload failure: {e}")
        record_production_state(video_path, PublishingState.FAILED.value, metadata={
            "error": str(e),
            "error_type": "UnexpectedException",
        })
        return f"local://failed_upload/{os.path.basename(video_path)}"
