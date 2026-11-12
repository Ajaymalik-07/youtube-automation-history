# Phase 21.1 — OAuth Reauthorization & Live Analytics Validation

**Repository:** `Ajaymalik-07/youtube-automation-history`  
**Branch:** `feature/youtube-growth-overhaul` (not merged to `main`)  
**Configured Channel:** **Stories Malik** (`UCb1BDNY8WxoD1q_UVyEmvuw`)  
**Timezone / Preserved Cadence:** `Asia/Kolkata` — 1 Long-form + 5 Shorts = 6 videos/day  

---

## 1. Pre-Implementation Audit Findings

1. **OAuth Token & Scope Audit (`youtube_token.pickle` & `.env`):**
   - `youtube_token.pickle` exists on disk, is valid (`valid=True`), and contains a refresh token (`has_refresh_token=True`).
   - However, it currently holds **only** `https://www.googleapis.com/auth/youtube.upload` and is missing:
     - `https://www.googleapis.com/auth/youtube.readonly`
     - `https://www.googleapis.com/auth/yt-analytics.readonly`
   - Calling `channels.list(mine=True)` with the current token returns HTTP 403 (`insufficientPermissions`), and `youtubeAnalytics.reports().query()` is gated out by `audit_token_scopes()`.

2. **Token Overwrite & Test Contamination Bugs Found & Fixed:**
   - **Token Overwrite Risk (`uploader/oauth_manager.py`):** `reauthorize_channel()` previously wrote the new token to `youtube_token.pickle` and `.env` (`YOUTUBE_TOKEN_BASE64`) **before** verifying granted scopes or channel ownership via `channels.list(mine=True)`. If an operator authorized the wrong Google account or unchecked a scope, the existing valid token and `.env` were already overwritten.
   - **Test-Induced `.env` Mutation (`tests/test_oauth_analytics.py` + `uploader/oauth_manager.py`):** Running `pytest` invoked `safe_refresh_credentials()` and `reauthorize_channel()` on `DummyCreds`, which overwrote `YOUTUBE_TOKEN_BASE64` in the repository's `.env` with pickled `DummyCreds`. This was caught during the audit, `.env` was immediately restored from the intact `youtube_token.pickle` on disk, and global test isolation was added in `tests/conftest.py`.
   - **Token Refresh Sync (`uploader/youtube.py`):** `_get_service()` refreshed expired tokens without synchronizing `YOUTUBE_TOKEN_BASE64` in `.env`.
   - **Public Fallback Misattribution (`apis/youtube_analytics.py`):** When OAuth Analytics scope was missing, `get_video_analytics(video_id)` called `get_channel_and_last_video_analytics()`, which substituted the *most recently uploaded* video's public stats regardless of `video_id`.
   - **Zero vs. Unavailable Coercion (`apis/growth_database.py`, `agents/growth_analyst.py`, `agents/adaptive_engine.py`):** Unavailable private metrics (`None`) were coerced to `0` / `0.0`, causing reports to display `0.0% APV` / `0.0 min` and causing `get_adaptive_production_brief()` to emit low-retention alerts from missing data.
   - **Duplicate Snapshots (`apis/growth_database.py`):** Repeated syncs in the same observation period appended duplicate entries to `snapshot_history`.

3. **Channel Identity Verification (Public Data API v3):**
   - `YOUTUBE_CHANNEL_ID` (`UCb1BDNY8WxoD1q_UVyEmvuw`) was verified via YouTube Data API v3 (`apis/youtube_stats.py`):
     - **Title:** `Stories Malik`
     - **Subscribers:** `2`
     - **Total Views:** `528`
     - **Total Videos:** `74`

---

## 2. Implemented Changes

### A. Safe OAuth Reauthorization & Channel Verification (`uploader/oauth_manager.py`, `authorize_youtube.py`, `uploader/youtube.py`)
- Added `verify_granted_scopes()` and `verify_channel_identity(creds, expected_channel_id=...)`.
- Updated `reauthorize_channel()` so:
  - It **never** overwrites `youtube_token.pickle` or `.env` until: (1) all 3 required scopes (`youtube.upload`, `youtube.readonly`, `yt-analytics.readonly`) are verified on `creds`, and (2) `channels.list(mine=True)` confirms the channel matches `expected_channel_id` (`UCb1BDNY8WxoD1q_UVyEmvuw`).
  - Existing tokens are backed up (`.bak`) and updated atomically via `.tmp` write/replace; `.env` is updated only after all checks succeed and only outside pytest (`_should_sync_env`).
  - Uses `bind_addr="127.0.0.1"` and restores `OAUTHLIB_INSECURE_TRANSPORT` in `finally`.
- Updated `authorize_youtube.py` to pass `expected_channel_id=config.YOUTUBE_CHANNEL_ID`.
- Updated `uploader/youtube.py` (`_get_service()`) to refresh tokens via `safe_refresh_credentials()`.

### B. Owner Analytics Separation, Deduplication & Unavailable Handling (`apis/growth_database.py`, `apis/youtube_analytics.py`)
- **`apis/growth_database.py`:**
  - `record_snapshot()` preserves `None` for unavailable metrics instead of coercing to `0`/`0.0`, stores `channel_id` and `owner_analytics_available`, and deduplicates `snapshot_history` entries per `(checkpoint, observation_period)` while preserving all distinct historical periods.
- **`apis/youtube_analytics.py`:**
  - `get_video_analytics()` never substitutes another video's stats and strictly keeps private owner metrics (`estimatedMinutesWatched`, `averageViewDuration`, `averageViewPercentage`, `subscribersGained`, `impressions`, `impressionClickThroughRate`, `returningViewers`) as `None` when OAuth scope is missing.
  - `sync_owner_channel_analytics()` verifies channel ownership against `config.YOUTUBE_CHANNEL_ID`, marks unavailable private metrics as `None`, detects `<48h` delayed videos (`delayed_videos`), and explicitly separates `metrics_retrieved`, `metrics_unavailable`, and `metrics_unavailable_at_video_level`.

### C. Growth Intelligence & Experiment Guards (`agents/growth_analyst.py`, `agents/adaptive_engine.py`, `agents/experiment_tracker.py`)
- Updated `analyze_shorts_performance()`, `analyze_longform_performance()`, `_generate_markdown_report()`, and `generate_weekly_adaptive_strategy()` to render `Unavailable (pending Analytics OAuth)` or `Unavailable via standard Analytics API v2` rather than `0.0` when metrics are `None`.
- Updated `get_adaptive_production_brief()` so missing APV/CTR never triggers false low-retention or low-CTR directives.
- Updated `ExperimentTracker.record_experiment_sample()` to reject `metric_value=None` (`ValueError`) so unsupported/unavailable metrics cannot influence experiment conclusions.

### D. Global Test Isolation (`tests/conftest.py`, `tests/test_phase21_1_live_analytics_validation.py`)
- Added `autouse` fixture `isolate_production_artifacts` in `tests/conftest.py` isolating `config.OUTPUT_DIR`, `DB_FILE`, `SNAPSHOT_FILE`, `WEEKLY_REPORT_FILE`, `PRODUCTION_DB_FILE`, `EXPERIMENTS_FILE`, `SCHEDULE_FILE`, `DIAGNOSTICS_DIR`, `TOKEN_FILE`, `save_env`, and `update_youtube_token_env`.
- Added 8 new tests in `tests/test_phase21_1_live_analytics_validation.py`.

---

## 3. Live Validation & Metric Distinction Matrix

Executed `.venv\Scripts\python.exe automation.py --weekly-review` and repeated `sync_owner_channel_analytics(days_back=30)` against live channel `UCb1BDNY8WxoD1q_UVyEmvuw`:

| Metric / Capability | Status in Live Environment | Classification |
|---|---|---|
| Channel identity & recent video IDs (`50` in 30d window: `28` Shorts, `22` Long-form) | Retrieved via YouTube Data API v3 (`youtube_data_api_key_fallback`) | Public Data API v3 |
| Public `views`, `likes`, `comments` | Retrieved per exact video ID | Public Data API v3 |
| `estimatedMinutesWatched`, `averageViewDuration`, `averageViewPercentage`, `subscribersGained`, `trafficSources` | Blocked (`OAuth token lacks yt-analytics.readonly`) — stored as `null`, rendered `Unavailable` | **Unavailable (OAuth Scope Blocker)** |
| `channels.list(mine=True)` owner upload listing | Blocked (`HTTP 403 insufficientPermissions`, lacks `youtube.readonly`) | **Unavailable (OAuth Scope Blocker)** |
| `impressions`, `impressionClickThroughRate` | Not exposed via standard Analytics API v2 `reports.query` | **Unavailable at API / Video Level** |
| `returningViewers` | Not exposed per-video in standard Analytics API v2 `reports.query` | **Unavailable at Video Level** |
| Newly published videos (`< 48h`) | Subject to YouTube ~48h Analytics reporting latency | **Delayed (Reporting Latency)** |
| Duplicate snapshot guard | Verified across back-to-back syncs (`snapshot_history` length remained `1` for `92kjsBopLOw`) | **PASS** |
| Mock data in production `output/` | Verified absent (`vid_777`, `lf_01`, `sh_01` purged; real `50` videos synced) | **PASS** |

---

## 4. Test Results

- **Full Suite (`.venv\Scripts\python.exe -m pytest`):** **155 passed in 10.21s** (0 failures, 0 skipped), including all 8 tests in `tests/test_phase21_1_live_analytics_validation.py` and all 9 tests in `tests/test_phase21_cadence_preservation.py`.
- **Publishing Safeguards:** Preserved `1` Long-form + `5` Shorts = `6/day` in `Asia/Kolkata`, zero mandatory human approval, and no automatic frequency reduction.

---

## 5. Unresolved Blockers & Exact Next Actions

### Unresolved Blocker
- **Interactive Google OAuth Consent Required:** `youtube_token.pickle` currently only holds `https://www.googleapis.com/auth/youtube.upload`. In this headless/automated agent session, Google's interactive browser consent screen cannot be completed without the channel owner signing in and checking all 3 permission boxes (`youtube.upload`, `youtube.readonly`, `yt-analytics.readonly`). Therefore, live owner Analytics API v2 retrieval (`watch_time`, `AVD`, `APV`, `subscribersGained`, `trafficSources`) could only be verified end-to-end via unit/integration tests with mocked Analytics API v2 responses, while live execution confirmed the exact OAuth scope failure and safe fallback/limitation reporting.

### Exact Next Actions (for the Channel Owner)
1. Run the interactive authorization script locally in a browser session signed into the **Stories Malik** (`UCb1BDNY8WxoD1q_UVyEmvuw`) Google account:
   ```bash
   python authorize_youtube.py
   ```
2. On the Google consent screen, check **all three** permission boxes (`Manage your YouTube videos`, `View your YouTube account`, and `View YouTube Analytics reports`) and click **Continue**.
   - `authorize_youtube.py` will verify all 3 scopes and confirm channel ID `UCb1BDNY8WxoD1q_UVyEmvuw` before atomically updating `youtube_token.pickle` and `.env` (`YOUTUBE_TOKEN_BASE64`).
3. If running GitHub Actions (`daily_youtube_automation.yml`), update the repository's `YOUTUBE_TOKEN_BASE64` secret with the updated value from `.env`.
4. Re-run the weekly review to populate live private owner Analytics v2 metrics into `output/historical_performance_db.json` and `output/weekly_growth_intelligence.md`:
   ```bash
   python automation.py --weekly-review
   ```
5. Verify owner analytics connection:
   ```bash
   python -c "from apis.youtube_analytics import get_analytics_capabilities_and_limitations; import json; print(json.dumps(get_analytics_capabilities_and_limitations(), indent=2))"
   ```
   Confirm `"owner_analytics_connected": true` and `"missing_scopes": []`.

