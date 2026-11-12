"""
Automated Production Lifecycle & State Machine
Enforces autonomous 18-stage progression, validates state transitions,
prevents duplicate uploads, and ensures quality gate compliance.
No manual human approval is required.
"""
import os
import sys
import json
import time
import threading
import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List
import config

_DEFAULT_PRODUCTION_DB_FILE = os.path.join(config.OUTPUT_DIR, "production_database.json")
PRODUCTION_DB_FILE = _DEFAULT_PRODUCTION_DB_FILE
_DB_LOCK = threading.RLock()


def _get_production_db_file() -> str:
    """Resolve production DB path dynamically so config.OUTPUT_DIR monkeypatches work safely."""
    if PRODUCTION_DB_FILE != _DEFAULT_PRODUCTION_DB_FILE:
        return PRODUCTION_DB_FILE
    return os.path.join(config.OUTPUT_DIR, "production_database.json")


def _pid_is_alive(pid: int) -> bool:
    """Best-effort check whether an OS process ID is still running (Win32 & POSIX safe)."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        # Note: On Windows, os.kill(pid, 0) sends CTRL_C_EVENT — use OpenProcess instead.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return ctypes.GetLastError() == 5  # ACCESS_DENIED implies process exists
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
                return True
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


class CrossProcessFileLock:
    """
    Portable OS-level atomic lockfile context manager (works on Windows & Linux).
    Uses atomic O_CREAT|O_EXCL lockfile creation with PID + timestamp metadata,
    automatic stale-lock recovery (dead PID or expired TTL), and guaranteed release.
    """

    def __init__(self, lock_path: str, timeout_seconds: float = 30.0, stale_seconds: float = 600.0):
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        self.stale_seconds = stale_seconds
        self._acquired = False
        self._token = f"{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex[:8]}"

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.lock_path) or ".", exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                try:
                    payload = json.dumps({
                        "pid": os.getpid(),
                        "token": self._token,
                        "created_at": time.time(),
                    }).encode("utf-8")
                    os.write(fd, payload)
                finally:
                    os.close(fd)
                self._acquired = True
                return True
            except FileExistsError:
                # Throttle stale-lock file opens slightly to avoid Windows sharing contention with release()
                now_ts = time.time()
                try:
                    if os.path.exists(self.lock_path):
                        st_mtime = os.path.getmtime(self.lock_path)
                        if (now_ts - st_mtime) > self.stale_seconds:
                            os.remove(self.lock_path)
                            continue
                        with open(self.lock_path, encoding="utf-8") as f:
                            meta = json.load(f)
                        holder_pid = int(meta.get("pid", 0))
                        age = now_ts - float(meta.get("created_at", now_ts))
                        if age > self.stale_seconds or (holder_pid and holder_pid != os.getpid() and not _pid_is_alive(holder_pid)):
                            try:
                                os.remove(self.lock_path)
                                continue
                            except OSError:
                                pass
                except Exception:
                    try:
                        if os.path.exists(self.lock_path) and (time.time() - os.path.getmtime(self.lock_path)) > self.stale_seconds:
                            os.remove(self.lock_path)
                            continue
                    except Exception:
                        pass

                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for cross-process lock: {self.lock_path}")
                time.sleep(0.03)

    def release(self) -> None:
        if self._acquired:
            try:
                for _ in range(20):
                    try:
                        os.remove(self.lock_path)
                        break
                    except FileNotFoundError:
                        break
                    except PermissionError:
                        # On Windows another waiting process may briefly hold a read handle
                        time.sleep(0.01)
                    except OSError:
                        break
            finally:
                self._acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class PublishingState(str, Enum):
    TOPIC_SELECTED       = "TOPIC_SELECTED"
    RESEARCH_IN_PROGRESS = "RESEARCH_IN_PROGRESS"
    RESEARCH_VALIDATED   = "RESEARCH_VALIDATED"
    SCRIPT_GENERATED     = "SCRIPT_GENERATED"
    SCRIPT_VALIDATED     = "SCRIPT_VALIDATED"
    VIDEO_RENDERING      = "VIDEO_RENDERING"
    VIDEO_RENDERED       = "VIDEO_RENDERED"
    VIDEO_VALIDATED      = "VIDEO_VALIDATED"
    METADATA_VALIDATED   = "METADATA_VALIDATED"
    UPLOAD_QUEUED        = "UPLOAD_QUEUED"
    UPLOADING            = "UPLOADING"
    UPLOADED_PRIVATE     = "UPLOADED_PRIVATE"
    SCHEDULED            = "SCHEDULED"
    PUBLISHED            = "PUBLISHED"
    ANALYTICS_PENDING    = "ANALYTICS_PENDING"
    COMPLETED            = "COMPLETED"
    FAILED               = "FAILED"
    BLOCKED_QUALITY_GATE = "BLOCKED_QUALITY_GATE"


# Legacy state mapping for backward-compatibility with older runs
LEGACY_STATE_MAPPING = {
    "DRAFT": PublishingState.TOPIC_SELECTED.value,
    "RESEARCH_APPROVED": PublishingState.RESEARCH_VALIDATED.value,
    "SCRIPT_APPROVED": PublishingState.SCRIPT_VALIDATED.value,
    "REVIEW_PENDING": PublishingState.METADATA_VALIDATED.value,
    "APPROVED": PublishingState.UPLOAD_QUEUED.value,
    "REJECTED": PublishingState.BLOCKED_QUALITY_GATE.value,
}


PERMITTED_TRANSITIONS = {
    PublishingState.TOPIC_SELECTED: {
        PublishingState.RESEARCH_IN_PROGRESS,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.RESEARCH_IN_PROGRESS: {
        PublishingState.RESEARCH_VALIDATED,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.RESEARCH_VALIDATED: {
        PublishingState.SCRIPT_GENERATED,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.SCRIPT_GENERATED: {
        PublishingState.SCRIPT_VALIDATED,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.SCRIPT_VALIDATED: {
        PublishingState.VIDEO_RENDERING,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.VIDEO_RENDERING: {
        PublishingState.VIDEO_RENDERED,
        PublishingState.FAILED,
    },
    PublishingState.VIDEO_RENDERED: {
        PublishingState.VIDEO_VALIDATED,
        PublishingState.METADATA_VALIDATED,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.VIDEO_VALIDATED: {
        PublishingState.METADATA_VALIDATED,
        PublishingState.UPLOAD_QUEUED,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.METADATA_VALIDATED: {
        PublishingState.UPLOAD_QUEUED,
        PublishingState.UPLOADING,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.UPLOAD_QUEUED: {
        PublishingState.UPLOADING,
        PublishingState.UPLOADED_PRIVATE,
        PublishingState.SCHEDULED,
        PublishingState.PUBLISHED,
        PublishingState.BLOCKED_QUALITY_GATE,
        PublishingState.FAILED,
    },
    PublishingState.UPLOADING: {
        PublishingState.UPLOADED_PRIVATE,
        PublishingState.SCHEDULED,
        PublishingState.PUBLISHED,
        PublishingState.FAILED,
    },
    PublishingState.UPLOADED_PRIVATE: {
        PublishingState.SCHEDULED,
        PublishingState.PUBLISHED,
        PublishingState.ANALYTICS_PENDING,
        PublishingState.COMPLETED,
        PublishingState.FAILED,
    },
    PublishingState.SCHEDULED: {
        PublishingState.PUBLISHED,
        PublishingState.ANALYTICS_PENDING,
        PublishingState.COMPLETED,
        PublishingState.FAILED,
    },
    PublishingState.PUBLISHED: {
        PublishingState.ANALYTICS_PENDING,
        PublishingState.COMPLETED,
        PublishingState.FAILED,
    },
    PublishingState.ANALYTICS_PENDING: {
        PublishingState.COMPLETED,
        PublishingState.ANALYTICS_PENDING,
        PublishingState.FAILED,
    },
    PublishingState.COMPLETED: {
        PublishingState.ANALYTICS_PENDING,
    },
    PublishingState.FAILED: {
        PublishingState.TOPIC_SELECTED,
        PublishingState.RESEARCH_IN_PROGRESS,
        PublishingState.SCRIPT_GENERATED,
        PublishingState.VIDEO_RENDERING,
        PublishingState.VIDEO_VALIDATED,
        PublishingState.METADATA_VALIDATED,
        PublishingState.UPLOAD_QUEUED,
        PublishingState.SCHEDULED,
        PublishingState.PUBLISHED,
        PublishingState.UPLOADED_PRIVATE,
    },
    PublishingState.BLOCKED_QUALITY_GATE: {
        PublishingState.TOPIC_SELECTED,
        PublishingState.RESEARCH_IN_PROGRESS,
        PublishingState.SCRIPT_GENERATED,
        PublishingState.VIDEO_RENDERING,
        PublishingState.METADATA_VALIDATED,
        PublishingState.FAILED,
    },
}


def normalize_state(state: str) -> PublishingState:
    """Normalize legacy state names into the 18-stage lifecycle."""
    if isinstance(state, PublishingState):
        return state
    mapped = LEGACY_STATE_MAPPING.get(state, state)
    try:
        return PublishingState(mapped)
    except ValueError:
        raise ValueError(f"Unknown publishing state: {state}")


def _load_db_unlocked(db_file: str) -> dict:
    if os.path.exists(db_file):
        try:
            with open(db_file, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _save_db_unlocked(db_file: str, db: dict) -> None:
    db_dir = os.path.dirname(db_file) or "."
    os.makedirs(db_dir, exist_ok=True)
    tmp_path = os.path.join(db_dir, f".{os.path.basename(db_file)}.{uuid.uuid4().hex[:8]}.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp_path, db_file)


def load_production_db() -> dict:
    """Load persistent production database with thread & cross-process file lock."""
    db_file = _get_production_db_file()
    os.makedirs(os.path.dirname(db_file) or ".", exist_ok=True)
    with _DB_LOCK:
        with CrossProcessFileLock(f"{db_file}.lock"):
            return _load_db_unlocked(db_file)


def save_production_db(db: dict) -> None:
    """Atomically save persistent production database to disk under cross-process lock."""
    db_file = _get_production_db_file()
    with _DB_LOCK:
        with CrossProcessFileLock(f"{db_file}.lock"):
            _save_db_unlocked(db_file, db)


def validate_transition(current_state: str, next_state: str) -> Tuple[bool, Optional[str]]:
    """
    Validates if transition from current_state to next_state is permitted.
    Returns (is_valid: bool, error_message: str | None).
    """
    try:
        curr = normalize_state(current_state)
        nxt = normalize_state(next_state)
    except ValueError as e:
        return False, f"Invalid state value: {e}"

    allowed = PERMITTED_TRANSITIONS.get(curr, set())
    if nxt not in allowed:
        return False, f"Illegal state transition from {curr.value} to {nxt.value}. Permitted targets: {[s.value for s in allowed]}"

    return True, None


def get_production_record(video_path: str) -> Optional[dict]:
    """Retrieve production record for a specific video file."""
    db = load_production_db()
    norm_path = os.path.normpath(video_path)
    return db.get(norm_path) or db.get(os.path.basename(video_path))


def record_production_state(video_path: str, state: str, metadata: Optional[dict] = None) -> dict:
    """
    Updates or initializes a video's production lifecycle state atomically across processes.
    Enforces Phase 22.1 State Machine Integrity: failed, blocked, or un-collected videos
    cannot be falsely marked COMPLETED.
    """
    db_file = _get_production_db_file()
    with _DB_LOCK:
        with CrossProcessFileLock(f"{db_file}.lock"):
            db = _load_db_unlocked(db_file)
            norm_path = os.path.normpath(video_path)
            key = norm_path

            record = db.get(key)
            now = datetime.now(timezone.utc).isoformat()
            norm_target_state = normalize_state(state).value

            if norm_target_state == PublishingState.COMPLETED.value:
                if not record:
                    raise ValueError("Cannot mark uninitialized/pending video as COMPLETED.")
                curr_norm = normalize_state(record.get("current_state", PublishingState.TOPIC_SELECTED.value))
                if curr_norm not in (
                    PublishingState.UPLOADED_PRIVATE,
                    PublishingState.SCHEDULED,
                    PublishingState.PUBLISHED,
                    PublishingState.ANALYTICS_PENDING,
                    PublishingState.COMPLETED,
                ):
                    raise ValueError(
                        f"Cannot mark video in state '{curr_norm.value}' as COMPLETED "
                        "(failed, blocked, or in-progress jobs cannot complete)."
                    )
                analytics_ok = bool(
                    (metadata or {}).get("analytics_collected")
                    or (record.get("metadata") or {}).get("analytics_collected")
                )
                if not analytics_ok:
                    raise ValueError(
                        "Cannot mark video as COMPLETED without verified analytics collection "
                        "(analytics_collected=True required)."
                    )

            if not record:
                record = {
                    "video_path": video_path,
                    "filename": os.path.basename(video_path),
                    "current_state": norm_target_state,
                    "history": [],
                    "quality_gate": None,
                    "metadata": metadata or {},
                    "retry_count": 0,
                    "recovered_count": 0,
                    "was_failed": norm_target_state == PublishingState.FAILED.value,
                    "created_at": now,
                    "updated_at": now,
                }
            elif record["current_state"] != norm_target_state:
                prev_state = record["current_state"]
                is_valid, err = validate_transition(prev_state, norm_target_state)
                if not is_valid:
                    print(f"   ⚠ State transition warning: {err}")
                record["history"].append({
                    "from_state": prev_state,
                    "to_state": norm_target_state,
                    "timestamp": now,
                })
                if norm_target_state == PublishingState.FAILED.value:
                    record["was_failed"] = True
                elif (prev_state == PublishingState.FAILED.value or record.get("was_failed")) and norm_target_state in (
                    PublishingState.UPLOADED_PRIVATE.value,
                    PublishingState.SCHEDULED.value,
                    PublishingState.PUBLISHED.value,
                    PublishingState.ANALYTICS_PENDING.value,
                    PublishingState.COMPLETED.value,
                ):
                    record["recovered_count"] = int(record.get("recovered_count", 0)) + 1
                    record["was_failed"] = False
                record["current_state"] = norm_target_state

            if metadata:
                record.setdefault("metadata", {}).update(metadata)
                if "quality_report" in metadata and isinstance(metadata["quality_report"], dict):
                    record["quality_gate"] = metadata["quality_report"]
            record["updated_at"] = now

            db[key] = record
            _save_db_unlocked(db_file, db)
            return record


def record_retry_attempt(video_path: str, stage: str, error_msg: str, job_id: Optional[str] = None) -> dict:
    """Increment and persist retry count and failure reason for a video/job atomically."""
    db_file = _get_production_db_file()
    with _DB_LOCK:
        with CrossProcessFileLock(f"{db_file}.lock"):
            db = _load_db_unlocked(db_file)
            norm_path = os.path.normpath(video_path)
            now = datetime.now(timezone.utc).isoformat()
            record = db.get(norm_path) or {
                "video_path": video_path,
                "filename": os.path.basename(video_path),
                "current_state": PublishingState.FAILED.value,
                "history": [],
                "quality_gate": None,
                "metadata": {},
                "retry_count": 0,
                "recovered_count": 0,
                "was_failed": True,
                "created_at": now,
                "updated_at": now,
            }
            record["retry_count"] = int(record.get("retry_count", 0)) + 1
            meta = record.setdefault("metadata", {})
            if job_id:
                meta["job_id"] = job_id
            meta["last_retry_stage"] = stage
            meta["last_error"] = str(error_msg)[:500]
            meta["last_retry_at"] = now
            record["updated_at"] = now
            db[norm_path] = record
            _save_db_unlocked(db_file, db)
            return record


def record_quality_gate_result(video_path: str, report: dict) -> dict:
    """
    Records an automated quality gate validation report atomically.
    Transitions state to METADATA_VALIDATED if passed, or BLOCKED_QUALITY_GATE if failed.
    """
    passed = report.get("passed", False)
    target_state = (
        PublishingState.METADATA_VALIDATED.value
        if passed
        else PublishingState.BLOCKED_QUALITY_GATE.value
    )
    return record_production_state(video_path, target_state, metadata={"quality_report": report})


def is_eligible_for_upload(video_path: str) -> Tuple[bool, Optional[str]]:
    """
    Autonomous Gate Evaluation:
    Determines whether a video file is eligible for YouTube upload.
    No human approval is required.
    Checks:
    1. Video has a valid production record.
    2. Video is not already uploaded or published (duplicate prevention).
    3. Video is not currently blocked by a failed quality gate.
    4. Video has reached a validated pre-upload stage.
    """
    record = get_production_record(video_path)
    if not record:
        # First-time encounter, check file presence
        if os.path.exists(video_path) and os.path.getsize(video_path) > 100 * 1024:
            return True, None
        return False, "No production record found and video file does not exist on disk."

    curr_state = normalize_state(record.get("current_state", PublishingState.TOPIC_SELECTED.value))
    meta = record.get("metadata", {}) or {}
    existing_yt_id = meta.get("youtube_id")
    is_proc_failed = meta.get("error_type") == "ProcessingFailure"

    # Duplicate Prevention Check (includes existing youtube_id and ANALYTICS_PENDING)
    if curr_state in (
        PublishingState.UPLOADED_PRIVATE,
        PublishingState.SCHEDULED,
        PublishingState.PUBLISHED,
        PublishingState.ANALYTICS_PENDING,
        PublishingState.COMPLETED,
    ) or (existing_yt_id and not is_proc_failed):
        return False, f"Video is already uploaded or published (YouTube ID: {existing_yt_id})."

    # Quality Gate Check
    if curr_state == PublishingState.BLOCKED_QUALITY_GATE:
        return False, "Video is blocked by automated quality gate failure."

    # Eligible states
    eligible_states = {
        PublishingState.VIDEO_RENDERED,
        PublishingState.VIDEO_VALIDATED,
        PublishingState.METADATA_VALIDATED,
        PublishingState.UPLOAD_QUEUED,
        PublishingState.FAILED,  # Retryable
    }

    if curr_state not in eligible_states:
        return False, f"Video is in state '{curr_state.value}', not yet ready for upload."

    # Check quality report if present
    q_gate = record.get("quality_gate") or record.get("metadata", {}).get("quality_report")
    if q_gate and not q_gate.get("passed", True):
        return False, "Video has recorded quality gate issues."

    return True, None
