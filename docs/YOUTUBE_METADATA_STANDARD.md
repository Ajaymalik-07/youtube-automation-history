# YouTube Metadata and Upload Parameters Standard

**Channel:** Stories Malik (`@StoriesMalik`)  
**Scope:** Video Resource Snippet, Status Parameters, Regional Category Verification & Upload Rules  
**Status:** Canonical & Enforced (Phase 17 Overhaul)  

---

## 1. Editorial Vision: Authentic Discovery over Checklist Gamification

A static "100/100" numerical checklist score is an internal rule-based heuristic, **not** the YouTube recommendation algorithm. Artificially stuffing descriptions with fake tags (`History 1`, `History 2`), repetitive boilerplate, or fabricated chapters (`0:00 Introduction\n1:00 Chapter One`) degrades viewer trust and triggers YouTube spam filters.

Stories Malik replaces artificial SEO gamification with verified, platform-compliant metadata standards.

---

## 2. Complete Video Metadata Structure

Every published video carries complete, verified metadata:

1. **Title:** Accurate, compelling candidate selected from Search, Story, or Curiosity models (under 100 characters).
2. **Description (under 5,000 characters):**
   - **First 200 Characters:** Natural summary establishing the historical event, ruler, and stakes.
   - **Body:** 2–3 paragraphs providing historical background and archaeological context.
   - **Genuine Chapters (Long-form):** Timestamps derived strictly from actual narration section timings (`0:00 Intro`, `1:15 Setting the Stage`, etc.). Placeholder chapters are forbidden.
   - **Archival Citations:** Links to primary inscriptions, ASI reports, or museum collections.
   - **Organic Call-to-Action:** Dynamic CTA inviting subscription to `Stories Malik`.
   - **Hashtags:** 3 to 5 targeted historical hashtags (`#History #AncientIndia #Documentary #Archaeology #StoriesMalik`) placed cleanly at the conclusion.
3. **Tags:** 8 to 14 relevant historical keywords under 480 total characters.
4. **Category:** Verified regional category ID (default: `27` for Education).
5. **Language Settings:** `snippet.defaultLanguage = "hi"` (Hindi), with English subtitle tracks where auto-dubbed.

---

## 3. Video Resource Status Fields

Every `videos.insert` call explicitly configures YouTube status parameters:

| Field | Configuration | Rationale |
|---|---|---|
| `status.privacyStatus` | `"private"` (scheduled) / `"public"` (immediate) | Governed by active upload mode |
| `status.publishAt` | RFC 3339 UTC string with `Z` | Auto-releases video at designated IST slot |
| `status.license` | `"youtube"` | Standard YouTube license |
| `status.embeddable` | `True` | Allows video embedding on educational portals |
| `status.publicStatsViewable` | `True` | Transparent audience reach reporting |
| `status.selfDeclaredMadeForKids` | `False` | Enables comments, notifications, and full monetization |
| `status.containsSyntheticMedia` | `True` | Mandatory YouTube disclosure for AI-narrated documentary content |

---

## 4. Regional Category Verification

Rather than assuming category IDs are universal, `verify_category_id(youtube, category_id, region_code="IN")` queries `videoCategories.list` for the target region to guarantee the ID is valid before sending upload payloads.

---

## 5. Notification Governance

To prevent viewer notification fatigue while maintaining maximum reach:
- **Long-Form Documentaries:** `notifySubscribers = True` (informs community of major weekly releases).
- **Daily Shorts:** `notifySubscribers = False` (Shorts are distributed natively via the vertical Shorts Feed rather than clogging subscriber notification trays).
