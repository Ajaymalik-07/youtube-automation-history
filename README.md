<div align="center">

# YAAS: YouTube Agentic AI Studio
### Stories Malik — Hindi-First Historical Documentary & Shorts Engine

**A reliable, evidence-grounded, Hindi-first YouTube production system for long-form historical documentaries and dedicated YouTube Shorts.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Channel](https://img.shields.io/badge/Channel-Stories%20Malik-red?style=flat-square&logo=youtube)](https://youtube.com)
[![Language](https://img.shields.io/badge/Primary%20Language-Hindi%20(Devanagari)-orange?style=flat-square)](docs/HINDI_RENDERING_STANDARD.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-88%20Passing-brightgreen?style=flat-square)](tests/)

[**Quick Start**](#-quick-start) · [**Architecture & Standards**](#-standards--documentation) · [**Content Pillars**](#-10-historical-content-pillars) · [**Publishing Safety**](#-publishing-safety-gate) · [**Analytics**](#-youtube-analytics-v2)

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
- **Run Automated Test Suite (88 tests):**
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

*A research quality gate (`validate_research_quality_gate`) blocks scripts if central claims lack verifiable evidence.*

---

## 🔤 Devanagari Hindi Subtitle & Font Engine

- **Unicode NFC Normalization:** All Hindi narration text is normalized to NFC form prior to wrapping and shaping.
- **Grapheme Cluster Preservation:** Consonants with vowel signs (matras), viramas, and nuktas are never split across line breaks.
- **Font Stack:** Bundled `assets/fonts/NotoSansDevanagari-Bold.ttf` prioritized for complete Devanagari glyph coverage.
- **Contrast & Legibility:** Charcoal semi-transparent bounding boxes (`rgba(10, 10, 20, 0.72)`) guarantee caption readability across vibrant or dark historical backgrounds.
- **Independent Shorts Safe Zones:** Dynamic framing calculations keep vertical captions within mobile safe areas (120px to 380px from bottom edge).

---

## 🛡️ Publishing Safety Gate

To guarantee brand integrity and prevent accidental unauthorized public uploads:
1. **Deterministic 10-State Machine:**
   `DRAFT` ➔ `RESEARCH_APPROVED` ➔ `SCRIPT_APPROVED` ➔ `VIDEO_RENDERED` ➔ `REVIEW_PENDING` ➔ `APPROVED` ➔ `SCHEDULED` ➔ `PUBLISHED`
2. **Mandatory Human Approval:**
   `uploader/youtube.py` strictly verifies human approval in `uploader/safety.py`. Unapproved videos are blocked and held in `output/pending_uploads/`.
3. **Private Default Privacy:**
   New uploads default to `privacyStatus: "private"` (or `"unlisted"` for review), never public.
4. **Graceful Review Server:**
   The review server runs on a background `werkzeug` daemon thread and shuts down cleanly upon decision receipt, eliminating abrupt process terminations (`os.kill`).

---

## 📊 YouTube Analytics v2 & Growth Analyst

- **Official API Integration (`apis/youtube_analytics.py`):**
  Collects watch time, average view duration (AVD), average percentage viewed (APV), impressions CTR, and traffic source distributions.
- **Snapshot Intervals:** Automatically persists metrics at **24h, 48h, 7d, and 28d** post-upload in `output/analytics_snapshots.json`.
- **Weekly Growth Analysis (`agents/growth_analyst.py`):**
  Diagnoses retention drop-offs, clusters topic performance across the 10 pillars, and produces evidence-based production recommendations.

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
│   └── growth_analyst.py       ← Weekly performance analysis & retention diagnostics
│
├── apis/
│   ├── knowledge.py            ← Archive.org, Crossref & historical evidence discovery
│   ├── trends.py               ← On-this-day historical events & archaeological feeds
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
│   └── youtube.py              ← YouTube Data API v3 uploader with private defaults
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
│   ├── PUBLISHING_EXPERIMENT_PLAN.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── CHANGELOG.md
│
└── tests/                      ← 88 automated pytest tests
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
- [30-Day Publishing Experiment Plan](docs/PUBLISHING_EXPERIMENT_PLAN.md)
- [Full Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Release Changelog](docs/CHANGELOG.md)

---

## ⚖️ License & Attribution

This project is open-source under the [MIT License](LICENSE). Built for the **Stories Malik** channel.
