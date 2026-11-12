"""
Regression tests for Phase 30 — Controlled Content Experiments & Performance Validation.
"""

import json
import subprocess
from datetime import datetime, timezone

import pytest

import config
from agents.adaptive_engine import get_production_run_brief
from agents.phase30_experiments import (
    ALLOWED_RESULT_CLASSIFICATIONS,
    PHASE30_REPORT_FILES,
    ExperimentRegistry,
    assign_shorts_duration_cohort,
    audit_phase29_directive_compliance,
    build_analytics_reconciliation,
    build_shorts_duration_experiment,
    generate_phase30_reports,
    probe_encoded_duration_ffprobe,
)
from uploader.quality_gates import validate_script_gate


def test_experiment_registration_and_unique_ids(tmp_path):
    reg = ExperimentRegistry(str(tmp_path / "reg.json"))
    reg.register({"experiment_id": "EXP-1", "format": "short", "result_classification": "RUNNING"})
    with pytest.raises(ValueError, match="Duplicate experiment_id"):
        reg.register({"experiment_id": "EXP-1", "format": "short", "result_classification": "RUNNING"})
    with pytest.raises(ValueError, match="Invalid result_classification"):
        reg.register({"experiment_id": "EXP-2", "format": "short", "result_classification": "BOGUS"})


def test_cohort_assignment_and_invalid_duration_exclusion():
    assert assign_shorts_duration_cohort(38.0) == ("cohort_a_31_45s", None)
    assert assign_shorts_duration_cohort(54.0) == ("cohort_b_46_60s", None)
    assert assign_shorts_duration_cohort(28.0) == ("valid_production_25_30s_excluded_from_experiment", None)
    assert assign_shorts_duration_cohort(20.0)[0] == "excluded_invalid"
    assert assign_shorts_duration_cohort(67.0)[0] == "excluded_invalid"
    assert assign_shorts_duration_cohort(None)[0] == "excluded_invalid"


def test_no_premature_winner_and_minimum_sample_enforcement():
    # Even with huge difference, 1 video per arm must never be VALIDATED
    assert ExperimentRegistry.classify_result([10.0], [90.0], min_per_arm=10) == "INSUFFICIENT_DATA"
    # Missing analytics (None) are excluded, never treated as 0
    assert ExperimentRegistry.classify_result([None, None, None, None, None], [50.0, 60.0], min_per_arm=10) == "INSUFFICIENT_DATA"
    # 5 per arm with >=15% lift -> PROMISING (not VALIDATED until min_per_arm=10)
    assert ExperimentRegistry.classify_result([20.0] * 5, [30.0] * 5, min_per_arm=10) == "PROMISING"
    # 10 per arm with >=15% lift -> VALIDATED
    assert ExperimentRegistry.classify_result([20.0] * 10, [30.0] * 10, min_per_arm=10) == "VALIDATED"
    # 10 per arm with <=-15% drop -> REJECTED
    assert ExperimentRegistry.classify_result([30.0] * 10, [20.0] * 10, min_per_arm=10) == "REJECTED"


def test_duration_experiment_delays_and_missing_analytics():
    ind = {
        "formats": {
            "short": [
                {"video_id": "S_A1", "title": "Short A1", "duration_seconds": 36.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 40, "estimatedMinutesWatched": 10.0, "averageViewDuration": 25.0, "averageViewPercentage": 69.0, "subscribersGained": 0}},
                {"video_id": "S_DEL", "title": "Short Delayed", "duration_seconds": 50.0, "data_availability": "reporting_delay_pending", "metrics": {"views": None}},
                {"video_id": "S_OVER", "title": "Short Over 60", "duration_seconds": 67.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 146}},
            ]
        }
    }
    payload, _ = build_shorts_duration_experiment(ind)
    assert payload["winner_declared"] is False
    assert payload["result_classification"] == "INSUFFICIENT_DATA"
    assert payload["cohort_b_46_60s"]["videos"][0]["analytics_status"] == "REPORTING_DELAY"
    assert payload["excluded_out_of_policy_count"] == 1


def test_analytics_reconciliation_preserves_both_totals(tmp_path):
    (tmp_path / "post_oauth_live_verification_report.json").write_text(json.dumps({
        "window_30_complete_days_utc": {"startDate": "2026-10-13", "endDate": "2026-11-11"},
        "format_separated_performance_30d": {"by_creator_content_type": {"shorts": {"views": 446, "estimatedMinutesWatched": 105}}},
    }), encoding="utf-8")
    (tmp_path / "phase28_individual_video_analytics.json").write_text(json.dumps({
        "evaluation_window": {"start_date": "2026-08-14", "end_date": "2026-11-12"},
        "formats": {"short": [
            {"video_id": "V1", "data_availability": "measured_owner_analytics", "metrics": {"views": 10, "estimatedMinutesWatched": 0.0, "averageViewDuration": 20.0}}
        ]},
    }), encoding="utf-8")
    (tmp_path / "phase28_shorts_performance_report.json").write_text(json.dumps({
        "totals": {"views": 446, "estimatedMinutesWatched": 95.0},
    }), encoding="utf-8")

    rec, _ = build_analytics_reconciliation(str(tmp_path))
    assert rec["discrepancy_analysis"]["views_difference"] == 0
    assert rec["discrepancy_analysis"]["watch_minutes_difference"] == 10.0
    assert rec["discrepancy_analysis"]["totals_forced_to_match"] is False


def test_directive_compliance_and_end_to_end_deliverables(tmp_path):
    comp = audit_phase29_directive_compliance()
    assert comp["all_checks_passed"] is True

    (tmp_path / "phase28_individual_video_analytics.json").write_text(json.dumps({
        "evaluation_window": {"start_date": "2026-08-14", "end_date": "2026-11-12"},
        "formats": {
            "short": [
                {"video_id": "S1", "title": "Why did Dwarka sink? #shorts", "duration_seconds": 52.0, "published_at": "2026-11-01T00:00:00Z", "data_availability": "measured_owner_analytics", "metrics": {"views": 50, "estimatedMinutesWatched": 12.0, "averageViewDuration": 25.0, "averageViewPercentage": 48.0, "subscribersGained": 1}},
            ],
            "longform": [
                {"video_id": "L1", "title": "Ganga River", "duration_seconds": 606.0, "published_at": "2026-10-29T00:00:00Z", "data_availability": "measured_owner_analytics", "metrics": {"views": 37, "estimatedMinutesWatched": 47.0, "averageViewDuration": 100.0, "averageViewPercentage": 16.61, "subscribersGained": 0}},
            ],
            "unknown": [],
        },
    }), encoding="utf-8")

    res = generate_phase30_reports(output_dir=str(tmp_path), now_utc=datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc))
    assert res["ok"] is True
    for fname in PHASE30_REPORT_FILES.values():
        assert (tmp_path / fname).exists()

    hook_rep = json.loads((tmp_path / PHASE30_REPORT_FILES["hook_experiment"]).read_text(encoding="utf-8"))
    assert hook_rep["videos"][0]["checkpoints"]["first_5s_retention"] is None
    assert hook_rep["videos"][0]["checkpoints"]["swipe_away_rate"] is None

    lf_val = json.loads((tmp_path / PHASE30_REPORT_FILES["longform_validation"]).read_text(encoding="utf-8"))
    assert lf_val["sample_size_sufficient"] is False
    assert lf_val["impressions_and_ctr_available"] is False

    recs = json.loads((tmp_path / PHASE30_REPORT_FILES["growth_recommendations"]).read_text(encoding="utf-8"))
    assert recs["cadence_preserved"]["longform_per_day"] == 1
    assert recs["cadence_preserved"]["shorts_per_day"] == 5
    for r in recs["recommendations"]:
        assert r["experiment_id"]
        assert r["requires_quality_gate"] is True
        assert r["result_classification"] in ALLOWED_RESULT_CLASSIFICATIONS


def test_adaptive_engine_quality_gates_cadence_and_branch():
    brief = get_production_run_brief("shorts")
    assert "phase30_experiment_guidance" in brief
    assert probe_encoded_duration_ffprobe("nonexistent_file.mp4") is None

    ok, _ = validate_script_gate({"title": "T", "sections": [{"narration": "short"}], "estimated_duration_seconds": 10}, is_shorts=True)
    assert ok is False

    assert getattr(config, "SHORTS_DAILY_COUNT", 5) == 5
    assert getattr(config, "LONGFORM_DAILY_COUNT", 1) == 1
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    assert branch == "feature/youtube-growth-overhaul"

