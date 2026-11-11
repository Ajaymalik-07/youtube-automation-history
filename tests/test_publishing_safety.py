"""
Unit tests for Phase 12: Publishing Safety, State Machine, and Approval Gates.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from uploader.safety import (
    PublishingState,
    validate_transition,
    record_production_state,
    record_human_approval,
    is_approved_for_upload,
    load_production_db,
    save_production_db,
)
from uploader.youtube import upload_to_youtube


@pytest.fixture(autouse=True)
def clean_production_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_production_db.json"
    import uploader.safety as s
    monkeypatch.setattr(s, "PRODUCTION_DB_FILE", str(test_db))
    yield
    if test_db.exists():
        test_db.unlink()


def test_permitted_and_illegal_state_transitions():
    # Permitted transitions
    valid, msg = validate_transition(PublishingState.DRAFT.value, PublishingState.RESEARCH_APPROVED.value)
    assert valid is True
    assert msg is None

    valid, msg = validate_transition(PublishingState.REVIEW_PENDING.value, PublishingState.APPROVED.value)
    assert valid is True

    valid, msg = validate_transition(PublishingState.APPROVED.value, PublishingState.PUBLISHED.value)
    assert valid is True

    # Illegal transitions
    valid, msg = validate_transition(PublishingState.DRAFT.value, PublishingState.PUBLISHED.value)
    assert valid is False
    assert "Illegal state transition" in msg

    valid, msg = validate_transition(PublishingState.PUBLISHED.value, PublishingState.DRAFT.value)
    assert valid is False


def test_record_production_state_and_history():
    video = "output/test_documentary.mp4"
    rec = record_production_state(video, PublishingState.VIDEO_RENDERED.value)
    assert rec["current_state"] == PublishingState.VIDEO_RENDERED.value
    assert len(rec["history"]) >= 0

    # Advance to review pending
    rec2 = record_production_state(video, PublishingState.REVIEW_PENDING.value)
    assert rec2["current_state"] == PublishingState.REVIEW_PENDING.value
    assert len(rec2["history"]) == 1
    assert rec2["history"][0]["from_state"] == PublishingState.VIDEO_RENDERED.value
    assert rec2["history"][0]["to_state"] == PublishingState.REVIEW_PENDING.value


def test_human_approval_unlocks_upload():
    video = "output/chola_navy.mp4"
    record_production_state(video, PublishingState.VIDEO_RENDERED.value)

    # Before approval, upload MUST be blocked
    assert is_approved_for_upload(video) is False

    # Issue human approval
    app_rec = record_human_approval(video, reviewer="lead_editor", notes="Fact-checks and audio verified")
    assert app_rec["current_state"] == PublishingState.APPROVED.value
    assert app_rec["approval_record"]["approved"] is True
    assert app_rec["approval_record"]["reviewer"] == "lead_editor"

    # After approval, upload is authorized
    assert is_approved_for_upload(video) is True


def test_upload_to_youtube_blocks_unapproved_video(tmp_path, monkeypatch):
    video_file = tmp_path / "unapproved_short.mp4"
    video_file.write_text("dummy video")
    video_path = str(video_file)

    script = {
        "title": "Unapproved Video Test",
        "description": "Test description",
        "topic": "Indian History",
    }

    # Upload attempt without prior approval
    res = upload_to_youtube(script, video_path=video_path, bypass_approval=False)

    assert "pending_approval" in res
    assert is_approved_for_upload(video_path) is False

    # Verify pending upload manifest was created
    pending_dir = os.path.join("output", "pending_uploads")
    manifest = os.path.join(pending_dir, f"upload_{os.path.basename(video_path)}.json")
    assert os.path.exists(manifest)
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
        assert data["status"] == "awaiting_human_approval"


def test_upload_to_youtube_proceeds_with_approval_token(tmp_path, monkeypatch):
    video_file = tmp_path / "approved_short.mp4"
    video_file.write_text("dummy video")
    video_path = str(video_file)

    # Mock is_configured and _get_service
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)

    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_insert.next_chunk.return_value = (None, {"id": "mock_yt_vid_999"})
    mock_service.videos().insert.return_value = mock_insert
    monkeypatch.setattr(yt, "_get_service", lambda: mock_service)

    # Approve video
    record_production_state(video_path, PublishingState.VIDEO_RENDERED.value)
    record_human_approval(video_path, reviewer="ajay_malik")

    script = {
        "title": "Approved Documentary Test",
        "description": "Evidence verified script",
        "topic": "Harappan Sanitation",
    }

    res = upload_to_youtube(script, video_path=video_path, bypass_approval=False)
    assert res == "https://www.youtube.com/watch?v=mock_yt_vid_999"

    # Verify state updated to PUBLISHED
    db = load_production_db()
    rec = db.get(os.path.normpath(video_path))
    assert rec["current_state"] == PublishingState.PUBLISHED.value
    assert rec["metadata"]["youtube_id"] == "mock_yt_vid_999"
