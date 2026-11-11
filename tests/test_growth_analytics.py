"""
Unit Tests for YouTube Analytics API Integration & Growth Analysis Engine (Phases 10 & 11)
Verifies performance checkpoint persistence, graceful fallbacks, and growth report generation.
"""
import pytest
from apis.youtube_analytics import (
    record_performance_checkpoint,
    load_snapshots,
    get_video_analytics,
)
from agents.growth_analyst import (
    analyze_channel_growth_and_performance,
    generate_weekly_growth_report,
)


def test_record_performance_checkpoint(tmp_path, monkeypatch):
    test_snap_file = str(tmp_path / "test_snapshots.json")
    monkeypatch.setattr("apis.youtube_analytics.SNAPSHOT_FILE", test_snap_file)

    vid = "test_vid_123"
    metrics_24h = {"views": 1500, "estimatedMinutesWatched": 4500, "averageViewDuration": 180}
    
    res = record_performance_checkpoint(vid, "24h", metrics_24h)
    assert res["video_id"] == vid
    assert "24h" in res["checkpoints"]
    assert res["checkpoints"]["24h"]["metrics"]["views"] == 1500

    metrics_48h = {"views": 3200, "estimatedMinutesWatched": 9800, "averageViewDuration": 184}
    res_48 = record_performance_checkpoint(vid, "48h", metrics_48h)
    assert "24h" in res_48["checkpoints"]
    assert "48h" in res_48["checkpoints"]
    assert res_48["checkpoints"]["48h"]["metrics"]["views"] == 3200


def test_analytics_fallback_when_unauthenticated():
    res = get_video_analytics("sample_nonexistent_id")
    assert "ok" in res
    assert "video_id" in res
    assert res["source"] in ("youtube_data_api_fallback", "none", "youtube_analytics_api")


def test_growth_analyst_cluster_grouping():
    sample_runs = [
        {"type": "longform", "title": "The Rise of Chandragupta Maurya and Chanakya", "score": 90},
        {"type": "longform", "title": "Rajendra Chola Naval Empire in Southeast Asia", "score": 92},
        {"type": "longform", "title": "The Battle of Haldighati: Maharana Pratap", "score": 88},
        {"type": "short", "title": "Why Delhi Iron Pillar Never Rusts", "score": 95},
    ]

    report = analyze_channel_growth_and_performance(sample_runs, snapshots={})
    assert report["total_videos_analyzed"] == 4
    assert report["longform_count"] == 3
    assert report["shorts_count"] == 1
    assert "Kings, Queens & Empires" in report["cluster_distribution"]
    assert "Battles & Military Strategy" in report["cluster_distribution"]
    assert len(report["evidence_based_recommendations"]) >= 2
    assert "human approval" in report["governance_rule"]
