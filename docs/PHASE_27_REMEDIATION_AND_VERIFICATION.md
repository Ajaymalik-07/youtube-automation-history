# Phase 27 — Production Defect Remediation & Live Analytics Verification

**Repository:** `Ajaymalik-07/youtube-automation-history`  
**Branch:** `feature/youtube-growth-overhaul` (`main` untouched)  
**Cadence Preserved:** 1 Long-Form (`19:00 IST`) + 5 Shorts (`09:00, 12:00, 16:00, 19:00, 22:00 IST`) = 6 videos/day (`Asia/Kolkata`)  
**Policy Guarantees:** Automated quality gates mandatory, no mandatory human approval, no automatic frequency reduction, zero paid APIs, zero mutation of existing live videos.

---

## 1. Workstream 1 — Shorts Duration Enforcement

- **Root Cause:** `video/creator.py` previously used `audio.subclip(0, max_short_secs)` which silently truncated audio mid-sentence, and lacked post-encode `ffprobe` validation against `config.SHORTS_MAX_SECONDS` (`60s`). Historical Shorts `92kjsBopLOw` (`64s`), `2IQAyTfqql8` (`69s`), and `BnJVr_OL8_A` (`64s`) were uploaded from `main` without this post-encode guard.
- **Remediation Implemented:**
  - Added `probe_media_duration()` (via `ffprobe`) and `validate_format_and_duration_contract()` in `uploader/safety.py`.
  - Removed silent `audio.subclip(...)` mid-sentence truncation in `video/creator.py`; Shorts audio exceeding `60.0s` now raises `ValueError` before rendering, and every encoded render is verified post-encode via `ffprobe` before returning.
  - Integrated format & duration contract checks into `uploader/safety.py` (`is_eligible_for_upload()`), blocking any Short `> 60.0s`, `< 25.0s`, missing duration metadata, or corrupt media from reaching upload.

---

## 2. Workstream 2 — Long-Form / Shorts Format Classification

- **Root Cause:** Historical videos `S-NzB9Ra4dg` (`73s`) and `I1w0I4eec8s` (`71s`) were classified as `longform` (`> 65s` fallback) despite being ~1-minute videos. Existing `config.py` thresholds define `SHORTS_MIN_SECONDS = 25`, `SHORTS_MAX_SECONDS = 60`, `VIDEO_MIN_MINUTES = 8` (`480s`), and `VIDEO_MAX_MINUTES = 13` (hard cap `870s`).
- **Remediation Implemented:**
  - Added `normalize_content_format()` and `validate_format_and_duration_contract()` in `uploader/safety.py` enforcing:
    - `short`: `25.0s <= actual_duration <= 60.0s`
    - `longform`: `480.0s <= actual_duration <= 870.0s`
  - Rejects missing/invalid `declared_format`, contradictory `metadata_format` / `db_format`, and `71s` / `73s` renders declared as `longform`.
  - Existing live videos on YouTube are **not** modified or reclassified; historical mismatches are only reported.

---

## 3. Workstream 3 — Duplicate Hook Prefix Remediation

- **Root Cause:** Legacy titles (`92kjsBopLOw`, `BnJVr_OL8_A`, `5yj8REbj0B8`, `S-NzB9Ra4dg`, `zJ-VF6aCsc8`) carried redundant/duplicated hook prefixes before `:` (and multi-colon English/corrupted-Hindi prefixes).
- **Remediation Implemented:**
  - Added `sanitize_title_duplicate_prefix()` in `agents/seo_optimizer.py`, called automatically in `optimize_for_100_percent()`, and added duplicate-prefix rejection in `validate_youtube_metadata()`.

---

## 4. Live OAuth & Analytics Verification Status

- **Channel ID:** `UCb1BDNY8WxoD1q_UVyEmvuw`
- **OAuth Status:** **`BLOCKED`** — `youtube_token.pickle` has `youtube.upload` only; missing `youtube.readonly` and `yt-analytics.readonly`.
- **Reauthorization Command (run interactively by channel owner):**
  ```powershell
  .venv\Scripts\python.exe authorize_youtube.py
  ```
- **Verification Scope:** No live OAuth analytics retrieval is claimed; public Data API v3 fallback remains cleanly separated from `null` private owner metrics.

---

## 5. Tests & Verification

- **Added:** `tests/test_phase27_remediation.py` covering all Workstream 1, 2, and 3 boundaries (`59.5s`, `60.0s`, `60.01s`, `64.0s`, missing/corrupt media, `71s`/`73s` long-form rejection, contradictory format metadata, and duplicate hook prefix stripping/validation).

