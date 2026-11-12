"""
Regression tests for Phase 29 — Content Intelligence & Storytelling Optimization.
"""

import json
import subprocess
from datetime import datetime, timezone

import config
from agents.adaptive_engine import get_production_run_brief
from agents.phase29_content_intelligence import (
    PHASE29_REPORT_FILES,
    build_duration_experiment_report,
    classify_historical_claim,
    classify_missing_analytics_status,
    enforce_topic_diversity,
    generate_phase29_reports,
    get_phase29_production_directives,
)
from uploader.quality_gates import validate_script_gate


def test_missing_analytics_and_zero_vs_empty_distinction():
    assert classify_missing_analytics_status({
        "data_availability": "measured_owner_analytics",
        "metrics": {"views": 0},
    }) == "CONFIRMED_ZERO"

    assert classify_missing_analytics_status({
        "data_availability": "empty_result_no_recorded_activity",
        "api_request_status": "ok_empty_rows",
        "metrics": {"views": None},
    }) == "NO_ROWS_RETURNED"

    assert classify_missing_analytics_status({
        "data_availability": "reporting_delay_pending",
        "metrics": {"views": None},
    }) == "REPORTING_DELAY"

    assert classify_missing_analytics_status({
        "data_availability": "api_error",
        "api_request_status": "api_error",
        "metrics": {"views": None},
    }) == "API_ERROR"

    assert classify_missing_analytics_status({
        "data_availability": "not_published_yet",
        "api_request_status": "skipped_unpublished",
        "metrics": {"views": None},
    }) == "SCHEDULED_OR_PRIVATE"

    assert classify_missing_analytics_status({
        "data_availability": "unexpected_state",
        "metrics": {"views": 5},
    }) == "INSUFFICIENT_EVIDENCE"


def test_historical_evidence_classification_and_topic_diversity():
    assert classify_historical_claim("Excavation radiocarbon dated layer to 1500 BCE") == "verified_historical_facts"
    assert classify_historical_claim("Local folklore describes a haunted curse") == "legends_and_folklore"
    assert classify_historical_claim("Scholars debate this disputed claim") == "disputed_claims"
    assert classify_historical_claim("Cinematic reconstruction of the court") == "creative_storytelling"

    candidates = [
        {"topic": "A1", "domain": "Lost cities"},
        {"topic": "A2", "domain": "Lost cities"},
        {"topic": "A3", "domain": "Lost cities"},
        {"topic": "B1", "domain": "Ancient civilizations"},
        {"topic": "C1", "domain": "Forgotten rulers"},
    ]
    div = enforce_topic_diversity(candidates, max_share=0.30)
    assert div["diversity_ok"] is False
    assert "Lost cities" in div["capped_topics"]
    assert div["domain_counts"]["Lost cities"] == 1


def test_duration_experiment_cohorts_and_no_premature_winner():
    ind = {
        "formats": {
            "short": [
                {"video_id": "S1", "duration_seconds": 38.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 20, "averageViewPercentage": 40.0}},
                {"video_id": "S2", "duration_seconds": 52.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 25, "averageViewPercentage": 45.0}},
                {"video_id": "S_OVER", "duration_seconds": 67.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 146, "averageViewPercentage": 39.68}},
            ]
        }
    }
    rep = build_duration_experiment_report(ind)
    assert rep["validation_policy_preserved"] == {"min_seconds": 25, "max_seconds": 60}
    assert rep["cohorts"]["31_to_45_seconds"]["measured_nonzero_count"] == 1
    assert rep["cohorts"]["46_to_60_seconds"]["measured_nonzero_count"] == 1
    assert rep["excluded_outside_25_60s_policy_count"] == 1
    assert rep["winner_declared"] is False


def test_production_directives_and_quality_gates_preserved():
    d_short = get_phase29_production_directives("shorts")
    assert "hook_directive" in d_short and "first_frame_directive" in d_short
    assert d_short["duration_policy_seconds"] == [25, 60]

    d_long = get_phase29_production_directives("longform")
    assert "30 seconds" in d_long["hook_directive"]

    brief = get_production_run_brief("shorts")
    assert "phase29_directives" in brief

    # Existing quality gate must still reject out-of-policy Shorts duration
    ok, issues = validate_script_gate({"title": "Test", "sections": [{"narration": "Too short"}], "estimated_duration_seconds": 10}, is_shorts=True)
    assert ok is False and len(issues) > 0


def test_generate_phase29_reports_end_to_end(tmp_path):
    now = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)
    (tmp_path / "phase28_video_inventory.json").write_text(json.dumps({
        "total_videos": 3,
        "videos": [{"video_id": "V1"}, {"video_id": "V2"}, {"video_id": "V3"}],
    }), encoding="utf-8")
    (tmp_path / "phase28_individual_video_analytics.json").write_text(json.dumps({
        "evaluation_window": {"start_date": "2026-08-14", "end_date": "2026-11-12"},
        "latest_populated_channel_day": "2026-11-09",
        "formats": {
            "short": [
                {"video_id": "V1", "title": "The Secret of Lost City Dwarka", "format": "short", "duration_seconds": 40.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 100, "estimatedMinutesWatched": 25.0, "averageViewDuration": 25.0, "averageViewPercentage": 62.5, "subscribersGained": 1}},
                {"video_id": "V2", "title": "Zero Row Video", "format": "short", "duration_seconds": 42.0, "data_availability": "measured_owner_analytics", "metrics": {"views": 0, "estimatedMinutesWatched": 0.0, "averageViewDuration": 0.0, "averageViewPercentage": 0.0, "subscribersGained": 0}},
            ],
            "longform": [
                {"video_id": "V3", "title": "Ganga River", "format": "longform", "duration_seconds": 600.0, "data_availability": "empty_result_no_recorded_activity", "metrics": {"views": None}},
            ],
            "unknown": [],
        },
    }), encoding="utf-8")

    res = generate_phase29_reports(output_dir=str(tmp_path), now_utc=now)
    assert res["ok"] is True
    assert res["classification_counts"]["CONFIRMED_ZERO"] == 1
    assert res["classification_counts"]["NO_ROWS_RETURNED"] == 1
    assert res["classification_counts"]["MEASURED_NONZERO"] == 1
    for fname in PHASE29_REPORT_FILES.values():
        assert (tmp_path / fname).exists()

    recs = json.loads((tmp_path / PHASE29_REPORT_FILES["content_recommendations"]).read_text(encoding="utf-8"))
    assert recs["cadence_preserved"]["longform_per_day"] == 1
    assert recs["cadence_preserved"]["shorts_per_day"] == 5
    for r in recs["recommendations"]:
        assert r["video_ids"]
        assert r["evidence"]
        assert r["requires_quality_gate"] is True


def test_cadence_and_branch_integrity():
    assert getattr(config, "SHORTS_DAILY_COUNT", 5) == 5
    assert getattr(config, "LONGFORM_DAILY_COUNT", 1) == 1
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    assert branch == "feature/youtube-growth-overhaul"

