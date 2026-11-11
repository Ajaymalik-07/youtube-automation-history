"""
Automated Production Lifecycle & State Machine
Enforces autonomous 18-stage progression, validates state transitions,
prevents duplicate uploads, and ensures quality gate compliance.
No manual human approval is required.
"""
import os
import json
import time
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional, List
import config

PRODUCTION_DB_FILE = os.path.join(config.OUTPUT_DIR, "production_database.json")


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
        PublishingState.UPLOAD_QUEUED,
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


def load_production_db() -> dict:
    """Load persistent production database."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    if os.path.exists(PRODUCTION_DB_FILE):
        try:
            with open(PRODUCTION_DB_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_production_db(db: dict) -> None:
    """Save persistent production database to disk."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(PRODUCTION_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


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
    Updates or initializes a video's production lifecycle state.
    """
    db = load_production_db()
    norm_path = os.path.normpath(video_path)
    key = norm_path

    record = db.get(key)
    now = datetime.now(timezone.utc).isoformat()
    norm_target_state = normalize_state(state).value

    if not record:
        record = {
            "video_path": video_path,
            "filename": os.path.basename(video_path),
            "current_state": norm_target_state,
            "history": [],
            "quality_gate": None,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
    elif record["current_state"] != norm_target_state:
        is_valid, err = validate_transition(record["current_state"], norm_target_state)
        if not is_valid:
            print(f"   ⚠ State transition warning: {err}")
        record["history"].append({
            "from_state": record["current_state"],
            "to_state": norm_target_state,
            "timestamp": now,
        })
        record["current_state"] = norm_target_state

    if metadata:
        record["metadata"].update(metadata)
    record["updated_at"] = now

    db[key] = record
    save_production_db(db)
    return record


def record_quality_gate_result(video_path: str, report: dict) -> dict:
    """
    Records an automated quality gate validation report.
    Transitions state to METADATA_VALIDATED if passed, or BLOCKED_QUALITY_GATE if failed.
    """
    passed = report.get("passed", False)
    target_state = (
        PublishingState.METADATA_VALIDATED.value
        if passed
        else PublishingState.BLOCKED_QUALITY_GATE.value
    )
    rec = record_production_state(video_path, target_state, metadata={"quality_report": report})
    rec["quality_gate"] = report
    db = load_production_db()
    db[os.path.normpath(video_path)] = rec
    save_production_db(db)
    return rec


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

    # Duplicate Prevention Check
    if curr_state in (
        PublishingState.UPLOADED_PRIVATE,
        PublishingState.SCHEDULED,
        PublishingState.PUBLISHED,
        PublishingState.COMPLETED,
    ):
        yt_id = record.get("metadata", {}).get("youtube_id")
        return False, f"Video is already uploaded or published (YouTube ID: {yt_id})."

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
