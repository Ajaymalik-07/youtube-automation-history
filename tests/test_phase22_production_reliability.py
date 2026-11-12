"""
Phase 22 — Production Reliability & End-to-End Validation Test Suite.

Covers:
- Complete stage lifecycle & per-job checkpoint recovery
- 19:00 IST Shorts 4/5 + Long-form concurrency & slot isolation
- Pre-rendered manifest preservation of research & script for quality gates
- Processing failure string handling, quota exhaustion halt, & transient retry recovery
- Channel identity guard & idempotent duplicate upload prevention
- Real FFmpeg-probed rendering QA (1920x1080, 1080x1920, AAC audio, Shorts <=60s cap, black frames, SRT)
- Production reliability report (Shorts vs Long-form separated + OAuth BLOCKED reporting)
- Adaptive engine missing-metric & cadence preservation safeguards
"""
import concurrent.futures
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import automation
import config
from agents.adaptive_engine import (
    evaluate_cadence_change_eligibility,
    generate_weekly_adaptive_strategy,
)
from agents.growth_analyst import generate_production_reliability_report
from apis.growth_database import HistoricalPerformanceDB
from uploader.quality_gates import (
    evaluate_all_quality_gates,
    validate_srt_captions,
    validate_video_gate,
)
from uploader.safety import (
    PublishingState,
    get_production_record,
    is_eligible_for_upload,
    load_production_db,
    record_production_state,
)
from uploader.youtube import upload_to_youtube


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    """Isolate OUTPUT_DIR, schedule state, production DB, and growth DB per test."""
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
    monkeypatch.setattr(
        automation,
        "get_shorts_topics_for_day",
        lambda date_str, count=5: [
            (f"Harappan Water Engineering Part {i}", "hi" if i <= 3 else "en")
            for i in range(1, count + 1)
        ],
    )
    yield out_dir


def _valid_research(topic="Harappan Hydraulic Engineering", pillar="Ancient Engineering & Architecture"):
    return {
        "topic": topic,
        "video_title": topic,
        "period": "2600–1900 BCE",
        "geographic_location": "Dholavira, Gujarat, India",
        "focus_angle": pillar,
        "claims_and_evidence": [
            {"claim": f"{topic} archaeological evidence", "evidence_level": "ESTABLISHED_FACT"},
            {"claim": f"{topic} check dam diversion", "evidence_level": "STRONGLY_SUPPORTED"},
            {"claim": f"{topic} multi-tier cisterns", "evidence_level": "ESTABLISHED_FACT"},
        ],
        "verified_timeline": [
            {"era": "3000 BCE", "event": "Foundation phase"},
            {"era": "2500 BCE", "event": "Peak expansion"},
        ],
        "confidence_score": 0.91,
        "tags": ["Harappa", "IndianHistory", "AncientEngineering", "Shorts"],
    }


def _valid_script(title="Harappan Water Secrets", is_shorts=False):
    if is_shorts:
        return {
            "title": f"{title} #Shorts",
            "video_type": "shorts",
            "description": "Verified archaeological evidence of ancient water engineering in Dholavira #Shorts #History",
            "tags": ["Dholavira", "Harappa", "IndianHistory", "Shorts"],
            "estimated_duration_seconds": 45.0,
            "sections": [
                {"id": 1, "narration": "Four thousand years ago in the arid Rann of Kutch, engineers built sixteen massive stone reservoirs that stored monsoon water for an entire metropolis."},
                {"id": 2, "narration": "Evidence uncovered by the Archaeological Survey of India proves precision sandstone masonry diverted seasonal floods through underground stone settling channels."},
                {"id": 3, "narration": "Every drop of rainwater sustained tens of thousands of residents long before Roman aqueducts existed. Subscribe to Stories Malik for verified history."},
            ],
        }
    return {
        "title": title,
        "video_type": "normal",
        "description": "Deep documentary investigation into the ancient water harvesting systems of Dholavira and the Indus Valley Civilization.",
        "tags": ["Dholavira", "Harappa", "AncientIndia", "Documentary"],
        "estimated_duration_seconds": 540.0,
        "sections": [
            {
                "id": i,
                "title": f"Chapter {i}",
                "narration": (
                    f"In historical investigation segment {i}, archaeological surveys across Gujarat and Khadir Bet island "
                    f"demonstrate how urban architects of Dholavira designed stepped sandstone reservoirs, diversion dams, "
                    f"and subterranean channels during phase {i} to store seasonal floodwaters cleanly across multiple centuries "
                    f"of arid desert conditions without institutional collapse."
                ),
            }
            for i in range(1, 9)
        ],
    }


def _mock_youtube_service(channel_id="UCb1BDNY8WxoD1q_UVyEmvuw", vid_id="yt_test_001"):
    svc = MagicMock()
    svc.channels().list.return_value.execute.return_value = {
        "items": [{"id": channel_id, "snippet": {"title": "Stories Malik"}}]
    }
    svc.videoCategories().list.return_value.execute.return_value = {"items": [{"id": "27"}]}
    insert_req = MagicMock()
    insert_req.next_chunk.return_value = (None, {"id": vid_id})
    svc.videos().insert.return_value = insert_req
    svc.videos().list.return_value.execute.return_value = {
        "items": [{
            "snippet": {"channelId": channel_id},
            "status": {"uploadStatus": "uploaded", "privacyStatus": "private", "publishAt": "2026-11-20T13:30:00Z"},
            "processingDetails": {"processingStatus": "succeeded"},
        }]
    }
    return svc


def test_e2e_short_full_lifecycle_and_checkpoints(isolated_workspace, monkeypatch):
    import uploader.youtube as yt
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")
    monkeypatch.setattr(automation, "is_configured", lambda: True)
    monkeypatch.setattr(yt, "is_configured", lambda: True)
    mock_svc = _mock_youtube_service(vid_id="short_e2e_1")
    monkeypatch.setattr(yt, "_get_service", lambda: mock_svc)

    res_calls = []
    monkeypatch.setattr(
        automation,
        "research_topic",
        lambda *a, **kw: (res_calls.append(1) or _valid_research()),
    )
    monkeypatch.setattr(automation, "write_script", lambda *a, **kw: _valid_script(is_shorts=True))
    monkeypatch.setattr(automation, "download_images", lambda s, d: {sec["id"]: [] for sec in s["sections"]})

    def fake_narr(script, out_dir, **kw):
        os.makedirs(out_dir, exist_ok=True)
        mp3 = os.path.join(out_dir, "narration.mp3")
        srt = os.path.join(out_dir, "narration.srt")
        with open(mp3, "wb") as f:
            f.write(b"ID3" + b"0" * 4096)
        with open(srt, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:04,000\nAncient water reservoirs.\n\n")
        return mp3

    def fake_video(script, audio_path, out_dir, img_map, video_type="shorts"):
        vpath = os.path.join(out_dir, "final_short.mp4")
        with open(vpath, "wb") as f:
            f.write(b"0" * (220 * 1024))
        return vpath

    monkeypatch.setattr(automation, "generate_narration", fake_narr)
    monkeypatch.setattr(automation, "create_video", fake_video)

    res = automation.create_and_publish_single_short(index=1, is_prerender=False, for_date="2026-11-15")
    assert res["ok"] is True
    assert res["url"] == "https://www.youtube.com/watch?v=short_e2e_1"
    assert res["job_id"].startswith("short-2026-11-15-s1-")
    assert res["content_id"].startswith("short-2026-11-15-s1-")

    rec = get_production_record(res["video_path"])
    assert rec is not None
    assert rec["current_state"] == PublishingState.ANALYTICS_PENDING.value
    visited = [h["from_state"] for h in rec["history"]] + [rec["current_state"]]
    for expected in (
        PublishingState.TOPIC_SELECTED.value,
        PublishingState.RESEARCH_IN_PROGRESS.value,
        PublishingState.RESEARCH_VALIDATED.value,
        PublishingState.SCRIPT_GENERATED.value,
        PublishingState.SCRIPT_VALIDATED.value,
        PublishingState.VIDEO_RENDERING.value,
        PublishingState.VIDEO_RENDERED.value,
        PublishingState.VIDEO_VALIDATED.value,
        PublishingState.METADATA_VALIDATED.value,
        PublishingState.UPLOAD_QUEUED.value,
        PublishingState.UPLOADING.value,
        PublishingState.ANALYTICS_PENDING.value,
    ):
        assert expected in visited


def test_checkpoint_resume_after_interruption(isolated_workspace, monkeypatch):
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: False)
    calls = {"research": 0, "script": 0, "render": 0}

    monkeypatch.setattr(
        automation,
        "research_topic",
        lambda *a, **kw: (calls.__setitem__("research", calls["research"] + 1) or _valid_research()),
    )
    monkeypatch.setattr(
        automation,
        "write_script",
        lambda *a, **kw: (calls.__setitem__("script", calls["script"] + 1) or _valid_script(is_shorts=True)),
    )
    monkeypatch.setattr(automation, "download_images", lambda s, d: {1: []})

    def fake_narr(script, out_dir, **kw):
        os.makedirs(out_dir, exist_ok=True)
        mp3 = os.path.join(out_dir, "narration.mp3")
        srt = os.path.join(out_dir, "narration.srt")
        with open(mp3, "wb") as f:
            f.write(b"ID3" + b"0" * 2048)
        with open(srt, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:03,000\nCheckpointed audio.\n\n")
        return mp3

    def crash_on_first_render(script, audio_path, out_dir, img_map, video_type="shorts"):
        calls["render"] += 1
        if calls["render"] == 1:
            raise RuntimeError("Simulated mid-render interruption")
        vpath = os.path.join(out_dir, "final_short.mp4")
        with open(vpath, "wb") as f:
            f.write(b"0" * (220 * 1024))
        return vpath

    monkeypatch.setattr(automation, "generate_narration", fake_narr)
    monkeypatch.setattr(automation, "create_video", crash_on_first_render)

    with pytest.raises(RuntimeError, match="Simulated mid-render interruption"):
        automation.create_and_publish_single_short(index=2, is_prerender=False, for_date="2026-11-16")

    assert calls["research"] == 1
    assert calls["script"] == 1

    # Restart run on same slot & date: must resume from checkpoint without re-running research/script
    res2 = automation.create_and_publish_single_short(index=2, is_prerender=False, for_date="2026-11-16")
    assert res2["ok"] is True
    assert calls["research"] == 1
    assert calls["script"] == 1
    assert calls["render"] == 2


def test_1900_ist_concurrency_and_slot_isolation(isolated_workspace, monkeypatch):
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")

    def fake_svc_factory():
        svc = _mock_youtube_service(vid_id="concurrent_vid")
        return svc

    monkeypatch.setattr(yt, "_get_service", fake_svc_factory)
    monkeypatch.setattr(automation, "research_topic", lambda *a, **kw: _valid_research())
    monkeypatch.setattr(
        automation,
        "write_script",
        lambda research, video_type="long", **kw: _valid_script(is_shorts=(video_type == "shorts")),
    )
    monkeypatch.setattr(automation, "translate_script", lambda s, **kw: s)
    monkeypatch.setattr(automation, "download_images", lambda s, d: {sec["id"]: [] for sec in s["sections"]})

    def fake_narr(script, out_dir, filename="narration.mp3", srt_filename="narration.srt", **kw):
        os.makedirs(out_dir, exist_ok=True)
        mp3 = os.path.join(out_dir, filename)
        srt = os.path.join(out_dir, srt_filename)
        with open(mp3, "wb") as f:
            f.write(b"ID3" + b"0" * 2048)
        with open(srt, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:03,000\nIsolated stream.\n\n")
        return mp3

    def fake_video(script, audio_path, out_dir, img_map, video_type="normal"):
        fname = "final_short.mp4" if video_type == "shorts" else "final_video.mp4"
        vpath = os.path.join(out_dir, fname)
        with open(vpath, "wb") as f:
            f.write(b"0" * (600 * 1024))
        return vpath

    monkeypatch.setattr(automation, "generate_narration", fake_narr)
    monkeypatch.setattr(automation, "create_video", fake_video)
    monkeypatch.setattr(automation.thumbnail, "render", lambda style, path, *a, **kw: (open(path, "wb").write(b"J" * (20 * 1024)) and path) or path)
    monkeypatch.setattr(config, "MUSIC_ENABLED", False)

    target_date = "2026-11-18"
    pub_at = "2026-11-18T13:30:00Z"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_short = pool.submit(
            automation.create_and_publish_single_short,
            index=4,
            is_prerender=False,
            for_date=target_date,
            publish_at=pub_at,
        )
        f_long = pool.submit(
            automation.create_and_publish_longform,
            is_prerender=False,
            for_date=target_date,
            publish_at=pub_at,
        )
        s_res = f_short.result()
        l_res = f_long.result()

    assert s_res["ok"] is True
    assert l_res["ok"] is True
    assert os.path.dirname(s_res["video_path"]) != os.path.dirname(l_res["video_path"])
    assert "short" in s_res["content_id"] and "longform" in l_res["content_id"]

    sched = automation.load_schedule_state()
    assert sched.get(f"last_short_pub_{target_date}_19") is True
    assert sched.get("last_longform_pub_date") == target_date
    db = load_production_db()
    assert os.path.normpath(s_res["video_path"]) in db
    assert os.path.normpath(l_res["video_path"]) in db


def test_prerender_manifest_preserves_research_and_script_on_reuse(isolated_workspace, monkeypatch):
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")
    monkeypatch.setattr(yt, "_get_service", lambda: _mock_youtube_service(vid_id="prerender_ok"))

    monkeypatch.setattr(automation, "research_topic", lambda *a, **kw: _valid_research())
    monkeypatch.setattr(automation, "write_script", lambda *a, **kw: _valid_script(is_shorts=True))
    monkeypatch.setattr(automation, "download_images", lambda s, d: {sec["id"]: [] for sec in s["sections"]})
    monkeypatch.setattr(automation, "generate_narration", lambda s, d, **kw: (open(os.path.join(d, "narration.mp3"), "wb").write(b"ID3" + b"0" * 1024), open(os.path.join(d, "narration.srt"), "w").write("1\n00:00:00,000 --> 00:00:03,000\nCaption.\n\n"), os.path.join(d, "narration.mp3"))[2])
    monkeypatch.setattr(automation, "create_video", lambda s, a, d, m, video_type="shorts": (open(os.path.join(d, "final_short.mp4"), "wb").write(b"0" * (220 * 1024)), os.path.join(d, "final_short.mp4"))[1])

    q_res = automation.create_and_publish_single_short(index=1, is_prerender=True, for_date="2026-11-19")
    assert q_res["url"] == "local://scheduled_queue/2026-11-19/short_1"

    mf = isolated_workspace / "scheduled_queue" / "short_1_2026-11-19.json"
    assert mf.exists()
    manifest = json.loads(mf.read_text(encoding="utf-8"))
    assert manifest.get("research", {}).get("topic") == "Harappan Hydraulic Engineering"
    assert len(manifest.get("script", {}).get("sections", [])) >= 3

    # Reusing the manifest runs full quality gates (skip_quality_gate=False) and succeeds!
    pub_url = automation.publish_scheduled_short(index=1, target_date="2026-11-19")
    assert pub_url == "https://www.youtube.com/watch?v=prerender_ok"
    assert not mf.exists()


def test_processing_failure_quota_halt_and_retry_recovery(isolated_workspace, monkeypatch):
    from googleapiclient.errors import HttpError
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UCb1BDNY8WxoD1q_UVyEmvuw")

    vid = isolated_workspace / "test_recovery_short.mp4"
    vid.write_bytes(b"0" * (220 * 1024))

    # 1. Processing failure returns string, never None
    fail_svc = _mock_youtube_service(vid_id="proc_fail_1")
    fail_svc.videos().list.return_value.execute.return_value = {
        "items": [{
            "snippet": {"channelId": "UCb1BDNY8WxoD1q_UVyEmvuw"},
            "status": {"uploadStatus": "rejected", "rejectionReason": "policyViolation"},
            "processingDetails": {"processingStatus": "failed"},
        }]
    }
    monkeypatch.setattr(yt, "_get_service", lambda: fail_svc)
    out = upload_to_youtube(script=_valid_script(is_shorts=True), video_path=str(vid), research=_valid_research(), is_shorts=True)
    assert isinstance(out, str) and out.startswith("local://failed_processing/")

    # 2. Quota exhaustion returns local://pending_quota_reset/... and persists manifest
    vid2 = isolated_workspace / "test_quota_short.mp4"
    vid2.write_bytes(b"0" * (220 * 1024))
    quota_svc = _mock_youtube_service()
    fake_resp = MagicMock()
    fake_resp.status = 403
    fake_resp.reason = "Forbidden"
    quota_svc.videos().insert.return_value.next_chunk.side_effect = HttpError(fake_resp, b"quotaExceeded")
    monkeypatch.setattr(yt, "_get_service", lambda: quota_svc)

    out_q = upload_to_youtube(script=_valid_script(is_shorts=True), video_path=str(vid2), research=_valid_research(), is_shorts=True)
    assert out_q.startswith("local://pending_quota_reset/")
    pending_mf = isolated_workspace / "pending_uploads" / "upload_test_quota_short.mp4.json"
    assert pending_mf.exists()
    assert json.loads(pending_mf.read_text(encoding="utf-8"))["status"] == "pending_quota_reset"

    # 3. Retry pending uploads once API recovers -> transitions FAILED -> SCHEDULED -> ANALYTICS_PENDING & prevents duplicate
    ok_svc = _mock_youtube_service(vid_id="recovered_vid_77")
    monkeypatch.setattr(yt, "_get_service", lambda: ok_svc)
    recovery = automation.retry_pending_uploads()
    assert len(recovery["succeeded"]) == 1
    assert recovery["succeeded"][0]["url"] == "https://www.youtube.com/watch?v=recovered_vid_77"
    assert not pending_mf.exists()

    rec = get_production_record(str(vid2))
    assert rec["current_state"] == PublishingState.ANALYTICS_PENDING.value
    assert rec["recovered_count"] >= 1
    eligible, reason = is_eligible_for_upload(str(vid2))
    assert eligible is False
    assert "already uploaded" in reason.lower()


def test_channel_identity_guard_blocks_wrong_channel(isolated_workspace, monkeypatch):
    import uploader.youtube as yt
    monkeypatch.setattr(yt, "is_configured", lambda: True)
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UC_STORIES_MALIK_EXPECTED")
    wrong_svc = _mock_youtube_service(channel_id="UC_WRONG_PERSONAL_CHANNEL")
    monkeypatch.setattr(yt, "_get_service", lambda: wrong_svc)

    vid = isolated_workspace / "channel_guard_short.mp4"
    vid.write_bytes(b"0" * (220 * 1024))
    res = upload_to_youtube(script=_valid_script(is_shorts=True), video_path=str(vid), research=_valid_research(), is_shorts=True)
    assert res.startswith("local://channel_mismatch/")
    assert wrong_svc.videos().insert.return_value.next_chunk.call_count == 0


def test_real_rendered_media_qa_gates(isolated_workspace):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not available in PATH")

    # Helper to create real H.264 + AAC test artifacts using testsrc2 (high visual entropy >= 512 KB, non-black) or solid black
    def _render_mp4(name, width, height, duration_s, source="testsrc2", silent_audio=True):
        out = str(isolated_workspace / name)
        v_input = (
            f"color=c=black:s={width}x{height}:d={duration_s}"
            if source == "black"
            else f"testsrc2=size={width}x{height}:rate=24:duration={duration_s}"
        )
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", v_input]
        if silent_audio:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration_s}"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-b:v", "3000k", "-minrate", "2500k", "-maxrate", "4000k", "-bufsize", "4000k", "-pix_fmt", "yuv420p"]
        if silent_audio:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-movflags", "+faststart", out]
        subprocess.run(cmd, check=True, capture_output=True)
        return out

    # 1. Valid 1920x1080 long-form sample
    lf_mp4 = _render_mp4("valid_lf.mp4", 1920, 1080, 2.5, source="testsrc2", silent_audio=True)
    ok_lf, issues_lf = validate_video_gate(lf_mp4, is_shorts=False, deep_probe=True, check_black_frames=True)
    assert ok_lf is True, f"Unexpected issues: {issues_lf}"

    # 2. Valid 1080x1920 Short sample with SRT captions
    sh_mp4 = _render_mp4("valid_short.mp4", 1080, 1920, 2.5, source="testsrc2", silent_audio=True)
    srt_file = isolated_workspace / "valid_short.srt"
    srt_file.write_text("1\n00:00:00,100 --> 00:00:02,400\nHistorical Shorts Caption\n\n", encoding="utf-8")
    ok_sh, issues_sh = validate_video_gate(sh_mp4, is_shorts=True, deep_probe=True, check_black_frames=True, srt_path=str(srt_file))
    assert ok_sh is True, f"Unexpected issues: {issues_sh}"

    # 3. Over-limit 62s Short must fail Shorts <= 60s gate
    over_sh = _render_mp4("over_limit_short.mp4", 1080, 1920, 62.0, source="testsrc2", silent_audio=True)
    ok_over, issues_over = validate_video_gate(over_sh, is_shorts=True, deep_probe=True)
    assert ok_over is False
    assert any("exceeds maximum allowed" in i.lower() for i in issues_over)

    # 4. Black frames Short (>= 1.5s solid black) must fail black_frames QA
    black_sh = _render_mp4("black_short.mp4", 1080, 1920, 3.0, source="black", silent_audio=True)
    ok_blk, issues_blk = validate_video_gate(black_sh, is_shorts=True, deep_probe=True, check_black_frames=True)
    assert ok_blk is False
    assert any("black-frame" in i.lower() for i in issues_blk)

    # 5. Video without audio stream must fail
    no_aud = _render_mp4("no_audio_short.mp4", 1080, 1920, 2.5, source="testsrc2", silent_audio=False)
    ok_na, issues_na = validate_video_gate(no_aud, is_shorts=True, deep_probe=True)
    assert ok_na is False
    assert any("no audio stream" in i.lower() for i in issues_na)

    # 6. Wrong orientation (1920x1080 labeled as Short) must fail
    ok_ori, issues_ori = validate_video_gate(lf_mp4, is_shorts=True, deep_probe=True)
    assert ok_ori is False
    assert any("aspect ratio" in i.lower() for i in issues_ori)


def test_production_reliability_report_separates_shorts_and_longform(isolated_workspace, monkeypatch):
    import apis.youtube_analytics as ya
    monkeypatch.setattr(
        ya,
        "get_analytics_capabilities_and_limitations",
        lambda: {
            "owner_analytics_connected": False,
            "data_api_key_available": True,
            "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"],
            "limitations": ["OAuth token missing analytics scopes."],
        },
    )

    # Seed separated production history
    record_production_state(str(isolated_workspace / "s1.mp4"), PublishingState.FAILED.value, metadata={"type": "short", "error_type": "HttpError"})
    record_production_state(str(isolated_workspace / "s1.mp4"), PublishingState.SCHEDULED.value, metadata={"type": "short"})
    record_production_state(str(isolated_workspace / "s1.mp4"), PublishingState.ANALYTICS_PENDING.value, metadata={"type": "short"})

    record_production_state(str(isolated_workspace / "s2.mp4"), PublishingState.BLOCKED_QUALITY_GATE.value, metadata={"type": "short", "quality_report": {"passed": False, "blocking_issues": ["[Video] No audio"]}})
    record_production_state(str(isolated_workspace / "lf1.mp4"), PublishingState.FAILED.value, metadata={"type": "longform", "error_type": "RenderingFailure"})

    report = generate_production_reliability_report(output_dir=str(isolated_workspace))
    assert report["formats"]["shorts"]["jobs_started"] == 2
    assert report["formats"]["shorts"]["jobs_completed"] == 1
    assert report["formats"]["shorts"]["recovery_success"] == 1
    assert report["formats"]["shorts"]["blocked_by_quality_gates"] == 1
    assert report["formats"]["longform"]["jobs_started"] == 1
    assert report["formats"]["longform"]["jobs_failed"] == 1
    assert report["formats"]["longform"]["rendering_failures"] == 1
    assert report["analytics_sync_status"]["status"] == "BLOCKED"
    assert os.path.exists(report["json_path"])
    assert os.path.exists(report["markdown_path"])


def test_adaptive_engine_missing_metrics_and_cadence_preservation(isolated_workspace, monkeypatch):
    # Ensure missing analytics keep metrics None and NEVER recommend reducing 5+1 cadence
    db = HistoricalPerformanceDB(db_path=str(isolated_workspace / "growth_history.json"))
    db.record_snapshot(
        video_id="vid_no_analytics_1",
        video_format="short",
        topic="Kalinga War",
        content_pillar="Battles & Military Strategy",
        publication_timestamp=(datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        video_duration=45.0,
        title="Kalinga War #Shorts",
        views=1200,
    )
    import apis.growth_database as gdb_mod
    monkeypatch.setattr(gdb_mod, "_db_instance", db)
    import agents.growth_analyst as ga_mod
    monkeypatch.setattr(ga_mod, "get_performance_db", lambda: db)
    import agents.adaptive_engine as ae_mod
    monkeypatch.setattr(ae_mod, "get_performance_db", lambda: db)

    cadence_check = evaluate_cadence_change_eligibility()
    assert cadence_check["sufficient_baseline_evidence"] is False
    assert cadence_check["recommended_action"] == "PRESERVE_ESTABLISHED_CADENCE"
    assert cadence_check["auto_reduction_blocked"] is True
    assert cadence_check["schedule_mutated"] is False
    assert config.LONGFORM_DAILY_COUNT == 1
    assert config.SHORTS_DAILY_COUNT == 5

    strat = generate_weekly_adaptive_strategy(evaluation_window_days=30)
    est = strat["cadence_governance"]["established_cadence"]
    assert est["longform_per_day"] == 1
    assert est["shorts_per_day"] == 5
    assert est["total_per_day"] == 6
    assert strat["cadence_governance"]["schedule_mutated"] is False
    assert strat["statistical_evaluation"]["shorts_retention"]["available"] is False
    assert "Insufficient" in strat["statistical_evaluation"]["shorts_retention"]["policy_tier"]
