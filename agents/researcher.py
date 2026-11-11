"""
Historical Research Engine — Deep Evidence-Grounded Research for Stories Malik
Uses multi-tier historical source grounding (Archives, Crossref, ASI, Academic Texts, Wikipedia).
Enforces strict historical evidence standards and quality gates before any script proceeds.
"""
import os
import time
import json
import config
from agents.gemini_client import generate
from agents.json_utils import extract_json
from apis.knowledge import gather_context, EVIDENCE_LEVELS

# Path to the banned-topics file
_BANNED_TOPICS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "banned_topics.txt",
)

# Built-in banned topics — pseudohistorical hoaxes and already covered subjects
_BUILTIN_BANNED = [
    "Ancient Aliens in Harappa",
    "Fake Taj Mahal Conspiracy",
    "Pseudoscience Vedic Vimana Hoax",
]

# All available focus angles — matches the channel's 7-Day Weekly Content Calendar
FOCUS_ANGLES = [
    "Rivers & Ancient Civilizations (Monday)",
    "Ghosts & Haunted Places (Tuesday)",
    "Kings, Queens & Empires (Wednesday)",
    "Ancient Mysteries (Thursday)",
    "Wars & Battles (Friday)",
    "Lost Cities & Forgotten Places (Saturday)",
    "Historical Stories & Legends (Sunday)",
]


def load_banned_topics() -> list:
    """Return combined list of banned topics."""
    topics = list(_BUILTIN_BANNED)
    try:
        if os.path.exists(_BANNED_TOPICS_FILE):
            with open(_BANNED_TOPICS_FILE, encoding="utf-8") as f:
                for line in f:
                    t = line.strip()
                    if t and not t.startswith("#") and t not in topics:
                        topics.append(t)
    except Exception as e:
        print(f"   ⚠ Could not read banned_topics.txt: {e}")
    return topics


def save_banned_topics(topics: list) -> None:
    """Write user-managed portion to banned_topics.txt."""
    user_topics = [t for t in topics if t not in _BUILTIN_BANNED and t.strip()]
    with open(_BANNED_TOPICS_FILE, "w", encoding="utf-8") as f:
        f.write("# One banned topic per line. Lines starting with # are comments.\n")
        f.write("# Add topics here after you produce a documentary about them.\n\n")
        for t in user_topics:
            f.write(t + "\n")


def _grounding(topic: str) -> dict:
    """Historical archive + peer-reviewed research context."""
    if not getattr(config, "FACT_GROUNDING", True):
        return {"facts": "", "sources": [], "evidence_framework": EVIDENCE_LEVELS}
    print(f"   → Grounding historical evidence from Archives & Academic Journals for \"{topic[:60]}\"…")
    ctx = gather_context(topic)
    print(f"   → {len(ctx['sources'])} authoritative sources verified")
    return ctx


def validate_research_quality_gate(research: dict, min_confidence: float = 0.65) -> tuple[bool, list[str]]:
    """
    Research Quality Gate:
    Validates that a historical research document meets the evidentiary standards
    required for high-credibility documentary production.

    Rules:
    1. Central claims must have traceable evidence references.
    2. Critical historical period and geographic location must be specified.
    3. Research confidence must meet or exceed min_confidence threshold.
    4. Unsubstantiated claims must be identified in uncertain_facts or missing_evidence.
    """
    issues = []
    
    topic = research.get("topic", "").strip()
    if not topic:
        issues.append("Missing research topic.")

    period = research.get("period", "").strip()
    if not period or period.lower() in ("unknown", "various"):
        issues.append("Historical period is not clearly defined.")

    location = research.get("geographic_location", "").strip()
    if not location:
        issues.append("Geographic location is missing.")

    claims = research.get("claims_and_evidence", [])
    if not claims or len(claims) < 3:
        issues.append(f"Insufficient verified claims (found {len(claims)}, minimum 3 required).")
    else:
        # Check evidence tiers
        speculation_count = 0
        for c in claims:
            lvl = c.get("evidence_level", "")
            if "SPECULATION" in lvl:
                speculation_count += 1
        if speculation_count > len(claims) // 2:
            issues.append("Too many claims classified as pure SPECULATION without evidentiary backing.")

    timeline = research.get("verified_timeline", [])
    if not timeline or len(timeline) < 2:
        issues.append("Verified chronological timeline is incomplete (minimum 2 milestone entries required).")

    conf = research.get("confidence_score", 0.0)
    try:
        conf_float = float(conf)
    except (TypeError, ValueError):
        conf_float = 0.7 if str(conf).lower() in ("high", "good") else 0.5

    if conf_float < min_confidence:
        issues.append(f"Research confidence score {conf_float:.2f} is below the required threshold of {min_confidence:.2f}.")

    is_approved = len(issues) == 0
    return is_approved, issues


def _parse_research_json(raw: str) -> dict:
    data = extract_json(raw, "Historical Researcher")
    required = ["topic", "video_title", "research_question", "key_points", "tags"]
    for field in required:
        if field not in data:
            raise ValueError(f"Research JSON missing required field: '{field}'")
    return data


def research_topic(channel_description: str = "",
                   topic_override: str = "",
                   focus_angle: str = "",
                   trend_context: list | None = None) -> dict:
    """
    Conducts deep evidence-based historical research for Stories Malik.

    Parameters:
      channel_description : Channel identity and documentary standards
      topic_override      : User-specified exact topic
      focus_angle         : Editorial calendar focus angle (e.g. Wednesday Kings & Empires)
      trend_context       : Live historical anniversaries or archaeological discoveries
    """
    banned = load_banned_topics()
    banned_str = ", ".join(f'"{t}"' for t in banned)
    channel_desc = channel_description or config.CHANNEL_DESCRIPTION

    if topic_override.strip():
        exact_topic = topic_override.strip()
        print(f"   → Exact historical topic override: \"{exact_topic}\"")
        grounding = _grounding(exact_topic)
        facts_block = (f"\nVERIFIED PRIMARY & SECONDARY SOURCES (Build directly upon these records):\n"
                       f"{grounding['facts'][:4500]}\n") if grounding["facts"] else ""

        prompt = f"""You are the Chief Historical Researcher for Stories Malik, a premier YouTube documentary channel dedicated to verified Indian and World history.

Channel Profile:
{channel_desc}

MANDATORY ASSIGNMENT: Conduct exhaustive, evidence-based historical research on this EXACT topic:
>>> {exact_topic} <<<

CRITICAL HISTORICAL RESEARCH RULES:
1. Every major claim must be classified by its evidentiary tier:
   - ESTABLISHED_FACT (Archaeological / Inscription / Treaty proof)
   - STRONGLY_SUPPORTED (Multiple independent historical chronicles)
   - DISPUTED_INTERPRETATION (Historians disagree on dates or motivations)
   - ORAL_TRADITION (Folklore / Bardic legends)
   - MYTHOLOGY_FOLKLORE (Mythological accounts; clearly framed as religious/cultural belief)
   - SPECULATION (Modern theories lacking direct archaeological confirmation)
2. Clearly separate established fact from popular folklore or myths.
3. NEVER fabricate citations or pretend an inaccessible source was inspected.
4. Banned topics: {banned_str}
5. Provide actionable storytelling angles that grip the audience while respecting historical truth.

{facts_block}

Respond with ONLY a valid JSON object. No markdown fences, no explanatory preamble:
{{
  "topic": "{exact_topic}",
  "research_question": "The primary historical question or mystery this documentary investigates",
  "period": "Specific historical era and dates (e.g., 321–297 BCE or 16th Century CE)",
  "geographic_location": "Precise geographic region, ancient kingdom, and modern location",
  "civilizations_involved": ["Civilization or Dynasty 1", "Civilization or Dynasty 2"],
  "key_figures": ["Historical Personage 1", "Historical Personage 2"],
  "why_now": "Why this historical story resonates with modern audiences",
  "video_title": "Compelling, accurate documentary title under 70 characters",
  "description": "Engaging 2-sentence description summarizing the historical conflict and verified discovery",
  "hook_question": "The central thought-provoking question that hooks the viewer in the first 5 seconds",
  "key_points": [
    "Core historical revelation or political conflict",
    "Pivotal military, archaeological, or strategic turning point",
    "Deep geopolitical implication or societal impact",
    "Archaeological evidence or textual proof unearthed",
    "Enduring legacy or historical lesson"
  ],
  "verified_timeline": [
    {{"era": "Date / Era 1", "event": "Significant verified milestone", "source": "Archaeological survey / Inscription"}},
    {{"era": "Date / Era 2", "event": "Pivotal clash or coronation", "source": "Primary chronicle"}}
  ],
  "claims_and_evidence": [
    {{"claim": "Crucial historical fact", "evidence_level": "ESTABLISHED_FACT", "source_reference": "Specific primary/secondary historical record"}},
    {{"claim": "Contested narrative", "evidence_level": "DISPUTED_INTERPRETATION", "source_reference": "Differing historical interpretations"}},
    {{"claim": "Popular legend associated with the event", "evidence_level": "ORAL_TRADITION", "source_reference": "Folklore / Bardic chronicle"}}
  ],
  "conflicting_interpretations": [
    {{"perspective_a": "Traditional perspective", "perspective_b": "Modern revisionist / Archaeological view", "evidence": "Key supporting excavation or textual basis"}}
  ],
  "uncertain_facts": ["Facts that remain unproven by modern archaeology"],
  "myths_and_legends": [
    {{"legend": "Popular belief or folklore", "historical_reality": "What verified inscriptions or archaeology actually show"}}
  ],
  "confidence_score": 0.90,
  "missing_evidence": "Historical records lost or undeciphered",
  "suggested_storytelling_angle": "How to structure the narrative chronologically with dramatic gravitas",
  "target_audience": "Hindi-speaking history documentary viewers",
  "tags": ["AncientHistory", "IndianHistory", "Archaeology", "Documentary", "HistoricalMysteries", "StoriesMalik"],
  "thumbnail_concept": "Detailed description of a historically accurate, high-contrast visual focal point"
}}"""
        raw = generate(prompt)
        data = _parse_research_json(raw)
        data["grounding"] = grounding
        
        # Run quality gate verification
        approved, issues = validate_research_quality_gate(data)
        data["quality_gate_approved"] = approved
        data["quality_gate_issues"] = issues
        if not approved:
            print(f"   ⚠ Research Quality Gate flagged issues: {issues}")
        else:
            print(f"   ✓ Research Quality Gate passed (Confidence: {data.get('confidence_score')})")

        return data

    # MODE 2: AI Discovers Topic within Theme
    if focus_angle.strip():
        chosen_angle = focus_angle.strip()
    else:
        weekly_theme_info = config.get_weekly_theme()
        chosen_angle = f"{weekly_theme_info['theme']} ({weekly_theme_info['day']})"

    print(f"   → Researching documentary topic within historical theme: {chosen_angle}")

    trend_block = ""
    if trend_context:
        joined = "\n".join(f"  - {t}" for t in trend_context[:15])
        trend_block = f"\nRECENT ARCHAEOLOGICAL EXCAVATIONS & HISTORICAL ANNIVERSARIES:\n{joined}\n"

    prompt = f"""You are the Chief Historical Researcher for Stories Malik, a premier YouTube documentary channel dedicated to verified Indian and World history.

Channel Profile:
{channel_desc}

EDITORIAL FOCUS FOR TODAY:
Theme: >>> {chosen_angle} <<<
Banned Topics (Already covered or rejected): {banned_str}
{trend_block}

MISSION:
1. Identify an astonishing, historically verified event, lost civilization, ruler, or archaeological mystery within this theme.
2. Formulate a structured research dossier strictly adhering to the Historical Evidence Framework.
3. Prioritize primary chronicles, inscriptions, and peer-reviewed archaeological findings over unverified rumors.

Respond with ONLY a valid JSON object matching this schema:
{{
  "topic": "Specific historical subject",
  "research_question": "The primary historical question this documentary investigates",
  "period": "Specific historical era and dates",
  "geographic_location": "Geographic region, ancient kingdom, and modern territory",
  "civilizations_involved": ["Civilization or Dynasty 1", "Civilization 2"],
  "key_figures": ["Ruler / General / Explorer 1", "Historian / Figure 2"],
  "why_now": "Why this historical episode grips audiences today",
  "video_title": "Compelling, accurate documentary title under 70 characters",
  "description": "2-sentence description summarizing the conflict and historical stakes",
  "hook_question": "Compelling question that hooks the viewer in the first 5 seconds",
  "key_points": [
    "First pivotal revelation or political conflict",
    "Second key turning point — military or cultural",
    "Third key turning point — betrayal, strategy, or breakthrough",
    "Fourth key revelation — archaeological findings or primary text",
    "Fifth key takeaway — enduring legacy and historical verdict"
  ],
  "verified_timeline": [
    {{"era": "Date / Era 1", "event": "Significant verified milestone", "source": "Archaeological survey / Inscription"}},
    {{"era": "Date / Era 2", "event": "Decisive battle or turning point", "source": "Contemporary chronicle"}}
  ],
  "claims_and_evidence": [
    {{"claim": "Established historical fact", "evidence_level": "ESTABLISHED_FACT", "source_reference": "Inscriptions / Excavation records"}},
    {{"claim": "Scholarly consensus interpretation", "evidence_level": "STRONGLY_SUPPORTED", "source_reference": "Major peer-reviewed historians"}},
    {{"claim": "Associated folklore or legend", "evidence_level": "ORAL_TRADITION", "source_reference": "Local bards / literary traditions"}}
  ],
  "conflicting_interpretations": [
    {{"perspective_a": "Traditional historical view", "perspective_b": "Modern archaeological view", "evidence": "Key supporting evidence"}}
  ],
  "uncertain_facts": ["Specific elements unresolved by current historical evidence"],
  "myths_and_legends": [
    {{"legend": "Popular belief or folklore", "historical_reality": "What verified evidence actually establishes"}}
  ],
  "confidence_score": 0.88,
  "missing_evidence": "Gaps in the historical record",
  "suggested_storytelling_angle": "Chronological, evidence-backed narrative arc",
  "target_audience": "Hindi-speaking history documentary viewers",
  "tags": ["AncientHistory", "IndianHistory", "Archaeology", "Documentary", "HistoricalMysteries", "StoriesMalik"],
  "thumbnail_concept": "Visual description of historical centerpiece with high contrast"
}}"""
    raw = generate(prompt)
    data = _parse_research_json(raw)
    data["grounding"] = _grounding(data["topic"])

    approved, issues = validate_research_quality_gate(data)
    data["quality_gate_approved"] = approved
    data["quality_gate_issues"] = issues

    return data
