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


def _should_sync_env(token_path: str, sync_env: Optional[bool]) -> bool:
    """Only sync .env when explicitly requested or operating on the live root TOKEN_FILE outside pytest."""
    if sync_env is not None:
        return bool(sync_env)
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return os.path.abspath(token_path) == os.path.abspath(TOKEN_FILE)


def _atomic_write_pickle(obj: Any, target_path: str) -> None:
    """Atomically write pickle bytes to disk without leaving partial files."""
    parent = os.path.dirname(os.path.abspath(target_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{target_path}.tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(obj, f)
    if os.path.exists(target_path):
        os.replace(tmp_path, target_path)
    else:
        os.rename(tmp_path, target_path)


def verify_granted_scopes(creds) -> Tuple[bool, List[str]]:
    """Checks that credentials object covers all REQUIRED_SCOPES."""
    granted = list(getattr(creds, "scopes", None) or [])
    has_full_youtube = "https://www.googleapis.com/auth/youtube" in granted
    missing = []
    for req in REQUIRED_SCOPES:
        if req in granted:
            continue
        if has_full_youtube and req in (
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ):
            continue
        missing.append(req)
    return len(missing) == 0, missing


def verify_channel_identity(
    creds,
    expected_channel_id: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Verifies OAuth credentials against YouTube Data API v3 channels.list(mine=True)
    and optionally confirms the authenticated channel matches `expected_channel_id`.
    """
    yt = build("youtube", "v3", credentials=creds)
    ch_resp = yt.channels().list(mine=True, part="snippet,id").execute()
    items = ch_resp.get("items", [])
    if not items:
        return False, {"error": "Authenticated Google account does not own a YouTube channel."}

    channel_id = items[0].get("id", "")
    channel_title = items[0].get("snippet", {}).get("title", "Unknown Channel")

    exp = (expected_channel_id or "").strip()
    if exp and exp.startswith("UC") and channel_id != exp:
        return False, {
            "error": (
                f"Channel identity mismatch: authorized '{channel_title}' ({channel_id}), "
                f"expected '{exp}'. Existing valid token preserved."
            ),
            "channel_id": channel_id,
            "channel_title": channel_title,
            "expected_channel_id": exp,
        }

    return True, {"channel_id": channel_id, "channel_title": channel_title}


def safe_refresh_credentials(
    creds,
    token_path: str = TOKEN_FILE,
    sync_env: Optional[bool] = None,
) -> bool:
    """
    Safely refreshes an expired credential object and persists it atomically to disk
    (and .env only for live production credentials). Never logs tokens.
    """
    if not creds or not creds.refresh_token:
        return False
    try:
        creds.refresh(Request())
        _atomic_write_pickle(creds, token_path)
        if _should_sync_env(token_path, sync_env) and hasattr(config, "update_youtube_token_env"):
            with open(token_path, "rb") as f:
                config.update_youtube_token_env(f.read())
        return bool(creds.valid)
    except Exception:
        return False


def reauthorize_channel(
    client_secret_file: Optional[str] = None,
    token_path: str = TOKEN_FILE,
    open_browser: bool = True,
    timeout_seconds: int = 240,
    expected_channel_id: Optional[str] = None,
    sync_env: Optional[bool] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Executes safe Google OAuth reauthorization requesting all required scopes.
    Safeguards:
    - Does NOT overwrite a valid existing token or .env until scope AND channel identity checks succeed.
    - Creates a backup (.bak) of existing token before writing the verified new token.
    - Restores backup if disk persistence fails.
    - Never logs credentials or secrets.
    """
    config.sync_client_secret_file()
    cs_file = client_secret_file or getattr(config, "YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")

    if not os.path.exists(cs_file):
        return False, {"error": f"Client secret file not found: {cs_file}"}

    prev_insecure = os.environ.get("OAUTHLIB_INSECURE_TRANSPORT")
    backup_created = False
    wrote_new_token = False

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
            bind_addr="127.0.0.1",
            port=8080,
            open_browser=False,
            timeout_seconds=timeout_seconds,
            state=state_token,
        )

        if not creds or not creds.valid:
            raise RuntimeError("OAuth server returned invalid credentials.")

        # 1. Verify all required scopes BEFORE overwriting any existing token
        scopes_ok, missing_scopes = verify_granted_scopes(creds)
        if not scopes_ok:
            raise RuntimeError(
                "Authorization succeeded but required OAuth scopes were not granted: "
                + ", ".join(missing_scopes)
            )

        # 2. Verify channel access & identity BEFORE overwriting any existing token
        id_ok, id_info = verify_channel_identity(creds, expected_channel_id=expected_channel_id)
        if not id_ok:
            raise RuntimeError(id_info.get("error", "Channel identity verification failed."))

        # 3. Backup existing working token, then persist verified token atomically
        if os.path.exists(token_path):
            try:
                shutil.copy2(token_path, BACKUP_TOKEN_FILE)
                backup_created = True
            except Exception as e:
                print(f"   ⚠ Could not create token backup: {e}")

        _atomic_write_pickle(creds, token_path)
        wrote_new_token = True

        # 4. Update base64 in .env only for live credentials after all checks succeed
        if _should_sync_env(token_path, sync_env) and hasattr(config, "update_youtube_token_env"):
            with open(token_path, "rb") as f:
                config.update_youtube_token_env(f.read())

        if backup_created and os.path.exists(BACKUP_TOKEN_FILE):
            try:
                os.remove(BACKUP_TOKEN_FILE)
            except Exception:
                pass

        return True, {
            "channel_title": id_info["channel_title"],
            "channel_id": id_info["channel_id"],
            "scopes": list(creds.scopes) if creds.scopes else [],
        }

    except Exception as e:
        err_msg = str(e)
        if wrote_new_token and backup_created and os.path.exists(BACKUP_TOKEN_FILE):
            try:
                shutil.copy2(BACKUP_TOKEN_FILE, token_path)
                print("   ℹ Restored previous working token from backup after persistence error.")
            except Exception:
                pass
        return False, {"error": err_msg}
    finally:
        if prev_insecure is None:
            os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
        else:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = prev_insecure
