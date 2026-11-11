# Long-Form Scriptwriting Standard (8–13 Minutes)
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/LONG_FORM_SCRIPT_STANDARD.md`  

---

## 1. Editorial Vision & Pacing

Stories Malik produces cinematic, authoritative historical documentaries. Every long-form documentary is crafted to sustain viewer retention through genuine narrative tension, archaeological evidence, and chronological momentum—not cheap sensationalism or fake twists.

### Pacing & Duration Parameters
* **Target Video Duration:** 8 to 13 minutes (safe under YouTube's 15-minute unverified upload cap; hard cap at 14:30).
* **Narration Speed:** ~120 words per minute (measured documentary cadence with resonant pauses).
* **Target Script Word Count:** 950 to 1,280 words across 8 to 10 narrative chapters.
* **Primary Language:** Broadcast-quality Hindi in Devanagari script (`हिंदी`).
* **Secondary Subtitles:** Accurate, synchronized English translations.

---

## 2. Narrative Documentary Architecture

Rather than imposing a rigid cookie-cutter template on every subject, the scriptwriter utilizes an adaptable 10-stage historical narrative arc:

```
[0:00 - 0:45] Chapter 1: Hook & Historical Contradiction
   ▼
[0:45 - 2:00] Chapter 2: Setting the Stage (Geopolitics & Environmental Backdrop)
   ▼
[2:00 - 3:30] Chapter 3: The Catalyst (The Ambitious Ruler, Discovery, or Provocation)
   ▼
[3:30 - 5:00] Chapter 4: The Narrative Pivot ("लेकिन यहाँ इतिहास एक मोड़ लेता है...")
   ▼
[5:00 - 7:30] Chapters 5-7: Deep Historical Chronology (Battles, Inscriptions, Treaties)
   ▼
[7:30 - 9:30] Chapter 8: The Climax, Crisis & Collapse
   ▼
[9:30 - 11:00] Chapter 9: Archaeological Excavations & Modern Scientific Findings
   ▼
[11:00 - 12:30] Chapter 10: The Civilizational Verdict & Channel CTA (Stories Malik)
```

---

## 3. Mandatory Quality Standards

### Rules for Authentic Narration:
1. **No Formulaic Repetition:** Never use identical opening hooks across videos (e.g. avoid starting every video with *"क्या आपने कभी सोचा है..."*).
2. **Devanagari Precision:** Narration must be written in grammatically sound Hindi with proper Devanagari conjuncts and matras.
3. **No Fabricated Dialogue:** Never invent historical conversations or present literary dramatizations as historical records.
4. **Distinguish Legend from Archaeology:** When discussing oral lore (e.g. Chetak's leap, Kuldhara's curse), explicitly distinguish recorded inscriptions from folklore.
5. **English Visual Queries:** All stock image and footage search prompts (`image_query`, `image_query_2`, `image_query_3`) must remain in English to query global visual repositories accurately.

---

## 4. Script Quality Gate Checklist

Every generated script is automatically evaluated before audio voiceover synthesis:

| Check Item | Validation Rule | Error Consequence |
| :--- | :--- | :--- |
| **Section Count** | 8 to 11 structured chapters | Rejects if $< 8$ sections |
| **Word Count** | 900 to 1,350 total words | Re-prompts if outside bounds |
| **Duration Safe Cap** | Estimated duration $\le 14:30$ | Flags for trimming if $> 14:30$ |
| **Language Integrity** | Narration contains $\ge 70\%$ Devanagari characters (for `hi`) | Rejects if English or garbled |
| **Branding CTA** | Final section cites `Stories Malik` | Re-inserts canonical CTA |
| **Visual Prompts** | 3 historical visual queries per section | Fills defaults if missing |
