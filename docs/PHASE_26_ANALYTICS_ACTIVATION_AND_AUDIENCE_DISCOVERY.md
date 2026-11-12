# Phase 26 — Analytics Activation & Audience Discovery Sprint

**Repository:** `Ajaymalik-07/youtube-automation-history`  
**Branch:** `feature/youtube-growth-overhaul` (`main` untouched)  
**Cadence Preserved:** 1 Long-Form (`19:00 IST`) + 5 Shorts (`09:00, 12:00, 16:00, 19:00, 22:00 IST`) = 6 videos/day (`Asia/Kolkata`)  
**Policy Guarantees:** Automated quality gates mandatory, no mandatory human approval, no automatic frequency reduction, zero paid APIs.

---

## 1. OAuth Activation Audit (`output/oauth_analytics_activation_report.json`)

- **Channel Identity:** `UCb1BDNY8WxoD1q_UVyEmvuw`
- **Status:** **`BLOCKED`** (interactive reauthorization required)
- **Granted Scope:** `["https://www.googleapis.com/auth/youtube.upload"]`
- **Missing Scopes:** `["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]`
- **Exact Local Reauthorization Command:**
  ```powershell
  .venv\Scripts\python.exe authorize_youtube.py
  ```

---

## 2. API Capability Matrix (`apis/youtube_analytics.py` — `get_api_capability_matrix`)

Generated in `output/api_capability_matrix.json`, distinguishing **YouTube Data API v3**, **YouTube Analytics API v2**, and **YouTube Studio-only** metrics:
- **Authorized today (Data API v3):** `views`, `likes_and_comments` (channel + video level, cumulative totals only).
- **Blocked pending `yt-analytics.readonly` (Analytics API v2, ~48h delay):** `watch_time_minutes`, `average_view_duration_seconds`, `average_percentage_viewed`, `subscribers_gained`, `traffic_sources`, `returning_viewers` (channel-level only).
- **Not exposed in Analytics API v2 (Studio UI / Reach Reports only):** `impressions_and_ctr`, `shorts_viewed_vs_swiped_and_retention_curves`.

---

## 3. Actual Published Content Audit (`output/actual_content_audit_report.json`)

Audited 5 recent published Shorts and 3 recent Long-form videos:
- **Shorts (`5` audited):**
  - `92kjsBopLOw` (`64.0s`, `0` views): Exceeds `60s` Shorts ceiling; redundant/duplicated hook prefix before colon.
  - `2IQAyTfqql8` (`69.0s`, `0` views): Exceeds `60s` Shorts ceiling.
  - `BnJVr_OL8_A` (`64.0s`, `0` views): Exceeds `60s` Shorts ceiling; redundant/duplicated hook prefix before colon.
  - `5yj8REbj0B8` (`59.0s`, `4` views): Redundant/duplicated hook prefix before colon.
  - `AWZehKAswCc` (`60.0s`, `1` view): Clean duration and title structure.
- **Long-Form (`3` audited):**
  - `zJ-VF6aCsc8` (`502.0s`, `0` views): Full 8m22s documentary duration.
  - `S-NzB9Ra4dg` (`73.0s`, `2` views): Under 3 minutes (misclassified Short); duplicated hook prefix before colon.
  - `I1w0I4eec8s` (`71.0s`, `8` views): Under 3 minutes (misclassified Short).

---

## 4. Audience Discovery & Experiment Readiness

- **`output/audience_discovery_report.json`:** Explicitly separates `measured_demand` (`28` Shorts / `33` views; `22` Long-form / `59` views; no fabricated search volumes) from `editorial_judgment` (topic diversity & pillar recommendations).
- **`output/experiment_readiness_report.json`:** `EXP-001`, `EXP-002`, and `EXP-003` remain `BLOCKED` pending `yt-analytics.readonly` / Studio reach access, with no metric substitution.

---

## 5. Verification

- **Tests Added:** `tests/test_phase26_analytics_and_discovery.py` (API capability matrix permissions, actual content audit duration/title checks, and Phase 26 report separation).
- **Live `--weekly-review`:** Completed cleanly; generated all 6 Phase 26 reports alongside Phase 23–25 reports and synced SQLite WAL + backup (`weekly_review_20261112T085658Z_723b`).

