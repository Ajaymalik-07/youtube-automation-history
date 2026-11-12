import json
from unittest.mock import patch

from agents.experiment_tracker import ExperimentTracker
from agents.growth_analyst import generate_phase25_execution_report
from apis.growth_database import HistoricalPerformanceDB


def test_analytics_readiness_gate_marks_blocked_and_unblocks_on_oauth(tmp_path):
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
        },
        {
            "id": "EXP-002",
            "name": "Title CTR Test",
            "category": "title_approach",
            "target_format": "longform",
            "target_metric": "ctr",
            "status": "in_progress",
            "min_sample_size": 5,
            "samples": [],
        },
    ]
    tracker.save()

    res_blocked = tracker.apply_analytics_readiness_gate(owner_analytics_connected=False, ctr_available=False)
    assert res_blocked["blocked_count"] == 2
    assert set(res_blocked["blocked_experiment_ids"]) == {"EXP-001", "EXP-002"}
    assert all(e["status"] == "BLOCKED" for e in tracker.get_all_experiments())

    res_partial = tracker.apply_analytics_readiness_gate(owner_analytics_connected=True, ctr_available=False)
    assert res_partial["active_experiment_ids"] == ["EXP-001"]
    assert res_partial["blocked_experiment_ids"] == ["EXP-002"]


def test_phase25_execution_report_baseline_and_honesty(tmp_path):
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    db.record_snapshot(
        video_id="S1",
        video_format="short",
        topic="Iron Pillar",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-12T06:30:00Z",
        video_duration=55.0,
        title="Iron Pillar #Shorts",
        views=10,
        owner_analytics_available=False,
    )
    db.record_snapshot(
        video_id="L1",
        video_format="longform",
        topic="Kailash Temple",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-11T13:30:00Z",
        video_duration=520.0,
        title="Kailash Temple Mystery",
        views=25,
        owner_analytics_available=False,
    )
    db.record_snapshot(
        video_id="MOCK_1",
        video_format="longform",
        topic="Mock",
        content_pillar="Test",
        publication_timestamp="2026-11-11T13:30:00Z",
        video_duration=520.0,
        title="Mock",
        views=50000,
        metadata_extras={"is_test_fixture": True},
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
         patch("apis.youtube_analytics.get_analytics_capabilities_and_limitations", return_value={"owner_analytics_connected": False, "limitations": []}), \
         patch("uploader.oauth_manager.audit_token_scopes", return_value={"granted_scopes": ["youtube.upload"], "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"]}):
        rep = generate_phase25_execution_report(output_dir=str(tmp_path), evaluation_window_days=30)

    assert rep["cadence_preserved"]["longform_daily"] == 1
    assert rep["cadence_preserved"]["shorts_daily"] == 5
    assert rep["baseline"]["shorts"]["video_count"] == 1
    assert rep["baseline"]["shorts"]["median_views"] == 10.0
    assert rep["baseline"]["longform"]["video_count"] == 1
    assert rep["baseline"]["longform"]["median_views"] == 25.0
    assert rep["baseline"]["shorts"]["average_percentage_viewed"] is None
    assert rep["baseline"]["longform"]["impressions"] is None
    assert rep["thirty_day_findings"]["statistically_supported_findings"] == []
    assert rep["experiment_register"][0]["status"] == "BLOCKED"
    assert json.loads(open(rep["report_path"], encoding="utf-8").read())

