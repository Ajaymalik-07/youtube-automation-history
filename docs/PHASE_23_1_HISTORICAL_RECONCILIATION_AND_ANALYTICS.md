# Phase 23.1 — Historical Reconciliation & Analytics Activation

**Repository:** `Ajaymalik-07/youtube-automation-history`  
**Branch:** `feature/youtube-growth-overhaul` (`main` untouched)  
**Cadence Preserved:** 1 Long-form (`19:00 IST`) + 5 Shorts (`09:00, 12:00, 16:00, 19:00, 22:00 IST`) = 6 videos/day (`Asia/Kolkata`)

---

## 1. Branch & CI State Audit

- **Root cause of historical fragmentation:**
  - GitHub Actions (`daily_youtube_automation.yml`) on `main` ran autonomously through `2026-11-12` (`origin/main` at `1c5397a`), committing **only** `output/automation_schedule.json` (`105` `history_runs`, `64` `_url` slot keys, including scheduled `2026-11-13` slots).
  - On `main`, `.gitignore` still ignored `output/production_database.json`, `output/pending_uploads/`, `output/yaas_state.sqlite`, and `output/historical_performance_db.json`.
  - Meanwhile, Phase 21–23 development occurred on `feature/youtube-growth-overhaul` (where `output/automation_schedule.json` stopped at `2026-11-04` with `20` `history_runs`).
- **Safe branch-state strategy implemented:**
  - Added `load_git_ref_json(git_ref, repo_rel_path)` and `reconcile_branch_schedule_state(output_dir, git_ref="origin/main")` in `apis/state_store.py`.
  - Uses monotonic `merge_schedule_states()` to union `history_runs` and `_url` slot keys from `origin/main:output/automation_schedule.json` into local `output/automation_schedule.json` + `yaas_state.sqlite` without overwriting newer local state and without merging code into `main`.
  - Applied live sync: `local_history_runs: 20` + `incoming_history_runs: 105` -> `merged_history_runs: 105`, `new_url_keys_added: 55`.

---

## 2. Historical YouTube Reconciliation (25 Live Videos)

Enhanced `reconcile_channel_publications()` in `uploader/youtube.py` to inspect:
1. `output/production_database.json`
2. `output/automation_schedule.json` (both `history_runs` AND `*_url` slot keys)
3. `output/pending_uploads/*.json` and `output/scheduled_queue/*.json`
4. `output/yaas_state.sqlite` (`state_blobs` table)
5. `output/backups/*/automation_schedule.json` & `production_database.json`
6. Read-only `origin/main:output/automation_schedule.json` (only for live workspace runs; isolated tests default to `include_git_main_state=False`).

### Live Reconciliation Summary (`output/youtube_reconciliation_report.json`)
- **Channel ID:** `UCb1BDNY8WxoD1q_UVyEmvuw` (`ownership_mismatches: []`)
- **Live videos inspected:** `25`
- **Reconciliation coverage:** **`88.0%`** (`22 / 25`, up from `0.0%`)
- **4-Category Classification Breakdown:**
  1. `verified_production_record`: **`0`** (CI on `main` did not yet track `production_database.json`)
  2. `verified_upload_incomplete_local_history`: **`22`** (matched via CI-persisted `automation_schedule.json` `_url` slot keys & `history_runs`)
  3. `external_or_manual_upload`: **`0`**
  4. `unrecoverable_historical_record`: **`3`** (`80WvgmPVo6U`, `iknW0OgMcDE`, `F3Doom5zlvM` from `2026-11-09` — automated-style titles, zero local/SQLite/backup/manifest/`origin/main` git history; no metadata or analytics fabricated)

---

## 3. OAuth Analytics Status & Data Quality Guard

- **Current OAuth Token (`youtube_token.pickle`) Audit:**
  - `exists: true`, `has_refresh_token: true`
  - `granted_scopes`: `["https://www.googleapis.com/auth/youtube.upload"]`
  - `missing_scopes`: `["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]`
  - **Status:** **`BLOCKED`** for private YouTube Analytics API v2 (watch time, AVD, APV, subscribers gained, traffic sources).
- **Exact interactive local reauthorization command (run by channel owner):**
  ```powershell
  .venv\Scripts\python.exe authorize_youtube.py
  ```
- **Data Quality & Provenance Enforcement:**
  - Public Data API v3 (`youtube_data_api_key_fallback`) is never substituted for private owner analytics; unavailable private metrics remain `null`.
  - `agents/adaptive_engine.py` (`generate_weekly_adaptive_strategy`) now explicitly excludes any record where `owner_analytics_available is False`, `is_test_fixture` is truthy, or `data_provenance == "mock_or_test_data"` from APV statistical evaluation.

---

## 4. Regenerated Reports & Verification

- **Live `automation.py --weekly-review`:**
  - Synced `50` videos in `output/historical_performance_db.json` (public Data API stats, `owner_analytics_available=False`, `null` private metrics).
  - Reconciled `25` live videos (`88.0%` coverage).
  - Synced `output/yaas_state.sqlite` WAL ledger and created checksummed backup `output/backups/weekly_review_20261112T083419Z_609b`.
  - Regenerated all 6 reports (`weekly_shorts_performance_report.json`, `weekly_longform_performance_report.json`, `rolling_30day_growth_report.json`, `experiment_evaluation_report.json`, `youtube_reconciliation_report.json`, `persistent_state_health_report.json`).
- **Automated Test Suite:**
  - Added `tests/test_phase23_1_historical_reconciliation.py` covering 4-category reconciliation, zero fabrication, duplicate prevention, cross-branch schedule merging, SQLite/backup parity, and adaptive engine provenance guards.
  - Production Readiness: **Data integrity & historical reconciliation VERIFIED (`88.0%` coverage); Owner Analytics v2 remains `BLOCKED` pending interactive OAuth reauthorization (`authorize_youtube.py`).**

