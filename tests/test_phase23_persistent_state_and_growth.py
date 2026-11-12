"""
Phase 23 — Persistent Production State & 30-Day Growth Validation Test Suite.

Covers:
- Schema versioning & v1 -> v2 migrations (production DB, growth DB, legacy snapshots, schedule)
- Stale-state overwrite protection & monotonic conflict merging
- SQLite WAL ledger durability + SHA-256 checksummed backup & restore
- Real multi-process persistence & workflow restart recovery
- Channel reconciliation (schedule recovery without metadata fabrication, duplicate prevention, coverage tracking)
- 30-day growth measurement & 6 Phase 23 reports (Shorts vs Long-form, provenance tags, None != 0)
- Controlled experiment governance (Bonferroni multiple-comparison threshold & single-variable isolation)
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

import config
from agents.experiment_tracker import ExperimentTracker
from agents.growth_analyst import generate_phase23_reports
from apis.growth_database import HistoricalPerformanceDB
from apis.state_store import (
    CURRENT_SCHEMA_VERSION,
    create_state_backup,
    generate_persistent_state_health_report,
    merge_growth_records,
    merge_production_records,
    merge_schedule_states,
    migrate_growth_records,
    migrate_production_records,
    migrate_schedule_state,
    restore_from_sqlite,
    restore_state_backup,
    sync_to_sqlite,
)
from apis.youtube_analytics import generate_weekly_format_report
from uploader.safety import (
    PublishingState,
    _save_db_unlocked,
    load_production_db,
    record_production_state,
)
from uploader.youtube import reconcile_channel_publications


def test_schema_migrations_v1_to_v2_and_legacy_snapshots(tmp_path):
    legacy_prod = {
        "output/v_old.mp4": {
            "video_path": "output/v_old.mp4",
            "current_state": "APPROVED",
            "history": [],
            "metadata": {"type": "short"},
        }
    }
    norm_p, p_info = migrate_production_records(legacy_prod)
    key = os.path.normpath("output/v_old.mp4")
    assert norm_p[key]["current_state"] == PublishingState.UPLOAD_QUEUED.value
    assert norm_p[key]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert norm_p[key]["revision"] >= 1
    assert p_info["migrated_records"] == 1

    legacy_snaps = {
        "vid_legacy_1": {
            "title": "Ancient Indus Trade",
            "is_shorts": True,
            "published_at": "2026-11-01T09:00:00Z",
            "metrics": {"views": 4200, "estimatedMinutesWatched": None},
        }
    }
    norm_g, g_info = migrate_growth_records(legacy_snaps)
    assert norm_g["vid_legacy_1"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert norm_g["vid_legacy_1"]["latest_metrics"]["views"] == 4200
    assert norm_g["vid_legacy_1"]["latest_metrics"]["watch_time_minutes"] is None
    assert g_info["migrated_records"] == 1

    sched_v2 = migrate_schedule_state({"last_longform_date": "2026-11-10"})
    assert sched_v2["schema_version"] == CURRENT_SCHEMA_VERSION
    assert sched_v2["revision"] == 1
    assert sched_v2["last_longform_date"] == "2026-11-10"


def test_stale_state_conflict_protection_and_monotonic_merge(tmp_path):
    key = os.path.normpath("output/conflict_short.mp4")
    newer = {
        key: {
            "schema_version": 2,
            "revision": 5,
            "video_path": "output/conflict_short.mp4",
            "current_state": PublishingState.SCHEDULED.value,
            "updated_at": "2026-11-12T08:00:00+00:00",
            "history": [{"from_state": "UPLOADING", "to_state": "SCHEDULED", "timestamp": "2026-11-12T08:00:00+00:00"}],
            "retry_count": 1,
            "recovered_count": 1,
            "metadata": {"youtube_id": "yt_win"},
        }
    }
    stale = {
        key: {
            "schema_version": 2,
            "revision": 2,
            "video_path": "output/conflict_short.mp4",
            "current_state": PublishingState.FAILED.value,
            "updated_at": "2026-11-12T06:00:00+00:00",
            "history": [{"from_state": "VIDEO_RENDERED", "to_state": "FAILED", "timestamp": "2026-11-12T06:00:00+00:00"}],
            "retry_count": 0,
            "recovered_count": 0,
            "metadata": {},
        }
    }
    merged, stats = merge_production_records(newer, stale)
    assert merged[key]["current_state"] == PublishingState.SCHEDULED.value
    assert merged[key]["revision"] == 5
    assert len(merged[key]["history"]) == 2
    assert stats["stale_incoming_rejected"] == 1

    # Direct on-disk stale save protection in safety.py
    db_file = str(tmp_path / "prod_conflict.json")
    import uploader.safety as safety_mod
    safety_mod.PRODUCTION_DB_FILE = db_file
    _save_db_unlocked(db_file, newer)
    _save_db_unlocked(db_file, stale)
    reloaded = load_production_db()
    assert reloaded[key]["current_state"] == PublishingState.SCHEDULED.value

    # Growth merge preserves owner analytics over fallback snapshot
    g_owner = {
        "v1": {
            "video_id": "v1",
            "revision": 3,
            "owner_analytics_available": True,
            "latest_retrieval_timestamp": "2026-11-12T07:00:00+00:00",
            "snapshot_history": [{"checkpoint": "48h", "observation_period": "2026-11-12", "owner_analytics_available": True, "metrics": {"views": 500, "watch_time_minutes": 180.0}}],
            "latest_metrics": {"views": 500, "watch_time_minutes": 180.0},
        }
    }
    g_stale_pub = {
        "v1": {
            "video_id": "v1",
            "revision": 1,
            "owner_analytics_available": False,
            "latest_retrieval_timestamp": "2026-11-12T09:00:00+00:00",
            "snapshot_history": [{"checkpoint": "48h", "observation_period": "2026-11-12", "owner_analytics_available": False, "metrics": {"views": 510, "watch_time_minutes": None}}],
            "latest_metrics": {"views": 510, "watch_time_minutes": None},
        }
    }
    gm, _ = merge_growth_records(g_owner, g_stale_pub)
    assert gm["v1"]["owner_analytics_available"] is True
    assert gm["v1"]["snapshot_history"][0]["metrics"]["watch_time_minutes"] == 180.0

    sm = merge_schedule_states(
        {"revision": 2, "last_short_pub_2026-11-12_9": True, "history_runs": [{"type": "short", "url": "https://youtube.com/watch?v=1", "date_ist": "2026-11-12T09:00:00"}]},
        {"revision": 1, "last_short_pub_2026-11-12_12": True, "history_runs": [{"type": "short", "url": "https://youtube.com/watch?v=2", "date_ist": "2026-11-12T12:00:00"}]},
    )
    assert sm["last_short_pub_2026-11-12_9"] is True
    assert sm["last_short_pub_2026-11-12_12"] is True
    assert len(sm["history_runs"]) == 2


def test_sqlite_wal_durability_backup_and_checksum_restore(tmp_path):
    import uploader.safety as safety_mod
    out_dir = tmp_path / "state_out"
    out_dir.mkdir(parents=True)
    config.OUTPUT_DIR = str(out_dir)
    safety_mod.PRODUCTION_DB_FILE = str(out_dir / "production_database.json")

    record_production_state("output/b1.mp4", PublishingState.VIDEO_RENDERED.value, metadata={"type": "short"})
    gdb = HistoricalPerformanceDB(db_path=str(out_dir / "historical_performance_db.json"))
    gdb.record_snapshot("yt_b1", "short", "Maurya Mystery", "Indian Kings", "2026-11-10T09:00:00Z", 45.0, "Maurya Mystery", views=900)
    (out_dir / "pending_uploads").mkdir()
    (out_dir / "pending_uploads" / "upload_abc_final_short.mp4.json").write_text('{"status":"pending_quota_reset"}', encoding="utf-8")

    sync_res = sync_to_sqlite(base_dir=str(out_dir))
    assert "production_database.json" in sync_res["authoritative_stores"]
    assert (out_dir / "yaas_state.sqlite").exists()

    backup = create_state_backup(base_dir=str(out_dir), label="ci_pre")
    assert "production_database.json" in backup["checksums"]
    assert "pending_uploads/upload_abc_final_short.mp4.json" in backup["checksums"]

    # Corrupt JSON -> restore from SQLite WAL ledger
    (out_dir / "production_database.json").write_text("{CORRUPT_JSON", encoding="utf-8")
    sqlite_rec = restore_from_sqlite(base_dir=str(out_dir), store_names=["production_database.json"])
    assert "production_database.json" in sqlite_rec["restored"]
    assert os.path.normpath("output/b1.mp4") in load_production_db()

    # Delete JSON -> restore from checksummed backup
    (out_dir / "production_database.json").unlink()
    b_rec = restore_state_backup(backup["backup_dir"], base_dir=str(out_dir))
    assert "production_database.json" in b_rec["restored"]

    # Tampered backup file triggers checksum verification failure
    with open(os.path.join(backup["backup_dir"], "production_database.json"), "a", encoding="utf-8") as f:
        f.write(" ")
    with pytest.raises(ValueError, match="Checksum verification failed"):
        restore_state_backup(backup["backup_dir"], base_dir=str(out_dir))


def test_cross_process_persistence_and_workflow_restart_recovery(tmp_path):
    out_dir = tmp_path / "mp_persist"
    out_dir.mkdir(parents=True)
    worker_py = tmp_path / "p23_worker.py"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    worker_py.write_text(
        "\n".join([
            "import os, sys",
            f"sys.path.insert(0, {repo_root!r})",
            "import config",
            "import uploader.safety as s",
            "from apis.growth_database import HistoricalPerformanceDB",
            "from apis.state_store import sync_to_sqlite",
            "out_dir, w_idx = sys.argv[1], int(sys.argv[2])",
            "config.OUTPUT_DIR = out_dir",
            "s.PRODUCTION_DB_FILE = os.path.join(out_dir, 'production_database.json')",
            "gdb = HistoricalPerformanceDB(db_path=os.path.join(out_dir, 'historical_performance_db.json'))",
            "for i in range(4):",
            "    s.record_production_state(f'output/p23_{w_idx}_{i}.mp4', s.PublishingState.VIDEO_RENDERED.value, metadata={'type': 'short'})",
            "    gdb.record_snapshot(f'yt_{w_idx}_{i}', 'short', 'Topic', 'Pillar', '2026-11-11T09:00:00Z', 40.0, f'Short {w_idx}-{i}', views=100 + i)",
            "sync_to_sqlite(base_dir=out_dir)",
        ]),
        encoding="utf-8",
    )

    p1 = subprocess.Popen([sys.executable, str(worker_py), str(out_dir), "1"])
    p2 = subprocess.Popen([sys.executable, str(worker_py), str(out_dir), "2"])
    assert p1.wait(timeout=20) == 0
    assert p2.wait(timeout=20) == 0

    health = generate_persistent_state_health_report(base_dir=str(out_dir))
    assert health["stores"]["production_database.json"]["record_count"] == 8
    assert health["stores"]["production_database.json"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert health["stores"]["historical_performance_db.json"]["record_count"] == 8
    assert health["sqlite_ledger"]["exists"] is True


def test_reconciliation_recovers_history_without_fabrication_and_separates_unmatched(tmp_path):
    out_dir = tmp_path / "recon_out"
    out_dir.mkdir(parents=True)
    config.OUTPUT_DIR = str(out_dir)

    import automation
    import uploader.safety as safety_mod
    automation.SCHEDULE_FILE = str(out_dir / "automation_schedule.json")
    safety_mod.PRODUCTION_DB_FILE = str(out_dir / "production_database.json")

    # Local failed job (no youtube_id) + schedule entry missing from growth DB
    record_production_state("output/failed_local.mp4", PublishingState.FAILED.value, metadata={"job_id": "job_f1", "error_type": "RenderingFailure"})
    automation.save_schedule_state({
        "history_runs": [
            {"type": "short", "title": "Ashoka Edict Secret", "url": "https://www.youtube.com/watch?v=vid_sched_1", "date_ist": "2026-11-10T09:00:00+05:30"}
        ]
    })

    svc = MagicMock()
    svc.channels().list.return_value.execute.return_value = {"items": [{"id": config.YOUTUBE_CHANNEL_ID, "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
    svc.playlistItems().list.return_value.execute.return_value = {"items": [{"contentDetails": {"videoId": "vid_sched_1"}}, {"contentDetails": {"videoId": "vid_ext_2"}}]}
    svc.videos().list.return_value.execute.return_value = {
        "items": [
            {"id": "vid_sched_1", "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Ashoka Edict Secret", "publishedAt": "2026-11-10T03:30:00Z"}, "status": {"privacyStatus": "public"}, "contentDetails": {"duration": "PT48S"}, "statistics": {"viewCount": "320"}},
            {"id": "vid_ext_2", "snippet": {"channelId": config.YOUTUBE_CHANNEL_ID, "title": "Untracked External Short", "publishedAt": "2026-11-11T03:30:00Z"}, "status": {"privacyStatus": "public"}, "contentDetails": {"duration": "PT52S"}, "statistics": {"viewCount": "180"}},
        ]
    }

    rep1 = reconcile_channel_publications(output_dir=str(out_dir), youtube_service=svc)
    assert rep1["recovered_historical_count"] == 1
    assert rep1["untracked_on_channel_count"] == 1
    assert rep1["local_failed_jobs_without_youtube_id_count"] == 1
    assert rep1["reconciliation_coverage_pct"] == 50.0
    assert os.path.exists(str(out_dir / "youtube_reconciliation_report.json"))
    assert os.path.exists(str(out_dir / "reconciliation_history.json"))

    # Recovered historical record preserves None for private analytics (no fabrication!)
    gdb = HistoricalPerformanceDB(db_path=str(out_dir / "historical_performance_db.json"))
    rec = gdb.get_video("vid_sched_1")
    assert rec is not None
    assert rec["latest_metrics"]["views"] == 320
    assert rec["latest_metrics"]["watch_time_minutes"] is None
    assert rec["owner_analytics_available"] is False

    # Re-running reconciliation does not duplicate recovery
    rep2 = reconcile_channel_publications(output_dir=str(out_dir), youtube_service=svc)
    assert rep2["recovered_historical_count"] == 0
    assert len(json.loads((out_dir / "reconciliation_history.json").read_text(encoding="utf-8"))) == 2


def test_rolling_30day_reports_separate_shorts_longform_and_unavailable_metrics(tmp_path, monkeypatch):
    import apis.youtube_analytics as ya
    import apis.growth_database as gdb_mod
    import agents.growth_analyst as ga_mod

    monkeypatch.setattr(
        ya,
        "get_analytics_capabilities_and_limitations",
        lambda: {
            "owner_analytics_connected": False,
            "has_public_data_api_fallback": True,
            "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"],
            "limitations": ["Owner Analytics v2 missing yt-analytics.readonly"],
        },
    )

    gdb = HistoricalPerformanceDB(db_path=str(tmp_path / "growth_p23.json"))
    now_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    gdb.record_snapshot("sh_p23", "short", "Indus Plumbing", "Engineering", now_iso, 45.0, "Indus Plumbing #Shorts", views=1500, watch_time_minutes=None, average_percentage_viewed=None, subscribers_gained=None, hook_style="question_paradox", owner_analytics_available=False)
    gdb.record_snapshot("lf_p23", "longform", "Chola Navy", "Empires", now_iso, 640.0, "Chola Navy Empire", views=850, watch_time_minutes=None, average_percentage_viewed=None, impressions=None, ctr=None, subscribers_gained=None, owner_analytics_available=False)

    monkeypatch.setattr(gdb_mod, "_db_instance", gdb)
    monkeypatch.setattr(ga_mod, "get_performance_db", lambda: gdb)
    monkeypatch.setattr(ya, "get_performance_db", lambda: gdb)

    # Weekly format report reads HistoricalPerformanceDB & keeps unavailable private metrics as None (not 0.0!)
    fmt_rep = generate_weekly_format_report(days_back=30)
    assert fmt_rep["shorts_analytics"]["total_views"] == 1500
    assert fmt_rep["shorts_analytics"]["total_watch_time_minutes"] is None
    assert fmt_rep["longform_analytics"]["total_impressions"] is None
    assert fmt_rep["data_provenance"]["private_owner_analytics_status"] == "BLOCKED"

    # Prevent live network calls in reconcile inside generate_phase23_reports
    monkeypatch.setattr(config, "YOUTUBE_API_KEY", "")
    reports = generate_phase23_reports(base_dir=str(tmp_path), evaluation_window_days=30, is_mock_or_test_data=True)
    assert len(reports["paths"]) == 6
    for rpath in reports["paths"].values():
        assert os.path.exists(rpath)
    assert reports["rolling_30day_growth"]["data_provenance"]["mode"] == "mock_or_test_data"
    assert "BLOCKED" in reports["rolling_30day_growth"]["data_provenance"]["private_owner_analytics"]
    assert config.LONGFORM_DAILY_COUNT == 1 and config.SHORTS_DAILY_COUNT == 5


def test_experiment_governance_bonferroni_and_cadence_safeguards(tmp_path):
    tracker = ExperimentTracker(storage_path=str(tmp_path / "exp_p23.json"))

    # Multiple variables rejected
    with pytest.raises(ValueError, match="exactly 1 primary variable"):
        tracker.register_controlled_experiment({
            "hypothesis": "Changing hook AND length increases APV on history Shorts.",
            "baseline": "Standard narrative intro",
            "changed_variables": ["hook_variation", "video_duration"],
            "success_metric": "average_percentage_viewed",
        })

    exp = tracker.register_controlled_experiment({
        "id": "EXP-P23-1",
        "name": "Question Paradox Hook Test",
        "hypothesis": "Visual paradox hook yields higher 30-day average percentage viewed.",
        "baseline": "Narrative timeline opening",
        "primary_variable": "hook_variation",
        "success_metric": "average_percentage_viewed",
        "min_sample_size": 6,
    })
    assert exp["evaluation_window_days"] == 30
    assert exp["auto_apply_to_schedule"] is False

    # Feed 6 inconclusive/small-difference samples -> stays in_progress due to Bonferroni threshold
    for i, val in enumerate([70.0, 71.0, 69.5]):
        tracker.record_experiment_sample("EXP-P23-1", f"c_{i}", "control", val)
    for i, val in enumerate([72.0, 71.5, 70.5]):
        tracker.record_experiment_sample("EXP-P23-1", f"t_{i}", "test", val)

    cur = next(e for e in tracker.get_all_experiments() if e["id"] == "EXP-P23-1")
    assert cur["status"] == "in_progress"
    assert cur["uncertainty_report"]["multiple_comparison_adjusted_alpha"] < 0.05
    assert cur["uncertainty_report"]["bonferroni_significant"] is False
