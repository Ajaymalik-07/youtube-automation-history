# Video Production and Visual Quality Standard
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/VIDEO_PRODUCTION_STANDARD.md`  

---

## 1. Technical Video Specifications

| Format | Resolution | Aspect Ratio | Frame Rate | Bitrate / Preset | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Long-Form Documentary** | **2560×1440 (2K QHD)** | 16:9 Landscape | 24 FPS | libx264, preset ultrafast/veryfast | Forces YouTube VP09/AV01 premium allocation. |
| **YouTube Shorts** | **1080×1920 (FHD)** | 9:16 Vertical | 30 FPS | libx264, mobile optimized | Maximizes clarity across smartphone displays. |

---

## 2. Visual Storytelling & Historical Authenticity

Historical documentaries require visual discipline to establish authority and avoid breaking immersion:

1. **Topical Imagery First:** Visual search queries must target precise historical artifacts, ancient fortresses, inscriptions, archaeological digs, and period maps.
2. **AI Illustration Ethics:** When AI-generated visuals (Pollinations) are used for lost ancient settings, they must be styled as artistic interpretations and never falsely labelled as authentic historical photographs.
3. **No Anachronistic Imagery:** Sci-fi, modern neon cityscapes, and unrelated stock footage are strictly banned. If a search query fails, the pipeline falls back exclusively to historical ruins, ancient stone architecture, and parchment textures.
4. **Cinematic Motion (Ken Burns Effect):** Slow, dignified zoom and pan (1.00 $\rightarrow$ 1.10 scale over 10s intervals) simulates multi-camera documentary panning across ancient murals and excavation sites.

---

## 3. Audio Engineering & Voiceover Standards

* **Voice Model:** Microsoft Edge-TTS `hi-IN-MadhurNeural` (deep, authoritative male voice for Hindi) / `en-US-AndrewNeural` (for English).
* **Cadence & Pitch:** `VOICE_RATE = "-4%"` (measured documentary gravity), `VOICE_PITCH = "-2Hz"` (resonant baritone).
* **Background Music:** Layered at `MUSIC_VOLUME = 0.12` (subtle ambient underscore) beneath narration to ensure voiceover clarity remains pristine.
* **Resilient Audio Generation:** 3-tier fallback with exponential backoff retries if Microsoft speech endpoints experience rate-limiting.

---

## 4. Attribution & Licensing Integrity

* **Attribution Persistence:** Every downloaded image is tracked in `output/credits.json` with photographer name, platform, and license type.
* **Description Credits:** When third-party licenses (Creative Commons, Openverse) mandate attribution, credits are dynamically inserted into the YouTube description.
* **Unforced Third-Party Branding:** Unrelated third-party promo watermarks are never inserted into video frames. The channel's canonical watermark is governed by `config.VIDEO_WATERMARK` and `config.brand_text()`.
