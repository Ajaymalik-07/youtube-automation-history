"""
Unit tests for Production Lifecycle, 18-State Machine, and Automated Upload Eligibility.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from uploader.safety import (
    PublishingState,
    validate_transition,
    record_production_state,
    is_eligible_for_upload,
    load_production_db,
    save_production_db,
)


@pytest.fixture(autouse=True)
def clean_production_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_production_db.json"
    import uploader.safety as s
    monkeypatch.setattr(s, "PRODUCTION_DB_FILE", str(test_db))
    yield
    if test_db.exists():
        test_db.unlink()


def test_18_state_lifecycle_transitions():
    # Permitted linear progression
    valid, msg = validate_transition(PublishingState.TOPIC_SELECTED.value, PublishingState.RESEARCH_IN_PROGRESS.value)
    assert valid is True
    assert msg is None

    valid, msg = validate_transition(PublishingState.RESEARCH_IN_PROGRESS.value, PublishingState.RESEARCH_VALIDATED.value)
    assert valid is True

    valid, msg = validate_transition(PublishingState.METADATA_VALIDATED.value, PublishingState.UPLOAD_QUEUED.value)
    assert valid is True

    valid, msg = validate_transition(PublishingState.UPLOAD_QUEUED.value, PublishingState.UPLOADING.value)
    assert valid is True

    valid, msg = validate_transition(PublishingState.UPLOADING.value, PublishingState.SCHEDULED.value)
    assert valid is True

    # Quality Gate Blocking
    valid, msg = validate_transition(PublishingState.RESEARCH_VALIDATED.value, PublishingState.BLOCKED_QUALITY_GATE.value)
    assert valid is True

    # Illegal jumps (cannot jump from TOPIC_SELECTED directly to PUBLISHED)
    valid, msg = validate_transition(PublishingState.TOPIC_SELECTED.value, PublishingState.PUBLISHED.value)
    assert valid is False
    assert "Illegal state transition" in msg


def test_record_production_state_and_history():
    video = "output/test_documentary.mp4"
    rec = record_production_state(video, PublishingState.VIDEO_RENDERED.value)
    assert rec["current_state"] == PublishingState.VIDEO_RENDERED.value
    assert len(rec["history"]) == 0

    # Advance to metadata validated
    rec2 = record_production_state(video, PublishingState.METADATA_VALIDATED.value)
    assert rec2["current_state"] == PublishingState.METADATA_VALIDATED.value
    assert len(rec2["history"]) == 1
    assert rec2["history"][0]["from_state"] == PublishingState.VIDEO_RENDERED.value
    assert rec2["history"][0]["to_state"] == PublishingState.METADATA_VALIDATED.value


def test_automated_upload_eligibility_without_human_approval(tmp_path):
    video_file = tmp_path / "valid_doc.mp4"
    # Write > 200KB to satisfy video size check
    video_file.write_bytes(b"0" * (250 * 1024))
    video_path = str(video_file)

    # Initially in VIDEO_RENDERED
    record_production_state(video_path, PublishingState.VIDEO_RENDERED.value)
    eligible, reason = is_eligible_for_upload(video_path)
    assert eligible is True
    assert reason is None

    # When blocked by quality gate, eligibility is denied
    record_production_state(video_path, PublishingState.BLOCKED_QUALITY_GATE.value)
    eligible, reason = is_eligible_for_upload(video_path)
    assert eligible is False
    assert "blocked by automated quality gate" in reason

    # When already published, duplicate upload is prevented
    record_production_state(video_path, PublishingState.PUBLISHED.value, metadata={"youtube_id": "yt_123"})
    eligible, reason = is_eligible_for_upload(video_path)
    assert eligible is False
    assert "already uploaded" in reason
