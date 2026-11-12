import json
from unittest.mock import patch

import config
from apis.growth_database import HistoricalPerformanceDB
from agents.adaptive_engine import (
    evaluate_hook_candidates,
    evaluate_storytelling_structure,
    generate_adaptive_opportunity_report,
)
from agents.experiment_tracker import ExperimentTracker
from agents.growth_analyst import (
    diagnose_audience_growth,
    evaluate_packaging_candidate,
    generate_phase24_reports,
)
from agents.statistical_validator import compute_welch_t_test, get_sample_policy


def test_diagnose_audience_growth_provenance_and_blocked_oauth(tmp_path):
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    db.record_snapshot(
        video_id="REAL_SHORT_1",
        video_format="short",
        topic="Iron Pillar",
        content_pillar="Ancient India",
        publication_timestamp="2026-11-12T06:30:00Z",
        video_duration=55.0,
        title="Why Has This 1,600-Year-Old Iron Pillar Never Rusted? #Shorts",
        views=5,
        likes=1,
        comments=0,
        owner_analytics_available=False,
    )
    db.record_snapshot(
        video_id="MOCK_FIXTURE_2",
        video_format="longform",
        topic="Test Fixture",
        content_pillar="Test",
        publication_timestamp="2026-11-12T06:30:00Z",
        video_duration=600.0,
        title="Mock Fixture Video",
        views=99999,
        average_percentage_viewed=88.0,
        owner_analytics_available=True,
        metadata_extras={"is_test_fixture": True},
    )

    with patch(
        "apis.youtube_analytics.get_analytics_capabilities_and_limitations",
        return_value={"owner_analytics_connected": False, "limitations": ["Missing yt-analytics.readonly"]},
    ), patch(
        "uploader.oauth_manager.audit_token_scopes",
        return_value={"granted_scopes": ["youtube.upload"], "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"]},
    ):
        diag = diagnose_audience_growth(evaluation_window_days=30, db_override=db)

    assert diag["analytics_dependent_optimization_status"] == "BLOCKED"
    assert diag["owner_analytics_connected"] is False
    assert diag["records_inspected"] == 1
    assert diag["excluded_mock_or_test_records"] == 1
    assert diag["shorts_diagnosis"]["public_metrics"]["total_views"] == 5
    assert diag["shorts_diagnosis"]["private_owner_metrics"]["average_percentage_viewed"] is None
    assert diag["shorts_diagnosis"]["private_owner_metrics"]["viewed_vs_swiped_ratio"] is None
    assert diag["longform_diagnosis"]["private_owner_metrics"]["impressions"] is None
    assert diag["longform_diagnosis"]["private_owner_metrics"]["ctr"] is None
    assert "do not prove poor documentary quality" in diag["longform_diagnosis"]["bottleneck_diagnosis"]


def test_packaging_evaluation_rejects_clickbait_and_fake_historical_photos():
    good = evaluate_packaging_candidate(
        title="1600 साल पुराने इस Iron Pillar पर कभी जंग क्यों नहीं लगा?",
        thumbnail_spec={
            "visual_concept": "Close-up of Mehrauli Iron Pillar inscription",
            "text_overlay": "1600 Years Rust-Free",
            "matches_video_content": True,
            "presents_ai_as_authentic_photo": False,
        },
        documentary_topic="Mehrauli Iron Pillar metallurgy",
        video_format="longform",
    )
    assert good["passed"] is True
    assert good["has_clickbait"] is False
    assert good["title_score"] >= 8.0

    bad = evaluate_packaging_candidate(
        title="YOU WON'T BELIEVE THIS SHOCKING TRUTH!!!",
        thumbnail_spec={
            "visual_concept": "Dramatic AI scene",
            "text_overlay": "THIS WILL BLOW YOUR MIND RIGHT NOW",
            "matches_video_content": False,
            "presents_ai_as_authentic_photo": True,
        },
        documentary_topic="Mehrauli Iron Pillar metallurgy",
        video_format="longform",
    )
    assert bad["passed"] is False
    assert bad["has_clickbait"] is True
    assert any("authentic historical photograph" in iss for iss in bad["issues"])


def test_hook_and_storytelling_evaluation_blocks_shorts_cliffhanger_bait():
    hook_res = evaluate_hook_candidates(
        topic="Kailash Temple",
        candidate_hooks=[
            "Welcome back guys today we are going to talk about an amazing temple in India.",
            "How did ancient artisans carve the entire Kailash Temple top-down out of one rock?",
        ],
        historical_evidence="Rashtrakuta rock-cut monolith excavation records",
    )
    assert "Kailash Temple" in hook_res["selected_hook"]
    assert hook_res["winning_score"] >= 7.0

    cliffhanger_short = {
        "video_type": "shorts",
        "sections": [
            {"narration": "How was Kailash Temple carved top-down from a single basalt cliff?", "visual_prompt": "Aerial view of Ellora"},
            {"narration": "Archaeological records show Rashtrakuta artisans removed 200,000 tons of rock.", "visual_prompt": "Chisel marks close-up"},
            {"narration": "To know the real secret, watch the full video in the pinned comment!", "visual_prompt": "Arrow pointing down"},
        ],
    }
    res_bad = evaluate_storytelling_structure(cliffhanger_short)
    assert res_bad["passed"] is False
    assert any("cliffhanger bait" in iss.lower() for iss in res_bad["issues"])

    complete_short = {
        "video_type": "shorts",
        "sections": [
            {"narration": "How was Kailash Temple carved top-down from a single basalt cliff?", "visual_prompt": "Aerial view of Ellora"},
            {"narration": "Archaeological records show Rashtrakuta artisans cut vertical trenches first, removing 200,000 tons of rock.", "visual_prompt": "Basalt trench diagram"},
            {"narration": "That top-down engineering meant one mistake could never be patched, proving centuries of planning.", "visual_prompt": "Monolith courtyard sunlight"},
        ],
    }
    res_good = evaluate_storytelling_structure(complete_short)
    assert res_good["passed"] is True
    assert res_good["overall_score"] >= 7.5


def test_experiment_isolation_sample_safeguards_and_phase24_reports(tmp_path):
    # Statistical safeguard: small sample must remain inconclusive
    policy = get_sample_policy(2)
    assert policy["allow_conclusions"] is False
    sig = compute_welch_t_test([10.0, 12.0], [20.0, 22.0])
    assert sig["valid_test"] is False
    assert sig["is_significant"] is False

    # Topic opportunity report
    db = HistoricalPerformanceDB(db_path=str(tmp_path / "historical_performance_db.json"))
    opp = generate_adaptive_opportunity_report(db_override=db)
    assert len(opp["recommended_shorts"]) > 0
    assert len(opp["recommended_longform"]) > 0

    # Packaging vs storytelling experiment isolation in Phase 24 report suite
    tracker = ExperimentTracker()
    tracker.register_controlled_experiment({
        "id": "PKG-101",
        "name": "Curiosity Title vs Search Title",
        "category": "packaging",
        "target_format": "longform",
        "hypothesis": "Curiosity title improves CTR without clickbait",
        "baseline": "Current longform CTR",
        "primary_variable": "title_angle",
        "success_metric": "ctr",
        "target_metric": "ctr",
        "control_variant": "Search Title",
        "test_variant": "Curiosity Title",
        "min_sample_size": 10,
    })
    tracker.register_controlled_experiment({
        "id": "STR-202",
        "name": "5s Visual Paradox Hook",
        "category": "storytelling",
        "target_format": "short",
        "hypothesis": "Visual paradox hook improves 30s retention",
        "baseline": "Current Shorts APV",
        "primary_variable": "opening_hook",
        "success_metric": "average_percentage_viewed",
        "target_metric": "average_percentage_viewed",
        "control_variant": "Standard Hook",
        "test_variant": "Visual Paradox Hook",
        "min_sample_size": 10,
    })

    with patch("agents.growth_analyst.get_performance_db", return_value=db), \
         patch("agents.experiment_tracker.get_experiment_tracker", return_value=tracker), \
         patch("apis.youtube_analytics.get_analytics_capabilities_and_limitations", return_value={"owner_analytics_connected": False, "limitations": []}), \
         patch("uploader.oauth_manager.audit_token_scopes", return_value={"granted_scopes": ["youtube.upload"], "missing_scopes": ["youtube.readonly", "yt-analytics.readonly"]}):
        rep = generate_phase24_reports(output_dir=str(tmp_path), evaluation_window_days=30)

    assert rep["packaging_experiment_report"]["total_experiments"] == 1
    assert rep["storytelling_experiment_report"]["total_experiments"] == 1
    assert rep["phase24_30day_optimization_report"]["analytics_dependent_optimization_status"] == "BLOCKED"
    assert rep["phase24_30day_optimization_report"]["cadence_preserved"]["longform_daily"] == 1
    assert rep["phase24_30day_optimization_report"]["cadence_preserved"]["shorts_daily"] == 5
    for path in rep["paths"].values():
        assert json.loads(open(path, encoding="utf-8").read())
