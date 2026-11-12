# Phase 21 — Publishing Cadence Preservation Amendment

**Repository:** `Ajaymalik-07/youtube-automation-history`  
**Channel:** **Stories Malik** (`UCeAbQ_380b_8Z98N9474w-g`)  
**Timezone:** `Asia/Kolkata` (IST, UTC+05:30)  
**Default Daily Cadence:** **1 Long-Form + 5 YouTube Shorts = 6 videos/day**

---

## 1. Pre-Implementation Audit Findings

Before modifying code, a full codebase and live-environment audit was conducted across scheduling, upload orchestration, quality gates, analytics, adaptive intelligence, OAuth credentials, and test isolation:

1. **Established Daily Schedule vs. Legacy Docs & Config Mismatch:**
   - `automation.py` (`DEFAULT_SLOTS`, `run_advance_pipeline`, `create_and_publish_shorts_batch`) and `.github/workflows/daily_youtube_automation.yml` already implemented **5 Shorts (`09:00, 12:00, 16:00, 19:00, 22:00 IST`) + 1 Long-form (`19:00 IST`) = 6 videos/day**.
   - However, `config.py` lacked canonical daily cadence counts (`LONGFORM_DAILY_COUNT`, `SHORTS_DAILY_COUNT`), and `SHORTS_UPLOAD_CONFIG["target_hours_ist"]` was set to `[10, 18]` while `uploader/youtube.py` (`calculate_next_scheduled_time`) hardcoded `[10, 18]` and `[19]` instead of reading configurable settings.
   - `docs/PUBLISHING_EXPERIMENT_PLAN.md` still documented an outdated Phase 14 schedule (2 long-form/week + 1 Short/day).

2. **Premature Schedule Mutation & Runtime Defects in `automation.py`:**
   - `adapt_upload_slot()` shifted `longform_target_hour_ist` after only `runs >= 2`, violating statistical sample-size discipline and risking silent schedule shifts on insufficient data.
   - `create_and_publish_single_short()` referenced `format_choice` without defining it (potential `NameError` when rendering unqueued Shorts).
   - `run_advance_pipeline()` treated `local://blocked_quality_gate/...` URLs as generic upload failures instead of logging an individual quality-gate block and continuing remaining daily slots.

3. **Analytics Metrics & Evaluation Policy Gaps:**
   - `analyze_shorts_performance()` and `analyze_longform_performance()` in `agents/growth_analyst.py` did not compute **median views per video**, **Shorts watch time / AVD**, **returning viewers**, **hook/duration breakdowns** (`duration_perf` was computed in `analyze_shorts_performance` but omitted from the return dictionary), or **production failure & quality-gate rejection rates**.
   - Neither `growth_analyst.py` nor `adaptive_engine.py` enforced a **rolling 30-day evaluation window**, incorporated **publication-age adjustment** into top-video rankings, or explicitly separated **correlation from demonstrated improvement**.
   - `agents/experiment_tracker.py` lacked `"publishing_frequency"` experiment validation enforcing single-variable isolation, hypothesis, measurable success criteria, baseline preservation, and minimum rolling 30-day baseline evidence.

4. **OAuth & Live Owner Analytics Audit:**
   - Auditing `youtube_token.pickle` via `uploader/oauth_manager.py` confirmed the token is valid with a refresh token, but currently holds only `https://www.googleapis.com/auth/youtube.upload`.
   - It lacks `https://www.googleapis.com/auth/youtube.readonly` and `https://www.googleapis.com/auth/yt-analytics.readonly`, causing `channels.list(mine=true)` to return HTTP 403 (`insufficientPermissions`).
   - Meanwhile, `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID` (YouTube Data API v3) are active and returned real channel telemetry (`channel_total_videos: 73`, `channel_total_views: 528`, `channel_subscribers: 2`, and 50 recent videos in the rolling 30-day sync).

5. **Test Isolation Defect:**
   - `tests/test_oauth_analytics.py` wrote mock test data (`vid_777`, `lf_01`, `sh_01`) directly into `output/historical_performance_db.json`, `output/analytics_snapshots.json`, and `output/weekly_analytics_report.json` during test runs.

---

## 2. Implemented Changes

### A. Configurable Cadence Preservation (`config.py`, `uploader/youtube.py`, `automation.py`)
- **`config.py`:**
  - Added `LONGFORM_DAILY_COUNT` (default `1`), `SHORTS_DAILY_COUNT` (default `5`), `TOTAL_DAILY_VIDEOS` (default `6`), `LONGFORM_TARGET_HOURS_IST` (default `[19]`), `SHORTS_TARGET_HOURS_IST` (default `[9, 12, 16, 19, 22]`), `EVALUATION_WINDOW_DAYS` (default `30`), `WEEKLY_REVIEW_INTERVAL_DAYS` (default `7`), and `PUBLISHING_CADENCE_POLICY` (`auto_reduce_frequency=False`, `require_human_approval=False`).
  - Synchronized `LONGFORM_UPLOAD_CONFIG` and `SHORTS_UPLOAD_CONFIG` with the canonical target hours and daily counts.
- **`uploader/youtube.py`:**
  - Updated `calculate_next_scheduled_time()` to read configurable slot hours from `config` and resolve `config.PUBLISHING_TIMEZONE` (`Asia/Kolkata`) via `ZoneInfo` with safe IST fallback.
- **`automation.py`:**
  - Added `get_effective_cadence()` and backward-compatible `load_schedule_state()` merging defaults with existing `output/automation_schedule.json`.
  - Updated `get_shorts_topics_for_day()`, `create_and_publish_shorts_batch()`, `run_advance_pipeline()`, and `print_status()` to respect configurable daily counts while preserving 1 Long-form + 5 Shorts = 6/day by default.
  - Fixed `format_choice` `NameError` in `create_and_publish_single_short()` by rotating across `SHORTS_FORMATS`.
  - Updated `adapt_upload_slot()` to require `min_runs_required=5` across at least 2 slots before logging a non-mutating recommendation, never reducing daily frequency or silently mutating the production schedule from small samples.
  - Updated `run_advance_pipeline()` and `create_and_publish_*` to treat `local://blocked_quality_gate/...` as an individual quality-gate block without halting the remaining daily slots.
  - Added `run_weekly_performance_review()` and `--weekly-review` CLI flag.

### B. Owner Analytics Connectivity & Limitation Reporting (`apis/youtube_analytics.py`, `apis/growth_database.py`)
- **`apis/growth_database.py`:**
  - Added optional `returning_viewers` and `hook_style` fields to `record_snapshot()`.
  - Added `get_videos_in_window(days=30, video_format=None)` for rolling 30-day filtering.
- **`apis/youtube_analytics.py`:**
  - Set `EVALUATION_WINDOW_DAYS = 30` as default for `get_video_analytics()` and `generate_weekly_format_report()`.
  - Added `get_analytics_capabilities_and_limitations()` to audit OAuth scopes and explicitly report missing scopes and YouTube Analytics API v2 constraints.
  - Added `sync_owner_channel_analytics(days_back=30)` connecting to owner YouTube Analytics v2 when permitted and falling back transparently to YouTube Data API v3 (`YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID`) with explicit limitation notices when OAuth scopes are missing.
  - Expanded `generate_weekly_format_report()` with `median_views`, `total_watch_time_minutes`, `avg_view_duration_seconds`, `returning_viewers`, long-form `total_impressions` / `avg_ctr`, and `analytics_limitations`.

### C. Separate Format Analysis, Metrics & Evaluation Policy (`agents/statistical_validator.py`, `agents/growth_analyst.py`)
- **`agents/statistical_validator.py`:**
  - Added `calculate_median()` and `compute_publication_age_days()`.
- **`agents/growth_analyst.py`:**
  - Updated `analyze_shorts_performance()` and `analyze_longform_performance()` to remain strictly separate and compute:
    - Median views per video (`median_views_per_video`)
    - Watch time (`total_watch_time_minutes`, `avg_watch_time_minutes`)
    - Average view duration (`avg_view_duration_seconds`, `median_view_duration_seconds`)
    - Average percentage viewed (`observed_avg_apv` / `avg_percentage_viewed`, `median_apv`)
    - Impressions and CTR for long-form (`total_impressions`, `avg_ctr`, `median_ctr`, plus explicit API availability note)
    - Subscriber conversion per 1,000 views (`sub_conversion_per_1k`)
    - Returning viewers (`returning_viewers` availability & explicit limitation note)
    - Breakdowns by **topic** (`topic_breakdown`), **format** (`format_breakdown` for Shorts), **hook** (`hook_breakdown` via `classify_hook_style()`), and **duration** (`duration_breakdown`)
    - Publication-age accounting (`avg_publication_age_days`, `median_age_adjusted_velocity`)
  - Added `analyze_production_and_quality_gates()` reporting tracked productions, quality-gate rejection rate (`quality_gate_rejection_rate_pct`), production failure rate (`production_failure_rate_pct`), and per-gate failure breakdown.
  - Updated `generate_growth_intelligence_dossier()` and `_generate_markdown_report()` to use the rolling 30-day window, embed `cadence_policy`, `production_reliability`, `analytics_limitations`, and distinguish `correlation_vs_demonstrated_improvement`.

### D. Adaptive Publishing Policy & Frequency Experiment Governance (`agents/experiment_tracker.py`, `agents/adaptive_engine.py`)
- **`agents/experiment_tracker.py`:**
  - Added `"publishing_frequency"` to `VALID_EXPERIMENT_CATEGORIES`.
  - Added `validate_frequency_experiment_proposal()` and `ExperimentTracker.create_frequency_experiment()` requiring: documented hypothesis, exactly 1 variable changed at a time (no simultaneous multi-variable edits), measurable success criteria, preserved baseline comparison, and sufficient 30-day baseline evidence (`>= 10` long-form and `>= 30` Shorts). Recorded experiments always set `auto_apply_to_schedule = False`.
- **`agents/adaptive_engine.py`:**
  - Added `evaluate_cadence_change_eligibility()` defaulting to `PRESERVE_ESTABLISHED_CADENCE` and blocking automatic frequency reduction.
  - Updated `select_next_controlled_experiment()` so `publishing_frequency` is never auto-selected to mutate the production schedule.
  - Updated `generate_weekly_adaptive_strategy()` and `_render_adaptive_strategy_md()` to use the rolling 30-day window and include `cadence_governance`, `shorts_performance`, `longform_performance`, `production_reliability`, `analytics_limitations`, and `correlation_vs_demonstrated_improvement`.

### E. Documentation & Test Suite Isolation
- Updated `docs/PUBLISHING_EXPERIMENT_PLAN.md` to preserve the 1 Long-form + 5 Shorts daily cadence.
- Fixed `tests/test_oauth_analytics.py` with `isolate_analytics_files` fixture so unit tests never mutate `output/`.
- Created `tests/test_phase21_cadence_preservation.py` covering all Phase 21 requirements.

---

## 3. Analytics Connectivity & Explicit Limitations

When `python automation.py --weekly-review` was executed against the live Stories Malik environment:
- **Synced Owner Data:** 50 recent videos (28 Shorts, 22 Long-form) within the rolling 30-day window were synced via YouTube Data API v3 (`youtube_data_api_key_fallback`).
- **Explicitly Reported Limitations:**
  1. `youtube_token.pickle` currently grants only `youtube.upload`, lacking `youtube.readonly` and `yt-analytics.readonly`; therefore private owner YouTube Analytics v2 metrics (watch time, AVD, APV, subscribers gained per video, and traffic sources) remain unavailable until the channel owner runs `python authorize_youtube.py`.
  2. Standard YouTube Analytics API v2 `reports.query` does not expose thumbnail impressions or impressions CTR without YouTube Studio reach-report access.
  3. YouTube Analytics API v2 carries ~48-hour processing latency for newly published videos.
  4. Second-by-second retention curves and Shorts `Viewed vs Swiped Away` ratios are not exposed in standard v2 dimensions.
  5. `returningViewers` is unavailable per-video in standard Analytics v2 queries.

---

## 4. Phase 21 Acceptance Criteria Verification

| Acceptance Criterion | Status | Evidence |
|---|---|---|
| Existing 5 Shorts + 1 long-form daily schedule preserved | **PASS** | `config.LONGFORM_DAILY_COUNT == 1`, `config.SHORTS_DAILY_COUNT == 5`, `TOTAL_DAILY_VIDEOS == 6`, `Asia/Kolkata`. |
| Schedule remains configurable & backward-compatible | **PASS** | Env vars + `load_schedule_state()` + `get_effective_cadence()` + `calculate_next_scheduled_time()`. |
| No mandatory human approval introduced | **PASS** | `PUBLISHING_CADENCE_POLICY["require_human_approval"] is False`; `is_eligible_for_upload()` autonomous. |
| Automated quality gates remain enforced per video | **PASS** | Individual failing videos return `local://blocked_quality_gate/...` without halting other daily slots. |
| Analytics connected to actual owner data where OAuth permits | **PASS** | `sync_owner_channel_analytics()` queries Analytics v2 when scoped and Data API v3 fallback otherwise. |
| Analytics limitations explicitly reported | **PASS** | `get_analytics_capabilities_and_limitations()` surfaced in weekly JSON/MD reports and CLI output. |
| No frequency reduction without documented evidence | **PASS** | `evaluate_cadence_change_eligibility()`, `adapt_upload_slot()`, and `validate_frequency_experiment_proposal()`. |
| Existing automated publishing & recovery behavior intact | **PASS** | Full `pytest` suite (`tests/test_automated_publishing.py`, `tests/test_phase21_cadence_preservation.py`, etc.) passing. |

