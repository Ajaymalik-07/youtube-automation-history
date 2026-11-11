# Hindi Font, Subtitle, and Devanagari Rendering Standard
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/HINDI_RENDERING_STANDARD.md`  

---

## 1. Overview & Typography Standards

Devanagari script possesses complex typographic requirements: combining vowel markers (matras), virama/halants, conjunct ligatures (samyuktakshar), and anusvaras. Rendering Hindi text naively as arbitrary Latin-style glyphs causes broken conjuncts, floating matras, or detached characters.

Stories Malik strictly enforces verified Devanagari font rendering across all video formats.

### Primary Fonts
* **Devanagari Primary Bold:** `Noto Sans Devanagari Bold` (SIL Open Font License, stored locally in `assets/fonts/NotoSansDevanagari-Bold.ttf`).
* **Devanagari Display / Royal Heading:** `Rozha One Regular` (stored locally in `assets/fonts/RozhaOne-Regular.ttf`).
* **System Fallbacks:** Windows (`Nirmala.ttc`, `mangal.ttf`), Linux (`fonts-deva`, `fonts-noto-core`).

---

## 2. Unicode NFC Normalization & Grapheme Clusters

All text passing into text-measuring and frame-drawing engines MUST be normalized to Unicode Canonical Composition (**NFC**):

```python
import unicodedata
normalized_text = unicodedata.normalize("NFC", raw_text)
```

### Why NFC is Mandatory:
In Unicode NFD (Decomposed), a character like `कि` may be stored as two separate code points: `क` (U+0915) + `ि` (U+093F). Standard FreeType text measurement can detach the vowel sign or miscalculate line-wrapping bounding boxes. In NFC, precombined conjuncts are preserved canonically.

### Grapheme Cluster Integrity:
When line wrapping long subtitles or thumbnail text, the system uses `split_devanagari_graphemes()` to guarantee that halants (`्`) and combining marks are never separated from their root consonant.

---

## 3. Subtitle Contrast & Mobile Safe Areas

### Long-Form (16:9 2K / 1080p)
* **Position:** Centered horizontally, sit above the timeline progress bar (`H - 90px - patch_h`).
* **Background Pill:** Semi-transparent dark background (`RGBA: (0, 0, 0, 160)`) with rounded corners (`radius: 8px`).
* **Drop Shadow:** Multi-pixel solid dark drop shadow for 100% contrast against bright sky or sand footage.

### Shorts (9:16 Vertical 1080×1920)
* **Position:** Centered horizontally at `Y = 70%–72%` (strictly within the middle 70% safe zone, above bottom channel handle and title).
* **Font Size:** Responsive 52–56pt bold.
* **Side Padding:** 80px horizontal margin to prevent overlap with YouTube Shorts right-side engagement buttons (Like, Dislike, Comment, Share).

---

## 4. Visual Test Verification Suite

All font loaders and rendering pipelines are verified against the benchmark test sentence containing complex conjuncts and historical names:

```
"प्राचीन सभ्यता, महाराणा प्रताप, चंद्रगुप्त मौर्य, ऐतिहासिक युद्ध, भारत का गौरवशाली इतिहास।"
```

Automated visual regression tests in `tests/test_hindi_rendering.py` render actual image frames and verify:
1. Long-form 16:9 subtitle pill composition.
2. Shorts 9:16 vertical caption layout.
3. Multi-line wrapping of compound Sanskrit/Hindi names.
4. Grapheme cluster retention across line breaks.
