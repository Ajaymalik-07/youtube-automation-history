"""
Unit Tests for Metadata Validation, 3 Title Candidates, and Thumbnails (Phases 8 & 9)
Verifies clean metadata standards, genuine chapter generation, and multi-concept thumbnails.
"""
import pytest
from agents.seo_optimizer import (
    generate_title_candidates,
    validate_youtube_metadata,
    build_genuine_chapters,
    optimize_for_100_percent,
)
from video.thumbnail import generate_thumbnail_concepts


def test_generate_title_candidates_structure():
    topic = "The Maritime Invasion of Srivijaya by Rajendra Chola"
    cands_hi = generate_title_candidates(topic, language="hi")
    assert "search_oriented" in cands_hi
    assert "story_oriented" in cands_hi
    assert "curiosity_oriented" in cands_hi
    assert len(cands_hi["search_oriented"]) > 10

    cands_en = generate_title_candidates(topic, language="en")
    assert "Documentary" in cands_en["search_oriented"]
    assert "Rise and Fall" in cands_en["story_oriented"]
    assert "Untold Truth" in cands_en["curiosity_oriented"]


def test_validate_metadata_passes_clean_data():
    valid_title = "The Naval Expeditions of Rajendra Chola I"
    valid_desc = (
        "In this complete documentary, we explore the extraordinary maritime conquests of the Chola Empire in 1025 CE. "
        "Discover how ancient Indian shipwrights engineered blue-water vessels to navigate the Malacca Strait.\n\n"
        "⏱ CHAPTERS\n0:00 Intro\n1:20 The Fleet\n\n#History #StoriesMalik #Documentary"
    )
    valid_tags = ["Chola", "IndianHistory", "Maritime", "Archaeology", "AncientCivilizations"]
    
    is_valid, issues = validate_youtube_metadata(valid_title, valid_desc, valid_tags, is_shorts=False)
    assert is_valid is True
    assert len(issues) == 0


def test_validate_metadata_rejects_dummy_filler_tags():
    tags_with_filler = ["History", "AncientIndia", "History 1", "History 2"]
    is_valid, issues = validate_youtube_metadata(
        "A Valid Documentary Title About Ancient Forts",
        "Valid description text of sufficient length for test purposes here.",
        tags_with_filler
    )
    assert is_valid is False
    assert any("dummy filler tags" in iss for iss in issues)


def test_validate_metadata_rejects_placeholder_chapters():
    desc_with_fake_chapters = (
        "Valid description text of sufficient length.\n\n"
        "0:00 Introduction\n1:00 Chapter One\n\n#History"
    )
    is_valid, issues = validate_youtube_metadata(
        "A Valid Documentary Title About Ancient Forts",
        desc_with_fake_chapters,
        ["History", "Archaeology"]
    )
    assert is_valid is False
    assert any("placeholder fake chapters" in iss for iss in issues)


def test_build_genuine_chapters_from_sections():
    sections = [
        {"id": 1, "title": "Intro", "narration": "word " * 120},  # ~60 sec
        {"id": 2, "title": "The Conquest", "narration": "word " * 120},  # ~60 sec
        {"id": 3, "title": "The Legacy", "narration": "word " * 120},  # ~60 sec
    ]
    chapters = build_genuine_chapters(sections)
    assert "0:00 Introduction" in chapters
    assert "1:00 The Conquest" in chapters
    assert "2:00 The Legacy" in chapters


def test_generate_thumbnail_concepts():
    concepts = generate_thumbnail_concepts("The Secret of Kailash Temple", "Kailash Temple")
    assert "search_oriented" in concepts
    assert "story_oriented" in concepts
    assert "curiosity_oriented" in concepts
    assert "*" in concepts["search_oriented"]["text"]
