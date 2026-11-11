"""
Comprehensive Test Suite for Phase 17: Fully Automated YouTube Publishing & Scheduling.
Verifies automated quality gates, scheduled and immediate publication modes,
Asia/Kolkata timezone scheduling, idempotent duplicate prevention, and zero human approval dependencies.
"""
import os
import json
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import MagicMock, patch

import config
from uploader.safety import (
    PublishingState,
    load_production_db,
    record_production_state,
    is_eligible_for_upload,
)
from uploader.quality_gates import (
    validate_research_gate,
    validate_script_gate,
    validate_video_gate,
    validate_metadata_gate,
    evaluate_all_quality_gates,
)
from uploader.youtube import (
    upload_to_youtube,
    calculate_next_scheduled_time,
    verify_upload_and_processing,
    verify_category_id,
)


@pytest.fixture(autouse=True)
def clean_production_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_production_db.json"
    import uploader.safety as s
    monkeypatch.setattr(s, "PRODUCTION_DB_FILE", str(test_db))
    yield
    if test_db.exists():
        test_db.unlink()


def test_quality_gates_pass_on_valid_inputs(tmp_path):
    video_file = tmp_path / "valid_doc.mp4"
    video_file.write_bytes(b"0" * (600 * 1024))
    thumb_file = tmp_path / "valid_thumb.jpg"
    thumb_file.write_bytes(b"0" * (25 * 1024))

    research = {
        "topic": "Harappan Hydraulic Engineering",
        "period": "2600–1900 BCE",
        "geographic_location": "Dholavira, Gujarat, India",
        "claims_and_evidence": [
            {"claim": "Dholavira possessed sophisticated water reservoirs", "evidence_level": "ESTABLISHED_FACT"},
            {"claim": "Check dams diverted water from seasonal streams", "evidence_level": "STRONGLY_SUPPORTED"},
            {"claim": "Rainwater harvesting supported city during droughts", "evidence_level": "ESTABLISHED_FACT"},
        ],
        "verified_timeline": [
            {"era": "3000 BCE", "event": "Early Harappan settlement founded"},
            {"era": "2500 BCE", "event": "Great reservoirs constructed"},
        ],
        "confidence_score": 0.92,
    }

    script = {
        "title": "Dholavira: Ancient Water Engineering Explained",
        "sections": [
            {"id": 1, "narration": "In the arid salt desert of Kutch in Gujarat lies an extraordinary Bronze Age archaeological marvel that successfully defied devastating desert droughts for over a thousand years. This ancient planned city belonged to the Indus Valley Civilization and developed the most sophisticated municipal water harvesting and reservoir management network anywhere in the ancient world."},
            {"id": 2, "narration": "Archaeologists excavating Dholavira discovered sixteen massive rock-cut reservoirs interconnected by stone masonry channels that encircled the entire citadel. Built entirely from precision-cut sandstone, these colossal cisterns could store an estimated two hundred and fifty thousand cubic meters of fresh water to sustain an urban population during dry seasons."},
            {"id": 3, "narration": "When brief monsoon flash floods poured down the seasonal Mansar and Manhar torrents, stone check dams diverted the storm water through underground culverts straight into multi-tiered settling basins. Silt and debris settled naturally at the bottom before crystal-clear drinking water poured into the central urban reservoirs."},
            {"id": 4, "narration": "This 4500-year-old hydraulic technology proves ancient Indian urban planners mastered environmental adaptation and civil engineering long before the Roman aqueducts were conceived. Their ability to thrive in a hyper-arid climate highlights the profound scientific knowledge preserved across Harappan cities."},
            {"id": 5, "narration": "The city layout featured an elaborate citadel, middle town, and lower town fortified by monumental stone walls and stepped ceremonial pathways. Inscriptions discovered near the northern city gate reveal the world-famous Dholavira Signboard, ten massive gypsum hieroglyphic symbols that remain one of history's greatest undeciphered epigraphic mysteries."},
            {"id": 6, "narration": "Excavations carried out by the Archaeological Survey of India reveal continuous habitation across seven distinct cultural stages from early Harappan foundations to late phase decline. Even as regional rainfall patterns shifted dramatically, the city adapted its water catchment strategies to withstand prolonged climatic stress."},
            {"id": 7, "narration": "As the monsoons permanently weakened around nineteen hundred BCE, the inhabitants gradually dispersed into smaller agrarian settlements across Saurashtra. Yet their extraordinary masonry, stone quarrying, and hydraulic engineering remained preserved beneath the desert sands of Khadir Bet island for millennia."},
            {"id": 8, "narration": "Today the monumental ruins of Dholavira stand recognized as a UNESCO World Heritage site and an eternal testament to ancient Indian engineering ingenuity. By studying how ancient civilizations solved critical resource challenges, modern engineers can draw vital lessons for our own sustainable urban future."}
        ],
    }

    metadata = {
        "title": "Dholavira: The Ancient Indian Civilization That Mastered Water",
        "description": "Discover the 4,500-year-old engineering marvels of Dholavira's massive stone water reservoirs.",
        "tags": ["Dholavira", "Harappa", "AncientEngineering", "IndianHistory"],
        "categoryId": "27",
        "defaultLanguage": "hi",
    }

    report = evaluate_all_quality_gates(
        research=research,
        script=script,
        video_path=str(video_file),
        thumb_path=str(thumb_file),
        metadata=metadata,
        is_shorts=False,
    )

    assert report["passed"] is True
    assert len(report["blocking_issues"]) == 0
    assert report["gates"]["research"]["passed"] is True
    assert report["gates"]["script"]["passed"] is True
    assert report["gates"]["video"]["passed"] is True
    assert report["gates"]["metadata"]["passed"] is True


def test_quality_gates_block_bad_inputs_and_write_diagnostic(tmp_path):
    bad_video = tmp_path / "corrupt.mp4"
    bad_video.write_bytes(b"corrupt")  # size < 100KB

    bad_research = {
        "topic": "",  # missing topic
        "period": "unknown",
        "geographic_location": "",
        "claims_and_evidence": [],  # empty claims
        "confidence_score": 0.2,  # too low
    }

    bad_script = {
        "title": "Bad",
        "sections": [{"id": 1, "narration": "[INSERT NARRATION HERE]"}]
    }

    report = evaluate_all_quality_gates(
        research=bad_research,
        script=bad_script,
        video_path=str(bad_video),
        is_shorts=False,
    )

    assert report["passed"] is False
    assert len(report["blocking_issues"]) > 0
    # Verify diagnostic file was created on disk
    diag_file = report.get("diagnostic_file")
    assert diag_file is not None
    assert os.path.exists(diag_file)
    with open(diag_file, encoding="utf-8") as f:
        saved = json.load(f)
        assert saved["passed"] is False


def test_scheduled_publication_mode_uses_private_and_publish_at(tmp_path, monkeypatch):
    video_file = tmp_path / "scheduled_video.mp4"
    video_file.write_bytes(b"0" * (200 * 1024))
    video_path = str(video_file)

    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)

    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_insert.next_chunk.return_value = (None, {"id": "sched_vid_001"})
    mock_service.videos().insert.return_value = mock_insert
    mock_service.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    mock_service.videos().list.return_value.execute.return_value = {
        "items": [{
            "status": {"uploadStatus": "uploaded", "privacyStatus": "private", "publishAt": "2026-11-12T13:30:00Z"},
            "processingDetails": {"processingStatus": "succeeded"},
        }]
    }
    monkeypatch.setattr(yt, "_get_service", lambda: mock_service)

    script = {
        "title": "Scheduled Documentary Test",
        "description": "Evidence verified script for scheduled publication",
        "sections": [{"id": 1, "narration": "Valid narration"}],
    }

    future_ts = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    res = upload_to_youtube(
        script=script,
        video_path=video_path,
        publish_at=future_ts,
        upload_mode=config.UPLOAD_MODE_SCHEDULED,
        skip_quality_gate=True,
    )

    assert res == "https://www.youtube.com/watch?v=sched_vid_001"

    # Verify request payload sent to YouTube
    call_kwargs = mock_service.videos().insert.call_args[1]
    body = call_kwargs["body"]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"] == future_ts
    assert body["status"]["containsSyntheticMedia"] is True

    # Verify state updated to SCHEDULED
    db = load_production_db()
    rec = db[os.path.normpath(video_path)]
    assert rec["metadata"]["mode"] == config.UPLOAD_MODE_SCHEDULED
    assert rec["metadata"]["publish_at"] == future_ts


def test_immediate_publication_mode_uses_public_without_publish_at(tmp_path, monkeypatch):
    video_file = tmp_path / "immediate_video.mp4"
    video_file.write_bytes(b"0" * (200 * 1024))
    video_path = str(video_file)

    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)

    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_insert.next_chunk.return_value = (None, {"id": "pub_vid_002"})
    mock_service.videos().insert.return_value = mock_insert
    mock_service.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    mock_service.videos().list.return_value.execute.return_value = {
        "items": [{
            "status": {"uploadStatus": "uploaded", "privacyStatus": "public"},
            "processingDetails": {"processingStatus": "succeeded"},
        }]
    }
    monkeypatch.setattr(yt, "_get_service", lambda: mock_service)

    script = {
        "title": "Immediate Public Documentary Test",
        "description": "Evidence verified script for immediate publication",
        "sections": [{"id": 1, "narration": "Valid narration"}],
    }

    res = upload_to_youtube(
        script=script,
        video_path=video_path,
        upload_mode=config.UPLOAD_MODE_IMMEDIATE,
        skip_quality_gate=True,
    )

    assert res == "https://www.youtube.com/watch?v=pub_vid_002"

    call_kwargs = mock_service.videos().insert.call_args[1]
    body = call_kwargs["body"]
    assert body["status"]["privacyStatus"] == "public"
    assert "publishAt" not in body["status"]


def test_private_archive_mode_uses_private_without_publish_at(tmp_path, monkeypatch):
    video_file = tmp_path / "archive_video.mp4"
    video_file.write_bytes(b"0" * (200 * 1024))
    video_path = str(video_file)

    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)

    mock_service = MagicMock()
    mock_insert = MagicMock()
    mock_insert.next_chunk.return_value = (None, {"id": "arch_vid_003"})
    mock_service.videos().insert.return_value = mock_insert
    mock_service.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    mock_service.videos().list.return_value.execute.return_value = {
        "items": [{
            "status": {"uploadStatus": "uploaded", "privacyStatus": "private"},
            "processingDetails": {"processingStatus": "succeeded"},
        }]
    }
    monkeypatch.setattr(yt, "_get_service", lambda: mock_service)

    script = {
        "title": "Private Archive Documentary Test",
        "description": "Evidence verified script for private archive",
        "sections": [{"id": 1, "narration": "Valid narration"}],
    }

    res = upload_to_youtube(
        script=script,
        video_path=video_path,
        upload_mode=config.UPLOAD_MODE_PRIVATE,
        skip_quality_gate=True,
    )

    assert res == "https://www.youtube.com/watch?v=arch_vid_003"

    call_kwargs = mock_service.videos().insert.call_args[1]
    body = call_kwargs["body"]
    assert body["status"]["privacyStatus"] == "private"
    assert "publishAt" not in body["status"]


def test_calculate_next_scheduled_time_is_strictly_future_ist():
    # Long-form
    ts_long = calculate_next_scheduled_time(is_shorts=False)
    assert ts_long.endswith("Z")
    dt_long = datetime.fromisoformat(ts_long.replace("Z", "+00:00"))
    now_utc = datetime.now(timezone.utc)
    assert dt_long > now_utc + timedelta(minutes=20)

    # Shorts
    ts_shorts = calculate_next_scheduled_time(is_shorts=True)
    assert ts_shorts.endswith("Z")
    dt_shorts = datetime.fromisoformat(ts_shorts.replace("Z", "+00:00"))
    assert dt_shorts > now_utc + timedelta(minutes=20)


def test_duplicate_upload_prevention_idempotency(tmp_path, monkeypatch):
    video_file = tmp_path / "already_published.mp4"
    video_file.write_bytes(b"0" * (200 * 1024))
    video_path = str(video_file)

    # Record in production db as PUBLISHED with a URL
    record_production_state(video_path, PublishingState.PUBLISHED.value, metadata={
        "youtube_url": "https://www.youtube.com/watch?v=existing_id_777",
        "youtube_id": "existing_id_777",
    })

    script = {"title": "Duplicate Check"}
    # Call upload - should return existing URL immediately without touching YouTube service
    res = upload_to_youtube(script, video_path=video_path, skip_quality_gate=True)
    assert res == "https://www.youtube.com/watch?v=existing_id_777"


def test_verify_upload_and_processing_inspects_youtube_status():
    mock_yt = MagicMock()
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [{
            "status": {
                "uploadStatus": "uploaded",
                "privacyStatus": "private",
                "publishAt": "2026-11-12T13:30:00Z",
                "rejectionReason": None,
            },
            "processingDetails": {
                "processingStatus": "succeeded",
            }
        }]
    }

    status_data = verify_upload_and_processing(mock_yt, "test_vid_123")
    assert status_data["ok"] is True
    assert status_data["upload_status"] == "uploaded"
    assert status_data["processing_status"] == "succeeded"
    assert status_data["publish_at"] == "2026-11-12T13:30:00Z"


def test_category_id_verification():
    mock_yt = MagicMock()
    mock_yt.videoCategories().list.return_value.execute.return_value = {
        "items": [{"id": "27"}, {"id": "28"}]
    }
    cat_id = verify_category_id(mock_yt, category_id="27", region_code="IN")
    assert cat_id == "27"

    # Fallback when requested category not supported
    cat_id_fallback = verify_category_id(mock_yt, category_id="99", region_code="IN")
    assert cat_id_fallback in ("27", "28")


def test_classify_content_disclosures():
    from uploader.quality_gates import classify_content_disclosures

    # 1. Historical documentary with AI TTS narration
    doc_script = {
        "title": "Secrets of the Harappan Civilization",
        "audio_source": "edge_tts",
        "target_audience": "General History Enthusiasts",
        "tags": ["history", "archaeology", "ancient india"]
    }
    disc = classify_content_disclosures(doc_script)
    assert disc["selfDeclaredMadeForKids"] is False
    assert disc["containsSyntheticMedia"] is True

    # 2. Explicit child-directed content
    kids_script = {
        "title": "Fun Cartoon Nursery Rhymes For Kids",
        "audio_source": "human_voice",
        "target_audience": "Toddlers and young children",
        "contains_synthetic_media": False
    }
    disc_kids = classify_content_disclosures(kids_script)
    assert disc_kids["selfDeclaredMadeForKids"] is True
    assert disc_kids["containsSyntheticMedia"] is False

    # 3. Authentic archival narration without synthetic elements
    archival_script = {
        "title": "Original 1947 Audio Archives of Independence",
        "audio_source": "archival_recording",
        "visual_source": "national_archives",
        "contains_synthetic_media": False,
        "made_for_kids": False
    }
    disc_archival = classify_content_disclosures(archival_script)
    assert disc_archival["selfDeclaredMadeForKids"] is False
    assert disc_archival["containsSyntheticMedia"] is False


def test_validate_video_gate_rejects_missing_thumbnail(tmp_path):
    from uploader.quality_gates import validate_video_gate
    vid = tmp_path / "sample.mp4"
    vid.write_bytes(b"0" * (600 * 1024))
    
    # Missing thumbnail path
    passed, issues = validate_video_gate(str(vid), thumb_path="non_existent_thumb.jpg")
    assert passed is False
    assert any("thumbnail" in i.lower() for i in issues)


def test_application_restart_duplicate_prevention(tmp_path):
    from uploader.safety import record_production_state, get_production_record, PublishingState
    vid = tmp_path / "restart_test.mp4"
    vid.write_bytes(b"0" * (600 * 1024))
    vid_path = str(vid)

    # Simulate production run pre-restart
    record_production_state(vid_path, PublishingState.PUBLISHED.value, metadata={
        "youtube_id": "yt_restart_999",
        "youtube_url": "https://www.youtube.com/watch?v=yt_restart_999",
    })

    # Simulate fresh process restart reading from disk
    rec = get_production_record(vid_path)
    assert rec is not None
    assert rec["current_state"] == PublishingState.PUBLISHED.value
    assert rec["metadata"]["youtube_id"] == "yt_restart_999"

    # Verify upload refuses to duplicate
    res = upload_to_youtube({"title": "Restart Test"}, video_path=vid_path, skip_quality_gate=True)
    assert res == "https://www.youtube.com/watch?v=yt_restart_999"

