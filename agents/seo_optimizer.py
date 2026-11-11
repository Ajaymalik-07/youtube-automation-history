"""
YouTube Metadata & Title Optimization Engine
Replaces artificial checklist gamification with authentic metadata standards:
1. Generates 3 distinct title candidates: Search-Oriented, Story-Oriented, and Curiosity-Oriented.
2. Validates metadata integrity (clean tags, real section chapters, natural descriptions).
3. Eliminates spammy filler, forced "The Secret of", fake tags ("History 1"), and placeholder chapters.
"""
import re
import json
import config
from apis import seo


def generate_title_candidates(topic: str, context: str = "", language: str = "hi") -> dict:
    """
    Generates 3 distinct title candidates:
    1. search_oriented: Optimized for high-intent search queries.
    2. story_oriented: Focuses on dramatic historical conflict and stakes.
    3. curiosity_oriented: Emphasizes the historical contradiction, discovery, or paradox.
    """
    clean_topic = re.sub(r"[^\w\s-]", "", topic).strip()

    if language == "hi":
        return {
            "search_oriented": f"{clean_topic}: संपूर्ण ऐतिहासिक सच",
            "story_oriented": f"{clean_topic} की खौफनाक दास्तान और अनसुना इतिहास",
            "curiosity_oriented": f"{clean_topic}: इतिहास की किताबों ने हमसे क्या छुपाया?",
        }

    return {
        "search_oriented": f"{clean_topic}: Complete Historical Documentary",
        "story_oriented": f"The Rise and Fall of {clean_topic}",
        "curiosity_oriented": f"The Untold Truth Behind {clean_topic}",
    }


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
    title = (title or "").strip()
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
