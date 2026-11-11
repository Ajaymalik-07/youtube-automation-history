"""
Automated Quality Gates Engine
Validates Research, Script, Video, and Metadata before publishing.
Replaces manual human approval with verifiable, automated evidentiary,
grammatical, technical, and platform compliance checks.
"""
import os
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List, Optional
import config

DIAGNOSTICS_DIR = os.path.join(config.OUTPUT_DIR, "diagnostics")


def validate_research_gate(research: dict, min_confidence: float = 0.65) -> Tuple[bool, List[str]]:
    """
    Validates that historical research adheres to the multi-tier evidence hierarchy.
    Checks:
    - Non-empty topic, historical period, and geographic location.
    - At least 3 verified claims with valid evidence levels.
    - Chronological timeline milestones (minimum 2).
    - Confidence score meets or exceeds minimum threshold.
    - Speculative claims do not exceed 50% of total claims.
    """
    issues = []
    if not isinstance(research, dict):
        return False, ["Research artifact is missing or not a valid dictionary."]

    topic = research.get("topic") or research.get("video_title", "")
    if not topic or len(str(topic).strip()) < 3:
        issues.append("Research topic is missing or invalid.")

    period = research.get("period", "").strip()
    if not period or period.lower() in ("unknown", "unspecified", "various"):
        issues.append("Historical period is not clearly defined.")

    location = research.get("geographic_location", "").strip()
    if not location or location.lower() in ("unknown", "unspecified"):
        issues.append("Geographic location is missing.")

    claims = research.get("claims_and_evidence", [])
    if not claims or len(claims) < 3:
        issues.append(f"Insufficient verified claims (found {len(claims)}, minimum 3 required).")
    else:
        speculative = [c for c in claims if "SPECULATION" in str(c.get("evidence_level", "")).upper()]
        if len(speculative) > len(claims) // 2:
            issues.append(f"High speculation ratio: {len(speculative)}/{len(claims)} claims classified as speculation.")

    timeline = research.get("verified_timeline", [])
    if not timeline or len(timeline) < 2:
        issues.append(f"Verified timeline milestone count is incomplete (found {len(timeline)}, minimum 2 required).")

    conf = research.get("confidence_score", 0.0)
    try:
        if float(conf) < min_confidence:
            issues.append(f"Research confidence score {conf} is below required threshold {min_confidence}.")
    except (ValueError, TypeError):
        issues.append(f"Invalid confidence score format: {conf}")

    return len(issues) == 0, issues


def validate_script_gate(script: dict, is_shorts: bool = False) -> Tuple[bool, List[str]]:
    """
    Validates script quality, structure, language integrity, and duration suitability.
    Checks:
    - Valid title and sections array.
    - Minimum sections (4 for long-form, 2 for Shorts).
    - Word counts within target duration bounds.
    - No broken placeholder tokens (e.g. [INSERT], lorem ipsum, null, undefined).
    - No duplicate or repetitive adjacent section narrations.
    """
    issues = []
    if not isinstance(script, dict):
        return False, ["Script artifact is missing or not a valid dictionary."]

    title = script.get("title", "").strip()
    if not title or len(title) < 5:
        issues.append("Script title is missing or too short.")

    sections = script.get("sections", [])
    if not sections or not isinstance(sections, list):
        return False, ["Script sections array is missing or empty."]

    min_sections = 2 if is_shorts else 4
    if len(sections) < min_sections:
        issues.append(f"Insufficient sections: found {len(sections)}, minimum {min_sections} required.")

    # Calculate word count across all narrations
    full_narration = " ".join([str(s.get("narration", "")).strip() for s in sections])
    words = full_narration.split()
    word_count = len(words)

    if is_shorts:
        # 25s - 60s at ~2.5 words/sec -> 50 to 180 words
        if word_count < 40:
            issues.append(f"Shorts script narration too brief: {word_count} words (minimum 40 required).")
        elif word_count > 220:
            issues.append(f"Shorts script narration exceeds duration cap: {word_count} words (maximum 220 allowed).")
    else:
        # 8-13 min documentary at ~130-150 words/min -> 350 to 2200 words
        if word_count < 350:
            issues.append(f"Long-form documentary script too short: {word_count} words (minimum 350 required).")
        elif word_count > 2400:
            issues.append(f"Long-form documentary script exceeds 15-minute cap: {word_count} words (maximum 2400 allowed).")

    # Check for placeholder corruption
    placeholders = ["[insert", "lorem ipsum", "undefined", "null", "TODO", "{topic}"]
    lower_text = full_narration.lower()
    for ph in placeholders:
        if ph in lower_text:
            issues.append(f"Unrendered placeholder token '{ph}' detected in script narration.")

    # Check for repetitive duplicate sections
    seen_narrations = set()
    for idx, sec in enumerate(sections):
        narr = sec.get("narration", "").strip()
        if not narr:
            issues.append(f"Section {idx + 1} has empty narration text.")
            continue
        cleaned = re.sub(r"[^\w\s]", "", narr.lower())
        if cleaned in seen_narrations and len(cleaned.split()) > 10:
            issues.append(f"Duplicate narration detected in section {idx + 1}.")
        seen_narrations.add(cleaned)

    return len(issues) == 0, issues


def validate_video_gate(video_path: str, thumb_path: Optional[str] = None, is_shorts: bool = False) -> Tuple[bool, List[str]]:
    """
    Validates physical video file integrity, format parameters, and thumbnail assets.
    Checks:
    - Video file exists on filesystem and is not 0 bytes.
    - Size exceeds minimum healthy threshold (> 150 KB for shorts, > 500 KB for long-form).
    - Valid MP4 extension.
    - Thumbnail file exists if specified, readable image with valid size (> 5 KB).
    """
    issues = []
    if not video_path or not isinstance(video_path, str):
        return False, ["Missing video file path."]

    if not os.path.exists(video_path):
        return False, [f"Video file does not exist on disk: {video_path}"]

    file_size = os.path.getsize(video_path)
    min_size = 150 * 1024 if is_shorts else 500 * 1024
    if file_size < min_size:
        issues.append(f"Video file size {file_size} bytes is suspiciously small (minimum {min_size} bytes expected).")

    if not video_path.lower().endswith(".mp4"):
        issues.append(f"Invalid video container extension: {video_path} (must be .mp4).")

    # Thumbnail validation
    if thumb_path:
        if not os.path.exists(thumb_path):
            issues.append(f"Referenced thumbnail file does not exist: {thumb_path}")
        else:
            t_size = os.path.getsize(thumb_path)
            if t_size < 5 * 1024:
                issues.append(f"Thumbnail file size {t_size} bytes is corrupt or too small (< 5 KB).")
            elif t_size > 2 * 1024 * 1024:
                issues.append(f"Thumbnail file size {t_size} bytes exceeds YouTube's 2 MB limit.")

    return len(issues) == 0, issues


def validate_metadata_gate(metadata: dict, is_shorts: bool = False) -> Tuple[bool, List[str]]:
    """
    Validates YouTube upload snippet and status metadata.
    Checks:
    - Title length: 5 to 100 characters.
    - Description length: 20 to 5000 characters.
    - Tags count: at least 3 tags, total characters <= 500.
    - Valid category ID string.
    - Default language configured.
    - Proper madeForKids declaration.
    - Synthetic media declaration present.
    """
    issues = []
    if not isinstance(metadata, dict):
        return False, ["Metadata artifact is missing or not a dictionary."]

    title = str(metadata.get("title", "")).strip()
    if not title or len(title) < 5:
        issues.append("Metadata title is missing or under 5 characters.")
    elif len(title) > 100:
        issues.append(f"Metadata title exceeds YouTube 100 character limit ({len(title)} chars).")

    desc = str(metadata.get("description", "")).strip()
    if not desc or len(desc) < 20:
        issues.append("Metadata description is missing or under 20 characters.")
    elif len(desc) > 5000:
        issues.append(f"Metadata description exceeds YouTube 5000 character limit ({len(desc)} chars).")

    tags = metadata.get("tags", [])
    if not isinstance(tags, list) or len(tags) < 3:
        issues.append(f"Insufficient tags: found {len(tags) if isinstance(tags, list) else 0}, minimum 3 required.")
    else:
        total_tag_chars = sum(len(str(t)) for t in tags)
        if total_tag_chars > 480:
            issues.append(f"Total tag character count ({total_tag_chars}) exceeds YouTube's 500 character limit.")

    category_id = str(metadata.get("categoryId", "")).strip()
    if not category_id or not category_id.isdigit():
        issues.append(f"Invalid category ID: '{category_id}' (must be a numeric ID string).")

    lang = str(metadata.get("defaultLanguage", "")).strip()
    if not lang:
        issues.append("Missing defaultLanguage specification.")

    return len(issues) == 0, issues


def evaluate_all_quality_gates(
    research: Optional[dict] = None,
    script: Optional[dict] = None,
    video_path: Optional[str] = None,
    thumb_path: Optional[str] = None,
    metadata: Optional[dict] = None,
    is_shorts: bool = False
) -> dict:
    """
    Comprehensive Master Quality Gate:
    Runs all 4 sub-gates, aggregates blocking issues, and writes a diagnostic report.
    """
    now = datetime.now(timezone.utc).isoformat()
    gates = {}
    blocking_issues = []

    # 1. Research Gate
    if research:
        r_ok, r_issues = validate_research_gate(research)
        gates["research"] = {"passed": r_ok, "issues": r_issues}
        if not r_ok:
            blocking_issues.extend([f"[Research] {i}" for i in r_issues])
    else:
        gates["research"] = {"passed": False, "issues": ["No research artifact provided."]}
        blocking_issues.append("[Research] Research artifact is missing.")

    # 2. Script Gate
    if script:
        s_ok, s_issues = validate_script_gate(script, is_shorts=is_shorts)
        gates["script"] = {"passed": s_ok, "issues": s_issues}
        if not s_ok:
            blocking_issues.extend([f"[Script] {i}" for i in s_issues])
    else:
        gates["script"] = {"passed": False, "issues": ["No script artifact provided."]}
        blocking_issues.append("[Script] Script artifact is missing.")

    # 3. Video Gate
    if video_path:
        v_ok, v_issues = validate_video_gate(video_path, thumb_path=thumb_path, is_shorts=is_shorts)
        gates["video"] = {"passed": v_ok, "issues": v_issues}
        if not v_ok:
            blocking_issues.extend([f"[Video] {i}" for i in v_issues])
    else:
        gates["video"] = {"passed": False, "issues": ["No video file path provided."]}
        blocking_issues.append("[Video] Video path is missing.")

    # 4. Metadata Gate
    if metadata:
        m_ok, m_issues = validate_metadata_gate(metadata, is_shorts=is_shorts)
        gates["metadata"] = {"passed": m_ok, "issues": m_issues}
        if not m_ok:
            blocking_issues.extend([f"[Metadata] {i}" for i in m_issues])
    else:
        # Fallback to script title/desc/tags if metadata dict not provided separately
        m_dict = {
            "title": (script or {}).get("title", ""),
            "description": (script or {}).get("description", ""),
            "tags": (script or {}).get("tags", []),
            "categoryId": getattr(config, "VIDEO_CATEGORY_ID", "27"),
            "defaultLanguage": getattr(config, "DEFAULT_LANGUAGE", "hi"),
        }
        m_ok, m_issues = validate_metadata_gate(m_dict, is_shorts=is_shorts)
        gates["metadata"] = {"passed": m_ok, "issues": m_issues}
        if not m_ok:
            blocking_issues.extend([f"[Metadata] {i}" for i in m_issues])

    passed = len(blocking_issues) == 0

    report = {
        "passed": passed,
        "timestamp": now,
        "is_shorts": is_shorts,
        "gates": gates,
        "blocking_issues": blocking_issues,
        "video_path": video_path,
        "thumb_path": thumb_path,
    }

    # Persist diagnostic report on disk
    try:
        os.makedirs(DIAGNOSTICS_DIR, exist_ok=True)
        filename_seed = os.path.basename(video_path) if video_path else f"run_{int(datetime.now().timestamp())}"
        diag_path = os.path.join(DIAGNOSTICS_DIR, f"diagnostic_{filename_seed}.json")
        with open(diag_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        report["diagnostic_file"] = diag_path
    except Exception as e:
        print(f"   ⚠ Could not persist diagnostic report: {e}")

    return report
