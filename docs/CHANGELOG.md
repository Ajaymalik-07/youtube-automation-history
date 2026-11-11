# Changelog

All notable changes to the YouTube Agentic AI Studio (YAAS) codebase are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] - 2026-11-11 - Phase 18: Production Readiness, Live YouTube Validation & Hardening

### Added
- **Explicit Content Disclosure Classifier (`uploader/quality_gates.py`):**
  - Programmatic determination of `selfDeclaredMadeForKids` based on audience analysis and COPPA guidelines.
  - Granular `containsSyntheticMedia` classification distinguishing AI voice synthesis / generative visuals from archival footage.
- **Deep Video Integrity Verification (`uploader/quality_gates.py`):**
  - Integrated `ffprobe` container inspection for `moov` atom validation, stream detection, aspect ratio confirmation, and audio presence.
- **Production Readiness & Hardening Audit Report (`docs/PHASE_18_PRODUCTION_READINESS.md`):**
  - Full PASS/FAIL/BLOCKED audit of live APIs, OAuth credentials, video renders, and failure recovery.
- **Visual Validation Asset Generation:**
  - Extracted representative 1080p and 9:16 verification frames with verified Devanagari text rendering and mobile safe zones.

### Changed
- `uploader/youtube.py`: Connected `classify_content_disclosures` directly to YouTube API `status` insertion payload.
- `config.py`: Hardened stdout/stderr UTF-8 reconfigure for Windows console compatibility.
- `tests/test_automated_publishing.py`: Expanded test suite to 98 tests covering disclosure classification, container validation, and restart idempotency.

---

## [2.1.0] - 2026-11-11 - Phase 17: Fully Automated YouTube Publishing & Scheduling

### Added
- **Automated Quality Gates Engine (`uploader/quality_gates.py`):**
  - Independent validation of Research evidence, Script structure/duration, Video file integrity, and Metadata parameters.
  - Automatic persistence of diagnostic reports to `output/diagnostics/` when validation fails.
- **18-State Production Lifecycle Machine (`uploader/safety.py`):**
  - Replaced manual approval with autonomous 18-stage progression: `TOPIC_SELECTED`, `RESEARCH_IN_PROGRESS`, `RESEARCH_VALIDATED`, `SCRIPT_GENERATED`, `SCRIPT_VALIDATED`, `VIDEO_RENDERING`, `VIDEO_RENDERED`, `VIDEO_VALIDATED`, `METADATA_VALIDATED`, `UPLOAD_QUEUED`, `UPLOADING`, `UPLOADED_PRIVATE`, `SCHEDULED`, `PUBLISHED`, `ANALYTICS_PENDING`, `COMPLETED`, `FAILED`, `BLOCKED_QUALITY_GATE`.
  - Automated upload eligibility verification (`is_eligible_for_upload`).
- **Autonomous Publishing & Scheduling Modes (`uploader/youtube.py`, `config.py`):**
  - `SCHEDULED_PUBLICATION` (default production mode): Private upload with future `publishAt` ISO 8601 UTC timestamp calculated in `Asia/Kolkata` (19:00 IST for long-form, 10:00 & 18:00 IST for Shorts).
  - `IMMEDIATE_PUBLICATION`: Public upload without `publishAt`.
  - `PRIVATE_ARCHIVE`: Private upload without `publishAt`.
- **Post-Upload Processing Verification (`uploader/youtube.py`):**
  - Inspection of `uploadStatus` and `processingDetails` via YouTube API `videos.list`.
- **Synthetic Media Disclosure & Parameter Governance:**
  - Mandatory YouTube `containsSyntheticMedia: True` disclosure for AI documentary narration/illustrations.
  - Configurable subscriber notification flags (enabled for long-form, disabled for Shorts).
- **Idempotent Duplicate Prevention:**
  - Prevents re-uploading already scheduled or published videos.
- **Automated Publishing Standard (`docs/AUTOMATED_PUBLISHING_STANDARD.md`):**
  - Comprehensive documentation of state machine, upload parameters, scheduling rules, and error recovery.

### Changed
- `pipeline.py`: Replaced blocking manual review server with automated quality gate evaluation and direct autonomous scheduled upload.
- `automation.py`: Switched queue manifest states to `UPLOAD_QUEUED` and wired research artifacts into automated uploads.
- `review/app.py`: Updated endpoints to display automated quality reports rather than serving as a blocking gate.

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
