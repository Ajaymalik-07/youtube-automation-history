"""
Regression tests for Phase 32 — YouTube Audience Growth & Content Optimization.
"""

import json
import subprocess
from datetime import datetime, timezone

import config
from agents.adaptive_engine import get_production_run_brief
from agents.phase32_growth_optimization import (
    ALLOWED_DECISION_CLASSES,
    PHASE32_REPORT_FILES,
    generate_phase32_reports,
    get_phase32_growth_directives,
    score_phase32_topic,
)
from agents.seo_optimizer import (
    audit_title_and_thumbnail_packaging,
    generate_title_candidates,
    validate_youtube_metadata,
)
from uploader.quality_gates import validate_script_gate
from video.thumbnail import generate_thumbnail_concepts


def test_topic_scoring_and_research_credibility():
    scored = score_phase32_topic(
        topic="Rakhigarhi DNA & Harappan Origins",
        domain="Archaeological discoveries",
        measured_channel_score=0.6,
        external_demand_score=0.7,
        editorial_score=0.8,
        research_confidence=0.9,
        suitable_formats=["short", "longform"],
        folklore_separated=True,
    )
    assert scored["composite_score"] == round(0.35 * 0.6 + 0.25 * 0.7 + 0.20 * 0.8 + 0.20 * 0.9, 3)
    assert set(scored["score_components"].keys()) == {
        "measured_channel_performance",
        "external_demand_evidence",
        "editorial_judgment",
        "research_confidence",
    }
    assert scored["folklore_explicitly_separated"] is True


def test_shorts_and_longform_production_directives():
    d_sh = get_phase32_growth_directives("shorts")
    assert d_sh["duration_policy"] == [25, 60]
    assert "first_frame_rule" in d_sh and "opening_rule" in d_sh

    d_lf = get_phase32_growth_directives("longform")
    assert d_lf["runtime_target_minutes"] == [8.0, 14.5]
    assert "distribution_rule" in d_lf


def test_title_thumbnail_quality_checks_and_metadata_validation():
    titles = generate_title_candidates("Submerged Dwarka", language="en")
    thumbs = generate_thumbnail_concepts(titles["curiosity_oriented"], "Submerged Dwarka")
    audit_ok = audit_title_and_thumbnail_packaging(
        titles["curiosity_oriented"], thumbs["curiosity_oriented"], topic="Submerged Dwarka"
    )
    assert audit_ok["approved"] is True
    assert audit_ok["checks"]["ctr_claimed"] is False

    # Repetitive boilerplate prefix must be flagged
    audit_bad = audit_title_and_thumbnail_packaging(
        "The Secret of Submerged Dwarka", {"text": "Too Many Words On This Thumbnail"}, topic="Submerged Dwarka"
    )
    assert audit_bad["approved"] is False
    assert audit_bad["checks"]["avoids_repetitive_template"] is False
    assert audit_bad["checks"]["thumbnail_readable"] is False

    # Metadata gate still enforces description & title limits
    ok_meta, meta_issues = validate_youtube_metadata("Too short", "Brief", [])
    assert ok_meta is False and len(meta_issues) >= 2


def test_end_to_end_phase32_reports_integrity_and_distribution(tmp_path):
    now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    (tmp_path / "post_oauth_live_verification_report.json").write_text(json.dumps({
        "window_30_complete_days_utc": {"startDate": "2026-10-13", "endDate": "2026-11-11"},
        "analytics_api_v2": {"channel_30d_totals": {"views": 486, "estimatedMinutesWatched": 154, "subscribersGained": 2}},
    }), encoding="utf-8")
    (tmp_path / "phase28_individual_video_analytics.json").write_text(json.dumps({
        "evaluation_window": {"start_date": "2026-08-14", "end_date": "2026-11-12"},
        "formats": {
            "short": [{"video_id": "S1", "title": "Why did Dwarka sink?", "duration_seconds": 50.0, "published_at": "2026-11-01T00:00:00Z", "data_availability": "measured_owner_analytics", "metrics": {"views": 100, "estimatedMinutesWatched": 30.0, "averageViewDuration": 25.0, "averageViewPercentage": 50.0, "subscribersGained": 1}}],
            "longform": [{"video_id": "L1", "title": "Ganga River", "duration_seconds": 600.0, "published_at": "2026-10-29T00:00:00Z", "data_availability": "measured_owner_analytics", "metrics": {"views": 37, "estimatedMinutesWatched": 47.0, "averageViewDuration": 100.0, "averageViewPercentage": 16.61, "subscribersGained": 0}}],
            "unknown": [],
        },
    }), encoding="utf-8")
    (tmp_path / "phase28_shorts_performance_report.json").write_text(json.dumps({"traffic_sources": []}), encoding="utf-8")
    (tmp_path / "phase28_longform_performance_report.json").write_text(json.dumps({"traffic_sources": [{"traffic_source": "RELATED_VIDEO", "views": 27}]}), encoding="utf-8")

    res = generate_phase32_reports(output_dir=str(tmp_path), now_utc=now)
    assert res["ok"] is True
    for fname in PHASE32_REPORT_FILES.values():
        assert (tmp_path / fname).exists()

    audit = json.loads((tmp_path / PHASE32_REPORT_FILES["channel_audit_json"]).read_text(encoding="utf-8"))
    assert audit["channel_30d_owner_totals"]["impressions"] is None
    assert audit["channel_30d_owner_totals"]["ctr"] is None
    assert audit["channel_30d_owner_totals"]["returningViewers"] is None
    assert audit["growth_diagnosis"]["empty_rows_never_treated_as_zero"] is True
    assert audit["growth_diagnosis"]["public_stats_substituted"] is False

    pkg = json.loads((tmp_path / PHASE32_REPORT_FILES["packaging_quality"]).read_text(encoding="utf-8"))
    assert pkg["existing_published_titles_modified"] is False
    assert pkg["ctr_available"] is False

    dist = json.loads((tmp_path / PHASE32_REPORT_FILES["distribution_strategy"]).read_text(encoding="utf-8"))
    assert dist["shorts_to_longform_policy"]["standalone_value_required"] is True
    assert dist["shorts_to_longform_policy"]["no_five_near_duplicate_promo_clips"] is True

    dec = json.loads((tmp_path / PHASE32_REPORT_FILES["growth_decision_engine"]).read_text(encoding="utf-8"))
    assert dec["single_viral_outlier_guardrail"] is True
    assert dec["cadence_preserved"]["longform_per_day"] == 1
    assert dec["cadence_preserved"]["shorts_per_day"] == 5
    for d in dec["decisions"]:
        assert d["classification"] in ALLOWED_DECISION_CLASSES
        assert d["requires_quality_gate"] is True


def test_adaptive_engine_quality_gates_cadence_and_branch():
    brief = get_production_run_brief("shorts")
    assert "phase32_growth_directives" in brief

    ok, _ = validate_script_gate({"title": "T", "sections": [{"narration": "short"}], "estimated_duration_seconds": 10}, is_shorts=True)
    assert ok is False

    assert getattr(config, "SHORTS_DAILY_COUNT", 5) == 5
    assert getattr(config, "LONGFORM_DAILY_COUNT", 1) == 1
    branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    assert branch == "feature/youtube-growth-overhaul"

