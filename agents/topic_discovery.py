"""
Content Strategy & Topic Discovery Engine for Stories Malik
Implements:
1. 10 Historical Content Pillars.
2. Transparent 8-dimensional Topic Opportunity Scoring.
3. Automated Topic Deduplication via Jaccard Token & N-gram Similarity.
4. Weekly Topic Research Report Generation (10 Long-form + 20 Shorts).
"""
import re
import math
from typing import List, Dict, Tuple, Optional, Any
import config

CONTENT_PILLARS = [
    {
        "id": 1,
        "name": "Ancient Indian Civilizations",
        "name_hi": "प्राचीन भारतीय सभ्यताएं",
        "description": "Indus Valley, Vedic era, Megalithic cultures, and early urban centers.",
        "keywords": ["Indus Valley", "Harappa", "Mohenjo-Daro", "Rakhigarhi", "Vedic", "Saraswati", "Dholavira"],
    },
    {
        "id": 2,
        "name": "Indian Kings, Empires & Dynasties",
        "name_hi": "भारतीय साम्राज्य और राजवंश",
        "description": "Mauryas, Guptas, Cholas, Marathas, Ahoms, Rashtrakutas, and Chalukyas.",
        "keywords": ["Maurya", "Chola", "Gupta", "Maratha", "Ashoka", "Chandragupta", "Shivaji", "Samudragupta"],
    },
    {
        "id": 3,
        "name": "Historical Battles & Military Strategy",
        "name_hi": "ऐतिहासिक युद्ध और रणनीतियां",
        "description": "Crucial tactical masterstrokes, armor, naval expeditions, and siege warfare.",
        "keywords": ["Haldighati", "Tarain", "Panipat", "Kalinga", "Warfare", "Siege", "Naval Battle"],
    },
    {
        "id": 4,
        "name": "Lost Cities & Archaeological Discoveries",
        "name_hi": "खोए हुए शहर और पुरातात्विक खोजें",
        "description": "Underwater cities, buried ruins, LiDAR discoveries, and ongoing ASI excavations.",
        "keywords": ["Dwarka", "Underwater Archaeology", "Keezhadi", "Kalibangan", "Sannati", "Excavation"],
    },
    {
        "id": 5,
        "name": "Ancient Technology, Architecture & Engineering",
        "name_hi": "प्राचीन तकनीक, वास्तुकला और इंजीनियरिंग",
        "description": "Top-down rock-cut temples, rustless metallurgy, hydraulic dam engineering.",
        "keywords": ["Kailash Temple", "Iron Pillar", "Granite Architecture", "Stepwells", "Ancient Engineering"],
    },
    {
        "id": 6,
        "name": "Historical Mysteries & Unresolved Questions",
        "name_hi": "ऐतिहासिक रहस्य और अनसुलझी पहेलियां",
        "description": "Undeciphered scripts, unexplained vanishings, royal secrets, and cryptids.",
        "keywords": ["Indus Script", "Kuldhara", "Lost Treasure", "Disappearance", "Ancient Mystery"],
    },
    {
        "id": 7,
        "name": "World Civilizations & Forgotten History",
        "name_hi": "विश्व सभ्यताएं और विस्मृत इतिहास",
        "description": "Mesopotamia, Egypt, Persia, Rome, Mesoamerica, and Silk Road trade networks.",
        "keywords": ["Mesopotamia", "Ancient Egypt", "Persia", "Silk Road", "Alexandria", "Sumer"],
    },
    {
        "id": 8,
        "name": "Historical Personalities & Their Real Stories",
        "name_hi": "ऐतिहासिक व्यक्तित्व और उनकी वास्तविक गाथाएं",
        "description": "Chanakya, Xuanzang, Rani Durgavati, Megasthenes, Aryabhata, and travel chronicles.",
        "keywords": ["Chanakya", "Xuanzang", "Megasthenes", "Aryabhata", "Durgavati", "Charak"],
    },
    {
        "id": 9,
        "name": "History Behind Famous Monuments & Places",
        "name_hi": "प्रसिद्ध स्मारकों और स्थलों का इतिहास",
        "description": "Nalanda University, Konark Sun Temple, Chittorgarh Fort, and Tanjore Brihadisvara.",
        "keywords": ["Nalanda", "Konark", "Brihadisvara", "Chittorgarh", "Ajanta", "Ellora"],
    },
    {
        "id": 10,
        "name": "Myths, Legends & Their Historical Origins",
        "name_hi": "पौराणिक गाथाएं और उनका ऐतिहासिक आधार",
        "description": "Separating archaeological fact from legend in epic events and ancient artifacts.",
        "keywords": ["Ram Setu", "Koh-i-Noor", "Historical Origins", "Fact vs Legend", "Epics"],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  TOPIC DEDUPLICATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

_STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "of", "to", "for", "with", "on", "at",
    "by", "from", "how", "why", "what", "who", "is", "was", "are", "were", "secret",
    "untold", "history", "documentary", "hindi", "story", "true", "mystery",
    "के", "का", "की", "में", "और", "से", "का", "रहस्य", "इतिहास", "सच"
}


def normalize_topic_tokens(title: str) -> set:
    """Extract lowercased, alphanumeric word stems excluding common stopwords."""
    cleaned = re.sub(r"[^\w\s]", " ", (title or "").lower())
    tokens = {t for t in cleaned.split() if len(t) > 2 and t not in _STOPWORDS}
    return tokens


def calculate_jaccard_similarity(title_a: str, title_b: str) -> float:
    """Calculate Jaccard similarity index between two titles based on significant tokens."""
    tokens_a = normalize_topic_tokens(title_a)
    tokens_b = normalize_topic_tokens(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


def calculate_containment_similarity(title_a: str, title_b: str) -> float:
    """Calculate overlap/containment coefficient: intersection / min(|A|, |B|)."""
    tokens_a = normalize_topic_tokens(title_a)
    tokens_b = normalize_topic_tokens(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    return len(intersection) / min(len(tokens_a), len(tokens_b))


def is_duplicate_topic(candidate: str, existing_topics: List[str], threshold: float = 0.50) -> Tuple[bool, Optional[str], float]:
    """
    Checks if a candidate topic overlaps significantly with an existing or already-published topic.
    Returns: (is_duplicate: bool, matched_topic: str | None, similarity: float)
    """
    cand_norm = candidate.strip().lower()
    for existing in existing_topics:
        ex_norm = existing.strip().lower()
        if cand_norm == ex_norm:
            return True, existing, 1.0
        
        sim_jaccard = calculate_jaccard_similarity(candidate, existing)
        sim_containment = calculate_containment_similarity(candidate, existing)
        
        # Flag as duplicate if Jaccard meets threshold OR containment is high (e.g. 70% of core keywords overlap)
        if sim_jaccard >= threshold or sim_containment >= 0.70:
            effective_sim = max(sim_jaccard, sim_containment)
            return True, existing, round(effective_sim, 2)
            
    return False, None, 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSPARENT TOPIC SCORING MODEL
# ══════════════════════════════════════════════════════════════════════════════

def score_topic_opportunity(
    topic: str,
    pillar_id: Optional[int] = None,
    has_primary_sources: bool = True,
    search_volume_indicator: int = 7,
    visual_richness: int = 8,
    audience_interest: int = 9,
    competition_level: int = 5,
    growth_brief: Optional[Dict[str, Any]] = None,
) -> Dict[str, any]:
    """
    Computes a transparent, 8-dimensional topic opportunity scorecard (1–10 scale).
    Distinct dimensional scores are preserved rather than collapsed into an opaque number.
    Optionally incorporates growth intelligence directives from past channel performance.
    """
    # 1. Audience Relevance (1-10)
    aud_score = max(1, min(10, audience_interest))

    # 2. Measurable Search Demand (1-10)
    search_score = max(1, min(10, search_volume_indicator))

    # 3. Historical Significance (1-10)
    hist_score = 8
    pillar = next((p for p in CONTENT_PILLARS if p["id"] == pillar_id), None)
    if pillar:
        # Check keyword matches
        title_lower = topic.lower()
        matches = sum(1 for kw in pillar["keywords"] if kw.lower() in title_lower)
        hist_score = min(10, 6 + matches * 2)

    # 4. Storytelling Potential (Conflict / Turning Point / Discovery) (1-10)
    story_markers = ["battle", "conquest", "mystery", "betrayal", "fall", "rise", "collapse", "secret", "युद्ध", "रहस्य"]
    has_story_marker = any(m in topic.lower() for m in story_markers)
    story_score = 9 if has_story_marker else 7

    # 5. Availability of Reliable Evidence (1-10)
    source_score = 9 if has_primary_sources else 6

    # 6. Competition & Content Differentiation (1-10)
    # Higher score = lower saturation / higher differentiation
    diff_score = max(1, min(10, 11 - competition_level))

    # 7. Visual Storytelling Potential (Architecture, Maps, Artifacts) (1-10)
    vis_score = max(1, min(10, visual_richness))

    # 8. Channel Alignment (Historical Documentary Niche) (1-10)
    align_score = 10 if pillar_id in range(1, 11) else 7

    # Growth Intelligence Bonus (if pillar aligns with historical growth brief)
    growth_bonus = 0.0
    if growth_brief and pillar:
        preferred = growth_brief.get("preferred_pillars", [])
        if pillar["name"] in preferred:
            growth_bonus = 3.0

    # Weighted Composite Score (0–100)
    # Weights: Audience 20%, Search 15%, Historical 15%, Storytelling 15%, Sources 15%, Visual 10%, Diff 10%
    composite = (
        aud_score * 2.0 +
        search_score * 1.5 +
        hist_score * 1.5 +
        story_score * 1.5 +
        source_score * 1.5 +
        vis_score * 1.0 +
        diff_score * 1.0 +
        growth_bonus
    )
    composite = min(100.0, composite)

    return {
        "topic": topic,
        "pillar_id": pillar_id,
        "pillar_name": pillar["name"] if pillar else "General History",
        "dimension_scores": {
            "audience_relevance": aud_score,
            "search_demand": search_score,
            "historical_significance": hist_score,
            "storytelling_potential": story_score,
            "source_availability": source_score,
            "visual_storytelling": vis_score,
            "content_differentiation": diff_score,
            "channel_alignment": align_score,
            "growth_intelligence_bonus": growth_bonus,
        },
        "composite_opportunity_score": round(composite, 1),
        "recommendation": "Strong Recommend" if composite >= 75 else ("Viable" if composite >= 60 else "Secondary"),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  WEEKLY TOPIC REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_weekly_topic_research_report(
    existing_published_topics: Optional[List[str]] = None,
    growth_brief: Optional[Dict[str, Any]] = None,
) -> Dict[str, any]:
    """
    Generates a structured weekly editorial topic research report with:
    - 10 evaluated long-form topic candidates (across content pillars).
    - 20 Shorts topic concepts.
    - Top 3 recommended long-form topics.
    - Top 5 recommended Shorts topics.
    - Full deduplication verification against past topics.
    """
    history_published = existing_published_topics or []
    
    # Curated topic seed matrix across the 10 pillars
    longform_candidates = [
        {"topic": "The Submerged Citadel of Dwarka: Marine Archaeology vs Ancient Texts", "pillar_id": 4, "angle": "Investigating marine excavation sonar and submerged stone anchors"},
        {"topic": "Rajendra Chola's Blue Water Armada: The 1025 CE Maritime Invasion of Srivijaya", "pillar_id": 2, "angle": "Naval architecture, trade tax disputes, and trans-oceanic military strategy"},
        {"topic": "The Rustless Iron Pillar of Delhi: 1600-Year Ancient Indian Metallurgy", "pillar_id": 5, "angle": "Misophite protective passive film and Gupta-era forge welding"},
        {"topic": "The Battle of Haldighati 1576: Maharana Pratap's Guerrilla Warfare in Aravalli", "pillar_id": 3, "angle": "Mountain pass tactical positioning, Chetak's leap, and diplomatic refusal"},
        {"topic": "The Great Bath and Water Architecture of Mohenjo-Daro: 4,500-Year Hydraulic Engineering", "pillar_id": 1, "angle": "Bitumen waterproofing, drainage channels, and urban sanitation planning"},
        {"topic": "The 100-Year Construction of Kailash Temple Ellora: Carved from a Single Mountain", "pillar_id": 5, "angle": "Top-down basalt excavation removing 200,000 tons of rock without scaffolds"},
        {"topic": "Xuanzang's Lost Journey to Nalanda: An Ancient University Buried in Sand", "pillar_id": 8, "angle": "Eyewitness travelogue chronicles, library fire accounts, and archaeological resurrection"},
        {"topic": "The Kalinga War 261 BCE: The Bloodbath That Transformed Emperor Ashoka", "pillar_id": 2, "angle": "Dayan River battlefield epigraphy, edict confessions, and Buddhist transformation"},
        {"topic": "The Abandoned Ghost City of Kuldhara: Why 84 Paliwal Villages Vanished in One Night", "pillar_id": 6, "angle": "Salim Singh taxation tyranny, water table drops, and community pact reality"},
        {"topic": "The Mystery of the Indus Valley Script: Why the World's Oldest Script Remains Undeciphered", "pillar_id": 6, "angle": "Sign frequencies, bilingual inscription deficit, and seal ownership marks"},
    ]

    shorts_candidates = [
        {"topic": "Did Chetak the Horse Really Wear an Elephant Trunk in Battle?", "pillar_id": 3, "angle": "Tactical disguise confusing war elephants"},
        {"topic": "Why Does Delhi's 1600-Year Iron Pillar Never Rust?", "pillar_id": 5, "angle": "High phosphorus passive iron-oxide film"},
        {"topic": "How Was Kailash Temple Carved from the Top Down?", "pillar_id": 5, "angle": "Zero room for error vertical quarrying"},
        {"topic": "The 84 Villages That Vanished Overnight in Kuldhara", "pillar_id": 6, "angle": "Paliwal Brahmin collective midnight migration"},
        {"topic": "The Secret Submerged City Found 120 Feet Under the Arabian Sea", "pillar_id": 4, "angle": "Gulf of Khambhat marine sonar discoveries"},
        {"topic": "How the Chola Navy Conquered Indonesia in 1025 CE", "pillar_id": 2, "angle": "Catamaran fleets across the Bay of Bengal"},
        {"topic": "The Golden Library of Nalanda That Burned for 3 Months", "pillar_id": 9, "angle": "Dharmaganja library collection destruction"},
        {"topic": "What Did the Indus Valley People Actually Look Like?", "pillar_id": 1, "angle": "Rakhigarhi craniofacial 3D reconstruction"},
        {"topic": "Why Did Ashoka Renounce Warfare After Kalinga?", "pillar_id": 2, "angle": "The carnage of 100,000 casualties on Rock Edict XIII"},
        {"topic": "The 2,000-Year-Old Astronomical Computer: Antikythera", "pillar_id": 7, "angle": "Bronze differential gear mechanism"},
        {"topic": "Did Rani Padmini of Chittorgarh Really Exist?", "pillar_id": 10, "angle": "Padmavat epic vs contemporary Persian records"},
        {"topic": "The Ancient Indian Stepwells Designed to Cool the Desert by 10 Degrees", "pillar_id": 5, "angle": "Chand Baori geometric subterranean architecture"},
        {"topic": "Why Nobody Can Decipher the Indus Valley Script", "pillar_id": 6, "angle": "Short seal text lengths and lack of Rosetta Stone"},
        {"topic": "The Curse of the Koh-i-Noor: Only Women and Priests Survive It", "pillar_id": 10, "angle": "Chronicle of kings poisoned and blinded"},
        {"topic": "How Chanakya Poisoned Chandragupta Maurya's Food Daily", "pillar_id": 8, "angle": "Mithridatism poison tolerance strategy"},
        {"topic": "The Secret Underground Tunnels Beneath Shaniwar Wada Fort", "pillar_id": 6, "angle": "Peshwa palace siege escape routes"},
        {"topic": "The 4,000-Year-Old Lost River Saraswati Found by Satellite", "pillar_id": 1, "angle": "ISRO paleochannel radar scans"},
        {"topic": "The Queen Who Fought the Mughals on an Armored War Elephant: Rani Durgavati", "pillar_id": 8, "angle": "Gondwana defensive mountain gorge ambush"},
        {"topic": "How Ancient Indians Performed Cataract Surgery in 600 BCE", "pillar_id": 5, "angle": "Sushruta Samhita couch technique"},
        {"topic": "The Submerged Greek Metropolis of Heracleion Found Under the Sea", "pillar_id": 7, "angle": "Thonis-Heracleion rediscovered in Abu Qir Bay"},
    ]

    # Process and deduplicate longform candidates
    scored_longform = []
    for cand in longform_candidates:
        is_dup, match, sim = is_duplicate_topic(cand["topic"], history_published)
        score_data = score_topic_opportunity(cand["topic"], pillar_id=cand["pillar_id"], growth_brief=growth_brief)
        score_data["is_duplicate"] = is_dup
        score_data["duplicate_match"] = match
        score_data["storytelling_angle"] = cand["angle"]
        scored_longform.append(score_data)

    # Process and deduplicate shorts candidates
    scored_shorts = []
    for cand in shorts_candidates:
        is_dup, match, sim = is_duplicate_topic(cand["topic"], history_published)
        score_data = score_topic_opportunity(cand["topic"], pillar_id=cand["pillar_id"], visual_richness=9, growth_brief=growth_brief)
        score_data["is_duplicate"] = is_dup
        score_data["duplicate_match"] = match
        score_data["storytelling_angle"] = cand["angle"]
        scored_shorts.append(score_data)

    # Filter out duplicates and sort by composite opportunity score
    valid_longform = [t for t in scored_longform if not t["is_duplicate"]]
    valid_longform.sort(key=lambda x: x["composite_opportunity_score"], reverse=True)

    valid_shorts = [t for t in scored_shorts if not t["is_duplicate"]]
    valid_shorts.sort(key=lambda x: x["composite_opportunity_score"], reverse=True)

    return {
        "report_generated_for": config.CHANNEL_NAME,
        "content_pillars_evaluated": len(CONTENT_PILLARS),
        "total_longform_evaluated": len(scored_longform),
        "total_shorts_evaluated": len(scored_shorts),
        "all_longform_topics": scored_longform,
        "all_shorts_topics": scored_shorts,
        "top_3_recommended_longform": valid_longform[:3],
        "top_5_recommended_shorts": valid_shorts[:5],
    }
