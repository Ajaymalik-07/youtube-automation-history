<div align="center">

# YAAS: YouTube Agentic AI Studio
### Stories Malik — Hindi-First Historical Documentary & Shorts Engine

**A reliable, evidence-grounded, Hindi-first YouTube production system for long-form historical documentaries and dedicated YouTube Shorts.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Channel](https://img.shields.io/badge/Channel-Stories%20Malik-red?style=flat-square&logo=youtube)](https://youtube.com)
[![Language](https://img.shields.io/badge/Primary%20Language-Hindi%20(Devanagari)-orange?style=flat-square)](docs/HINDI_RENDERING_STANDARD.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-138%20Passing-brightgreen?style=flat-square)](tests/)

[**Quick Start**](#-quick-start) · [**Standards & Documentation**](#-standards--documentation) · [**Adaptive AI Engine**](docs/PHASE_20_ADAPTIVE_CONTENT_OPTIMIZATION.md) · [**Growth Intelligence**](docs/PHASE_19_GROWTH_INTELLIGENCE.md) · [**OAuth & Analytics**](docs/PHASE_18_1_OAUTH_ANALYTICS.md) · [**Autonomous Publishing**](#-autonomous-publishing--quality-gates)

</div>

---

## ⚡ Quick Start

### 1. Clone & Set Up
```bash
git clone https://github.com/Ajaymalik-07/youtube-automation-history.git
cd youtube-automation-history
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and provide your free keys:
```bash
cp .env.example .env
```
Key configuration items:
- `GEMINI_API_KEY`: Free tier Google Gemini API key (recommended for historical script generation).
- `PEXELS_API_KEY`: Optional free key for authentic historical stock imagery.
- `YOUTUBE_CLIENT_SECRET_FILE`: Path to OAuth credentials (`client_secret.json`) for publishing and analytics.
- `YOUTUBE_UPLOAD_MODE`: `SCHEDULED_PUBLICATION` (default), `IMMEDIATE_PUBLICATION`, or `PRIVATE_ARCHIVE`.

### 3. Launch Modes
- **Interactive Web Studio (GUI):**
  ```bash
  python gui.py
  # Access at http://localhost:7070
  ```
- **Autonomous Historical Pipeline:**
  ```bash
  python automation.py --help
  # Test longform documentary generation
  python automation.py --longform
  # Generate daily 5-Shorts batch
  python automation.py --shorts-batch
  ```
- **Headless Pipeline with Autonomous Quality Gates:**
  ```bash
  python pipeline.py
  ```
- **Run Automated Test Suite (138 tests):**
  ```bash
  pytest
  ```

---

## 🏛 10 Historical Content Pillars

1. **Ancient Indian Civilizations:** Indus Valley, Vedic culture, Megalithic sites.
2. **Indian Kings, Empires & Dynasties:** Mauryas, Guptas, Cholas, Marathas, Rajputs.
3. **Historical Battles & Military Strategy:** Tactical breakdowns, fort defenses, sieges.
4. **Lost Cities & Archaeological Discoveries:** Marine archaeology, excavation reports.
5. **Ancient Technology, Architecture & Engineering:** Stepwells, temple acoustics, metallurgy.
6. **Historical Mysteries & Unresolved Questions:** Decipherment challenges, disappearance theories.
7. **World Civilizations & Forgotten History:** Mesopotamia, Persia, Silk Road connections.
8. **Historical Personalities & Unsung Heroes:** Chronicled biographies grounded in records.
9. **History Behind Famous Monuments:** Construction history, inscriptions, architectural secrets.
10. **Myths, Legends & Historical Origins:** Distinguishing verified archaeological fact from oral folklore.

---

## 📚 Multi-Tier Historical Evidence Framework

The system rejects unsupported speculation and science/astrophysics miscategorizations. Research sources strictly follow this hierarchy:
1. **Tier 1 (Official Records):** Government archives, Archaeological Survey of India (ASI).
2. **Tier 2 (Institutions):** Recognized museums, National Archives, state repositories.
3. **Tier 3 (Academic & Peer-Reviewed):** Crossref university publications, JSTOR, scholarly papers.
4. **Tier 4 (Excavation Reports):** Field archaeology monographs and survey publications.
5. **Tier 5 (Primary Sources):** Contemporary epigraphy, rock edicts, translated traveler logs (Faxian, Xuanzang, Megasthenes, Al-Biruni).
6. **Tier 6 (Preliminary Discovery):** Wikipedia and encyclopedia indexes for topic scoping (not treated as primary proof).

*A research quality gate (`validate_research_gate`) blocks scripts if central claims lack verifiable evidence.*

---

## 🔤 Devanagari Hindi Subtitle & Font Engine

- **Unicode NFC Normalization:** All Hindi narration text is normalized to NFC form prior to wrapping and shaping.
- **Grapheme Cluster Preservation:** Consonants with vowel signs (matras), viramas, and nuktas are never split across line breaks.
- **Font Stack:** Bundled `assets/fonts/NotoSansDevanagari-Bold.ttf` prioritized for complete Devanagari glyph coverage.
- **Contrast & Legibility:** Charcoal semi-transparent bounding boxes (`rgba(10, 10, 20, 0.72)`) guarantee caption readability across vibrant or dark historical backgrounds.
- **Independent Shorts Safe Zones:** Dynamic framing calculations keep vertical captions within mobile safe areas (120px to 380px from bottom edge).

---

## 🛡️ Autonomous Publishing & Quality Gates

Phase 17 removes all mandatory manual approval dependencies. The production workflow is governed strictly by verifiable automated quality gates and idempotent state tracking:

1. **Deterministic 18-Stage Lifecycle Machine:**
   `TOPIC_SELECTED` ➔ `RESEARCH_IN_PROGRESS` ➔ `RESEARCH_VALIDATED` ➔ `SCRIPT_GENERATED` ➔ `SCRIPT_VALIDATED` ➔ `VIDEO_RENDERING` ➔ `VIDEO_RENDERED` ➔ `VIDEO_VALIDATED` ➔ `METADATA_VALIDATED` ➔ `UPLOAD_QUEUED` ➔ `UPLOADING` ➔ `SCHEDULED` / `PUBLISHED` ➔ `ANALYTICS_PENDING` ➔ `COMPLETED`
2. **Four Automated Quality Gates (`uploader/quality_gates.py`):**
   - **Research:** Claims verified against source hierarchy, period/location defined, confidence $\ge 0.65$.
   - **Script:** Suitable duration bounds (350–2,400 words for long-form, 40–220 words for Shorts), zero broken tokens, no repetitive paragraphs.
   - **Video:** File exists, container valid, healthy file size, valid thumbnail dimensions.
   - **Metadata:** Title, description, tags, language (`hi`), and category verified.
3. **Supported Upload Modes:**
   - `SCHEDULED_PUBLICATION` (default production mode): Uploads with `privacyStatus: "private"` and future `publishAt` timestamp in `Asia/Kolkata` (19:00 IST for long-form, 10:00 & 18:00 IST for Shorts).
   - `IMMEDIATE_PUBLICATION`: Public upload without `publishAt`.
   - `PRIVATE_ARCHIVE`: Private upload without `publishAt`.
4. **Idempotent Duplicate Prevention:**
   Pre-upload checks prevent re-uploading already scheduled or published videos.
5. **Post-Upload Verification:**
   Queries YouTube API `videos.list` to verify upload processing status and ensure publication schedule integrity.

---

## 📊 YouTube Analytics v2 & Growth Analyst

- **Official API Integration (`apis/youtube_analytics.py`):**
  Collects watch time, average view duration (AVD), average percentage viewed (APV), impressions CTR, and traffic source distributions.
- **Snapshot Intervals:** Automatically persists metrics at **24h, 48h, 7d, and 28d** post-upload in `output/analytics_snapshots.json`.
- **Weekly Growth Analysis (`agents/growth_analyst.py`):**
  Diagnoses retention drop-offs, clusters topic performance across the 10 pillars, and produces evidence-based production recommendations.

---

## 🧭 Adaptive AI Content Optimization Engine (Phase 20)

See full documentation at [docs/PHASE_20_ADAPTIVE_CONTENT_OPTIMIZATION.md](docs/PHASE_20_ADAPTIVE_CONTENT_OPTIMIZATION.md).

- **Advanced Statistical Validation (`agents/statistical_validator.py`):** Enforces minimum sample size tiers, two-tailed 95% confidence intervals, IQR outlier filtering, duration-adjusted watch-time efficiency (WPMD), Welch's two-sample $t$-test, and logarithmic age-decay normalization.
- **Channel Content Diversity & Repetition Control (`agents/diversity_monitor.py`):** Tracks 24 historical personalities and 22 civilizations/dynasties; enforces a 25% single-pillar concentration ceiling; guards against repetitive opening hooks with token-level Jaccard similarity.
- **Topic Opportunity Engine (`agents/adaptive_engine.py`):** Scores and generates weekly opportunity dossiers with 20 candidate topics (10 Shorts, 5 Long-form, 5 Reserve) compliant with research quality gates.
- **Adaptive Shorts & Long-Form Engine:** Evaluates candidate hooks across 7 objective storytelling criteria; generates dynamic, subject-specific visual reveal directives (sonar/stratigraphy for archaeological digs, tactical elevation maps for military battles, metallurgy cross-sections for ancient engineering).
- **Automated Controlled Experimentation:** Selects active single-variable hypotheses with the fewest samples to systematically expand channel knowledge without multi-variable confounding.
- **Strategy Dossiers:** Generates `output/adaptive_content_strategy.json` and `output/adaptive_content_strategy.md`.

---

## 📁 Repository Structure

```
├── config.py                   ← Canonical settings (Stories Malik, Hindi-first, Asia/Kolkata)
├── automation.py               ← Autonomous production engine & adaptive scheduler
├── pipeline.py                 ← Headless end-to-end documentary pipeline
├── gui.py                      ← Interactive web studio (Flask, http://localhost:7070)
│
├── agents/
│   ├── researcher.py           ← Multi-tier historical evidence researcher & quality gate
│   ├── scriptwriter.py         ← Long-form documentary engine & 8-format Shorts pipeline
│   ├── topic_discovery.py      ← 10 content pillars, transparent scoring & deduplication
│   ├── seo_optimizer.py        ← 3 title candidates, chapter generation & authentic metadata
│   ├── growth_analyst.py       ← Weekly performance analysis & retention diagnostics
│   ├── experiment_tracker.py   ← Controlled growth experimentation framework (hypotheses & samples)
│   ├── statistical_validator.py ← Statistical validation (CI, IQR, WPMD, Welch t-test, age normalization)
│   ├── diversity_monitor.py    ← Channel content diversity, entity frequencies & hook deduplication
│   └── adaptive_engine.py      ← Adaptive topic opportunities, hook evaluation & narrative directives
│
├── apis/
│   ├── knowledge.py            ← Archive.org, Crossref & historical evidence discovery
│   ├── trends.py               ← On-this-day historical events & archaeological feeds
│   ├── growth_database.py      ← Immutable, versioned historical performance database
│   ├── youtube_analytics.py    ← Official YouTube Analytics API v2 & snapshot engine
│   └── seo.py                  ← Hindi/English keyword discovery & metadata validator
│
├── video/
│   ├── fonts.py                ← Devanagari Unicode NFC normalization & grapheme preservation
│   ├── creator.py              ← 16:9 & 9:16 video renderer with dynamic caption safe zones
│   ├── stock.py                ← Historical architectural fallbacks & image downloads
│   ├── thumbnail.py            ← Search, Story & Curiosity thumbnail concept generator
│   └── narrator.py             ← Edge-TTS voiceover & word-level caption alignment
│
├── uploader/
│   ├── safety.py               ← Publishing state machine, approval tokens & duplicate protection
│   ├── oauth_manager.py        ← Safe OAuth scope auditing, credential refresh & reauthorization
│   └── youtube.py              ← YouTube Data API v3 uploader & video processing verification
│
├── review/
│   └── app.py                  ← Local review dashboard with graceful Werkzeug shutdown
│
├── docs/                       ← Comprehensive architectural standards & reports
│   ├── AUDIT_REPORT.md
│   ├── CHANNEL_CONFIGURATION.md
│   ├── HISTORICAL_RESEARCH_STANDARD.md
│   ├── CONTENT_STRATEGY.md
│   ├── LONG_FORM_SCRIPT_STANDARD.md
│   ├── SHORTS_CONTENT_STANDARD.md
│   ├── HINDI_RENDERING_STANDARD.md
│   ├── VIDEO_PRODUCTION_STANDARD.md
│   ├── TITLE_THUMBNAIL_STANDARD.md
│   ├── YOUTUBE_METADATA_STANDARD.md
│   ├── YOUTUBE_ANALYTICS_STANDARD.md
│   ├── GROWTH_ANALYSIS_STANDARD.md
│   ├── PUBLISHING_SAFETY_STANDARD.md
│   ├── AUTOMATED_PUBLISHING_STANDARD.md
│   ├── PHASE_18_PRODUCTION_READINESS.md
│   ├── PHASE_18_1_OAUTH_ANALYTICS.md
│   ├── PHASE_19_GROWTH_INTELLIGENCE.md
│   ├── PUBLISHING_EXPERIMENT_PLAN.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── CHANGELOG.md
│
└── tests/                      ← 123 automated pytest tests
```

---

## 📜 Standards & Documentation

For detailed architectural guidelines, consult the `docs/` suite:
- [Repository Audit Report](docs/AUDIT_REPORT.md)
- [Channel Configuration Guide](docs/CHANNEL_CONFIGURATION.md)
- [Historical Research Standard](docs/HISTORICAL_RESEARCH_STANDARD.md)
- [Content Strategy Standard](docs/CONTENT_STRATEGY.md)
- [Long-Form Scriptwriting Standard](docs/LONG_FORM_SCRIPT_STANDARD.md)
- [Shorts Content Standard](docs/SHORTS_CONTENT_STANDARD.md)
- [Hindi Rendering Standard](docs/HINDI_RENDERING_STANDARD.md)
- [Video Production Standard](docs/VIDEO_PRODUCTION_STANDARD.md)
- [Title & Thumbnail Standard](docs/TITLE_THUMBNAIL_STANDARD.md)
- [YouTube Metadata Standard](docs/YOUTUBE_METADATA_STANDARD.md)
- [YouTube Analytics Standard](docs/YOUTUBE_ANALYTICS_STANDARD.md)
- [Growth Analysis Standard](docs/GROWTH_ANALYSIS_STANDARD.md)
- [Publishing Safety Standard](docs/PUBLISHING_SAFETY_STANDARD.md)
- [Automated Publishing Standard](docs/AUTOMATED_PUBLISHING_STANDARD.md)
- [Phase 18 Production Readiness Audit](docs/PHASE_18_PRODUCTION_READINESS.md)
- [Phase 18.1 OAuth & Analytics Verification](docs/PHASE_18_1_OAUTH_ANALYTICS.md)
- [Phase 19 Growth Intelligence Engine](docs/PHASE_19_GROWTH_INTELLIGENCE.md)
- [30-Day Publishing Experiment Plan](docs/PUBLISHING_EXPERIMENT_PLAN.md)
- [Full Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Release Changelog](docs/CHANGELOG.md)

---

## ⚖️ License & Attribution

This project is open-source under the [MIT License](LICENSE). Built for the **Stories Malik** channel.
