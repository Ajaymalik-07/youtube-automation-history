"""
YouTube Metadata & Title Optimization Engine
Replaces artificial checklist gamification with authentic metadata standards:
1. Generates 3 distinct title candidates: Search-Oriented, Story-Oriented, and Curiosity-Oriented.
2. Validates metadata integrity (clean tags, real section chapters, natural descriptions).
3. Eliminates spammy filler, forced "The Secret of", fake tags ("History 1"), and placeholder chapters.
"""
import re
import json
from typing import Optional, List, Dict, Any, Tuple
import config
from apis import seo


def generate_title_candidates(
    topic: str,
    context: str = "",
    language: str = "hi",
    preferred_style: Optional[str] = None,
) -> dict:
    """
    Generates 3 distinct title candidates:
    1. search_oriented: Optimized for high-intent search queries.
    2. story_oriented: Focuses on dramatic historical conflict and stakes.
    3. curiosity_oriented: Emphasizes the historical contradiction, discovery, or paradox.
    preferred_style: optional directive from Growth Intelligence Engine ('curiosity_oriented' | 'story_oriented' | 'search_oriented')
    """
    clean_topic = re.sub(r"[^\w\s-]", "", topic).strip()

    if language == "hi":
        res = {
            "search_oriented": f"{clean_topic}: संपूर्ण ऐतिहासिक सच",
            "story_oriented": f"{clean_topic} की खौफनाक दास्तान और अनसुना इतिहास",
            "curiosity_oriented": f"{clean_topic}: इतिहास की किताबों ने हमसे क्या छुपाया?",
        }
    else:
        res = {
            "search_oriented": f"{clean_topic}: Complete Historical Documentary",
            "story_oriented": f"The Rise and Fall of {clean_topic}",
            "curiosity_oriented": f"The Untold Truth Behind {clean_topic}",
        }

    valid_styles = ("search_oriented", "story_oriented", "curiosity_oriented")
    res["recommended_style"] = preferred_style if preferred_style in valid_styles else "curiosity_oriented"
    return res


def sanitize_title_duplicate_prefix(title: str) -> str:
    """
    Phase 27 Workstream 3: Removes redundant or duplicated hook prefixes before ':'
    (e.g. 'Shivajis secret escape: Shivaji's secret escape...', 'This 1600YearOld Iron: Why Has This 1,600-Year-Old Iron...',
    or multi-colon prefixes like 'समरट रहसय: Lost Wealth Secret: सम्राट अशोक...').
    """
    t = (title or "").strip()
    for _ in range(2):
        if ":" not in t:
            break
        prefix, rest = t.split(":", 1)
        prefix_clean = prefix.strip()
        rest_clean = rest.strip()
        if len(rest_clean) < 18 or not prefix_clean:
            break

        # Multi-colon prefix (e.g. 'Corrupted Hindi: English Hook: Actual Title')
        if ":" in rest_clean and len(prefix_clean.split()) <= 4:
            t = rest_clean
            continue

        # Pure-ASCII short prefix before a Devanagari Hindi title (e.g. 'Lost Wealth Secret: सम्राट अशोक...')
        dev_in_rest = sum(1 for ch in rest_clean if "\u0900" <= ch <= "\u097F")
        if prefix_clean.isascii() and len(prefix_clean.split()) <= 4 and dev_in_rest >= 4:
            t = rest_clean
            continue

        # Normalize punctuation/apostrophes/commas so 'Shivajis'/'1600YearOld' matches "Shivaji's"/"1,600-Year-Old"
        norm_rest = re.sub(r"[^a-z0-9\s]", "", rest_clean.lower())
        norm_rest_compact = norm_rest.replace(" ", "")
        p_words = [
            re.sub(r"[^a-z0-9]", "", w.lower())
            for w in prefix_clean.split()
        ]
        p_words = [w for w in p_words if len(w) >= 3]
        if p_words:
            matches = sum(1 for w in p_words if (w in norm_rest or w.rstrip("s") in norm_rest or w in norm_rest_compact))
            if matches >= max(1, len(p_words) // 2):
                t = rest_clean
                continue
        break
    return t


def validate_youtube_metadata(title: str, description: str, tags: list,
                              sections: list = None, is_shorts: bool = False) -> tuple[bool, list[str]]:
    """
    Validates YouTube metadata against platform best practices without corrupting text.
    Returns (is_valid: bool, issues: list[str]).
    """
    issues = []
    t = (title or "").strip()
    d = (description or "").strip()
    tg = list(tags or [])

    # Title checks
    if len(t) < 20:
        issues.append(f"Title is too short ({len(t)} chars, minimum 20 recommended).")
    elif len(t) > 100:
        issues.append(f"Title exceeds YouTube maximum length ({len(t)} chars, max 100).")
    if sanitize_title_duplicate_prefix(t) != t:
        issues.append("Title contains a redundant/duplicated hook prefix before ':'.")

    # Description checks
    if len(d) < 150:
        issues.append(f"Description is too brief ({len(d)} chars, minimum 150 recommended for SEO context).")
    elif len(d) > 5000:
        issues.append(f"Description exceeds YouTube limit ({len(d)} chars, max 5000).")

    # Tags check
    total_tag_chars = sum(len(x) for x in tg) + max(0, len(tg) - 1)
    if total_tag_chars > 495:
        issues.append(f"Tags exceed 500 character limit ({total_tag_chars} chars).")
    
    # Reject dummy filler tags
    if any(re.match(r"^history\s*\d+$", tag.strip().lower()) for tag in tg):
        issues.append("Contains dummy filler tags (e.g. 'History 1').")

    # Chapters check: reject placeholder chapters
    if "1:00 Chapter One" in d:
        issues.append("Contains placeholder fake chapters ('1:00 Chapter One').")

    is_valid = len(issues) == 0
    return is_valid, issues


def build_genuine_chapters(sections: list) -> str:
    """Builds authentic chapter timestamps derived strictly from actual section narration durations."""
    if not sections or len(sections) < 3:
        return ""

    lines = ["\n\n⏱ CHAPTERS", "─" * 30, "0:00 Introduction"]
    cursor = 0
    for s in sections[1:]:
        words = len(s.get("narration", "").split())
        dur = max(15, int(words / 120 * 60))
        cursor += dur
        m, sec = cursor // 60, cursor % 60
        chapter_title = s.get("title", f"Part {s.get('id', '')}")
        lines.append(f"{m}:{sec:02d} {chapter_title}")

    return "\n".join(lines) + "\n"


def optimize_for_100_percent(title: str, description: str, tags: list,
                              sections: list = None, topic: str = "",
                              is_shorts: bool = False, keyword: str = "") -> dict:
    """
    Non-destructive metadata optimizer that formats clean, production-ready metadata
    without spamming fake tags or arbitrary prefixing.
    """
    title = sanitize_title_duplicate_prefix((title or "").strip())
    description = (description or "").strip()
    tags = list(tags or [])
    sections = sections or []

    # 1. Determine keyword
    if not keyword:
        clean_topic = re.sub(r"[^\w\s]", "", topic or title).strip()
        words = [w for w in clean_topic.split() if len(w) > 3 and w.lower() not in ("what", "about", "with", "from", "video")]
        keyword = " ".join(words[:3]) if words else "Ancient History"

    # 2. Format Title cleanly without forced "The Secret of "
    if len(title) > 95:
        title = title[:92].rsplit(" ", 1)[0] + "..."
    elif len(title) < 25:
        title = f"{title} | Historical Documentary"

    # Caps ratio check
    letters = [c for c in title if c.isalpha()]
    if letters and (sum(c.isupper() for c in letters) / len(letters)) >= 0.7:
        title = title.title()

    # 3. Chapters in Description: only from real sections
    has_chapters = is_shorts or bool(re.search(r"(^|\n)0:00\s", description))
    if not has_chapters and sections and not is_shorts:
        genuine_chapters = build_genuine_chapters(sections)
        if genuine_chapters:
            description += genuine_chapters

    # 4. Organic CTA with canonical channel branding
    brand_name = getattr(config, "CHANNEL_NAME", "Stories Malik")
    cta_text = f"\n\n🔔 Subscribe to {brand_name} for weekly deep-dives into ancient history and verified documentary investigations!\n💬 Share your historical perspective in the comments below.\n"
    if not any(w in description.lower() for w in ("subscribe", "comment", "stories malik")):
        description += cta_text

    # 5. Clean, relevant tags (no dummy 'History 1' tags)
    clean_tags = [t.strip() for t in tags if t.strip() and not re.match(r"^history\s*\d+$", t.strip().lower())]
    historical_curated = [
        "Stories Malik", "History", "Ancient History", "Documentary",
        "Archaeology", "Indian History", "World History", "Ancient Civilizations"
    ]
    for h in historical_curated:
        if len(clean_tags) >= 12:
            break
        if h not in clean_tags and h.lower() not in [x.lower() for x in clean_tags]:
            clean_tags.append(h)

    # Keep under 490 chars
    while clean_tags and (sum(len(t) for t in clean_tags) + len(clean_tags) - 1) > 480:
        clean_tags.pop()

    # 6. Hashtags
    hashtags = re.findall(r"#\w+", description)
    if not hashtags:
        description += "\n\n#History #AncientIndia #Documentary #Archaeology #StoriesMalik"

    # Evaluate score using transparent seo.score
    res = seo.score(title, description, clean_tags, keyword=keyword, is_shorts=is_shorts)
    is_valid, validation_issues = validate_youtube_metadata(title, description, clean_tags, sections, is_shorts)

    return {
        "title": title,
        "description": description,
        "tags": clean_tags,
        "keyword": keyword,
        "score": res["score"],
        "checks": res["checks"],
        "is_valid": is_valid,
        "validation_issues": validation_issues,
        "ready_to_publish": is_valid,
    }
