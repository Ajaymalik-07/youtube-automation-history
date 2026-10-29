"""
Script Writer Agent — generates cinematic 15+ minute long-form History documentaries
and high-retention YouTube Shorts with multi-language support (Hindi primary + English auto-dub).
Uses shared Gemini client with model fallback chain.
"""
import json
import copy
import config
from agents.gemini_client import generate
from agents.json_utils import extract_json


def _facts_block(research: dict, limit: int = 5000) -> str:
    """Verified background from Wikipedia / arXiv, if the researcher found any."""
    facts = (research.get("grounding") or {}).get("facts", "")
    if not facts:
        return ""
    return (
        "\nVERIFIED HISTORICAL BACKGROUND & FACTS (Wikipedia / Academic sources). "
        "Use real historical figures, dates, battles, geographical names and archaeological evidence:\n"
        f"{facts[:limit]}\n"
    )


def write_script(research: dict, video_type: str = "normal", language: str = "hi") -> dict:
    """
    Generates a narrated script for a YouTube video or YouTube Short.
    video_type:
      - "normal" or "long": Deep 10–14 minute historical documentary (10–12 sections, ~1,200–1,500 words)
      - "shorts": High-velocity 50-60s vertical Shorts
    language: "hi" (Hindi primary) | "en" (English)
    """
    if video_type == "shorts":
        return _write_shorts_script(research, language=language)

    return _write_longform_script(
        research, language=language,
        min_minutes=getattr(config, "VIDEO_MIN_MINUTES", 10),
        max_minutes=getattr(config, "VIDEO_MAX_MINUTES", 14)
    )


def _write_longform_script(research: dict, language: str = "hi", min_minutes: int = 10, max_minutes: int = 14) -> dict:
    """
    Generates an epic 10–14 minute historical documentary script.
    At ~120-130 words/minute, 10–14 minutes requires 1,200 to 1,500 words across 10-12 sections.
    Guarantees the final video stays under YouTube's 15-minute limit.
    """
    key_points_str = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(research.get("key_points", [])))

    lang_instruction = (
        "LANGUAGE: Write all narration, section titles, and captions in rich, broadcast-quality HINDI (हिंदी - Devanagari script). "
        "Use captivating, dramatic vocabulary suited for deep historical storytelling and narration by a voice like Madhur (hi-IN-MadhurNeural). "
        "IMPORTANT: 'image_query', 'image_query_2', and 'image_query_3' MUST REMAIN IN ENGLISH so stock image search engines can find relevant visuals."
        if language == "hi" else
        "LANGUAGE: Write all narration, section titles, and captions in gripping, authoritative ENGLISH."
    )

    prompt = f"""You are the lead documentary scriptwriter for an epic History YouTube channel (like Dan Carlin's Hardcore History, Timeline, and Kings and Generals).

Video topic: {research.get('topic', '')}
Title: {research.get('video_title', '')}
Core hook question: {research.get('hook_question', '')}
Key points to cover:
{key_points_str}
{_facts_block(research)}

MANDATORY REQUIREMENT:
The video must be between {min_minutes} and {max_minutes} MINUTES LONG (optimally 11–13 minutes, strictly under {max_minutes} minutes to comply with YouTube upload rules).
You MUST write 10 to 12 comprehensive sections.
Each section's narration must be 100–130 words long, resulting in a total narration of 1,200 to 1,500 words (~11–13.5 minutes of narrated speech).
Do NOT exceed {max_minutes} minutes. Do NOT make it less than {min_minutes} minutes.

{lang_instruction}

STORYTELLING & PACING STRUCTURE:
- Section 1 (Hook): An astonishing, forgotten historical paradox or discovery that shatters common assumptions.
- Section 2 (Setting the Stage): The geopolitical, cultural, and environmental backdrop of the era.
- Section 3 (The Rising Power / Spark): The inciting event or ambitious ruler that set events into motion.
- Section 4 (The First Re-hook): A sudden reversal or secret pact ("लेकिन यहाँ कहानी एक खौफनाक मोड़ लेती है..." / "Here is where the history books misled us...").
- Sections 5 to 7 (Deep Historical Chronology): Strategic battles, court intrigues, primary texts, diary accounts, and archaeological clues.
- Section 8 (The Climax & Collapse): The peak of the conflict, betrayal, or fall of the civilization.
- Section 9 (Archaeological Findings & Modern Discoveries): What modern excavations, satellite scans, or carbon dating revealed.
- Section 10 to 11 (Historical Lessons & Modern Parallels): The philosophical and existential mirror for our modern world.
- Section 12 (Outro & Call to Action): Powerful final thought, thought-provoking question, and call to subscribe.

VISUAL REQUIREMENTS:
- Every section MUST provide 3 distinct ENGLISH image queries (image_query, image_query_2, image_query_3) tailored to history:
  e.g., "ancient temple ruins aerial dramatic", "ancient battlefield armor close-up", "historical ancient parchment manuscript macro", "archaeological excavation artifacts museum".

Respond with ONLY a valid JSON object. No markdown fences, no extra text:

{{
  "title": "{research.get('video_title', '')}",
  "description": "{research.get('description', '')}",
  "tags": {json.dumps(research.get('tags', []))},
  "sections": [
    {{
      "id": 1,
      "section_type": "hook",
      "title": "On-screen chapter title",
      "narration": "Full, immersive narration text of at least 110-140 words...",
      "image_query": "dramatic historical establishing shot ancient ruins aerial",
      "image_query_2": "ancient stone artifact museum lighting macro",
      "image_query_3": "historical concept illustration dramatic lighting",
      "bullet_points": ["Key mystery 1", "Historical enigma 2"],
      "caption_text": "Short highlight caption for screen",
      "duration_seconds": 55
    }}
  ]
}}
"""
    print(f"   → Writing 15+ min epic history script ({'Hindi' if language == 'hi' else 'English'})…")
    raw = generate(prompt)
    script = extract_json(raw, "Longform Scriptwriter")

    if "sections" not in script or len(script["sections"]) < 8:
        raise ValueError(f"Script returned too few sections ({len(script.get('sections', []))}).")

    script["language"] = language
    script["video_type"] = "normal"
    return script


def _write_shorts_script(research: dict, language: str = "hi") -> dict:
    """
    Generates a tight 50-60 second YouTube Shorts script (3 sections, vertical format).
    """
    key_points_str = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(research.get("key_points", [])[:3]))

    lang_instruction = (
        "LANGUAGE: Write all narration in punchy, dramatic HINDI (हिंदी - Devanagari script). "
        "Image queries MUST be in ENGLISH for image searching."
        if language == "hi" else
        "LANGUAGE: Write narration in punchy, viral ENGLISH."
    )

    prompt = f"""You are a viral YouTube Shorts scriptwriter specializing in shocking historical facts and ancient mysteries.

Video topic: {research.get('topic', '')}
Title: {research.get('video_title', '')}
Hook question: {research.get('hook_question', '')}
Key points:
{key_points_str}
{_facts_block(research, 2000)}

Write a viral 50-60 second historical Short. Rules:
- Hook in the FIRST 3 seconds — an unbelievable fact about ancient history.
- Rapid pace, high intrigue.
- Total narration must be 120-150 words across 3 sections.
- 3 sections ONLY: hook (10-12s), revelation (30-35s), cta (8-10s).
- {lang_instruction}

Respond with ONLY a valid JSON object. No markdown fences, no extra text:

{{
  "title": "{research.get('video_title', '')} #Shorts #History",
  "description": "Shocking historical truth that history books never told you. #Shorts #History #AncientMysteries",
  "tags": {json.dumps(research.get('tags', []) + ["Shorts", "YouTubeShorts", "History", "AncientHistory"])},
  "sections": [
    {{
      "id": 1,
      "section_type": "hook",
      "title": "hook_internal",
      "narration": "First 35 words...",
      "image_query": "ancient empire ruins dark cinematic",
      "image_query_2": "ancient gold artifact mystery close up",
      "image_query_3": "ancient king statue dramatic lighting",
      "image_query_4": "historical battlefield dramatic aerial",
      "bullet_points": [],
      "caption_text": "",
      "duration_seconds": 12
    }},
    {{
      "id": 2,
      "section_type": "content",
      "title": "content_internal",
      "narration": "Core shocking revelation 80-90 words...",
      "image_query": "archaeological excavation discovery close up",
      "image_query_2": "ancient manuscript hieroglyphics macro",
      "image_query_3": "ancient army formation battle cinematic",
      "image_query_4": "lost city jungle ancient temple",
      "bullet_points": [],
      "caption_text": "",
      "duration_seconds": 35
    }},
    {{
      "id": 3,
      "section_type": "cta",
      "title": "cta_internal",
      "narration": "Final punchline and follow CTA 20 words...",
      "image_query": "ancient pyramid starry night sky",
      "image_query_2": "history museum dark cinematic lighting",
      "image_query_3": "ancient mystery artifacts glowing",
      "image_query_4": "ancient temple sunrise drone view",
      "bullet_points": [],
      "caption_text": "",
      "duration_seconds": 10
    }}
  ]
}}
"""
    print(f"   → Writing History Shorts script ({'Hindi' if language == 'hi' else 'English'})…")
    raw = generate(prompt)
    script = extract_json(raw, "Shorts scriptwriter")

    if "sections" not in script or len(script["sections"]) < 2:
        raise ValueError("Shorts script returned too few sections.")

    script["language"] = language
    script["video_type"] = "shorts"
    return script


def translate_script(script: dict, target_lang: str = "en") -> dict:
    """
    Translates a script's narration, titles, and captions to target_lang (e.g. 'en' or 'hi')
    while preserving all IDs, image queries, and section timing structures for auto-dubbing.
    """
    lang_name = "English" if target_lang == "en" else "Hindi"
    print(f"   → Translating script to {lang_name} for auto-dubbing…")

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

    prompt = f"""You are a professional audio-dubbing translator and localization expert.
Translate the following YouTube video script content into broadcast-quality, natural-sounding {lang_name}.
Keep the emotional intensity, pacing, and dramatic historical tone intact.
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
      "bullet_points": ["Translated Point 1", "Translated Point 2"]
    }}
  ]
}}
"""
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
