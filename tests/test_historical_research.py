"""
Unit and Quality Gate Tests for Historical Research Engine (Phase 2)
Verifies evidence tier classification, research validation, and quality gates.
"""
import pytest
from apis.knowledge import EVIDENCE_LEVELS, gather_context
from agents.researcher import (
    validate_research_quality_gate,
    load_banned_topics,
    _parse_research_json,
)


def test_evidence_levels_comprehensive():
    expected_tiers = [
        "ESTABLISHED_FACT",
        "STRONGLY_SUPPORTED",
        "DISPUTED_INTERPRETATION",
        "ORAL_TRADITION",
        "MYTHOLOGY_FOLKLORE",
        "SPECULATION",
    ]
    for tier in expected_tiers:
        assert tier in EVIDENCE_LEVELS
        assert len(EVIDENCE_LEVELS[tier]) > 10


def test_quality_gate_passes_on_complete_research():
    complete_research = {
        "topic": "The Maritime Expeditions of Rajendra Chola I",
        "research_question": "How did the Chola Navy project power across Southeast Asia in 1025 CE?",
        "period": "1014–1044 CE (11th Century)",
        "geographic_location": "Thanjavur, Tamil Nadu to Srivijaya (Sumatra/Malaya)",
        "civilizations_involved": ["Chola Dynasty", "Srivijaya Empire"],
        "key_figures": ["Rajendra Chola I", "Sangrama Vijayottunggavarman"],
        "video_title": "The Secret Fleet: Rajendra Chola's Naval Invasion of Southeast Asia",
        "description": "How an ancient Indian empire built a blue-water navy that conquered Sumatra.",
        "hook_question": "How did an Indian emperor launch a naval armada 3,000 km across the ocean in 1025 CE?",
        "key_points": ["Thiruvalangadu plates", "Srivijaya trade routes", "Conquest of Kedah"],
        "tags": ["CholaNavy", "IndianHistory", "MaritimeHistory", "RajendraChola"],
        "verified_timeline": [
            {"era": "1014 CE", "event": "Coronation of Rajendra Chola I", "source": "Thanjavur Inscription"},
            {"era": "1025 CE", "event": "Naval expedition against Srivijaya", "source": "Thiruvalangadu Copper Plates"},
        ],
        "claims_and_evidence": [
            {
                "claim": "Rajendra Chola raided Srivijaya ports across the Malacca Strait in 1025 CE.",
                "evidence_level": "ESTABLISHED_FACT",
                "source_reference": "Thanjavur big temple inscription (1030 CE) and Song Dynasty records",
            },
            {
                "claim": "The raid was primarily motivated by maritime trade taxes and merchant guild appeals.",
                "evidence_level": "STRONGLY_SUPPORTED",
                "source_reference": "K.A. Nilakanta Sastri, 'The Colas'",
            },
            {
                "claim": "Chola ships used catamarans and advanced stitch-plank hulls with magnetic compasses.",
                "evidence_level": "DISPUTED_INTERPRETATION",
                "source_reference": "Maritime archaeology findings off Poompuhar",
            },
        ],
        "conflicting_interpretations": [
            {
                "perspective_a": "Military conquest and annexation",
                "perspective_b": "Chivalric raid to enforce open navigation treaties",
                "evidence": "Lack of permanent Chola administrative governors in Sumatra",
            }
        ],
        "uncertain_facts": ["Exact fleet size and casualty numbers are unrecorded in contemporary texts."],
        "myths_and_legends": [
            {"legend": "Cholas ruled China directly", "historical_reality": "Tributary merchant missions recorded in Song Annals"}
        ],
        "confidence_score": 0.92,
        "missing_evidence": "Excavations at Kadaram port sites remain partially unexplored.",
        "suggested_storytelling_angle": "Chronological documentary emphasizing strategic naval geography.",
    }

    approved, issues = validate_research_quality_gate(complete_research)
    assert approved is True
    assert len(issues) == 0


def test_quality_gate_rejects_insufficient_claims():
    incomplete_research = {
        "topic": "Mysterious Fort",
        "research_question": "Why is it empty?",
        "period": "Medieval",
        "geographic_location": "India",
        "claims_and_evidence": [
            {"claim": "Ghost sightings happen at night", "evidence_level": "SPECULATION", "source_reference": "Local tourist blog"}
        ],
        "verified_timeline": [],
        "confidence_score": 0.40,
    }

    approved, issues = validate_research_quality_gate(incomplete_research)
    assert approved is False
    assert any("Insufficient verified claims" in iss for iss in issues)
    assert any("timeline is incomplete" in iss for iss in issues)
    assert any("confidence score" in iss for iss in issues)


def test_quality_gate_rejects_excessive_speculation():
    speculative_research = {
        "topic": "Ancient Monolith",
        "period": "Iron Age",
        "geographic_location": "Deccan Plateau",
        "claims_and_evidence": [
            {"claim": "Built with alien levitation", "evidence_level": "SPECULATION", "source_reference": "Conspiracy forum"},
            {"claim": "Emits electromagnetic power", "evidence_level": "SPECULATION", "source_reference": "Modern conjecture"},
            {"claim": "Stands on rock foundation", "evidence_level": "ESTABLISHED_FACT", "source_reference": "ASI Report"},
        ],
        "verified_timeline": [
            {"era": "500 BCE", "event": "Erected", "source": "ASI"},
            {"era": "2020 CE", "event": "Excavated", "source": "ASI"},
        ],
        "confidence_score": 0.70,
    }

    approved, issues = validate_research_quality_gate(speculative_research)
    assert approved is False
    assert any("Too many claims classified as pure SPECULATION" in iss for iss in issues)


def test_banned_topics_excludes_physics_relics():
    banned = load_banned_topics()
    assert "The Boltzmann Brain" not in banned
    assert "Simulation Theory" not in banned
    assert "Quantum Immortality" not in banned
    assert any("Aliens" in t or "Hoax" in t for t in banned)
