# Changelog

All notable changes to the YouTube Agentic AI Studio (YAAS) codebase are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-11-11 - Overhaul: Hindi-First Historical Documentary System

### Added
- **Canonical Channel Configuration (`config.py`):** Established `Stories Malik` as canonical channel name, `DEFAULT_LANGUAGE="hi"`, `SECONDARY_LANGUAGE="en"`, and `TARGET_TIMEZONE="Asia/Kolkata"`.
- **Historical Evidence Hierarchy (`apis/knowledge.py`, `agents/researcher.py`):**
  - Replaced physics arXiv searches with 6-tier historical evidence framework: Government Archives, Academic Peer-Reviewed Journals (Crossref), Historical Archives (Archive.org), Archaeological Publications, and Primary Documents.
  - Implemented `validate_research_quality_gate()` to prevent ungrounded claims from reaching production.
- **Historical Content Strategy (`agents/topic_discovery.py`):**
  - Established 10 Historical Content Pillars.
  - Transparent 8-dimensional topic scorecard evaluating audience demand, evidence availability, visual storytelling, and historical significance.
  - Containment and Jaccard deduplication engine.
- **Long-Form Documentary Engine (`agents/scriptwriter.py`):**
  - Structured 8–13 minute documentary scripts (<14:30 safe cap, 950–1250 words, 8–10 chapters).
  - Built-in `validate_script_quality_gate()`.
- **Dedicated 8-Format Shorts Engine (`agents/scriptwriter.py`):**
  - Independent 4-stage storytelling: 0-2s Hook, 2-10s Context, 10-40s Main Narrative, Final Payoff.
  - Multi-candidate hook generation and selection across 8 distinct documentary formats.
- **Devanagari Font & Grapheme Preservation (`video/fonts.py`):**
  - Unicode NFC normalization (`unicodedata.normalize('NFC', text)`).
  - `split_devanagari_graphemes()` ensuring consonants, matras, viramas, and nuktas are never severed during text wrapping.
- **Authentic Metadata & 3 Title Candidates (`agents/seo_optimizer.py`):**
  - Replaced forced `"The Secret of "` prefixing with Search, Story, and Curiosity candidate generation.
  - Genuine chapter generation derived from actual script section narration timings.
  - `validate_youtube_metadata()` for policy adherence and character length limits.
- **Official YouTube Analytics API v2 (`apis/youtube_analytics.py`):**
  - Track watch time, average view duration (AVD), average percentage viewed (APV), subscriber conversion, and traffic source breakdowns.
  - Snapshot persistence engine across 24h, 48h, 7d, and 28d intervals.
- **Growth Analysis Engine (`agents/growth_analyst.py`):**
  - Topic cluster distribution, retention drop-off diagnosis, and evidence-grounded weekly recommendations.
- **Publishing Safety State Machine & Approval Gates (`uploader/safety.py`, `uploader/youtube.py`):**
  - 10 validated lifecycle states from `DRAFT` to `PUBLISHED`.
  - Mandatory human approval record required prior to upload.
  - Default `privacyStatus: "private"` for new uploads.
- **Graceful Review Server (`review/app.py`):**
  - Replaced destructive `os.kill(os.getpid(), 9)` with cooperative `werkzeug.serving.make_server` thread shutdown.
- **Security & Quality Assurance (`tests/`):**
  - 88 automated pytest tests covering unit, integration, visual rendering, and security audits.

### Changed
- `uploader/youtube.py`: Defaulted privacy status to `"private"` or `"unlisted"` instead of `"public"`.
- `automation.py`: Integrated genuine historical research for Shorts, and wired production state machine into scheduled queues.
- `video/creator.py`: Fixed `_draw_shorts_caption()` to use dynamic frame resolution `(fw, fh)` instead of hardcoded 16:9 canvas dimensions.
- `video/stock.py`: Replaced sci-fi neon city fallback queries with authentic historical architectural queries.

### Fixed
- Fixed unhandled Devanagari text breaking and conjunct detachment on Windows PIL systems without RAQM.
- Fixed process termination crash in review dashboard.
- Fixed topic deduplication undercounting for long compound historical titles.
