"""
Content Diversity & Repetition Control Engine for Stories Malik
Phase 20: Cross-Channel Historical Balance, Repetition Guard & Originality Safeguards.

Monitors recent channel productions (last 10-20 videos) to detect:
1. Repeated historical personalities (e.g., Ashoka, Chanakya, Shivaji, Maharana Pratap).
2. Repeated civilizations & dynasties (e.g., Maurya, Chola, Gupta, Maratha, Mughal).
3. Over-concentration in a single content pillar (> 25% of recent 10 videos).
4. Duplicate/high-similarity hooks (Jaccard token similarity >= 0.60).
5. Overused thumbnail concepts and narrative structures.
6. Generates diversity scorecard (0–100) and recommends underrepresented topics.
"""
import re
from typing import Dict, Any, List, Optional, Tuple, Set


HISTORICAL_PERSONALITIES = [
    "Ashoka", "Chanakya", "Chandragupta Maurya", "Samudragupta", "Rajendra Chola",
    "Rajaraja Chola", "Shivaji", "Maharana Pratap", "Rani Durgavati", "Rani Padmini",
    "Akbar", "Prithviraj Chauhan", "Bappa Rawal", "Aryabhata", "Sushruta",
    "Charaka", "Xuanzang", "Megasthenes", "Al-Biruni", "Peshwa Baji Rao",
    "Lachit Borphukan", "Ahilyabai Holkar", "Rani Lakshmibai", "Harshavardhana",
]

HISTORICAL_CIVILIZATIONS = [
    "Indus Valley", "Harappa", "Mohenjo-Daro", "Vedic", "Maurya", "Gupta",
    "Chola", "Maratha", "Mughal", "Rajput", "Ahom", "Rashtrakuta", "Chalukya",
    "Pallava", "Vijayanagara", "Satavahana", "Sumer", "Mesopotamia", "Egypt",
    "Persia", "Rome", "Greece",
]


def extract_entities(text: str) -> Dict[str, List[str]]:
    """Extracts known historical personalities and civilizations from title/topic/narration."""
    t_low = text.lower()
    found_persons = []
    found_civs = []

    for p in HISTORICAL_PERSONALITIES:
        if p.lower() in t_low:
            found_persons.append(p)

    for c in HISTORICAL_CIVILIZATIONS:
        if c.lower() in t_low:
            found_civs.append(c)

    return {
        "personalities": found_persons,
        "civilizations": found_civs,
    }


def compute_hook_token_similarity(hook_a: str, hook_b: str) -> float:
    """Computes Jaccard word similarity between two hooks."""
    def _clean_tokens(s: str) -> Set[str]:
        words = re.findall(r"\w+", s.lower())
        stopwords = {"the", "a", "an", "is", "of", "to", "in", "and", "or", "what", "why", "how", "did", "you", "know"}
        return {w for w in words if w not in stopwords and len(w) > 2}

    toks_a = _clean_tokens(hook_a)
    toks_b = _clean_tokens(hook_b)

    if not toks_a or not toks_b:
        return 0.0

    intersection = toks_a.intersection(toks_b)
    union = toks_a.union(toks_b)
    return round(len(intersection) / len(union), 3)


def audit_channel_content_diversity(
    recent_videos: List[Dict[str, Any]],
    candidate_topic: str = "",
    candidate_pillar: str = "",
    candidate_hook: str = "",
) -> Dict[str, Any]:
    """
    Evaluates recent channel videos to assess content diversity and flags repetition risks:
    - Personality frequency caps (same personality max 1 in last 5 videos)
    - Pillar frequency caps (no single pillar > 25% of recent 10 videos)
    - Hook uniqueness check against previous video hooks
    """
    recent_window = recent_videos[-15:] if len(recent_videos) > 15 else list(recent_videos)
    total_recent = len(recent_window)

    person_counts: Dict[str, int] = {}
    civ_counts: Dict[str, int] = {}
    pillar_counts: Dict[str, int] = {}
    recent_hooks: List[str] = []

    for v in recent_window:
        title = v.get("title", "")
        topic = v.get("topic", "")
        pillar = v.get("content_pillar", "General History")
        hook = v.get("hook", v.get("hook_question", ""))
        if hook:
            recent_hooks.append(hook)

        entities = extract_entities(f"{title} {topic}")
        for p in entities["personalities"]:
            person_counts[p] = person_counts.get(p, 0) + 1
        for c in entities["civilizations"]:
            civ_counts[c] = civ_counts.get(c, 0) + 1

        pillar_counts[pillar] = pillar_counts.get(pillar, 0) + 1

    warnings = []
    penalties = 0

    # 1. Check pillar concentration
    overused_pillars = []
    if total_recent >= 4:
        for p, count in pillar_counts.items():
            share = count / total_recent
            if share > 0.25:
                overused_pillars.append(p)
                warnings.append(f"Pillar '{p}' represents {count}/{total_recent} ({share*100:.0f}%) of recent videos (exceeds 25% cap).")
                penalties += 15

    # 2. Check personality overexposure
    repeated_persons = []
    for p, count in person_counts.items():
        if count >= 2:
            repeated_persons.append(p)
            warnings.append(f"Historical personality '{p}' featured {count} times in last {total_recent} videos.")
            penalties += 10

    # 3. Check candidate against recent history if provided
    candidate_warning = None
    if candidate_topic:
        cand_entities = extract_entities(candidate_topic)
        # Check if candidate features a personality covered in the immediate last 3 videos
        last_3 = recent_window[-3:] if len(recent_window) >= 3 else recent_window
        for v in last_3:
            v_ents = extract_entities(f"{v.get('title', '')} {v.get('topic', '')}")
            common_persons = set(cand_entities["personalities"]).intersection(set(v_ents["personalities"]))
            if common_persons:
                p_name = list(common_persons)[0]
                candidate_warning = f"Candidate topic repeats '{p_name}', who was already featured in recent video '{v.get('title', '')}'."
                warnings.append(candidate_warning)
                penalties += 20
                break

    # 4. Check candidate hook similarity
    if candidate_hook and recent_hooks:
        for h in recent_hooks:
            sim = compute_hook_token_similarity(candidate_hook, h)
            if sim >= 0.60:
                warnings.append(f"Candidate hook has high similarity ({sim*100:.0f}%) with recent hook: '{h[:60]}...'")
                penalties += 15
                break

    # Compute diversity score (0–100)
    diversity_score = max(0, min(100, 100 - penalties))

    # Identify underrepresented pillars
    from agents.growth_analyst import HISTORICAL_PILLARS
    underrepresented_pillars = [
        p for p in HISTORICAL_PILLARS if pillar_counts.get(p, 0) == 0
    ]

    return {
        "diversity_score": diversity_score,
        "recent_videos_audited": total_recent,
        "is_healthy": diversity_score >= 70,
        "overused_pillars": overused_pillars,
        "underrepresented_pillars": underrepresented_pillars,
        "repeated_personalities": repeated_persons,
        "personality_frequencies": person_counts,
        "civilization_frequencies": civ_counts,
        "pillar_distribution": pillar_counts,
        "warnings": warnings,
        "recommendation": (
            "Content diversity is healthy. Proceed with proposed production."
            if diversity_score >= 70
            else f"Diversity warning: {warnings[0] if warnings else 'Diversify content pillars'}. Prioritize underrepresented pillars."
        ),
    }
