"""
Phase 21 Test Suite: Publishing Cadence Preservation Amendment
Verifies:
1. Established 5 Shorts + 1 Long-form = 6 daily schedule (Asia/Kolkata) preserved by default.
2. Configurability & backward compatibility.
3. No mandatory human approval introduced.
4. Mandatory quality gates block individual failing videos without halting daily batch.
5. Separate Shorts & Long-form metrics (median views, watch time, AVD, APV, impressions/CTR,
   sub conversion/1k, returning viewers, topic/format/hook/duration breakdowns, production
   failure & quality-gate rejection rates).
6. Rolling 30-day evaluation window, publication-age accounting, correlation vs causation.
7. No silent schedule/frequency reduction from insufficient analytics.
8. Adaptive Publishing Policy governance for frequency experiments.
9. OAuth owner analytics connectivity & explicit limitation reporting.
"""
import os
import json
import pickle
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

import config
import automation
from apis.growth_database import HistoricalPerformanceDB
from apis.youtube_analytics import (
    get_analytics_capabilities_and_limitations,
    sync_owner_channel_analytics,
    generate_weekly_format_report,
)
from agents.growth_analyst import (
    analyze_shorts_performance,
    analyze_longform_performance,
    analyze_production_and_quality_gates,
    generate_growth_intelligence_dossier,
)
from agents.adaptive_engine import (
    evaluate_cadence_change_eligibility,
    generate_weekly_adaptive_strategy,
    select_next_controlled_experiment,
)
from agents.experiment_tracker import (
    ExperimentTracker,
    validate_frequency_experiment_proposal,
)
from uploader.youtube import calculate_next_scheduled_time
from uploader.safety import PublishingState, record_production_state, is_eligible_for_upload


@pytest.fixture(autouse=True)
def isolate_phase21_io(tmp_path, monkeypatch):
    """Isolate output files and singletons during Phase 21 tests."""
    import apis.youtube_analytics as ya
    import apis.growth_database as gdb
    import uploader.safety as safety
    import agents.experiment_tracker as et

    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "OUTPUT_DIR", str(out_dir))
    monkeypatch.setattr(automation, "SCHEDULE_FILE", str(out_dir / "automation_schedule.json"))
    monkeypatch.setattr(ya, "SNAPSHOT_FILE", str(out_dir / "analytics_snapshots.json"))
    monkeypatch.setattr(ya, "WEEKLY_REPORT_FILE", str(out_dir / "weekly_analytics_report.json"))
    monkeypatch.setattr(safety, "PRODUCTION_DB_FILE", str(out_dir / "production_database.json"))

    db_path = str(out_dir / "historical_performance_db.json")
    monkeypatch.setattr(gdb, "DB_FILE", db_path)
    monkeypatch.setattr(gdb, "LEGACY_SNAPSHOT_FILE", str(out_dir / "legacy_snapshots.json"))
    monkeypatch.setattr(gdb, "_db_instance", HistoricalPerformanceDB(db_path=db_path))

    exp_path = str(out_dir / "growth_experiments.json")
    monkeypatch.setattr(et, "EXPERIMENTS_FILE", exp_path)
    monkeypatch.setattr(et, "_tracker_instance", ExperimentTracker(storage_path=exp_path))
    yield


def test_default_publishing_cadence_preserved():
    assert config.LONGFORM_DAILY_COUNT == 1
    assert config.SHORTS_DAILY_COUNT == 5
    assert config.TOTAL_DAILY_VIDEOS == 6
    assert config.PUBLISHING_TIMEZONE == "Asia/Kolkata"
    assert config.LONGFORM_TARGET_HOURS_IST == [19]
    assert config.SHORTS_TARGET_HOURS_IST == [9, 12, 16, 19, 22]
    assert config.PUBLISHING_CADENCE_POLICY["auto_reduce_frequency"] is False
    assert config.PUBLISHING_CADENCE_POLICY["require_human_approval"] is False

    cadence = automation.get_effective_cadence()
    assert cadence["longform_daily_count"] == 1
    assert cadence["shorts_daily_count"] == 5
    assert cadence["total_daily_videos"] == 6
    assert cadence["timezone"] == "Asia/Kolkata"
    assert cadence["shorts_hours_ist"] == [9, 12, 16, 19, 22]


def test_schedule_configurable_and_backward_compatible(tmp_path, monkeypatch):
    # Legacy schedule JSON without Phase 21 daily count keys
    legacy_path = tmp_path / "output" / "automation_schedule.json"
    legacy_path.write_text(json.dumps({
        "longform_target_hour_ist": 20,
        "shorts_hours_ist": [9, 12, 16, 19, 22],
        "history_runs": [],
    }), encoding="utf-8")

    state = automation.load_schedule_state()
    cadence = automation.get_effective_cadence(state)
    assert cadence["longform_target_hour_ist"] == 20
    assert cadence["longform_daily_count"] == 1
    assert cadence["shorts_daily_count"] == 5

    # Configurable schedule slots in uploader/youtube.py
    monkeypatch.setattr(config, "SHORTS_UPLOAD_CONFIG", {"target_hours_ist": [9, 12, 16, 19, 22]})
    ts_short = calculate_next_scheduled_time(is_shorts=True)
    ts_long = calculate_next_scheduled_time(is_shorts=False)
    assert ts_short.endswith("Z")
    assert ts_long.endswith("Z")

    # Configurable daily Shorts topic count (default 5)
    assert len(automation.get_shorts_topics_for_day()) == 5


def test_no_mandatory_human_approval_required(tmp_path):
    vid = tmp_path / "auto_vid.mp4"
    vid.write_bytes(b"0" * (600 * 1024))
    record_production_state(str(vid), PublishingState.METADATA_VALIDATED.value, metadata={"quality_report": {"passed": True}})
    eligible, reason = is_eligible_for_upload(str(vid))
    assert eligible is True
    assert reason is None


def test_quality_gate_blocks_individual_video_without_halting_daily_batch(monkeypatch):
    def fake_single_short(index, is_prerender=False, for_date=None, publish_at=None):
        if index == 2:
            return {
                "ok": False,
                "blocked_quality_gate": True,
                "index": 2,
                "title": "Blocked Short 2",
                "url": "local://blocked_quality_gate/short_2.mp4",
                "video_path": "output/short_2.mp4",
                "score": 40,
            }
        return {
            "ok": True,
            "blocked_quality_gate": False,
            "index": index,
            "title": f"Valid Short {index}",
            "url": f"https://www.youtube.com/watch?v=sh_{index}",
            "video_path": f"output/short_{index}.mp4",
            "score": 100,
        }

    def fake_longform(is_prerender=False, for_date=None, publish_at=None):
        return {
            "ok": True,
            "title": "Valid Longform",
            "url": "https://www.youtube.com/watch?v=lf_1",
            "video_path": "output/lf_1.mp4",
            "score": 100,
        }

    monkeypatch.setattr(automation, "create_and_publish_single_short", fake_single_short)
    monkeypatch.setattr(automation, "create_and_publish_longform", fake_longform)

    res = automation.run_advance_pipeline(days_ahead=0, check_yesterday=False)
    assert len(res["blocked"]) == 1
    assert res["blocked"][0]["index"] == 2
    # Remaining 4 Shorts + 1 Long-form still published
    assert len(res["processed"]) == 5
    pub_urls = [p["url"] for p in res["processed"]]
    assert "https://www.youtube.com/watch?v=sh_1" in pub_urls
    assert "https://www.youtube.com/watch?v=sh_3" in pub_urls
    assert "https://www.youtube.com/watch?v=sh_4" in pub_urls
    assert "https://www.youtube.com/watch?v=sh_5" in pub_urls
    assert "https://www.youtube.com/watch?v=lf_1" in pub_urls


def test_separate_shorts_and_longform_metrics_and_breakdowns():
    now = datetime.now(timezone.utc)
    recent_2d = (now - timedelta(days=2)).isoformat()
    recent_10d = (now - timedelta(days=10)).isoformat()

    shorts = [
        {
            "video_id": "s1",
            "title": "Why Does Delhi Iron Pillar Never Rust?",
            "topic": "Delhi Iron Pillar",
            "content_pillar": "Ancient Technology, Architecture & Engineering",
            "publication_timestamp": recent_2d,
            "video_duration_seconds": 32.0,
            "metadata_extras": {"format": "ancient_engineering", "hook_style": "question_paradox"},
            "latest_metrics": {
                "views": 1000,
                "watch_time_minutes": 450.0,
                "average_view_duration_seconds": 27.0,
                "average_percentage_viewed": 84.0,
                "subscribers_gained": 4,
                "returning_viewers": 120,
            },
        },
        {
            "video_id": "s2",
            "title": "The Secret Submerged City of Dwarka",
            "topic": "Dwarka Underwater",
            "content_pillar": "Lost Cities & Archaeological Discoveries",
            "publication_timestamp": recent_10d,
            "video_duration_seconds": 46.0,
            "metadata_extras": {"format": "archaeological_discovery", "hook_style": "contradiction_secret"},
            "latest_metrics": {
                "views": 5000,
                "watch_time_minutes": 2800.0,
                "average_view_duration_seconds": 33.6,
                "average_percentage_viewed": 73.0,
                "subscribers_gained": 20,
                "returning_viewers": None,
            },
        },
        {
            "video_id": "s3",
            "title": "How Kailash Temple Was Carved Top Down?",
            "topic": "Kailash Temple",
            "content_pillar": "Ancient Technology, Architecture & Engineering",
            "publication_timestamp": recent_10d,
            "video_duration_seconds": 54.0,
            "metadata_extras": {"format": "ancient_engineering", "hook_style": "question_paradox"},
            "latest_metrics": {
                "views": 3000,
                "watch_time_minutes": 2100.0,
                "average_view_duration_seconds": 42.0,
                "average_percentage_viewed": 77.8,
                "subscribers_gained": 15,
            },
        },
    ]

    longform = [
        {
            "video_id": "l1",
            "title": "Rajendra Chola Naval Empire",
            "topic": "Chola Navy",
            "content_pillar": "Indian Kings, Empires & Dynasties",
            "publication_timestamp": recent_10d,
            "video_duration_seconds": 620.0,
            "latest_metrics": {
                "views": 4000,
                "watch_time_minutes": 18000.0,
                "average_view_duration_seconds": 270.0,
                "average_percentage_viewed": 43.5,
                "impressions": 40000,
                "ctr": 0.06,
                "subscribers_gained": 32,
            },
        },
        {
            "video_id": "l2",
            "title": "Why Did Harappan Cities Vanish?",
            "topic": "Indus Valley Decline",
            "content_pillar": "Ancient Indian Civilizations",
            "publication_timestamp": recent_2d,
            "video_duration_seconds": 740.0,
            "latest_metrics": {
                "views": 2000,
                "watch_time_minutes": 11000.0,
                "average_view_duration_seconds": 330.0,
                "average_percentage_viewed": 48.0,
                "impressions": 22000,
                "ctr": 0.05,
                "subscribers_gained": 18,
            },
        },
    ]

    sh_res = analyze_shorts_performance(shorts)
    assert sh_res["median_views_per_video"] == 3000.0
    assert sh_res["total_watch_time_minutes"] == 5350.0
    assert sh_res["avg_view_duration_seconds"] > 0
    assert sh_res["observed_avg_apv"] > 70.0
    assert sh_res["sub_conversion_per_1k"] > 0
    assert sh_res["returning_viewers"]["available"] is True
    assert sh_res["returning_viewers"]["total"] == 120
    assert "ancient_engineering" in sh_res["format_breakdown"]
    assert "question_paradox" in sh_res["hook_breakdown"]
    assert "under_35s" in sh_res["duration_breakdown"]
    assert "35_to_50s" in sh_res["duration_breakdown"]
    assert "over_50s" in sh_res["duration_breakdown"]
    assert sh_res["avg_publication_age_days"] is not None

    lf_res = analyze_longform_performance(longform)
    assert lf_res["median_views_per_video"] == 3000.0
    assert lf_res["total_watch_time_minutes"] == 29000.0
    assert lf_res["avg_view_duration_seconds"] == 300.0
    assert lf_res["packaging_diagnostics"]["total_impressions"] == 62000
    assert lf_res["packaging_diagnostics"]["avg_ctr"] == 0.055
    assert lf_res["returning_viewers"]["available"] is False
    assert "topic_breakdown" in lf_res
    assert "hook_breakdown" in lf_res
    assert "8_to_11m" in lf_res["duration_breakdown"]
    assert "11_to_15m" in lf_res["duration_breakdown"]


def test_production_failures_and_quality_gate_rejection_rates(tmp_path):
    prod_db = {
        "v1.mp4": {"current_state": PublishingState.SCHEDULED.value, "quality_gate": {"passed": True, "gates": {}}},
        "v2.mp4": {"current_state": PublishingState.BLOCKED_QUALITY_GATE.value, "quality_gate": {"passed": False, "gates": {"script": {"passed": False}}, "blocking_issues": ["[Script] Too short"]}},
        "v3.mp4": {"current_state": PublishingState.FAILED.value},
        "v4.mp4": {"current_state": PublishingState.COMPLETED.value, "quality_gate": {"passed": True, "gates": {}}},
    }
    diag_dir = tmp_path / "diags"
    diag_dir.mkdir()
    (diag_dir / "d1.json").write_text(json.dumps({"passed": True}))
    (diag_dir / "d2.json").write_text(json.dumps({"passed": False}))

    metrics = analyze_production_and_quality_gates(production_db=prod_db, diagnostics_dir=str(diag_dir))
    assert metrics["total_tracked_productions"] == 4
    assert metrics["quality_gate_blocked_count"] == 1
    assert metrics["quality_gate_rejection_rate_pct"] == 25.0
    assert metrics["production_failures_count"] == 1
    assert metrics["production_failure_rate_pct"] == 25.0
    assert metrics["gate_failure_breakdown"]["script"] == 1


def test_rolling_30_day_evaluation_and_no_premature_cadence_reduction(tmp_path):
    from apis.growth_database import get_performance_db
    db = get_performance_db()
    now = datetime.now(timezone.utc)
    # 1 recent video, 1 old video outside 30-day window
    db.record_snapshot(
        video_id="recent_1",
        video_format="longform",
        topic="Recent Doc",
        content_pillar="Ancient Indian Civilizations",
        publication_timestamp=(now - timedelta(days=5)).isoformat(),
        video_duration=600.0,
        title="Recent Doc",
        views=500,
        watch_time_minutes=200.0,
        average_percentage_viewed=45.0,
    )
    db.record_snapshot(
        video_id="old_1",
        video_format="longform",
        topic="Old Doc",
        content_pillar="Ancient Indian Civilizations",
        publication_timestamp=(now - timedelta(days=45)).isoformat(),
        video_duration=600.0,
        title="Old Doc",
        views=9999,
        watch_time_minutes=4000.0,
        average_percentage_viewed=55.0,
    )

    dossier = generate_growth_intelligence_dossier()
    assert dossier["evaluation_window_days"] == 30
    assert dossier["total_videos_analyzed"] == 1
    assert dossier["cadence_policy"]["longform_per_day"] == 1
    assert dossier["cadence_policy"]["shorts_per_day"] == 5
    assert "correlation_vs_demonstrated_improvement" in dossier
    assert len(dossier["analytics_limitations"]) >= 1

    # Insufficient data must NOT reduce or alter schedule
    elig = evaluate_cadence_change_eligibility()
    assert elig["recommended_action"] == "PRESERVE_ESTABLISHED_CADENCE"
    assert elig["schedule_mutated"] is False
    assert elig["auto_reduction_blocked"] is True

    # adapt_upload_slot must not shift slot on insufficient runs (<5)
    st = automation.load_schedule_state()
    st["longform_target_hour_ist"] = 19
    new_hour = automation.adapt_upload_slot(st, slot_hour=19, recorded_views=10)
    assert new_hour == 19

    # select_next_controlled_experiment never auto-selects publishing_frequency
    exp = select_next_controlled_experiment()
    assert exp["category"] != "publishing_frequency"


def test_adaptive_publishing_policy_frequency_experiment_validation(tmp_path):
    # 1. Rejects simultaneous multi-variable changes & insufficient baseline
    ok_bad, issues_bad = validate_frequency_experiment_proposal({
        "hypothesis": "Reducing both formats increases views.",
        "changed_variables": ["longform_frequency", "shorts_frequency"],
        "simultaneous_variable_changes": True,
        "success_criteria": "APV >= 50%",
        "baseline_comparison": "1 longform + 5 shorts daily",
        "baseline_longform_samples": 2,
        "baseline_shorts_samples": 5,
    })
    assert ok_bad is False
    assert any("1 major variable" in i for i in issues_bad)
    assert any("Simultaneous" in i for i in issues_bad)
    assert any("Insufficient baseline evidence" in i for i in issues_bad)

    # 2. Accepts valid single-variable experiment with documented evidence, without mutating schedule
    tracker = ExperimentTracker(storage_path=str(tmp_path / "freq_exp.json"))
    exp = tracker.create_frequency_experiment({
        "name": "Long-Form Cadence Test (Single Variable)",
        "hypothesis": "Testing 5 long-form/week vs 7 long-form/week improves median long-form watch time per video.",
        "changed_variables": ["longform_daily_count"],
        "success_criteria": "Long-form median watch time >= +20% with p < 0.05 over 30 days",
        "baseline_comparison": "1 long-form + 5 Shorts daily (Asia/Kolkata)",
        "test_variant": "5 long-form/week + 5 Shorts daily (Shorts unchanged)",
        "baseline_longform_samples": 12,
        "baseline_shorts_samples": 35,
    })
    assert exp["category"] == "publishing_frequency"
    assert exp["auto_apply_to_schedule"] is False
    assert config.LONGFORM_DAILY_COUNT == 1
    assert config.SHORTS_DAILY_COUNT == 5


class _DummyCreds:
    def __init__(self, scopes):
        self.scopes = scopes
        self.valid = True
        self.expired = False
        self.refresh_token = "rt"


def test_oauth_analytics_capabilities_and_limitations_reporting(tmp_path, monkeypatch):
    # Upload-only token -> explicitly reports missing scopes
    tok_path = tmp_path / "youtube_token.pickle"

    with open(tok_path, "wb") as f:
        pickle.dump(_DummyCreds(["https://www.googleapis.com/auth/youtube.upload"]), f)

    import uploader.oauth_manager as om
    monkeypatch.setattr(om, "TOKEN_FILE", str(tok_path))
    monkeypatch.setattr("apis.youtube_analytics.audit_token_scopes", lambda: om.audit_token_scopes(str(tok_path)))

    caps = get_analytics_capabilities_and_limitations()
    assert caps["owner_analytics_connected"] is False
    assert "https://www.googleapis.com/auth/yt-analytics.readonly" in caps["missing_scopes"]
    assert any("yt-analytics.readonly" in lim for lim in caps["limitations"])

    # Full scopes -> owner_analytics_connected True
    with open(tok_path, "wb") as f:
        pickle.dump(_DummyCreds(om.REQUIRED_SCOPES), f)
    caps_full = get_analytics_capabilities_and_limitations()
    assert caps_full["owner_analytics_connected"] is True

    # Mocked sync_owner_channel_analytics using OAuth owner services
    monkeypatch.setattr(config, "YOUTUBE_CHANNEL_ID", "UC_OWNER")
    mock_yt = MagicMock()
    mock_yt.channels().list.return_value.execute.return_value = {
        "items": [{"id": "UC_OWNER", "contentDetails": {"relatedPlaylists": {"uploads": "UU_OWNER"}}}]
    }
    mock_yt.playlistItems().list.return_value.execute.return_value = {
        "items": [{"contentDetails": {"videoId": "vid_owner_1"}}]
    }
    mock_yt.videos().list.return_value.execute.return_value = {
        "items": [{
            "id": "vid_owner_1",
            "snippet": {"title": "Dwarka Underwater Ruins", "publishedAt": datetime.now(timezone.utc).isoformat()},
            "statistics": {"viewCount": "850", "likeCount": "45", "commentCount": "9"},
            "contentDetails": {"duration": "PT10M30S"},
        }]
    }
    monkeypatch.setattr("uploader.youtube._get_service", lambda: mock_yt)
    monkeypatch.setattr("apis.youtube_analytics.query_analytics_report", lambda **kw: {
        "ok": True,
        "rows": [[850, 3200.0, 225.0, 35.7, 45, 9, 12]] if "insightTrafficSourceType" not in str(kw.get("dimensions", "")) else [],
    })

    sync_res = sync_owner_channel_analytics(days_back=30)
    assert sync_res["ok"] is True
    assert sync_res["videos_synced"] == 1
    assert sync_res["source"] == "youtube_analytics_api_v2"
