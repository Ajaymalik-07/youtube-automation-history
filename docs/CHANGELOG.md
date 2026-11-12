# Changelog

All notable changes to the YouTube Agentic AI Studio (YAAS) codebase are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.7.0] - 2026-11-12 - Phase 23: Persistent Production State & 30-Day Growth Validation

### Added
- **Authoritative Persistent State Architecture (`apis/state_store.py`, `.gitignore`, `.github/workflows/daily_youtube_automation.yml`):**
  - Implemented git-tracked authoritative JSON state (`output/production_database.json`, `output/historical_performance_db.json`, `output/automation_schedule.json`, `output/growth_experiments.json`, `output/state_manifest.json`, `output/pending_uploads/*.json`) paired with a free local SQLite WAL ledger (`output/yaas_state.sqlite`), SHA-256 checksummed rolling backups (`output/backups/`), schema `v2` migrations, and monotonic `(revision, updated_at)` merge guards against stale overwrites.
  - Restricted GitHub Actions `actions/cache` strictly to transient pre-rendered media (`output/scheduled_queue`) while persisting authoritative JSON databases via CI commits and pre-run backups.
- **Channel Reconciliation & Historical Recovery (`uploader/youtube.py`):**
  - Extended `reconcile_channel_publications()` to correlate live uploads across production records, upload manifests, and `automation_schedule.json`, safely recover missing historical growth records (`owner_analytics_available=False`, no fabricated metadata), classify unmatched external uploads separately from local failed jobs, and track coverage history (`output/reconciliation_history.json`, `output/youtube_reconciliation_report.json`).
- **30-Day Growth Validation & Consolidated Reporting (`agents/growth_analyst.py`, `apis/youtube_analytics.py`):**
  - Added `generate_phase23_reports()` (and CLI flags `--phase23-reports`, `--backup-state` in `automation.py`) generating provenance-labeled reports: `persistent_state_health_report.json`, `youtube_reconciliation_report.json`, `weekly_shorts_performance_report.json`, `weekly_longform_performance_report.json`, `rolling_30day_growth_report.json`, and `experiment_evaluation_report.json`.
  - Updated `generate_weekly_format_report()` to query `HistoricalPerformanceDB` cleanly and keep unavailable private metrics as `None` instead of `0.0`.
- **Experiment Statistical Governance (`agents/experiment_tracker.py`):**
  - Added `CrossProcessFileLock` atomic persistence, confidence intervals, Welch's $t$-test uncertainty reporting, Bonferroni multiple-comparisons adjusted alpha ($0.05 / m$), and `register_controlled_experiment()`.
- **Validation Suite & Documentation (`tests/test_phase23_persistent_state_and_growth.py`, `docs/PHASE_23_PERSISTENT_STATE_AND_GROWTH_VALIDATION.md`):**
  - Added 7 Phase 23 tests covering schema migrations, stale-state conflict handling, SQLite WAL + backup restore, multi-process persistence, channel reconciliation, 30-day growth reports, and Bonferroni experiment governance.

---

## [2.6.1] - 2026-11-12 - Phase 22.1: Live Publishing Reliability & Production Verification

### Added
- **Cross-Process File Locking (`uploader/safety.py`, `automation.py`):**
  - Added `CrossProcessFileLock` using atomic `os.open(..., os.O_CREAT | os.O_EXCL)` lockfiles with PID/timestamp metadata, Win32-safe (`OpenProcess`) & POSIX-safe stale dead-PID detection (avoiding `os.kill(pid, 0)` `CTRL_C_EVENT` on Windows), and guaranteed `finally` release.
  - Protected `production_database.json`, `automation_schedule.json`, and per-slot execution (`_acquire_cross_process_slot_lock`) across separate OS processes.
- **9-Stage Production Reliability Reporting & Live Channel Reconciliation (`agents/growth_analyst.py`, `uploader/youtube.py`):**
  - Extended `generate_production_reliability_report()` with explicit Shorts vs Long-form separated counters (`production_completed`, `quality_gate_passed`, `upload_completed`, `youtube_processing_completed`, `scheduled`, `actually_published`, `analytics_collected`, `failed`, `recovered`).
  - Added `reconcile_channel_publications()` (integrated into `--weekly-review`) correlating live channel uploads against `production_database.json` and `automation_schedule.json`.
- **Phase 22.1 Validation Suite & Report (`tests/test_phase22_1_live_publishing_validation.py`, `docs/PHASE_22_1_LIVE_PUBLISHING_VALIDATION.md`):**
  - Added 5 multi-process locking, quota recovery preservation, state-machine completion guard, 9-stage reporting, and channel reconciliation tests.

### Fixed
- Fixed `pending_uploads` filename collision (`upload_<content_id_or_hash>_<basename>.json`) so concurrent/multi-slot Shorts sharing `final_short.mp4` never overwrite each other on quota reset, and ensured `retry_pending_uploads()` updates schedule slot flags upon verified recovery.
- Guarded `PublishingState.COMPLETED` in `record_production_state()` against false completion of uninitialized, `FAILED`, `BLOCKED_QUALITY_GATE`, or un-collected `ANALYTICS_PENDING` records.
- Added sibling `credits.json` third-party attribution formatting (`_with_credits_attribution`) in `uploader/youtube.py`, orphan `temp_audio_*.m4a` cleanup in `video/creator.py`, and multi-run GitHub Actions cache + branch-safe rebase in `.github/workflows/daily_youtube_automation.yml`.

---

## [2.6.0] - 2026-11-12 - Phase 22: Production Reliability & End-to-End Validation

### Added
- **Per-Job Isolation, Checkpointing & 19:00 IST Slot Safety (`automation.py`):**
  - Added deterministic `content_id`, unique `job_id`, isolated run directories (`output/runs/<content_id>/`, `output/shorts_batch/<date>_short_<NN>/`), and stage `checkpoint.json` resume across research, script, images, narration, and rendering.
  - Added thread-safe slot locks (`_SLOT_LOCKS`) and atomic file-replace (`os.replace`) persistence for `automation_schedule.json` and `production_database.json`, preventing concurrent 19:00 IST Short 4/5 and Long-form collisions.
  - Added `retry_pending_uploads()` recovery runner inside `run_advance_pipeline()` and `--retry-pending` CLI flag.
- **Hardened Rendering & Content QA Gates (`uploader/quality_gates.py`, `video/creator.py`, `video/stock.py`):**
  - Enforced real stream resolution checks (`1080x1920` Shorts, `>= 1920x1080` Long-form), strict duration caps (`SHORTS_MAX_SECONDS <= 60s`, Long-form `<= 900s`), optional FFmpeg `blackdetect` check (`>= 1.5s`), and SRT caption validation (`validate_srt_captions()`).
  - Enforced Shorts `SHORTS_MAX_SECONDS` (`59.5s` max clamp) in `video/creator.py` and thread-safe stock credit locking in `video/stock.py`.
- **Production Reliability Reporting (`agents/growth_analyst.py`):**
  - Added `generate_production_reliability_report()` (wired into `--weekly-review` and `--reliability-report`) outputting separated Shorts vs Long-form reliability metrics (`output/production_reliability_report.json` / `.md`) and explicit OAuth analytics `BLOCKED` status.
- **GitHub Actions Concurrency Guard (`.github/workflows/daily_youtube_automation.yml`):**
  - Added `concurrency` group to prevent overlapping scheduled workflow runs from racing on state persistence.
- **Validation & Documentation (`tests/test_phase22_production_reliability.py`, `docs/PHASE_22_PRODUCTION_RELIABILITY.md`):**
  - Added 9 Phase 22 reliability, concurrency, retry recovery, channel guard, and real FFmpeg QA tests.

### Fixed
- Fixed `uploader/youtube.py` returning `None` on YouTube processing failures (now returns `"local://failed_processing/..."`), added bounded chunk retries on 5xx errors, aligned quota exhaustion return string (`"local://pending_quota_reset/..."`), and added pre-upload channel identity verification against `YOUTUBE_CHANNEL_ID`.
- Fixed duplicate-upload prevention in `uploader/youtube.py` and `uploader/safety.py` to recognize `ANALYTICS_PENDING` and `UPLOADED_PRIVATE` states cleanly and record `recovered_count` across multi-hop retries (`FAILED` -> `METADATA_VALIDATED` -> `SCHEDULED`).
- Fixed `automation.py` pre-rendered queue reuse (`scheduled_queue/*.json`) dropping `research` and `script`, which previously triggered guaranteed quality-gate rejections on reuse, and prevented failed/blocked daemon uploads from deleting manifests or marking slots completed.
- Cleaned leaked pytest artifacts from live `output/pending_uploads/` and `output/diagnostics/`.

---

## [2.5.1] - 2026-11-12 - Phase 21.1: OAuth Reauthorization & Live Analytics Validation

### Added
- **OAuth Identity & Scope Guard (`uploader/oauth_manager.py`, `authorize_youtube.py`):**
  - Added `verify_granted_scopes()` and `verify_channel_identity()` checking `config.YOUTUBE_CHANNEL_ID` and all 3 `REQUIRED_SCOPES` **before** overwriting any valid token or `.env`.
  - Added atomic pickle writes and `_should_sync_env()` protection.
- **Duplicate Snapshot Prevention & Unavailable Metric Representation (`apis/growth_database.py`, `apis/youtube_analytics.py`):**
  - Preserved `None` (`Unavailable`) instead of coercing missing private metrics to `0`.
  - Deduplicated `snapshot_history` per `(checkpoint, observation_period)` while preserving prior checkpoints.
  - Added explicit `metrics_retrieved`, `metrics_unavailable`, `metrics_delayed`, and `metrics_unavailable_at_video_level` reporting.
- **Global Test Isolation & Validation Suite (`tests/conftest.py`, `tests/test_phase21_1_live_analytics_validation.py`):**
  - Added `isolate_production_artifacts` `autouse` fixture preventing pytest runs from mutating `output/` or `.env`.
  - Added 8 Phase 21.1 tests (total suite: **155 passing tests**).
  - Documented live audit, validation results, unresolved OAuth blocker, and exact next actions in `docs/PHASE_21_1_LIVE_ANALYTICS_VALIDATION.md`.

### Fixed
- Prevented `get_video_analytics()` from substituting last-video public stats for arbitrary `video_id` lookups.
- Prevented `get_adaptive_production_brief()` and `ExperimentTracker.record_experiment_sample()` from using unavailable (`None`) metrics to drive directives or experiment conclusions.
- Restored `.env` `YOUTUBE_TOKEN_BASE64` from `youtube_token.pickle` after discovering prior test contamination.

---

## [2.5.0] - 2026-11-12 - Phase 21: Publishing Cadence Preservation Amendment

### Added
- **Configurable Canonical Daily Cadence (`config.py`, `automation.py`, `uploader/youtube.py`):**
  - Preserved established default cadence: **1 Long-Form (`19:00 IST`) + 5 YouTube Shorts (`09:00, 12:00, 16:00, 19:00, 22:00 IST`) = 6 videos/day** in `Asia/Kolkata`, configurable via `.env` and `automation_schedule.json`.
  - Added `get_effective_cadence()`, `PUBLISHING_CADENCE_POLICY`, and `--weekly-review` CLI runner in `automation.py`.
- **Owner Analytics Sync & Limitation Reporting (`apis/youtube_analytics.py`, `apis/growth_database.py`):**
  - Added `get_analytics_capabilities_and_limitations()`, `sync_owner_channel_analytics(days_back=30)`, and rolling 30-day window filtering (`get_videos_in_window`).
- **Expanded Format-Separated Metrics & Production Reliability (`agents/growth_analyst.py`, `agents/statistical_validator.py`):**
  - Added median views per video, Shorts watch time & AVD, returning viewers tracking/limitation reporting, topic/format/hook/duration breakdowns, publication-age accounting, and `analyze_production_and_quality_gates()` (production failures & quality-gate rejection rates).
  - Explicitly separated correlation from statistically demonstrated improvement.
- **Adaptive Publishing Policy Governance (`agents/experiment_tracker.py`, `agents/adaptive_engine.py`):**
  - Added `validate_frequency_experiment_proposal()`, `create_frequency_experiment()`, and `evaluate_cadence_change_eligibility()` preventing silent schedule changes or frequency reductions without sufficient rolling 30-day evidence.
- **Phase 21 Report & Test Suite (`docs/PHASE_21_CADENCE_PRESERVATION.md`, `tests/test_phase21_cadence_preservation.py`):**
  - Documented pre-implementation audit findings, implementation details, and live analytics limitations; added 9 new Phase 21 tests and isolated `tests/test_oauth_analytics.py` from `output/`.

### Fixed
- Fixed `format_choice` `NameError` in `automation.py` (`create_and_publish_single_short`).
- Updated `run_advance_pipeline` to handle `local://blocked_quality_gate` individually without halting remaining daily slots.
- Prevented `adapt_upload_slot()` from shifting release slots on insufficient runs (`< 5`).
- Updated `docs/PUBLISHING_EXPERIMENT_PLAN.md` to reflect the preserved 1 Long-form + 5 Shorts daily cadence.

---

## [2.4.0] - 2026-11-11 - Phase 20: Adaptive AI Content Optimization Engine

### Added
- **Advanced Statistical Validation Engine (`agents/statistical_validator.py`):**
  - Sample size tiers enforcing rigorous conclusions: Insufficient (<3), Preliminary (3-4), Moderate (5-9), Sound (10+).
  - Two-tailed 95% confidence intervals utilizing Student's $t$-distribution critical values based on degrees of freedom.
  - Interquartile Range (IQR) outlier detection to filter viral anomalies from skewing baseline editorial decisions.
  - Duration-Adjusted Watch-Time Efficiency (WPMD = watch time / video duration) for unbiased long-form format comparisons.
  - Welch's two-sample $t$-test with Satterthwaite degrees of freedom and two-tailed $p$-values.
  - Logarithmic time-decay views normalization to compare fresh releases with mature library videos.
- **Channel Content Diversity & Repetition Control (`agents/diversity_monitor.py`):**
  - Entity frequency tracking across 24 historical personalities and 22 civilizations/dynasties.
  - Content pillar concentration monitor flagging any pillar exceeding 25% of recent uploads.
  - Underrepresented pillar detection prioritizing neglected eras for upcoming production cycles.
  - Jaccard token similarity engine flagging duplicate or repetitive opening hooks ($\ge 0.60$ threshold).
- **Adaptive Topic Opportunity Engine (`agents/adaptive_engine.py`):**
  - Generates weekly opportunity reports with 20 candidate topics (10 recommended Shorts, 5 long-form, 5 reserve).
  - Scored across 5 dimensions: pillar historical strength, retention trajectory, civilizational novelty, visual storytelling potential, and evidence depth.
  - Strict enforcement of Historical Research Quality Gate.
- **Adaptive Shorts Engine (`agents/adaptive_engine.py`, `agents/scriptwriter.py`):**
  - 8 canonical documentary formats with multi-factor hook evaluation across 7 criteria (clarity, visual storytelling, historical grounding, curiosity, audience relevance, time to payoff, narrative completeness).
- **Evidence-Grounded Long-Form Directives (`agents/adaptive_engine.py`, `agents/scriptwriter.py`):**
  - Dynamic subject-tailored reveal directives (stratigraphic/sonar trench layers for excavations, tactical terrain maps for military battles, metallurgy cross-sections for ancient architecture).
  - Abolished rigid "minute-3 map reveal" rule in favor of organic historical pacing.
- **Automated Controlled Experimentation (`agents/adaptive_engine.py`, `agents/experiment_tracker.py`):**
  - Single-variable experiment selector prioritizing active hypotheses with lowest sample size without confounding variables.
- **Adaptive Strategy Dossiers (`output/adaptive_content_strategy.json`, `output/adaptive_content_strategy.md`):**
  - Automated weekly strategy reporting covering statistical metrics, diversity health, top topics, and experiment progress.
- **Comprehensive Test Suite (`tests/test_adaptive_content_engine.py`):**
  - 15 new unit and integration tests covering statistical validation, diversity monitoring, hook ranking, dynamic directives, experiments, dossiers, and security.

### Changed
- `agents/topic_discovery.py`: Integrated `diversity_monitor` audit directly into weekly research reports.
- `agents/scriptwriter.py`: Connected multi-factor hook evaluator and dynamic long-form directives.
- `automation.py`: Integrated `get_production_run_brief()` into automated Shorts and long-form workflows.
- Test suite expanded from 123 to **138 passing tests** (100% pass rate).

---

## [2.3.0] - 2026-11-11 - Phase 19: Stories Malik YouTube Growth Intelligence Engine

### Added
- **Historical Performance Database (`apis/growth_database.py`):**
  - Immutable, versioned storage of analytics checkpoints (`HistoricalPerformanceDB`) in `output/historical_performance_db.json`.
  - Full tracking: video format, topic, content pillar (1-10), duration, views, engaged views, watch time, AVD, APV, impressions, CTR, traffic sources.
- **Stories Malik Growth Intelligence Engine (`agents/growth_analyst.py`):**
  - Independent Shorts performance analysis across 8 documentary formats with duration sweet-spot analysis and subscriber conversion tracking.
  - Independent Long-form analysis decoupling packaging diagnostics (impressions/CTR) from storytelling diagnostics (AVD/APV).
  - Content pillar intelligence evaluating all 10 historical pillars, identifying underexplored and high-converting categories.
  - Title and thumbnail empirical pattern analysis (Search vs Story vs Curiosity, style traction).
  - Automated weekly reports in JSON (`output/weekly_growth_intelligence.json`) and Markdown (`output/weekly_growth_intelligence.md`).
  - Real-time `get_adaptive_production_brief()` directive for production agents.
- **Controlled Growth Experiment Framework (`agents/experiment_tracker.py`):**
  - Tracks hypotheses, sample sizes, control vs test variants, and conclusions in `output/growth_experiments.json`.
  - Enforces minimum sample size thresholds ($\ge 3$ videos) to prevent premature winning claims.
- **Phase 19 Growth Intelligence Documentation (`docs/PHASE_19_GROWTH_INTELLIGENCE.md`):**
  - Comprehensive documentation of architecture, metrics, and adaptive production loops.

### Changed
- `agents/topic_discovery.py`: Integrated adaptive growth brief into topic opportunity scoring (+3.0 bonus for underexplored/high-converting pillars).
- `agents/researcher.py`: Directed topic discovery towards high-traction historical pillars.
- `agents/scriptwriter.py`: Injected retention directives into long-form and Shorts script generation prompts.
- `agents/seo_optimizer.py`: Added `preferred_style` support to `generate_title_candidates()`.
- `video/thumbnail.py`: Added `preferred_style` support to `generate_thumbnail_concepts()`.
- `automation.py`: Connected adaptive growth briefs and automated recording into `HistoricalPerformanceDB`.
- Test suite expanded from 111 to **123 passing tests** (`tests/test_growth_intelligence.py`).

---

## [2.2.1] - 2026-11-11 - Phase 18.1: Google OAuth Reauthorization & Live Analytics Completion

### Added
- **OAuth Manager & Security Governance (`uploader/oauth_manager.py`):**
  - Scope auditing (`audit_token_scopes`) identifying granted vs missing scopes with descriptive purposes.
  - Safe reauthorization flow (`reauthorize_channel`) featuring automatic backup (`.bak`), safe rollback on cancel/error, and synchronization to `.env`.
- **Enhanced Video Processing Verification (`uploader/youtube.py`):**
  - Checks channel ownership against authenticated channel ID.
  - Detects processing failures and upload rejections (`is_processing_failed`), halts publication, and records `PublishingState.FAILED`.
- **YouTube Analytics API v2 Engine Overhaul (`apis/youtube_analytics.py`):**
  - Structured queries for 7 official core metrics and traffic source breakdown.
  - Format-separated reporting (`generate_weekly_format_report`) evaluating Shorts vs Long-form against retention benchmarks (45% long-form, 70% Shorts) and proposing future experiments.
  - Canonical persistence of structured analytics to `output/analytics_snapshots.json`.
- **Phase 18.1 Completion Report (`docs/PHASE_18_1_OAUTH_ANALYTICS.md`):**
  - Canonical documentation of scope audit, reauthorization steps, and integration statuses.

### Changed
- `config.py`: Enforced required scopes (`youtube.upload`, `youtube.readonly`, `yt-analytics.readonly`) and added `update_youtube_token_env()`.
- `authorize_youtube.py`: Upgraded to interactive scope auditor with multi-permission consent guidance.
- Test suite expanded from 98 to **111 passing tests** (`tests/test_oauth_analytics.py`).

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
