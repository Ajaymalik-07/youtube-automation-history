"""
Script Writer Agent — Cinematic Historical Documentaries & High-Retention Shorts
Generates:
1. 8–13 minute deep-dive historical documentaries (strictly under 14:30 YouTube unverified cap).
2. High-velocity 25–60s vertical Shorts with 4-part structure across 8 distinct documentary formats.
3. Multi-language narration support (Hindi primary in Devanagari + English auto-dub/translation).
4. Strict script quality gates validating word count, duration, and claim alignment.
"""
import json
import copy
import unicodedata
from typing import Optional, List, Dict, Any, Tuple
import config
from agents.gemini_client import generate
from agents.json_utils import extract_json

# Supported Shorts Documentary Formats
SHORTS_FORMATS = [
    "historical_fact",
    "mystery_investigation",
    "forgotten_personality",
    "battle_strategy",
    "ancient_engineering",
    "misconception_debunked",
    "archaeological_discovery",
    "longform_teaser",
]


def estimate_narration_duration(text: str, wpm: int = 120) -> float:
    """Estimates audio narration duration in seconds based on word count."""
    words = len(text.split())
    return (words / max(wpm, 60)) * 60.0


def _facts_block(research: dict, limit: int = 5000) -> str:
    """Verified background from research dossier."""
    facts = (research.get("grounding") or {}).get("facts", "")
    claims = research.get("claims_and_evidence", [])
    claims_text = "\n".join(
        f"  - [{c.get('evidence_level', 'FACT')}]: {c.get('claim', '')} (Ref: {c.get('source_reference', 'ASI/Archives')})"
        for c in claims
    )
    timeline = research.get("verified_timeline", [])
    timeline_text = "\n".join(
        f"  - {t.get('era', '')}: {t.get('event', '')}" for t in timeline
    )

    combined = ""
    if claims_text:
        combined += f"\nVERIFIED HISTORICAL CLAIMS & EVIDENCE:\n{claims_text}\n"
    if timeline_text:
        combined += f"\nCHRONOLOGICAL MILESTONES:\n{timeline_text}\n"
    if facts:
        combined += f"\nARCHIVAL BACKGROUND:\n{facts[:limit]}\n"
    return combined


def validate_script_quality_gate(script: dict) -> tuple[bool, list[str]]:
    """
    Validates script structure, length, language integrity, and duration.
    """
    issues = []
    sections = script.get("sections", [])
    video_type = script.get("video_type", "normal")
    lang = script.get("language", "hi")

    if video_type == "shorts":
        if len(sections) < 3:
            issues.append(f"Shorts script has too few sections ({len(sections)}, expected 3–4).")
        total_text = " ".join(s.get("narration", "") for s in sections)
        words = len(total_text.split())
        if words < 70:
            issues.append(f"Shorts narration too brief ({words} words, minimum 70 required for 25s+).")
        elif words > 175:
            issues.append(f"Shorts narration too long ({words} words, maximum 175 allowed to fit under 60s).")
    else:
        # Long-form documentary (8-13 min target, hard cap under 14:30)
        if len(sections) < 8:
            issues.append(f"Long-form documentary has too few sections ({len(sections)}, expected 8–10).")
        total_text = " ".join(s.get("narration", "") for s in sections)
        words = len(total_text.split())
        est_sec = estimate_narration_duration(total_text, wpm=120)
        
        if words < 850:
            issues.append(f"Long-form script is too short ({words} words, ~{est_sec/60:.1f} min; target is 8–13 min).")
        elif words > 1500:
            issues.append(f"Long-form script is too long ({words} words, ~{est_sec/60:.1f} min; exceeds safe 14-min cap).")
            
        if est_sec > 870:  # 14 minutes 30 seconds
            issues.append(f"Estimated duration {est_sec/60:.1f} min exceeds YouTube's hard 14:30 unverified limit.")

    # Check Devanagari character presence if Hindi
    if lang == "hi":
        all_narr = " ".join(s.get("narration", "") for s in sections)
        devanagari_chars = sum(1 for ch in all_narr if '\u0900' <= ch <= '\u097F')
        total_chars = max(1, len([c for c in all_narr if c.isalnum()]))
        if (devanagari_chars / total_chars) < 0.40:
            issues.append("Hindi script lacks sufficient Devanagari characters (detected mostly Latin script).")

    is_approved = len(issues) == 0
    return is_approved, issues


def write_script(
    research: dict,
    video_type: str = "normal",
    language: str = "hi",
    shorts_format: str = "historical_fact",
    growth_brief: Optional[dict] = None,
) -> dict:
    """
    Generates a narrated script for Stories Malik.
    video_type: 'normal' (8–13 min deep documentary) | 'shorts' (25–60s vertical)
    language: 'hi' (Hindi primary) | 'en' (English secondary)
    shorts_format: specialized format from SHORTS_FORMATS
    growth_brief: optional adaptive retention directives from growth intelligence
    """
    if video_type == "shorts":
        script = _write_shorts_script(research, language=language, shorts_format=shorts_format, growth_brief=growth_brief)
    else:
        script = _write_longform_script(
            research,
            language=language,
            min_minutes=getattr(config, "VIDEO_MIN_MINUTES", 8),
            max_minutes=getattr(config, "VIDEO_MAX_MINUTES", 13),
            growth_brief=growth_brief,
        )

    # Attach production metadata
    all_narr = " ".join(s.get("narration", "") for s in script.get("sections", []))
    total_words = len(all_narr.split())
    est_dur = estimate_narration_duration(all_narr, wpm=120)

    script["script_version"] = "2.0"
    script["research_reference"] = research.get("topic", "")
    script["word_count"] = total_words
    script["estimated_duration_seconds"] = round(est_dur, 1)
    script["estimated_duration_minutes"] = round(est_dur / 60.0, 2)
    script["language"] = language
    script["video_type"] = video_type
    script["channel_brand"] = getattr(config, "CHANNEL_NAME", "Stories Malik")

    approved, issues = validate_script_quality_gate(script)
    script["quality_gate_approved"] = approved
    script["quality_gate_issues"] = issues

    return script


def _write_longform_script(
    research: dict,
    language: str = "hi",
    min_minutes: int = 8,
    max_minutes: int = 13,
    growth_brief: Optional[dict] = None,
) -> dict:
    """Generates an authentic 8–13 minute historical documentary script."""
    key_points_str = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(research.get("key_points", [])))
    brand = getattr(config, "CHANNEL_NAME", "Stories Malik")

    pacing_directive = ""
    if growth_brief and growth_brief.get("longform_pacing_directive"):
        pacing_directive = f"\nHISTORICAL RETENTION DIRECTIVE (PAST PERFORMANCE INSIGHT):\n- {growth_brief['longform_pacing_directive']}\n"

    lang_instruction = (
        "LANGUAGE: Write all narration, section titles, and captions in authentic, broadcast-quality HINDI (हिंदी - Devanagari script). "
        "Use dignified, evocative historical vocabulary suitable for deep historical narration by hi-IN-MadhurNeural. "
        "IMPORTANT: 'image_query', 'image_query_2', and 'image_query_3' MUST REMAIN IN ENGLISH to query visual archives accurately."
        if language == "hi" else
        "LANGUAGE: Write all narration, section titles, and captions in authoritative, gripping ENGLISH."
    )

    prompt = f"""You are the lead historical documentary scriptwriter for {brand}, a channel dedicated to verified Indian and World history.

TOPIC: {research.get('topic', '')}
TITLE: {research.get('video_title', '')}
HOOK QUESTION: {research.get('hook_question', '')}
KEY POINTS:
{key_points_str}
{_facts_block(research, limit=4000)}
{pacing_directive}
PRODUCTION SPECIFICATIONS:
- Target Video Duration: {min_minutes} to {max_minutes} minutes (strictly under 14:00 to comply with YouTube limits).
- Target Script Length: 950 to 1,250 words total across 8 to 10 comprehensive chapters.
- Each chapter's narration must be approximately 100–130 words long.
- Do NOT use repetitive filler. Maintain chronological pacing and empirical evidence.
- Differentiate established historical facts from oral lore or myths.
- The final chapter must feature an organic, natural channel CTA: "यदि आपको इतिहास की यह यात्रा पसंद आई, तो Stories Malik को सब्सक्राइब करें..."

{lang_instruction}

STORYTELLING PACING:
- Chapter 1 (Hook & Paradox): The startling historical question or recent archaeological contradiction.
- Chapter 2 (Setting the Stage): Geopolitical, cultural, and environmental landscape.
- Chapter 3 (The Inciting Catalyst): The ambitious ruler, betrayal, or discovery that launched events.
- Chapter 4 (The Narrative Pivot): A sudden reversal or unforeseen military confrontation.
- Chapters 5-7 (Deep Historical Chronology): Tactical maneuvers, primary texts, diary accounts, and epigraphic proof.
- Chapter 8 (The Climax & Collapse): The peak of the conflict or fall of the dynasty.
- Chapter 9 (Archaeological Discoveries): What excavations, carbon dating, or satellite LIDAR revealed.
- Chapter 10 (Historical Verdict & CTA): Enduring civilizational legacy and call to subscribe to {brand}.

VISUAL SEARCH PROMPTS:
- Every section MUST provide 3 distinct ENGLISH image queries tailored to historical visuals (e.g. "ancient temple ruins aerial dramatic", "ancient battlefield armor close-up", "historical palm leaf manuscript macro", "archaeological excavation artifacts museum").

Respond with ONLY a valid JSON object matching this schema:
{{
  "title": "{research.get('video_title', '')}",
  "description": "{research.get('description', '')}",
  "tags": {json.dumps(research.get('tags', []))},
  "sections": [
    {{
      "id": 1,
      "section_type": "hook",
      "title": "On-screen chapter title",
      "narration": "Full, immersive narration text of 100-130 words in Hindi...",
      "image_query": "dramatic historical establishing shot ancient ruins aerial",
      "image_query_2": "ancient stone artifact museum lighting macro",
      "image_query_3": "historical concept illustration dramatic lighting",
      "bullet_points": ["Key mystery 1", "Historical evidence 2"],
      "caption_text": "Short highlight caption for screen",
      "duration_seconds": 60
    }}
  ]
}}"""
    print(f"   → Generating documentary script (8–13 min, authentic historical Devanagari) for {brand}…")
    raw = generate(prompt)
    script = extract_json(raw, "Longform Scriptwriter")

    if "sections" not in script or len(script["sections"]) < 8:
        raise ValueError(f"Script returned too few sections ({len(script.get('sections', []))}).")

    return script


def _write_shorts_script(
    research: dict,
    language: str = "hi",
    shorts_format: str = "historical_fact",
    growth_brief: Optional[dict] = None,
) -> dict:
    """Generates an independent, high-retention 25–60s YouTube Short with candidate hooks."""
    brand = getattr(config, "CHANNEL_NAME", "Stories Malik")
    key_points_str = "\n".join(f"  - {p}" for p in research.get("key_points", [])[:3])

    pacing_directive = ""
    if growth_brief and growth_brief.get("shorts_pacing_directive"):
        pacing_directive = f"\nHISTORICAL RETENTION DIRECTIVE (PAST PERFORMANCE INSIGHT):\n- {growth_brief['shorts_pacing_directive']}\n"

    lang_instruction = (
        "LANGUAGE: Write all narration in punchy, dramatic HINDI (हिंदी - Devanagari script). "
        "Keep visual image queries in ENGLISH."
        if language == "hi" else
        "LANGUAGE: Write narration in punchy, viral ENGLISH."
    )

    prompt = f"""You are the lead YouTube Shorts creator for {brand}, specializing in verified historical insights and archaeological discoveries.

TOPIC: {research.get('topic', '')}
FORMAT: {shorts_format}
CORE HOOK QUESTION: {research.get('hook_question', '')}
KEY FACTS:
{key_points_str}
{_facts_block(research, limit=2000)}
{pacing_directive}
SHORTS PRODUCTION RULES:
1. 25–60 Seconds Total Duration: Narration must be 100–145 total words across 3–4 tight sections.
2. 0–2s Hook: Immediate high-intrigue question or verified historical contradiction.
3. 2–10s Context: High stakes or geographical context.
4. 10–40s Revelation: Tactical revelation, archaeological evidence, or unexpected turning point.
5. Final 5s Payoff & CTA: Satisfying conclusion with a natural invitation to explore the full documentary on {brand}.
6. Generate 3 candidate hooks and select the single most compelling, historically accurate one for Section 1.
7. {lang_instruction}

Respond with ONLY valid JSON:
{{
  "title": "{research.get('video_title', '')} #Shorts #History #StoriesMalik",
  "description": "Historical discovery from {brand}. Subscribe for deep documentary investigations. #Shorts #History #AncientIndia",
  "tags": {json.dumps(research.get('tags', []) + ["Shorts", "YouTubeShorts", "History", "AncientHistory", "StoriesMalik"])},
  "candidate_hooks": [
    "Hook option 1",
    "Hook option 2",
    "Hook option 3"
  ],
  "selected_hook": "Hook option 1",
  "format": "{shorts_format}",
  "sections": [
    {{
      "id": 1,
      "section_type": "hook",
      "title": "The Hook",
      "narration": "First 25-35 words delivering the selected high-impact historical hook...",
      "image_query": "dramatic historical close up artifact cinematic",
      "image_query_2": "ancient warrior statue museum lighting",
      "image_query_3": "historical battlefield dark atmosphere",
      "image_query_4": "ancient temple aerial dramatic",
      "bullet_points": [],
      "caption_text": "",
      "duration_seconds": 12
    }},
    {{
      "id": 2,
      "section_type": "content",
      "title": "The Revelation",
      "narration": "Core 60-80 words detailing the verified evidence, strategic move, or discovery...",
      "image_query": "archaeological excavation site close up",
      "image_query_2": "ancient manuscript hieroglyphics macro",
      "image_query_3": "ancient army formation battle cinematic",
      "image_query_4": "lost city temple golden light",
      "bullet_points": [],
      "caption_text": "",
      "duration_seconds": 32
    }},
    {{
      "id": 3,
      "section_type": "payoff_cta",
      "title": "Payoff & CTA",
      "narration": "Final 20-30 words with historical verdict and invite to watch full documentary on Stories Malik...",
      "image_query": "ancient pyramid starry night sky",
      "image_query_2": "history museum dark cinematic lighting",
      "image_query_3": "ancient mystery artifacts glowing",
      "image_query_4": "ancient temple sunrise drone view",
      "bullet_points": [],
      "caption_text": "",
      "duration_seconds": 10
    }}
  ]
}}"""
    print(f"   → Generating dedicated YouTube Short script ({shorts_format}) in {'Hindi' if language == 'hi' else 'English'}…")
    raw = generate(prompt)
    script = extract_json(raw, "Shorts scriptwriter")

    if "sections" not in script or len(script["sections"]) < 2:
        raise ValueError("Shorts script returned too few sections.")

    # Phase 20: Multi-factor candidate hook evaluation
    cand_hooks = script.get("candidate_hooks", [])
    if cand_hooks:
        try:
            from agents.adaptive_engine import evaluate_hook_candidates
            hook_eval = evaluate_hook_candidates(research.get("topic", ""), cand_hooks)
            script["selected_hook"] = hook_eval["selected_hook"]
            script["hook_evaluation"] = hook_eval
        except Exception:
            pass

    return script


def translate_script(script: dict, target_lang: str = "en") -> dict:
    """Translates script narration, titles, and captions to target_lang for auto-dubbing."""
    lang_name = "English" if target_lang == "en" else "Hindi"
    print(f"   → Translating script to {lang_name} for auto-dubbing and synchronized subtitles…")

    sections_payload = [
        {
            "id": s["id"],
            "title": s.get("title", ""),
            "narration": s.get("narration", ""),
            "caption_text": s.get("caption_text", ""),
            "bullet_points": s.get("bullet_points", []),
        }
        for s in script.get("sections", [])
    ]

    prompt = f"""You are a professional historical documentary localization expert and translator.
Translate the following documentary script into broadcast-quality, natural-sounding {lang_name}.
Preserve historical names with standard spellings. Keep the dramatic pacing and solemn historical tone intact.
Preserve the exact same section IDs and array structure.

Title: {script.get('title', '')}
Description: {script.get('description', '')}

Sections to translate:
{json.dumps(sections_payload, ensure_ascii=False, indent=2)}

Respond with ONLY valid JSON:
{{
  "title": "Translated Title",
  "description": "Translated Description",
  "sections": [
    {{
      "id": 1,
      "title": "Translated Title",
      "narration": "Translated Narration...",
      "caption_text": "Translated Caption",
      "bullet_points": ["Point 1", "Point 2"]
    }}
  ]
}}"""
    try:
        raw = generate(prompt)
        translated_data = extract_json(raw, "Translator")
        new_script = copy.deepcopy(script)
        new_script["title"] = translated_data.get("title", script.get("title"))
        new_script["description"] = translated_data.get("description", script.get("description"))
        new_script["language"] = target_lang

        trans_map = {s["id"]: s for s in translated_data.get("sections", [])}
        for orig in new_script.get("sections", []):
            sid = orig["id"]
            if sid in trans_map:
                orig["title"] = trans_map[sid].get("title", orig.get("title"))
                orig["narration"] = trans_map[sid].get("narration", orig.get("narration"))
                orig["caption_text"] = trans_map[sid].get("caption_text", orig.get("caption_text"))
                orig["bullet_points"] = trans_map[sid].get("bullet_points", orig.get("bullet_points"))

        return new_script
    except Exception as e:
        print(f"   ⚠ Translation failed ({e}); falling back to original script")
        return script
