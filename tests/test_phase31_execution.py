"""
Regression tests for Phase 31 — Evidence Accumulation & Experiment Execution.
"""

import json
import subprocess
from datetime import datetime, timezone

import config
from agents.adaptive_engine import get_production_run_brief
from agents.phase31_execution import (
    EXPECTED_EXPERIMENT_IDS,
    PHASE31_REPORT_FILES,
    build_directive_effectiveness_report,
    collect_idempotent_checkpoints,
    generate_phase31_reports,
    load_existing_experiment_registry,
    map_decisions_to_adaptive_guidance,
)
from uploader.quality_gates import validate_script_gate


def test_experiment_continuity_and_stable_ids(tmp_path):
    (tmp_path / "phase30_experiment_registry.json").write_text(json.dumps({
        "experiments": [{"experiment_id": eid} for eid in EXPECTED_EXPERIMENT_IDS]
    }), encoding="utf-8")
    cont = load_existing_experiment_registry(str(tmp_path))
    assert cont["loaded_from_phase30"] is True
    assert cont["stable_ids_verified"] is True
    assert set(cont["experiments"].keys()) == set(EXPECTED_EXPERIMENT_IDS)


def test_idempotent_checkpoint_collection_and_no_duplicates():
    now = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)
    ind = {
        "evaluation_window": {"start_date": "2026-08-14", "end_date": "2026-11-12"},
        "formats": {
            "short": [
                {
                    "video_id": "S_MEAS",
                    "publication_age_days": 10.0,
                    "data_availability": "measured_owner_analytics",
                    "metrics": {"views": 50, "estimatedMinutesWatched": 12.0, "averageViewDuration": 24.0, "averageViewPercentage": 48.0, "subscribersGained": 1},
                },
                {
                    "video_id": "S_DEL",
                    "publication_age_days": 1.5,
                    "data_availability": "reporting_delay_pending",
                    "metrics": {"views": None},
                },
            ],
            "longform": [],
        },
    }
    first = collect_idempotent_checkpoints(ind, None, now)
    assert first["total_snapshots"] == 16  # 2 shorts * 2 exps * 4 checkpoints
    assert first["new_snapshots_added"] == 16

    # Re-run must be strictly idempotent with 0 duplicates
    second = collect_idempotent_checkpoints(ind, first, now)
    assert second["total_snapshots"] == 16
    assert second["new_snapshots_added"] == 0
    assert second["preserved_existing_snapshots"] == 16

    # Verify reporting-delay and pending-age states preserve None
    del_24h = next(s for s in second["snapshots"] if s["video_id"] == "S_DEL" and s["checkpoint_target"] == "24h")
    assert del_24h["checkpoint_state"] == "reporting_delay_pending"
    assert del_24h["metrics"]["views"] is None

    del_72h = next(s for s in second["snapshots"] if s["video_id"] == "S_DEL" and s["checkpoint_target"] == "72h")
    assert del_72h["checkpoint_state"] == "pending_target_age"
    assert del_72h["metrics"]["views"] is None


def test_adaptive_guidance_classification_mapping():
    decisions = {
        "decisions": [
            {"experiment_id": "E1", "format": "short", "classification": "VALIDATED", "supporting_video_ids": ["V1"], "sample_sizes": {}, "limitations": "none"},
            {"experiment_id": "E2", "format": "short", "classification": "PRELIMINARY", "supporting_video_ids": ["V2"], "sample_sizes": {}, "limitations": "small n"},
            {"experiment_id": "E3", "format": "short", "classification": "INSUFFICIENT_DATA", "supporting_video_ids": [], "sample_sizes": {}, "limitations": "n=0"},
            {"experiment_id": "E4", "format": "longform", "classification": "REJECTED", "supporting_video_ids": ["V3"], "sample_sizes": {}, "limitations": "drop"},
            {"experiment_id": "E5", "format": "longform", "classification": "NO_CLEAR_DIFFERENCE", "supporting_video_ids": ["V4"], "sample_sizes": {}, "limitations": "flat"},
        ]
    }
    mapped = map_decisions_to_adaptive_guidance(decisions)
    actions = {g["experiment_id"]: g["adaptive_action"] for g in mapped["guidance"]}
    assert actions["E1"] == "production_directive"
    assert actions["E2"] == "suggestion_only"
    assert actions["E3"] == "uncertainty_hold"
    assert actions["E4"] == "exclude_from_best_practices"
    assert actions["E5"] == "no_preference"


def test_end_to_end_phase31_reports_and_directive_tracking(tmp_path):
    now = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)
    (tmp_path / "phase30_experiment_registry.json").write_text(json.dumps({
        "experiments": [{"experiment_id": eid} for eid in EXPECTED_EXPERIMENT_IDS]
    }), encoding="utf-8")
    (tmp_path / "phase28_individual_video_analytics.json").write_text(json.dumps({
        "evaluation_window": {"start_date": "2026-08-14", "end_date": "2026-11-12"},
        "formats": {
            "short": [
                {"video_id": "S1", "title": "Why did Dwarka sink? #shorts", "duration_seconds": 50.0, "publication_age_days": 10.0, "published_at": "2026-11-01T00:00:00Z", "data_availability": "measured_owner_analytics", "metrics": {"views": 40, "estimatedMinutesWatched": 10.0, "averageViewDuration": 25.0, "averageViewPercentage": 50.0, "subscribersGained": 1}},
            ],
            "longform": [
                {"video_id": "L1", "title": "Ganga River", "duration_seconds": 600.0, "publication_age_days": 14.0, "published_at": "2026-10-29T00:00:00Z", "data_availability": "measured_owner_analytics", "metrics": {"views": 37, "estimatedMinutesWatched": 47.0, "averageViewDuration": 100.0, "averageViewPercentage": 16.61, "subscribersGained": 0}},
            ],
            "unknown": [],
        },
    }), encoding="utf-8")

    res = generate_phase31_reports(output_dir=str(tmp_path), now_utc=now)
    assert res["ok"] is True
    for fname in PHASE31_REPORT_FILES.values():
        assert (tmp_path / fname).exists()

    dur = json.loads((tmp_path / PHASE31_REPORT_FILES["shorts_duration_progress"]).read_text(encoding="utf-8"))
    assert dur["winner_declared"] is False
    assert dur["result_classification"] == "INSUFFICIENT_DATA"

    hook = json.loads((tmp_path / PHASE31_REPORT_FILES["hook_progress"]).read_text(encoding="utf-8"))
    assert hook["videos"][0]["swipe_away_rate"] is None
    assert hook["videos"][0]["first_5s_retention"] is None
    assert hook["videos"][0]["second_by_second_retention"] is None

    lf = json.loads((tmp_path / PHASE31_REPORT_FILES["longform_progress"]).read_text(encoding="utf-8"))
    assert lf["sample_size_sufficient"] is False
    assert lf["winning_opening_declared"] is False

    dir_eff = build_directive_effectiveness_report(str(tmp_path), now)
    assert dir_eff["shorts_pipeline_funnel"]["1_directive_generated"] is True
    assert dir_eff["shorts_pipeline_funnel"]["2_directive_accepted_by_scriptwriter"] is True


def test_adaptive_engine_quality_gates_cadence_and_branch():
    brief = get_production_run_brief("shorts")
    assert "phase31_experiment_guidance" in brief

    ok, _ = validate_script_gate({"title": "T", "sections": [{"narration": "short"}], "estimated_duration_seconds": 10}, is_shorts=True)
    assert ok is False

    assert getattr(config, "SHORTS_DAILY_COUNT", 5) == 5
    assert getattr(config, "LONGFORM_DAILY_COUNT", 1) == 1
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    assert branch == "feature/youtube-growth-overhaul"

