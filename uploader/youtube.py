"""
YouTube Uploader
Authenticates with the YouTube Data API v3 and uploads the final video and thumbnail.
Supports automated scheduled releases and direct public uploads.
"""
import os
import json
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
import config
from uploader.safety import (
    is_approved_for_upload,
    record_production_state,
    PublishingState,
)

TOKEN_FILE = "youtube_token.pickle"


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


def upload_to_youtube(script: dict, video_path: str, thumb_path: str = None,
                      title: str = None, description: str = None, tags: list = None,
                      privacy: str = None, publish_at: str = None,
                      bypass_approval: bool = False) -> str:
    """
    Uploads the video with verified title, description, tags, and thumbnail.
    Phase 12 Safety Gate: Enforces mandatory human approval unless bypass_approval is True.
    Defaults privacyStatus to 'private' or 'unlisted' to prevent accidental premature public release.
    Supports scheduled publishing via publish_at (RFC 3339 / ISO 8601 UTC timestamp).
    """
    from agents.seo_optimizer import optimize_for_100_percent
    topic = script.get("topic") or script.get("title", "")
    is_shorts = (script.get("video_type") == "shorts" or "short" in os.path.basename(video_path).lower())
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

    # --- Phase 12 Mandatory Approval Gate ---
    if not bypass_approval and not is_approved_for_upload(video_path):
        print(f"   🚨 Upload blocked by Publishing Safety Gate: Human approval not recorded for '{os.path.basename(video_path)}'")
        record_production_state(video_path, PublishingState.REVIEW_PENDING.value, metadata={
            "title": final_title,
            "blocked_reason": "Pending human approval before upload",
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
                "publish_at": publish_at,
                "status": "awaiting_human_approval",
            }, f, indent=2)
        print(f"      Preserved in pending review queue: {manifest_path}")
        return f"local://pending_approval/{os.path.basename(video_path)}"

    # Default to 'private' for unreviewed/new uploads if not specified
    default_privacy = getattr(config, "VIDEO_PRIVACY", "private")
    target_privacy = "private" if publish_at else (privacy or default_privacy)

    if not is_configured():
        print("   ℹ YouTube OAuth credentials not yet linked or token missing.")
        print(f"      Video {video_path} is rendered and verified.")
        os.makedirs(os.path.join(config.OUTPUT_DIR, "pending_uploads"), exist_ok=True)
        manifest_path = os.path.join(config.OUTPUT_DIR, "pending_uploads", f"upload_{os.path.basename(video_path)}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "video_path": video_path,
                "thumb_path": thumb_path,
                "title": final_title,
                "description": final_desc,
                "tags": final_tags,
                "publish_at": publish_at,
                "status": "ready_for_upload",
            }, f, indent=2)
        print(f"      Saved ready-to-publish manifest: {manifest_path}")
        return f"local://pending_upload/{os.path.basename(video_path)}"

    youtube = _get_service()

    body = {
        "snippet": {
            "title":       final_title[:100],
            "description": final_desc[:4950],
            "tags":        final_tags[:15],
            "categoryId":  config.VIDEO_CATEGORY_ID,
        },
        "status": {
            "privacyStatus":           target_privacy,
            "selfDeclaredMadeForKids": getattr(config, "MADE_FOR_KIDS", False),
        },
    }
    if publish_at:
        body["status"]["publishAt"] = publish_at

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
    )

    print(f"   → Uploading {os.path.basename(video_path)} with privacy: {target_privacy}…")
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
        print(f"   ✅ Video live on YouTube: {video_url}")

        # Set custom thumbnail if provided
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

        # Phase 12 State Transition: Mark as PUBLISHED
        record_production_state(video_path, PublishingState.PUBLISHED.value, metadata={
            "youtube_id": video_id,
            "youtube_url": video_url,
            "privacy": target_privacy,
            "title": final_title,
        })

        return video_url

    except HttpError as err:
        err_str = str(err)
        print(f"\n   ⚠ YouTube API Error during upload: {err}")
        if "quotaExceeded" in err_str or "quota" in err_str.lower():
            print("   🚨 Daily YouTube Data API Quota (10,000 units/day) has been reached.")
            print("      Video is rendered and safely preserved for automated upload when quota resets.")
        record_production_state(video_path, PublishingState.FAILED.value, metadata={
            "error": err_str,
            "reason": "YouTube API HttpError",
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
                "status": "pending_quota_reset",
            }, f, indent=2)
        print(f"   📦 Saved to pending queue: {manifest_path}")
        return f"local://pending_quota_reset/{os.path.basename(video_path)}"
    except Exception as e:
        print(f"\n   ⚠ Unexpected upload failure: {e}")
        record_production_state(video_path, PublishingState.FAILED.value, metadata={
            "error": str(e),
            "reason": "Unexpected upload exception",
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
                "error": str(e),
                "status": "failed_retry",
            }, f, indent=2)
        return f"local://failed_upload/{os.path.basename(video_path)}"
