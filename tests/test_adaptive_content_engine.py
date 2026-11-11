"""
Unit & Integration Tests for Phase 20: Adaptive AI Content Optimization Engine
Stories Malik — Performance Learning, Statistical Validation, Diversity & Experimentation.

Test scenarios:
1. Statistical sample policies and minimum-N enforcement.
2. Outlier detection using IQR filtering.
3. Duration-adjusted watch time (WPMD) efficiency.
4. Welch's t-test, p-value computation, and significance claims.
5. 95% Confidence Interval calculations.
6. Time-since-publication view normalization.
7. Channel diversity monitor: personality, civilization, and pillar caps.
8. Hook token similarity detection (preventing duplicate hooks).
9. Adaptive topic opportunity report (20 candidates: 10 Shorts, 5 Long-form, 5 Reserve).
10. Multi-factor hook evaluation across 7 objective criteria.
11. Evidence-specific dynamic scriptwriting directives (no forced minute-3 maps).
12. Automated experiment selection without multi-variable confounding.
13. Weekly adaptive content strategy dossier generation (JSON & Markdown).
14. Production run brief integration.
15. Security & credential isolation in strategy dossiers.
"""
import os
import json
import pytest
from datetime import datetime, timezone
import config
from agents.statistical_validator import (
    get_sample_policy,
    detect_outliers_iqr,
    calculate_mean_and_confidence_interval,
    compute_duration_adjusted_watch_time,
    compute_welch_t_test,
    normalize_views_by_age,
)
from agents.diversity_monitor import (
    extract_entities,
    compute_hook_token_similarity,
    audit_channel_content_diversity,
)
from agents.adaptive_engine import (
    generate_adaptive_opportunity_report,
    evaluate_hook_candidates,
    get_dynamic_scriptwriting_directive,
    select_next_controlled_experiment,
    generate_weekly_adaptive_strategy,
    get_production_run_brief,
)
from apis.growth_database import HistoricalPerformanceDB


@pytest.fixture
def mock_db(tmp_path):
    """Provides a fresh isolated HistoricalPerformanceDB instance."""
    db_file = str(tmp_path / "test_adaptive_db.json")
    db = HistoricalPerformanceDB(db_path=db_file)
    # Populate with sample historical records
    for i in range(1, 6):
        db.record_snapshot(
            video_id=f"vid_{i}",
            video_format="longform" if i <= 2 else "short",
            topic=f"Historical Topic {i}",
            content_pillar="Ancient Technology, Architecture & Engineering" if i % 2 == 0 else "Indian Kings, Empires & Dynasties",
            publication_timestamp="2026-11-01T10:00:00Z",
            video_duration=600.0 if i <= 2 else 45.0,
            title=f"The Great Chronicle of Dynasty {i}",
            views=1000 * i,
            watch_time_minutes=300.0 * i,
            average_percentage_viewed=42.0 + (i * 2),
            checkpoint="24h",
        )
    return db


# 1. Statistical Sample Policies & Minimum-N Enforcement
def test_statistical_sample_policies():
    assert get_sample_policy(1)["allow_conclusions"] is False
    assert get_sample_policy(2)["allow_conclusions"] is False
    assert get_sample_policy(3)["allow_conclusions"] is False  # Preliminary directional only
    assert get_sample_policy(4)["allow_conclusions"] is False
    assert get_sample_policy(5)["allow_conclusions"] is True   # Moderate
    assert get_sample_policy(12)["allow_conclusions"] is True  # Sound


# 2. Outlier Detection using IQR
def test_outlier_detection_iqr():
    normal_data = [42.0, 44.5, 43.0, 45.0, 43.8, 44.0, 42.9, 120.0]  # 120.0 is an outlier
    cleaned, outliers = detect_outliers_iqr(normal_data)
    assert 120.0 in outliers
    assert len(cleaned) == 7
    assert 120.0 not in cleaned


# 3. Duration-Adjusted Watch Time (WPMD)
def test_duration_adjusted_watch_time():
    # Video A: 12 minutes (720s), 360 minutes watch time -> 360 / 12 = 30 WPMD
    wpmd_a = compute_duration_adjusted_watch_time(watch_time_minutes=360.0, duration_seconds=720.0)
    assert wpmd_a == 30.0

    # Video B: 6 minutes (360s), 240 minutes watch time -> 240 / 6 = 40 WPMD (Higher efficiency!)
    wpmd_b = compute_duration_adjusted_watch_time(watch_time_minutes=240.0, duration_seconds=360.0)
    assert wpmd_b == 40.0
    assert wpmd_b > wpmd_a

    # Zero protection
    assert compute_duration_adjusted_watch_time(0.0, 0.0) == 0.0


# 4. Welch's t-test and Significance Claims
def test_welch_t_test_and_significance():
    # Case A: Insufficient samples
    res_small = compute_welch_t_test([10.0, 12.0], [15.0, 16.0])
    assert res_small["valid_test"] is False
    assert res_small["is_significant"] is False

    # Case B: Identical groups
    res_ident = compute_welch_t_test([50.0, 52.0, 51.0], [50.0, 52.0, 51.0])
    assert res_ident["valid_test"] is True
    assert res_ident["delta"] == 0.0
    assert res_ident["is_significant"] is False

    # Case C: Clear significant difference
    control = [40.0, 41.0, 39.5, 40.5]
    test = [78.0, 80.0, 79.5, 81.0]
    res_sig = compute_welch_t_test(control, test)
    assert res_sig["valid_test"] is True
    assert res_sig["is_significant"] is True
    assert res_sig["p_value"] < 0.05
    assert "Statistically significant" in res_sig["significance_statement"]


# 5. Confidence Interval Calculations
def test_confidence_interval_calculation():
    vals = [42.0, 44.0, 46.0, 45.0, 43.0]
    ci = calculate_mean_and_confidence_interval(vals)
    assert ci["n"] == 5
    assert ci["mean"] == 44.0
    assert ci["ci_lower"] < 44.0
    assert ci["ci_upper"] > 44.0
    assert ci["margin_of_error"] > 0.0


# 6. Time-since-publication View Normalization
def test_time_decay_view_normalization():
    # 1000 views in 2 days vs 1000 views in 60 days
    vel_fresh = normalize_views_by_age(views=1000, days_since_publication=2.0)
    vel_old = normalize_views_by_age(views=1000, days_since_publication=60.0)
    assert vel_fresh > vel_old


# 7. Channel Diversity Monitor (Personalities, Civilizations, Pillars)
def test_diversity_monitor_personality_and_pillar_caps():
    mock_recent = [
        {"title": "The Secrets of Ashoka the Great", "topic": "Ashoka Maurya", "content_pillar": "Indian Kings, Empires & Dynasties"},
        {"title": "Ashoka Rock Edict Inscriptions", "topic": "Ashoka Edicts", "content_pillar": "Indian Kings, Empires & Dynasties"},
        {"title": "Kalinga War of Ashoka", "topic": "Ashoka War", "content_pillar": "Indian Kings, Empires & Dynasties"},
        {"title": "Mauryan Administration and Ashoka", "topic": "Ashoka Empire", "content_pillar": "Indian Kings, Empires & Dynasties"},
    ]

    audit = audit_channel_content_diversity(
        mock_recent,
        candidate_topic="The Personal Life of Ashoka",
        candidate_pillar="Indian Kings, Empires & Dynasties",
    )

    assert audit["diversity_score"] < 70
    assert audit["is_healthy"] is False
    assert "Ashoka" in audit["repeated_personalities"]
    assert "Indian Kings, Empires & Dynasties" in audit["overused_pillars"]
    assert len(audit["underrepresented_pillars"]) > 0


# 8. Hook Token Similarity Detection
def test_hook_token_similarity():
    h1 = "Why does Delhi's 1600-year Iron Pillar never rust?"
    h2 = "Why does the 1600-year Iron Pillar in Delhi never rust?"
    h3 = "How was Kailash Temple carved from the top down?"

    sim_high = compute_hook_token_similarity(h1, h2)
    sim_low = compute_hook_token_similarity(h1, h3)

    assert sim_high >= 0.70
    assert sim_low < 0.20


# 9. Adaptive Topic Opportunity Report Generation (20 Candidates)
def test_adaptive_opportunity_report_generation(mock_db):
    report = generate_adaptive_opportunity_report(db_override=mock_db)
    assert report["total_candidates"] == 20
    assert len(report["recommended_shorts"]) == 10
    assert len(report["recommended_longform"]) == 5
    assert len(report["reserve_topics"]) == 5

    # Check structure of a candidate
    cand = report["recommended_longform"][0]
    assert "topic" in cand
    assert "pillar" in cand
    assert "evidence" in cand
    assert "angle" in cand
    assert "feasibility" in cand
    assert cand["composite_score"] >= 8.0


# 10. Multi-Factor Hook Evaluation
def test_hook_multi_factor_evaluation():
    candidates = [
        "Did Chetak the war horse really wear an elephant trunk in battle?",
        "History is full of stories about horses and kings in ancient India.",
        "A shocking battle secret.",
    ]
    eval_res = evaluate_hook_candidates("Battle of Haldighati", candidates, historical_evidence="Mewar armory records")
    assert "selected_hook" in eval_res
    # Best hook should be the specific, curious elephant trunk hook
    assert "Chetak" in eval_res["selected_hook"]
    assert eval_res["winning_score"] > 7.5


# 11. Evidence-Specific Dynamic Scriptwriting Directives
def test_dynamic_scriptwriting_directives():
    # Naval Battle
    naval_dir = get_dynamic_scriptwriting_directive(
        topic="Chola Naval Invasion",
        pillar_name="Historical Battles & Military Strategy",
    )
    assert "tactical terrain" in naval_dir["visual_reveal_directive"].lower() or "troop deployment" in naval_dir["visual_reveal_directive"].lower()

    # Archaeological Excavation
    arch_dir = get_dynamic_scriptwriting_directive(
        topic="Submerged Dwarka",
        pillar_name="Lost Cities & Archaeological Discoveries",
    )
    assert "stratigraphic" in arch_dir["visual_reveal_directive"].lower() or "sonar" in arch_dir["visual_reveal_directive"].lower()
    # Must NEVER blindly force minute 3 map reveal
    assert "minute 3 map" not in arch_dir["visual_reveal_directive"].lower()


# 12. Automated Experiment Selection Without Confounding
def test_automated_experiment_selection():
    exp = select_next_controlled_experiment()
    assert "experiment_id" in exp
    assert "name" in exp
    assert "hypothesis" in exp
    assert "instruction" in exp
    assert "control_variant" in exp
    assert "test_variant" in exp


# 13. Weekly Adaptive Content Strategy Dossier Generation
def test_weekly_adaptive_strategy_dossier_generation(mock_db, tmp_path, monkeypatch):
    test_out = str(tmp_path / "output_adaptive")
    monkeypatch.setattr(config, "OUTPUT_DIR", test_out)

    strategy = generate_weekly_adaptive_strategy(db_override=mock_db)
    assert "channel_name" in strategy
    assert "statistical_evaluation" in strategy
    assert "content_diversity" in strategy
    assert len(strategy["recommended_shorts_topics"]) == 10
    assert len(strategy["recommended_longform_topics"]) == 5

    # Verify JSON persisted
    json_path = os.path.join(test_out, "adaptive_content_strategy.json")
    assert os.path.exists(json_path)

    # Verify Markdown persisted
    md_path = os.path.join(test_out, "adaptive_content_strategy.md")
    assert os.path.exists(md_path)
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    assert "Stories Malik — Adaptive AI Content Strategy Dossier" in content
    assert "Advanced Statistical Retention Validation" in content


# 14. Production Run Brief Integration
def test_production_run_brief_integration():
    brief = get_production_run_brief("longform")
    assert "selected_candidate" in brief
    assert "narrative_directive" in brief
    assert "active_experiment" in brief
    assert brief["video_type"] == "longform"
    assert "diversity_score" in brief


# 15. Security & Credential Isolation
def test_security_credential_isolation_in_adaptive_engine(mock_db, tmp_path, monkeypatch):
    test_out = str(tmp_path / "output_sec_adapt")
    monkeypatch.setattr(config, "OUTPUT_DIR", test_out)

    strategy = generate_weekly_adaptive_strategy(db_override=mock_db)
    payload_str = json.dumps(strategy)

    forbidden = ["AIzaSy", "client_secret", "refresh_token", "private_key", "Bearer "]
    for token in forbidden:
        assert token not in payload_str, f"Security violation: found secret token '{token}' in adaptive strategy dossier"
