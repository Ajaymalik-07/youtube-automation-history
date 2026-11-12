"""
Phase 22.1 — Live Publishing Reliability & Production Verification Test Suite.

Covers:
- Quota-pending isolation, unique manifest naming (zero final_short.mp4 collisions),
  metadata/content_id/intent preservation, schedule slot reconciliation, and existing video_id duplicate guard
- True OS multi-process concurrency with CrossProcessFileLock + stale-PID/crash lock cleanup
- State machine enforcement preventing FAILED / BLOCKED / pending videos from being marked COMPLETED
- 9-stage separated Production Reliability Report (Shorts vs Long-form)
- Live channel publication reconciliation and third-party credits.json attribution
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import automation
import config
from agents.growth_analyst import generate_production_reliability_report
from apis.growth_database import HistoricalPerformanceDB
from uploader.safety import (
    CrossProcessFileLock,
    PublishingState,
    get_production_record,
    is_eligible_for_upload,
    load_production_db,
    record_production_state,
)
from uploader.youtube import reconcile_channel_publications, upload_to_youtube


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(automation, "SCHEDULE_FILE", str(out_dir / "automation_schedule.json"))
    import uploader.safety as safety_mod
    monkeypatch.setattr(safety_mod, "PRODUCTION_DB_FILE", str(out_dir / "production_database.json"))
    import uploader.quality_gates as qg_mod
    monkeypatch.setattr(qg_mod, "DIAGNOSTICS_DIR", str(out_dir / "diagnostics"))
    monkeypatch.setattr(
        automation,
        "get_performance_db",
        lambda: HistoricalPerformanceDB(db_path=str(out_dir / "growth_history.json")),
    )
    yield out_dir


def _sample_research(topic="Ancient Metallurgy in India"):
    return {
        "topic": topic,
        "video_title": topic,
        "period": "400 CE",
        "geographic_location": "Mehrauli, Delhi, India",
        "claims_and_evidence": [
            {"claim": "Rust-resistant iron pillar dates to Gupta era.", "evidence_level": "ESTABLISHED_FACT"},
            {"claim": "High phosphorus slag barrier prevented corrosion.", "evidence_level": "ESTABLISHED_FACT"},
            {"claim": "Brahmi inscription cites King Chandra.", "evidence_level": "STRONGLY_SUPPORTED"},
        ],
        "verified_timeline": [
            {"era": "400 CE", "event": "Pillar forged"},
            {"era": "1050 CE", "event": "Relocated to Lal Kot"},
        ],
        "confidence_score": 0.93,
    }


def _sample_script(title="Iron Pillar Mystery"):
    return {
        "title": f"{title} #Shorts",
        "video_type": "shorts",
        "description": "Verified archaeological chemistry behind the 1,600-year-old Delhi Iron Pillar. #Shorts #History",
        "tags": ["IronPillar", "AncientIndia", "Metallurgy", "Shorts"],
        "sections": [
            {"id": 1, "narration": "For sixteen hundred monsoon seasons this seven-ton iron column stood outdoors without rusting away."},
            {"id": 2, "narration": "Metallurgical tests revealed high phosphorus levels formed a protective passive layer over forged iron."},
            {"id": 3, "narration": "Gupta period smiths mastered solid-state forge welding long before modern industrial steel mills."},
        ],
    }


def test_quota_recovery_preserves_content_id_metadata_intent_and_prevents_duplicates(isolated_env, monkeypatch):
    from googleapiclient.errors import HttpError
    import uploader.youtube as yt

    monkeypatch.setattr(yt, "is_configured", lambda: True)
    monkeypatch.setattr(automation, "is_configured", lambda: True)
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")

    # Two separate Shorts sharing the SAME filename 'final_short.mp4' in isolated dirs
    d1 = isolated_env / "shorts_batch" / "2026-11-20_short_04"
    d2 = isolated_env / "shorts_batch" / "2026-11-20_short_05"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    v1 = d1 / "final_short.mp4"
    v2 = d2 / "final_short.mp4"
    v1.write_bytes(b"0" * (220 * 1024))
    v2.write_bytes(b"0" * (220 * 1024))

    pub1 = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT13:30:00Z")
    pub2 = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT16:30:00Z")

    record_production_state(str(v1), PublishingState.VIDEO_VALIDATED.value, metadata={
        "content_id": "short-2026-11-20-s4-h19",
        "job_id": "short-2026-11-20-s4-h19-aaa111",
        "target_date": "2026-11-20",
        "slot_hour_ist": 19,
        "index": 4,
        "intended_publish_at": pub1,
        "type": "short",
    })
    record_production_state(str(v2), PublishingState.VIDEO_VALIDATED.value, metadata={
        "content_id": "short-2026-11-20-s5-h22",
        "job_id": "short-2026-11-20-s5-h22-bbb222",
        "target_date": "2026-11-20",
        "slot_hour_ist": 22,
        "index": 5,
        "intended_publish_at": pub2,
        "type": "short",
    })

    quota_svc = MagicMock()
    quota_svc.channels().list.return_value.execute.return_value = {"items": [{"id": "UCb1BDNY8WxoD1q_UVyEmvuw"}]}
    quota_svc.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    resp403 = MagicMock(status=403, reason="Forbidden")
    quota_svc.videos().insert.return_value.next_chunk.side_effect = HttpError(resp403, b"quotaExceeded")
    monkeypatch.setattr(yt, "_get_service", lambda: quota_svc)

    out1 = upload_to_youtube(script=_sample_script("Pillar 4"), video_path=str(v1), research=_sample_research(), publish_at=pub1, is_shorts=True)
    out2 = upload_to_youtube(script=_sample_script("Pillar 5"), video_path=str(v2), research=_sample_research(), publish_at=pub2, is_shorts=True)
    assert out1.startswith("local://pending_quota_reset/")
    assert out2.startswith("local://pending_quota_reset/")

    manifests = sorted((isolated_env / "pending_uploads").glob("upload_*.json"))
    assert len(manifests) == 2
    loaded = [json.loads(m.read_text(encoding="utf-8")) for m in manifests]
    assert {m["content_id"] for m in loaded} == {"short-2026-11-20-s4-h19", "short-2026-11-20-s5-h22"}
    assert {m["original_publish_at"] for m in loaded} == {pub1, pub2}

    # Schedule state must NOT mark failed uploads as published
    sched_before = automation.load_schedule_state()
    assert not sched_before.get("last_short_pub_2026-11-20_19")
    assert not sched_before.get("last_short_pub_2026-11-20_22")

    # Quota reset -> recover both cleanly
    ok_svc = MagicMock()
    ok_svc.channels().list.return_value.execute.return_value = {"items": [{"id": "UCb1BDNY8WxoD1q_UVyEmvuw"}]}
    ok_svc.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    ok_svc.videos().insert.return_value.next_chunk.side_effect = [
        (None, {"id": "yt_quota_rec_4"}),
        (None, {"id": "yt_quota_rec_5"}),
    ]
    ok_svc.videos().list.return_value.execute.return_value = {
        "items": [{"snippet": {"channelId": "UCb1BDNY8WxoD1q_UVyEmvuw"}, "status": {"uploadStatus": "uploaded", "privacyStatus": "private"}, "processingDetails": {"processingStatus": "succeeded"}}]
    }
    monkeypatch.setattr(yt, "_get_service", lambda: ok_svc)

    recov = automation.retry_pending_uploads()
    assert len(recov["succeeded"]) == 2
    assert list((isolated_env / "pending_uploads").glob("upload_*.json")) == []

    sched_after = automation.load_schedule_state()
    assert sched_after.get("last_short_pub_2026-11-20_19") is True
    assert sched_after.get("last_short_pub_2026-11-20_22") is True

    # Existing youtube_id must never be uploaded again
    dup_res = upload_to_youtube(script=_sample_script("Pillar 4"), video_path=str(v1), research=_sample_research(), publish_at=pub1, is_shorts=True)
    assert dup_res == "https://www.youtube.com/watch?v=yt_quota_rec_4"
    eligible, reason = is_eligible_for_upload(str(v1))
    assert eligible is False
    assert "yt_quota_rec_4" in reason


def test_multiprocess_cross_process_lock_and_crash_cleanup(isolated_env):
    db_path = str(isolated_env / "production_database.json")

    # 1. Stale dead-PID lock cleanup
    stale_lock_file = str(isolated_env / "locks" / "stale_test.lock")
    os.makedirs(os.path.dirname(stale_lock_file), exist_ok=True)
    with open(stale_lock_file, "w", encoding="utf-8") as f:
        json.dump({"pid": 999999, "created_at": 1.0}, f)
    with CrossProcessFileLock(stale_lock_file, timeout_seconds=2.0, stale_seconds=1.0):
        assert os.path.exists(stale_lock_file)
    assert not os.path.exists(stale_lock_file)

    # 2. Exception cleanup guarantees lockfile removal
    crash_lock_file = str(isolated_env / "locks" / "crash_test.lock")
    with pytest.raises(RuntimeError):
        with CrossProcessFileLock(crash_lock_file, timeout_seconds=2.0):
            raise RuntimeError("boom")
    assert not os.path.exists(crash_lock_file)

    # 3. Real multi-process parallel writes across 2 separate OS Python processes
    sched_path = str(isolated_env / "automation_schedule.json")
    worker_py = isolated_env.parent / "mp_worker.py"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    worker_py.write_text(
        "\n".join([
            "import json, os, sys",
            f"sys.path.insert(0, {repo_root!r})",
            "import config",
            "import uploader.safety as s",
            "out_dir, w_idx, cnt = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])",
            "config.OUTPUT_DIR = out_dir",
            "s.PRODUCTION_DB_FILE = os.path.join(out_dir, 'production_database.json')",
            "for i in range(cnt):",
            "    s.record_production_state(f'output/mp_w{w_idx}_v{i}.mp4', s.PublishingState.VIDEO_RENDERED.value, metadata={'worker': w_idx, 'seq': i, 'type': 'short'})",
            "sched_file = os.path.join(out_dir, 'automation_schedule.json')",
            "lock_dir = os.path.join(out_dir, 'locks')",
            "with s.CrossProcessFileLock(os.path.join(lock_dir, 'slot-19-concurrency.lock')):",
            "    with s.CrossProcessFileLock(f'{sched_file}.lock'):",
            "        data = json.load(open(sched_file, encoding='utf-8')) if os.path.exists(sched_file) else {}",
            "        data[f'mp_worker_{w_idx}_done'] = True",
            "        with open(sched_file, 'w', encoding='utf-8') as f:",
            "            json.dump(data, f, indent=2)",
        ]),
        encoding="utf-8",
    )
    p1 = subprocess.Popen([sys.executable, str(worker_py), str(isolated_env), "1", "6"])
    p2 = subprocess.Popen([sys.executable, str(worker_py), str(isolated_env), "2", "6"])
    rc1 = p1.wait(timeout=20)
    rc2 = p2.wait(timeout=20)
    assert rc1 == 0
    assert rc2 == 0

    db = load_production_db()
    assert len(db) == 12
    sched = json.loads((isolated_env / "automation_schedule.json").read_text(encoding="utf-8"))
    assert sched.get("mp_worker_1_done") is True
    assert sched.get("mp_worker_2_done") is True
    assert not os.path.exists(f"{db_path}.lock")
    assert not os.path.exists(f"{sched_path}.lock")
    assert not os.path.exists(str(isolated_env / "locks" / "slot-19-concurrency.lock"))


def test_state_machine_prevents_false_completion_for_failed_or_pending(isolated_env):
    vid = str(isolated_env / "sm_guard.mp4")

    # Uninitialized video cannot be marked COMPLETED
    with pytest.raises(ValueError, match="uninitialized"):
        record_production_state(vid, PublishingState.COMPLETED.value, metadata={"analytics_collected": True})

    # FAILED video cannot be marked COMPLETED
    record_production_state(vid, PublishingState.FAILED.value, metadata={"type": "short"})
    with pytest.raises(ValueError, match="FAILED"):
        record_production_state(vid, PublishingState.COMPLETED.value, metadata={"analytics_collected": True})

    # BLOCKED_QUALITY_GATE video cannot be marked COMPLETED
    vid_blk = str(isolated_env / "sm_blocked.mp4")
    record_production_state(vid_blk, PublishingState.BLOCKED_QUALITY_GATE.value, metadata={"type": "short"})
    with pytest.raises(ValueError, match="BLOCKED_QUALITY_GATE"):
        record_production_state(vid_blk, PublishingState.COMPLETED.value, metadata={"analytics_collected": True})

    # ANALYTICS_PENDING without analytics_collected=True cannot be marked COMPLETED
    vid_pend = str(isolated_env / "sm_pending.mp4")
    record_production_state(vid_pend, PublishingState.SCHEDULED.value, metadata={"youtube_id": "yt_sm_1"})
    record_production_state(vid_pend, PublishingState.ANALYTICS_PENDING.value)
    with pytest.raises(ValueError, match="analytics"):
        record_production_state(vid_pend, PublishingState.COMPLETED.value)

    # With analytics_collected=True, COMPLETED succeeds
    rec = record_production_state(vid_pend, PublishingState.COMPLETED.value, metadata={"analytics_collected": True})
    assert rec["current_state"] == PublishingState.COMPLETED.value


def test_reliability_report_separates_all_nine_stages_by_format(isolated_env, monkeypatch):
    import apis.youtube_analytics as ya
    monkeypatch.setattr(
        ya,
        "get_analytics_capabilities_and_limitations",
        lambda: {
            "owner_analytics_connected": False,
            "has_public_data_api_fallback": True,
            "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"],
            "limitations": ["OAuth scopes missing."],
        },
    )

    # Short 1: failed -> recovered -> scheduled (not yet public, analytics pending)
    s1 = str(isolated_env / "s1_sched.mp4")
    record_production_state(s1, PublishingState.VIDEO_RENDERED.value, metadata={"type": "short"})
    record_production_state(s1, PublishingState.FAILED.value, metadata={"error_type": "HttpError"})
    record_production_state(s1, PublishingState.SCHEDULED.value, metadata={
        "youtube_id": "yt_s1",
        "publication_status": PublishingState.SCHEDULED.value,
        "youtube_processing_completed": True,
    })
    record_production_state(s1, PublishingState.ANALYTICS_PENDING.value)

    # Short 2: actually published + analytics collected -> COMPLETED
    s2 = str(isolated_env / "s2_done.mp4")
    record_production_state(s2, PublishingState.VIDEO_RENDERED.value, metadata={"type": "short"})
    record_production_state(s2, PublishingState.PUBLISHED.value, metadata={
        "youtube_id": "yt_s2",
        "publication_status": PublishingState.PUBLISHED.value,
        "actually_published": True,
        "youtube_processing_completed": True,
    })
    record_production_state(s2, PublishingState.ANALYTICS_PENDING.value)
    record_production_state(s2, PublishingState.COMPLETED.value, metadata={"analytics_collected": True})

    # Longform 1: quality gate blocked
    l1 = str(isolated_env / "l1_blk.mp4")
    record_production_state(l1, PublishingState.VIDEO_RENDERED.value, metadata={"type": "longform"})
    record_production_state(l1, PublishingState.BLOCKED_QUALITY_GATE.value, metadata={"quality_report": {"passed": False, "blocking_issues": ["[Script] short"]}})

    rep = generate_production_reliability_report(output_dir=str(isolated_env))
    sh = rep["formats"]["shorts"]
    lf = rep["formats"]["longform"]

    assert sh["production_completed"] == 2
    assert sh["quality_gate_passed"] == 2
    assert sh["upload_completed"] == 2
    assert sh["youtube_processing_completed"] == 2
    assert sh["scheduled"] == 1
    assert sh["actually_published"] == 1
    assert sh["analytics_collected"] == 1
    assert sh["failed"] == 0
    assert sh["recovered"] == 1

    assert lf["production_completed"] == 1
    assert lf["quality_gate_passed"] == 0
    assert lf["blocked_by_quality_gates"] == 1
    assert rep["analytics_sync_status"]["status"] == "BLOCKED"
    assert rep["analytics_sync_status"]["data_api_key_fallback_available"] is True


def test_reconcile_channel_publications_and_credits_attribution(isolated_env, monkeypatch):
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")

    # 1. Verify credits.json attribution gets appended on upload
    run_dir = isolated_env / "runs" / "short-credits"
    run_dir.mkdir(parents=True)
    vpath = run_dir / "final_short.mp4"
    vpath.write_bytes(b"0" * (220 * 1024))
    (run_dir / "credits.json").write_text(
        json.dumps([{"source": "Pexels", "author": "History Photographer", "license": "Pexels License"}]),
        encoding="utf-8",
    )

    svc = MagicMock()
    svc.channels().list.return_value.execute.return_value = {
        "items": [{"id": "UCb1BDNY8WxoD1q_UVyEmvuw", "contentDetails": {"relatedPlaylists": {"uploads": "UU_test"}}}]
    }
    svc.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    svc.videos().insert.return_value.next_chunk.return_value = (None, {"id": "yt_cred_1"})
    svc.videos().list.return_value.execute.return_value = {
        "items": [{"snippet": {"channelId": "UCb1BDNY8WxoD1q_UVyEmvuw"}, "status": {"uploadStatus": "uploaded", "privacyStatus": "private"}, "processingDetails": {"processingStatus": "succeeded"}}]
    }
    monkeypatch.setattr(yt, "_get_service", lambda: svc)

    url = upload_to_youtube(script=_sample_script("Attribution Test"), video_path=str(vpath), research=_sample_research(), is_shorts=True)
    assert url == "https://www.youtube.com/watch?v=yt_cred_1"
    sent_desc = svc.videos().insert.call_args[1]["body"]["snippet"]["description"]
    assert "Visual Credits:" in sent_desc
    assert "History Photographer" in sent_desc

    # 2. Reconcile scheduled -> public live channel status & external untracked videos
    svc.playlistItems().list.return_value.execute.return_value = {
        "items": [
            {"contentDetails": {"videoId": "yt_cred_1"}},
            {"contentDetails": {"videoId": "yt_external_99"}},
        ]
    }
    svc.videos().list.return_value.execute.return_value = {
        "items": [
            {
                "id": "yt_cred_1",
                "snippet": {"channelId": "UCb1BDNY8WxoD1q_UVyEmvuw", "title": "Attribution Test", "publishedAt": "2026-11-12T06:30:00Z"},
                "status": {"privacyStatus": "public"},
            },
            {
                "id": "yt_external_99",
                "snippet": {"channelId": "UCb1BDNY8WxoD1q_UVyEmvuw", "title": "External CI Video", "publishedAt": "2026-11-12T03:30:00Z"},
                "status": {"privacyStatus": "public"},
            },
        ]
    }
    recon = reconcile_channel_publications(output_dir=str(isolated_env), youtube_service=svc)
    assert recon["live_videos_inspected"] == 2
    assert recon["matched_production_db_count"] == 1
    assert recon["untracked_on_channel_count"] == 1
    assert get_production_record(str(vpath))["metadata"]["actually_published"] is True
