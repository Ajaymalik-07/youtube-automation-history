"""
Unit Tests for Scriptwriter Engine & Script Quality Gates (Phases 4 & 5)
Verifies long-form documentary standards, Shorts 4-part structure, duration calculations, and quality validation.
"""
import pytest
from agents.scriptwriter import (
    validate_script_quality_gate,
    estimate_narration_duration,
    SHORTS_FORMATS,
)


def test_shorts_formats_coverage():
    expected = [
        "historical_fact",
        "mystery_investigation",
        "forgotten_personality",
        "battle_strategy",
        "ancient_engineering",
        "misconception_debunked",
        "archaeological_discovery",
        "longform_teaser",
    ]
    for fmt in expected:
        assert fmt in SHORTS_FORMATS


def test_narration_duration_estimation():
    # 120 words at 120 wpm should take exactly 60 seconds
    text = "word " * 120
    duration = estimate_narration_duration(text, wpm=120)
    assert duration == 60.0

    # 1200 words at 120 wpm should take 600 seconds (10 minutes)
    long_text = "word " * 1200
    long_duration = estimate_narration_duration(long_text, wpm=120)
    assert long_duration == 600.0


def test_quality_gate_passes_valid_longform_script():
    hindi_paragraph = (
        "प्राचीन भारत के इतिहास में मौर्य साम्राज्य का उत्थान एक युगांतरकारी घटना थी। "
        "चाणक्य और चंद्रगुप्त मौर्य ने मिलकर एक अखंड साम्राज्य की नींव रखी। "
        "यह साम्राज्य तक्षशिला से पाटलिपुत्र तक फैला हुआ था। "
    ) * 4  # ~120 words per section

    valid_script = {
        "title": "The Rise of Maurya Empire",
        "description": "Historical documentary about Chandragupta Maurya.",
        "language": "hi",
        "video_type": "normal",
        "sections": [
            {"id": i, "title": f"Chapter {i}", "narration": hindi_paragraph}
            for i in range(1, 10)  # 9 chapters * ~120 words = ~1080 words (~9 minutes)
        ],
    }

    approved, issues = validate_script_quality_gate(valid_script)
    assert approved is True
    assert len(issues) == 0


def test_quality_gate_rejects_too_few_sections_longform():
    short_script = {
        "title": "Short Doc",
        "language": "hi",
        "video_type": "normal",
        "sections": [
            {"id": 1, "title": "Part 1", "narration": "प्राचीन इतिहास की कहानी। " * 20},
            {"id": 2, "title": "Part 2", "narration": "ऐतिहासिक युद्ध का विवरण। " * 20},
        ],
    }

    approved, issues = validate_script_quality_gate(short_script)
    assert approved is False
    assert any("too few sections" in iss for iss in issues)


def test_quality_gate_passes_valid_shorts_script():
    hindi_shorts_text = "क्या आप जानते हैं कि प्राचीन भारत में कैसे top-down मंदिर बनाए गए? यह एलोरा का कैलाश मंदिर है जिसे एक ही चट्टान काटकर तराशा गया।" * 3

    valid_shorts = {
        "title": "Kailash Temple Engineering #Shorts",
        "language": "hi",
        "video_type": "shorts",
        "sections": [
            {"id": 1, "section_type": "hook", "narration": hindi_shorts_text[:120]},
            {"id": 2, "section_type": "content", "narration": hindi_shorts_text[:250]},
            {"id": 3, "section_type": "payoff_cta", "narration": hindi_shorts_text[:100]},
        ],
    }

    approved, issues = validate_script_quality_gate(valid_shorts)
    assert approved is True
    assert len(issues) == 0
