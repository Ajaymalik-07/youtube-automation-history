# Phase 25 — 30-Day Audience Growth Execution & Controlled Experimentation

**Repository:** `Ajaymalik-07/youtube-automation-history`  
**Branch:** `feature/youtube-growth-overhaul` (`main` untouched)  
**Cadence Preserved:** 1 Long-Form (`19:00 IST`) + 5 Shorts (`09:00, 12:00, 16:00, 19:00, 22:00 IST`) = 6 videos/day (`Asia/Kolkata`)  
**Policy Guarantees:** Automated quality gates mandatory, no mandatory human approval, no automatic frequency reduction, zero paid APIs.

---

## 1. Analytics Readiness Gate

- **Channel Identity:** `UCb1BDNY8WxoD1q_UVyEmvuw`
- **OAuth Token (`youtube_token.pickle`):**
  - Granted: `["https://www.googleapis.com/auth/youtube.upload"]`
  - Missing: `["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]`
  - `owner_analytics_connected`: `false`
- **Gate Result (`ExperimentTracker.apply_analytics_readiness_gate`):**
  - All 3 analytics-dependent experiments (`EXP-001`, `EXP-002`, `EXP-003`) are explicitly marked **`BLOCKED`** rather than simulating missing metrics:
    - `EXP-001` (`short`, `average_percentage_viewed`): `BLOCKED` — OAuth token lacks `yt-analytics.readonly`.
    - `EXP-002` (`longform`, `ctr`): `BLOCKED` — YouTube Analytics API v2 does not expose impressions/CTR without Studio reach-report access.
    - `EXP-003` (`longform`, `average_percentage_viewed`): `BLOCKED` — OAuth token lacks `yt-analytics.readonly`.

---

## 2. Established 30-Day Baseline (`output/phase25_30day_growth_evaluation.json`)

- **Shorts Baseline (`28` videos, public Data API v3):**
  - `median_views`: **`1.0`** (`total_views: 33`, `median_publication_age_days: 3.45`)
  - `watch_time_minutes`, `average_view_duration_seconds`, `average_percentage_viewed`, `impressions`, `ctr`, `subscribers_gained`: **`null` (unavailable)**
- **Long-Form Baseline (`22` videos, public Data API v3):**
  - `median_views`: **`0.0`** (`total_views: 59`, `median_publication_age_days: 4.1`)
  - `watch_time_minutes`, `average_view_duration_seconds`, `average_percentage_viewed`, `impressions`, `ctr`, `subscribers_gained`: **`null` (unavailable)**
- **Excluded Mock/Test Fixtures:** `0`

---

## 3. Experiment Register & 30-Day Findings

- **Statistically Supported Findings:** `[]` (none — all 3 controlled experiments are `BLOCKED` pending owner analytics & sufficient samples).
- **Directional Observations:** `28` Shorts (`33` public views) and `22` Long-form (`59` public views) observed via public Data API v3.
- **Honesty Policy Enforced:** No positive growth conclusion is manufactured where owner analytics are `BLOCKED` or samples are insufficient.

---

## 4. Next 30-Day Recommendations

1. Run interactive OAuth reauthorization locally to unblock `EXP-001` and `EXP-003`:
   ```powershell
   .venv\Scripts\python.exe authorize_youtube.py
   ```
2. Preserve the 5 Shorts + 1 Long-form daily IST cadence while collecting comparable publication-age samples (`>= 5` per variant) once `yt-analytics.readonly` is active.

---

## 5. Verification

- **Tests Added:** `tests/test_phase25_growth_execution.py` (Analytics Readiness Gate `BLOCKED`/unblock transitions, separate Shorts/Long-form baseline, mock/test exclusion, and non-manufactured findings).
- **Live `--weekly-review`:** Synced `50` videos, reconciled `25` live videos (`88.0%` coverage), synced SQLite WAL + backup (`weekly_review_20261112T085213Z_42e6`), and generated `output/phase25_30day_growth_evaluation.json`.

