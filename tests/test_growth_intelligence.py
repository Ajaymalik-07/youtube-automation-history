"""
Unit & Integration Tests for Phase 19: YouTube Growth Intelligence Engine
Stories Malik — Analytics-driven production, format separation, and experimentation.

Test scenarios:
1. Historical performance database snapshot integrity and versioning.
2. Independent Shorts performance analysis (8 formats, APV, conversion).
3. Independent Long-form performance analysis (packaging vs storytelling separation).
4. Missing metrics and delayed analytics handling.
5. Small sample sizes and guard against premature winning claims.
6. Retention diagnostics & honest reporting of API limitations.
7. Topic performance intelligence across 10 historical pillars.
8. Title and thumbnail pattern analysis.
9. Automated weekly growth intelligence dossier generation (JSON & Markdown).
10. Controlled growth experiment tracking and sample size threshold verification.
11. Adaptive production brief integration across topic discovery, scriptwriter, SEO, and thumbnail.
12. Security and credential protection (no secret leaks in snapshots or reports).
"""
import os
import json
import pytest
from datetime import datetime, timezone
import config
from apis.growth_database import HistoricalPerformanceDB
from agents.experiment_tracker import ExperimentTracker
from agents.growth_analyst import (
    classify_content_pillar,
    classify_shorts_format,
    analyze_shorts_performance,
    analyze_longform_performance,
    analyze_topic_pillars,
    analyze_title_and_thumbnail,
    generate_growth_intelligence_dossier,
    get_adaptive_production_brief,
    HISTORICAL_PILLARS,
    SHORTS_FORMAT_CLASSES,
)
from agents.topic_discovery import score_topic_opportunity
from agents.seo_optimizer import generate_title_candidates
from video.thumbnail import generate_thumbnail_concepts


@pytest.fixture
def temp_db(tmp_path):
    """Provides an isolated HistoricalPerformanceDB instance."""
    db_file = str(tmp_path / "test_perf_db.json")
    return HistoricalPerformanceDB(db_path=db_file)


@pytest.fixture
def temp_tracker(tmp_path):
    """Provides an isolated ExperimentTracker instance."""
    exp_file = str(tmp_path / "test_growth_experiments.json")
    return ExperimentTracker(storage_path=exp_file)


# 1. Historical Performance Database Snapshot Integrity
def test_performance_db_versioned_snapshot_integrity(temp_db):
    video_id = "test_vid_001"
    
    # First snapshot: 24h
    temp_db.record_snapshot(
        video_id=video_id,
        video_format="longform",
        topic="Dwarka Marine Excavation",
        content_pillar="Lost Cities & Archaeological Discoveries",
        publication_timestamp="2026-11-01T10:00:00Z",
        video_duration=620.0,
        title="Submerged Dwarka Revealed",
        views=150,
        watch_time_minutes=45.0,
        average_view_duration_seconds=220.0,
        average_percentage_viewed=35.5,
        checkpoint="24h",
    )

    rec = temp_db.get_video(video_id)
    assert rec is not None
    assert len(rec["snapshot_history"]) == 1
    assert rec["snapshot_history"][0]["metrics"]["views"] == 150

    # Second snapshot: 48h with delayed/partial data
    temp_db.record_snapshot(
        video_id=video_id,
        video_format="longform",
        topic="Dwarka Marine Excavation",
        content_pillar="Lost Cities & Archaeological Discoveries",
        publication_timestamp="2026-11-01T10:00:00Z",
        video_duration=620.0,
        title="Submerged Dwarka Revealed",
        views=320,
        watch_time_minutes=110.0,
        average_view_duration_seconds=240.0,
        average_percentage_viewed=38.7,
        checkpoint="48h",
    )

    updated = temp_db.get_video(video_id)
    assert len(updated["snapshot_history"]) == 2
    # Ensure initial 24h snapshot is preserved verbatim
    assert updated["snapshot_history"][0]["metrics"]["views"] == 150
    assert updated["snapshot_history"][1]["metrics"]["views"] == 320
    assert updated["latest_metrics"]["views"] == 320


# 2. Shorts Performance Analysis (Independent Format Separation)
def test_shorts_independent_performance_analysis():
    mock_shorts = [
        {
            "video_id": "sh_1",
            "title": "Why Did Delhi's Iron Pillar Never Rust? #Shorts",
            "topic": "Delhi Iron Pillar Metallurgy",
            "video_duration_seconds": 45.0,
            "metadata_extras": {"format": "ancient_engineering"},
            "latest_metrics": {
                "views": 2500,
                "subscribers_gained": 12,
                "average_percentage_viewed": 78.5,
            },
        },
        {
            "video_id": "sh_2",
            "title": "Did Rani Padmini Really Exist? #Shorts",
            "topic": "Rani Padmini Chittorgarh",
            "video_duration_seconds": 52.0,
            "metadata_extras": {"format": "myth_vs_fact"},
            "latest_metrics": {
                "views": 3100,
                "subscribers_gained": 18,
                "average_percentage_viewed": 72.0,
            },
        },
        {
            "video_id": "sh_3",
            "title": "Kailash Temple Top Down Carving Secret #Shorts",
            "topic": "Ellora Kailash Carving",
            "video_duration_seconds": 38.0,
            "metadata_extras": {"format": "ancient_engineering"},
            "latest_metrics": {
                "views": 4200,
                "subscribers_gained": 25,
                "average_percentage_viewed": 81.2,
            },
        },
    ]

    analysis = analyze_shorts_performance(mock_shorts)
    assert analysis["sample_size"] == 3
    assert analysis["total_views"] == 9800
    assert analysis["total_subscribers_gained"] == 55
    assert analysis["sub_conversion_per_1k"] > 5.0  # ~5.61 per 1k views
    assert analysis["observed_avg_apv"] >= 70.0
    assert analysis["target_apv_benchmark"] == 70.0

    eng_fmt = analysis["format_breakdown"].get("ancient_engineering", {})
    assert eng_fmt["count"] == 2
    assert eng_fmt["avg_views"] > 3000


# 3. Long-Form Analysis (Packaging vs Storytelling Separation)
def test_longform_packaging_and_storytelling_separation():
    mock_longform = [
        {
            "video_id": "lf_1",
            "title": "The Maritime Conquests of Rajendra Chola",
            "topic": "Chola Navy Srivijaya",
            "video_duration_seconds": 680.0,
            "latest_metrics": {
                "views": 1200,
                "watch_time_minutes": 380.0,
                "impressions": 15000,
                "ctr": 0.08,  # 8% CTR (Strong)
                "average_view_duration_seconds": 290.0,
                "average_percentage_viewed": 42.6,  # Slightly under 45%
                "subscribers_gained": 35,
            },
            "traffic_sources": [
                {"traffic_source": "YT_SEARCH", "views": 700},
                {"traffic_source": "BROWSE_FEATURES", "views": 500},
            ],
        }
    ]

    analysis = analyze_longform_performance(mock_longform)
    assert analysis["sample_size"] == 1
    pkg = analysis["packaging_diagnostics"]
    story = analysis["storytelling_diagnostics"]

    # Packaging is healthy (8% CTR)
    assert "Healthy CTR" in pkg["evaluation"]
    # Storytelling is flagged because APV 42.6% is under 45.0% benchmark
    assert "Retention bottleneck" in story["evaluation"] or "45.0%" in story["evaluation"]


# 4. Missing Metrics and Delayed Analytics Handling
def test_missing_metrics_and_delayed_analytics():
    # Video just uploaded with zero/null metrics
    delayed_short = [
        {
            "video_id": "new_vid_123",
            "title": "Newly Uploaded Short",
            "topic": "Harappan Sanitation",
            "video_duration_seconds": 40.0,
            "latest_metrics": {
                "views": 0,
                "average_percentage_viewed": 0.0,
                "impressions": 0,
                "ctr": 0.0,
                "subscribers_gained": 0,
            },
        }
    ]

    analysis = analyze_shorts_performance(delayed_short)
    assert analysis["sample_size"] == 1
    assert analysis["total_views"] == 0
    assert analysis["observed_avg_apv"] == 0.0
    # Must not crash, must note limited sample
    assert any("sample size is limited" in obs.lower() for obs in analysis["observations"])


# 5. Small Sample Sizes Guard (No False Winning Hook Declarations)
def test_small_sample_size_guard():
    one_short = [
        {
            "video_id": "single_short",
            "title": "Did Chanakya Really Use Poison Girls?",
            "topic": "Chanakya Visha Kanya",
            "video_duration_seconds": 45.0,
            "latest_metrics": {"views": 100, "average_percentage_viewed": 92.0},
        }
    ]
    analysis = analyze_shorts_performance(one_short)
    # Must NOT declare winning hook based on 1 video
    assert any("withhold definitive hook conclusions until >= 3 samples" in obs.lower() for obs in analysis["observations"])


# 6. Retention Diagnostics & Transparent Reporting of API Limitations
def test_retention_reporting_transparency():
    empty_lf = analyze_longform_performance([])
    assert "observations" in empty_lf
    assert empty_lf["sample_size"] == 0

    lf = analyze_longform_performance([{
        "video_id": "test_retention",
        "title": "Kalinga War Analysis",
        "topic": "Ashoka Kalinga",
        "latest_metrics": {"views": 100, "average_percentage_viewed": 38.0},
    }])
    # Explicitly reports API limitation on second-by-second data
    assert "second-by-second" in lf["storytelling_diagnostics"]["first_30s_retention"]


# 7. Topic Performance Intelligence Across 10 Pillars
def test_topic_pillar_classification_and_intelligence():
    test_videos = [
        {"title": "Harappan Drainage System Excavation", "topic": "Indus Valley", "latest_metrics": {"views": 500, "watch_time_minutes": 100.0, "subscribers_gained": 5}},
        {"title": "The Great Naval Victory of Rajendra Chola", "topic": "Chola Navy", "latest_metrics": {"views": 1200, "watch_time_minutes": 350.0, "subscribers_gained": 20}},
        {"title": "Battle of Panipat 1526 Tactics", "topic": "Panipat Battle", "latest_metrics": {"views": 800, "watch_time_minutes": 200.0, "subscribers_gained": 8}},
    ]

    intel = analyze_topic_pillars(test_videos)
    assert intel["evaluated_pillars_count"] == 10
    assert intel["active_pillars_count"] == 3
    # Ensure remaining 7 pillars are identified as underexplored
    assert len(intel["underexplored_pillars"]) == 7
    assert "Indian Kings, Empires & Dynasties" in intel["high_performing_pillars"]
    assert "Lost Cities & Archaeological Discoveries" in intel["underexplored_pillars"]
    assert "governance_note" in intel


# 8. Title and Thumbnail Pattern Analysis
def test_title_and_thumbnail_analysis():
    videos = [
        {"title": "Dwarka: इतिहास की किताबों ने हमसे क्या छुपाया?"},  # Curiosity
        {"title": "The Rise and Fall of Chandragupta Maurya"},        # Story
        {"title": "Delhi Iron Pillar Complete Historical Truth"},    # Search
    ]

    res = analyze_title_and_thumbnail(videos)
    dist = res["title_angle_distribution"]
    assert dist["curiosity_oriented"] == 1
    assert dist["story_oriented"] == 1
    assert dist["search_oriented"] == 1
    assert "Test & Compare" in res["thumbnail_testing_status"]


# 9. Automated Weekly Growth Intelligence Dossier Generation
def test_weekly_growth_dossier_generation(tmp_path, monkeypatch):
    test_out = str(tmp_path / "output")
    monkeypatch.setattr(config, "OUTPUT_DIR", test_out)

    dossier = generate_growth_intelligence_dossier()
    assert "channel_name" in dossier
    assert "report_generated_at" in dossier
    assert "shorts_performance" in dossier
    assert "longform_performance" in dossier
    assert "topic_intelligence" in dossier
    assert "recommended_topics" in dossier
    assert "active_experiments" in dossier
    assert "confidence_limitations" in dossier

    # Verify JSON file written
    json_path = os.path.join(test_out, "weekly_growth_intelligence.json")
    assert os.path.exists(json_path)

    # Verify Markdown file written
    md_path = os.path.join(test_out, "weekly_growth_intelligence.md")
    assert os.path.exists(md_path)
    with open(md_path, encoding="utf-8") as f:
        md_content = f.read()
    assert "Weekly YouTube Growth Intelligence Report" in md_content
    assert "Shorts Performance" in md_content
    assert "Long-Form Documentaries" in md_content


# 10. Controlled Experiment Tracking & Sample Size Thresholds
def test_experiment_tracker_threshold_and_conclusions(temp_tracker):
    experiments = temp_tracker.get_all_experiments()
    assert len(experiments) >= 3

    exp_id = "EXP-001"
    # Record sample 1 (insufficient for conclusion)
    temp_tracker.record_experiment_sample(
        experiment_id=exp_id,
        video_id="v_1",
        variant="test",
        metric_value=78.0,
    )
    exp = next(e for e in temp_tracker.get_all_experiments() if e["id"] == exp_id)
    assert exp["status"] == "in_progress"
    assert "preliminary" in exp["confidence_level"]

    # Record sample 2 & 3
    temp_tracker.record_experiment_sample(experiment_id=exp_id, video_id="v_2", variant="control", metric_value=65.0)
    temp_tracker.record_experiment_sample(experiment_id=exp_id, video_id="v_3", variant="test", metric_value=82.0)

    updated_exp = next(e for e in temp_tracker.get_all_experiments() if e["id"] == exp_id)
    assert updated_exp["status"] == "completed"
    assert "moderate" in updated_exp["confidence_level"]
    assert "outperformed control" in updated_exp["conclusion"].lower()


# 11. Adaptive Production Brief Across Production Modules
def test_adaptive_production_brief_integration():
    brief = get_adaptive_production_brief()
    assert "preferred_pillars" in brief
    assert "shorts_pacing_directive" in brief
    assert "longform_pacing_directive" in brief
    assert "recommended_title_style" in brief
    assert "recommended_thumbnail_style" in brief

    # Test topic scoring adaptive bonus
    standard_score = score_topic_opportunity("Marine Archaeology of Dwarka", pillar_id=4)
    boosted_score = score_topic_opportunity(
        "Marine Archaeology of Dwarka",
        pillar_id=4,
        growth_brief={"preferred_pillars": ["Lost Cities & Archaeological Discoveries"]},
    )
    assert boosted_score["composite_opportunity_score"] > standard_score["composite_opportunity_score"]
    assert boosted_score["dimension_scores"]["growth_intelligence_bonus"] == 3.0

    # Test SEO optimizer adaptive style recommendation
    titles = generate_title_candidates("Indus Valley Secrets", preferred_style=brief["recommended_title_style"])
    assert titles["recommended_style"] == brief["recommended_title_style"]

    # Test thumbnail concept adaptive style recommendation
    thumb_concepts = generate_thumbnail_concepts("Kailash Temple", preferred_style=brief["recommended_thumbnail_style"])
    assert thumb_concepts["recommended_style"] == brief["recommended_thumbnail_style"]


# 12. Security & Credential Protection
def test_security_no_secret_leaks_in_growth_intelligence(tmp_path, monkeypatch):
    test_out = str(tmp_path / "output_sec")
    monkeypatch.setattr(config, "OUTPUT_DIR", test_out)

    dossier = generate_growth_intelligence_dossier()
    dossier_str = json.dumps(dossier)

    # Assure sensitive credentials or tokens are never present
    forbidden_tokens = ["AIzaSy", "client_secret", "refresh_token", "private_key", "Bearer "]
    for token in forbidden_tokens:
        assert token not in dossier_str, f"Security risk: sensitive credential fragment '{token}' found in growth dossier"
