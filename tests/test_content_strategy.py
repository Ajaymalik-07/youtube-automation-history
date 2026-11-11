"""
Unit Tests for Content Strategy and Topic Discovery (Phase 3)
Verifies the 10 Content Pillars, transparent 8-dimension scoring, deduplication, and weekly reporting.
"""
import pytest
from agents.topic_discovery import (
    CONTENT_PILLARS,
    is_duplicate_topic,
    score_topic_opportunity,
    generate_weekly_topic_research_report,
    calculate_jaccard_similarity,
)


def test_ten_content_pillars_defined():
    assert len(CONTENT_PILLARS) == 10
    ids = [p["id"] for p in CONTENT_PILLARS]
    assert sorted(ids) == list(range(1, 11))
    for p in CONTENT_PILLARS:
        assert len(p["name"]) > 5
        assert len(p["keywords"]) >= 4


def test_topic_deduplication_detects_duplicates():
    existing = [
        "The Battle of Haldighati 1576 Maharana Pratap",
        "Submerged City of Dwarka Marine Archaeology",
        "Kailash Temple Top Down Carving Secret",
    ]

    # Exact duplicate
    is_dup, match, sim = is_duplicate_topic("The Battle of Haldighati 1576 Maharana Pratap", existing)
    assert is_dup is True
    assert sim == 1.0

    # High similarity variant with different stopwords
    is_dup2, match2, sim2 = is_duplicate_topic("Maharana Pratap Battle of Haldighati Story", existing)
    assert is_dup2 is True
    assert sim2 >= 0.50
    assert "Haldighati" in match2


def test_topic_deduplication_allows_distinct_topics():
    existing = [
        "The Battle of Haldighati 1576 Maharana Pratap",
        "Submerged City of Dwarka Marine Archaeology",
    ]

    is_dup, match, sim = is_duplicate_topic("Nalanda University Library Fire and Xuanzang Records", existing)
    assert is_dup is False
    assert sim < 0.20
    assert match is None


def test_transparent_topic_scoring_structure():
    scorecard = score_topic_opportunity(
        topic="The Naval Expedition of Rajendra Chola I",
        pillar_id=2,
        has_primary_sources=True,
        search_volume_indicator=8,
        visual_richness=9,
        audience_interest=9,
        competition_level=4,
    )

    dims = scorecard["dimension_scores"]
    assert "audience_relevance" in dims
    assert "search_demand" in dims
    assert "historical_significance" in dims
    assert "storytelling_potential" in dims
    assert "source_availability" in dims
    assert "visual_storytelling" in dims
    assert "content_differentiation" in dims
    assert "channel_alignment" in dims

    assert 0 <= scorecard["composite_opportunity_score"] <= 100
    assert scorecard["recommendation"] in ("Strong Recommend", "Viable", "Secondary")


def test_weekly_topic_research_report_generation():
    report = generate_weekly_topic_research_report(existing_published_topics=["The Submerged Citadel of Dwarka"])
    
    assert report["content_pillars_evaluated"] == 10
    assert len(report["all_longform_topics"]) == 10
    assert len(report["all_shorts_topics"]) == 20
    assert len(report["top_3_recommended_longform"]) == 3
    assert len(report["top_5_recommended_shorts"]) == 5

    # Check deduplication applied: Dwarka should be marked duplicate
    dwarka = next((t for t in report["all_longform_topics"] if "Dwarka" in t["topic"]), None)
    assert dwarka is not None
    assert dwarka["is_duplicate"] is True
