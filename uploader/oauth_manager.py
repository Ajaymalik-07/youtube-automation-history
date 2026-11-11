"""
OAuth Manager & Security Governance
Phase 18.1: Safe Google OAuth Scope Auditing, Reauthorization, and Scope Enforcement.
Guarantees required scopes for YouTube Data API v3 and YouTube Analytics API v2:
- https://www.googleapis.com/auth/youtube.upload
- https://www.googleapis.com/auth/youtube.readonly
- https://www.googleapis.com/auth/yt-analytics.readonly
"""
import os
import sys
import pickle
import shutil
import secrets
import webbrowser
from typing import Dict, Any, Tuple, List, Optional
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import config

TOKEN_FILE = "youtube_token.pickle"
BACKUP_TOKEN_FILE = "youtube_token.pickle.bak"

REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

SCOPE_DESCRIPTIONS = {
    "https://www.googleapis.com/auth/youtube.upload": "Upload and schedule videos to YouTube channel.",
    "https://www.googleapis.com/auth/youtube.readonly": "Inspect video processing details, upload status, and channel metadata.",
    "https://www.googleapis.com/auth/yt-analytics.readonly": "Query private YouTube Analytics API (watch time, view duration, retention, traffic sources).",
    "https://www.googleapis.com/auth/youtube": "Full YouTube management (supersedes upload and readonly).",
}


def audit_token_scopes(token_path: str = TOKEN_FILE) -> Dict[str, Any]:
    """
    Audits existing credentials file and verifies scope coverage.
    Explains which permissions are missing without leaking secrets.
    """
    if hasattr(config, "sync_youtube_token_file"):
        config.sync_youtube_token_file()

    result = {
        "exists": False,
        "valid": False,
        "expired": False,
        "has_refresh_token": False,
        "granted_scopes": [],
        "missing_scopes": [],
        "missing_descriptions": {},
        "is_fully_authorized": False,
    }

    if not os.path.exists(token_path):
        result["missing_scopes"] = list(REQUIRED_SCOPES)
        result["missing_descriptions"] = {s: SCOPE_DESCRIPTIONS.get(s, "") for s in REQUIRED_SCOPES}
        return result

    result["exists"] = True
    try:
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

        if creds:
            result["valid"] = bool(creds.valid)
            result["expired"] = bool(creds.expired)
            result["has_refresh_token"] = bool(creds.refresh_token)
            granted = list(creds.scopes) if creds.scopes else []
            result["granted_scopes"] = granted

            # Determine missing scopes
            missing = []
            # 'https://www.googleapis.com/auth/youtube' satisfies both upload & readonly
            has_full_youtube = "https://www.googleapis.com/auth/youtube" in granted

            for req in REQUIRED_SCOPES:
                if req in granted:
                    continue
                if has_full_youtube and req in (
                    "https://www.googleapis.com/auth/youtube.upload",
                    "https://www.googleapis.com/auth/youtube.readonly",
                ):
                    continue
                missing.append(req)

            result["missing_scopes"] = missing
            result["missing_descriptions"] = {s: SCOPE_DESCRIPTIONS.get(s, "") for s in missing}
            result["is_fully_authorized"] = (len(missing) == 0) and (result["valid"] or result["has_refresh_token"])
    except Exception as e:
        result["error"] = str(e)
        result["missing_scopes"] = list(REQUIRED_SCOPES)

    return result


def safe_refresh_credentials(creds, token_path: str = TOKEN_FILE) -> bool:
    """
    Safely refreshes an expired credential object and persists it to disk and .env.
    Never logs tokens.
    """
    if not creds or not creds.refresh_token:
        return False
    try:
        creds.refresh(Request())
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        if hasattr(config, "update_youtube_token_env"):
            with open(token_path, "rb") as f:
                config.update_youtube_token_env(f.read())
        return creds.valid
    except Exception:
        return False


def reauthorize_channel(
    client_secret_file: Optional[str] = None,
    token_path: str = TOKEN_FILE,
    open_browser: bool = True,
    timeout_seconds: int = 240,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Executes safe Google OAuth reauthorization requesting all required scopes.
    Safeguards:
    - Creates a backup (.bak) of existing token before attempting flow.
    - Restores backup if reauthorization fails or is cancelled.
    - Never logs credentials or secrets.
    - Updates .env (YOUTUBE_TOKEN_BASE64) on success to maintain synchronization.
    """
    config.sync_client_secret_file()
    cs_file = client_secret_file or getattr(config, "YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")

    if not os.path.exists(cs_file):
        return False, {"error": f"Client secret file not found: {cs_file}"}

    # Backup existing working token
    backup_created = False
    if os.path.exists(token_path):
        try:
            shutil.copy2(token_path, BACKUP_TOKEN_FILE)
            backup_created = True
        except Exception as e:
            print(f"   ⚠ Could not create token backup: {e}")

    try:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        flow = InstalledAppFlow.from_client_secrets_file(cs_file, REQUIRED_SCOPES)
        flow.redirect_uri = "http://localhost:8080/"

        state_token = secrets.token_urlsafe(24)
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            state=state_token,
            include_granted_scopes="true",
        )

        if open_browser:
            webbrowser.open(auth_url)

        creds = flow.run_local_server(
            bind_addr="0.0.0.0",
            port=8080,
            open_browser=False,
            timeout_seconds=timeout_seconds,
            state=state_token,
        )

        if not creds or not creds.valid:
            raise RuntimeError("OAuth server returned invalid credentials.")

        # Persist new token
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

        # Update base64 in .env
        if hasattr(config, "update_youtube_token_env"):
            with open(token_path, "rb") as f:
                config.update_youtube_token_env(f.read())

        # Verify channel access
        yt = build("youtube", "v3", credentials=creds)
        ch_resp = yt.channels().list(mine=True, part="snippet,id").execute()
        items = ch_resp.get("items", [])
        channel_title = items[0]["snippet"]["title"] if items else "Unknown Channel"
        channel_id = items[0]["id"] if items else ""

        # Remove backup on confirmed success
        if backup_created and os.path.exists(BACKUP_TOKEN_FILE):
            try:
                os.remove(BACKUP_TOKEN_FILE)
            except Exception:
                pass

        return True, {
            "channel_title": channel_title,
            "channel_id": channel_id,
            "scopes": list(creds.scopes) if creds.scopes else [],
        }

    except Exception as e:
        err_msg = str(e)
        # Restore backup if available
        if backup_created and os.path.exists(BACKUP_TOKEN_FILE):
            try:
                shutil.copy2(BACKUP_TOKEN_FILE, token_path)
                print("   ℹ Restored previous working token from backup after reauthorization error.")
            except Exception:
                pass
        return False, {"error": err_msg}
