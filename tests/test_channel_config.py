"""
Tests for Channel Identity and Stale Brand Detection (Phase 1)
Ensures generated metadata, descriptions, and CTAs never use stale or legacy channel names.
"""
import pytest
import config
from agents.seo_optimizer import optimize_for_100_percent
import gui


def test_channel_canonical_identity():
    assert config.CHANNEL_NAME == "Stories Malik"
    assert config.DEFAULT_LANGUAGE == "hi"
    assert config.SECONDARY_LANGUAGE == "en"
    assert config.PUBLISHING_TIMEZONE == "Asia/Kolkata"
    assert config.VIDEO_MIN_MINUTES == 8
    assert config.VIDEO_MAX_MINUTES == 13
    assert config.SHORTS_MIN_SECONDS == 25
    assert config.SHORTS_MAX_SECONDS == 60


def test_stale_brand_not_in_seo_optimizer_cta():
    sample_title = "The Rise of Chandragupta Maurya"
    sample_desc = "A complete historical documentary about the Maurya Empire."
    sample_tags = ["Maurya", "History", "Ancient India"]
    
    result = optimize_for_100_percent(
        title=sample_title,
        description=sample_desc,
        tags=sample_tags,
        keyword="Chandragupta Maurya",
        is_shorts=False
    )
    
    desc = result["description"]
    assert "History Chronicles" not in desc
    assert "My AI Channel" not in desc
    assert config.CHANNEL_NAME in desc


def test_brand_text_helper_respects_channel_name(monkeypatch):
    monkeypatch.setattr(config, "BRAND_TEXT", "")
    monkeypatch.setattr(config, "CHANNEL_NAME", "Stories Malik")
    monkeypatch.setattr(config, "SHOW_CHANNEL_BRAND", True)
    assert config.brand_text() == "Stories Malik"


def test_brand_text_empty_when_branding_disabled(monkeypatch):
    monkeypatch.setattr(config, "SHOW_CHANNEL_BRAND", False)
    assert config.brand_text() == ""


def test_no_stale_brand_in_built_description():
    script = {
        "title": "Battle of Haldighati Documentary",
        "description": "The immortal stand of Maharana Pratap.",
        "tags": ["Haldighati", "Maharana Pratap", "History"],
        "sections": [
            {"id": 1, "title": "The Hook", "narration": "Narration text " * 30},
            {"id": 2, "title": "The Battle", "narration": "Narration text " * 30},
        ],
    }
    research = {
        "hook_question": "How did Maharana Pratap defy Akbar?",
        "key_points": ["Cavalry charge", "Chetak the horse", "Guerrilla tactics"],
        "grounding": {
            "facts": "Verified battle details.",
            "sources": [{"source": "ASI", "title": "Haldighati Records", "url": "https://asi.nic.in"}],
        },
    }
    
    desc = gui._build_description(script, research, video_type="normal")
    assert "History Chronicles" not in desc
    assert "raunakpatil.com" not in desc
