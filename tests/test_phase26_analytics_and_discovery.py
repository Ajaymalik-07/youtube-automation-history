import json
from unittest.mock import patch

from agents.experiment_tracker import ExperimentTracker
from agents.growth_analyst import audit_published_content_sample, generate_phase26_reports
from apis.growth_database import HistoricalPerformanceDB
from apis.youtube_analytics import get_api_capability_matrix


def test_api_capability_matrix_honest_permissions():
    with patch(
        "apis.youtube_analytics.get_analytics_capabilities_and_limitations",
        return_value={
            "has_public_data_api_fallback": True,
            "has_youtube_readonly_scope": False,
            "has_analytics_scope": False,
            "owner_analytics_connected": False,
        },
    ):
        matrix = get_api_capability_matrix()

    by_name = {m["metric"]: m for m in matrix["metrics"]}
    assert matrix["owner_analytics_connected"] is False
    assert by_name["views"]["currently_authorized"] is True
    assert by_name["watch_time_minutes"]["currently_authorized"] is False
    assert by_name["impressions_and_ctr"]["available_video_level"] is False
    assert by_name["shorts_viewed_vs_swiped_and_retention_curves"]["available_channel_level"] is False
    assert by_name["returning_viewers"]["available_video_level"] is False


def test_actual_content_audit_detects_duration_and_duplicate_prefix(tmp_path):
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    db.record_snapshot(
        video_id="SHORT_OVER_60",
        video_format="short",
        topic="Iron Pillar",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-12T06:30:00Z",
        video_duration=64.0,
        title="This 1600YearOld Iron: Why Has This 1,600-Year-Old Iron Pillar Never Rusted? #Shorts",
        views=0,
        owner_analytics_available=False,
    )
    db.record_snapshot(
        video_id="LF_TOO_SHORT",
        video_format="longform",
        topic="Chola Navy",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-11T13:30:00Z",
        video_duration=73.0,
        title="Indias Chola Navy: How India's Chola Navy Conquered 8 Countries",
        views=2,
        owner_analytics_available=False,
    )

    audit = audit_published_content_sample(output_dir=str(tmp_path), db_override=db)
    assert audit["shorts_sample_count"] == 1
    assert audit["longform_sample_count"] == 1
    s_findings = " | ".join(audit["shorts_audit"][0]["audit_findings"])
    l_findings = " | ".join(audit["longform_audit"][0]["audit_findings"])
    assert "exceeds 60s" in s_findings
    assert "duplicated hook prefix" in s_findings
    assert "under 3 minutes" in l_findings


def test_generate_phase26_reports_separates_demand_and_editorial_judgment(tmp_path):
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    db.record_snapshot(
        video_id="S1",
        video_format="short",
        topic="Iron Pillar",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-12T06:30:00Z",
        video_duration=55.0,
        title="Why Has This 1,600-Year-Old Iron Pillar Never Rusted? #Shorts",
        views=12,
        owner_analytics_available=False,
    )
    tracker = ExperimentTracker()
    tracker.experiments = [
        {
            "id": "EXP-001",
            "name": "Hook Test",
            "category": "hook_variation",
            "target_format": "short",
            "target_metric": "average_percentage_viewed",
            "status": "in_progress",
            "min_sample_size": 5,
            "samples": [],
        }
    ]
    tracker.save()

    with patch("agents.growth_analyst.get_performance_db", return_value=db), \
         patch("agents.experiment_tracker.get_experiment_tracker", return_value=tracker), \
         patch("apis.youtube_analytics.get_analytics_capabilities_and_limitations", return_value={"has_public_data_api_fallback": True, "has_youtube_readonly_scope": False, "has_analytics_scope": False, "owner_analytics_connected": False, "limitations": []}), \
         patch("uploader.oauth_manager.audit_token_scopes", return_value={"is_fully_authorized": False, "granted_scopes": ["youtube.upload"], "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"]}):
        rep = generate_phase26_reports(output_dir=str(tmp_path), evaluation_window_days=30)

    assert rep["oauth_analytics_activation"]["status"] == "BLOCKED"
    assert "measured_demand" in rep["audience_discovery"]
    assert "editorial_judgment" in rep["audience_discovery"]
    assert rep["experiment_readiness"]["experiments"][0]["status"] == "BLOCKED"
    for p in rep["paths"].values():
        assert json.loads(open(p, encoding="utf-8").read())

