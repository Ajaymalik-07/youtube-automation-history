# Historical Research and Evidence Standard
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/HISTORICAL_RESEARCH_STANDARD.md`  

---

## 1. Core Purpose & Philosophy

Stories Malik produces high-credibility, immersive historical documentaries and shorts in Hindi for viewers in India and across the world. A compelling historical narrative must never come at the expense of historical truth.

Viewers trust the channel because its claims are grounded in archaeological findings, epigraphic records, official treaties, and scholarly consensus. Sensationalist hoaxes, pseudoscientific myths presented as fact, and fabricated quotations are strictly forbidden.

---

## 2. Source-Quality Hierarchy

When researching any historical topic, sources must be evaluated according to the following strict hierarchy:

```
Tier 1: Government Archives & Inscriptional Records (ASI, National Archives, Epigraphia Indica)
   ▼
Tier 2: Recognized Museums & Historical Institutions (National Museum, British Museum, ASI site museums)
   ▼
Tier 3: Universities & Peer-Reviewed Academic Research (JSTOR, Crossref, Archaeological Journals)
   ▼
Tier 4: Primary Historical Documents & Translated Chronicles (Megasthenes, Xuanzang, Baburnama, Rajatarangini)
   ▼
Tier 5: Reputable Academic Books & Scholarly Monographs (Standard university press publications)
   ▼
Tier 6: Reputable Journalism for Contemporary Discoveries (Verified archaeological excavation reports)
   ▼
Tier 7: Encyclopedias (Wikipedia) — FOR PRELIMINARY DISCOVERY ONLY; NEVER AS SOLE EVIDENCE
```

> [!IMPORTANT]
> Wikipedia is useful for initial orientation, timeline sanity checks, and identifying primary source references. However, no central historical claim may be accepted in production based solely on a Wikipedia summary.

---

## 3. Evidence Classification Framework

Every factual claim in a research document is categorized into one of six standard evidentiary tiers:

| Tier Code | Classification | Definition | Production Treatment |
| :--- | :--- | :--- | :--- |
| **`ESTABLISHED_FACT`** | Established Historical Fact | Confirmed by direct archaeological excavations, epigraphy, coins, or verified treaties. | State definitively as historical fact with dates and locations. |
| **`STRONGLY_SUPPORTED`** | Strongly Supported Interpretation | Supported by multiple independent contemporary chronicles and broad academic consensus. | Narrate authoritatively with attribution to contemporary accounts. |
| **`DISPUTED_INTERPRETATION`** | Disputed Historical Interpretation | Legitimate debate among historians regarding motives, casualty counts, or exact dates. | Present both perspectives fairly without taking partisan sides. |
| **`ORAL_TRADITION`** | Oral Tradition / Bardic Record | Stories preserved through folk bards (e.g. Charans, Bhats, folk ballads). | Clearly identify as legendary or traditional accounts. |
| **`MYTHOLOGY_FOLKLORE`** | Mythology & Folklore | Religious epics, mythological sagas, or local folklore. | Frame respectfully as cultural belief/legend, distinct from archaeology. |
| **`SPECULATION`** | Modern Speculation | Modern theories, hypotheses, or unproven popular conjecture. | Clearly disclose as unconfirmed speculation or remove from core script. |

---

## 4. Structured Research Dossier Requirements

Every researched topic must produce a structured JSON dossier containing:

1. **`topic`:** The specific historical subject.
2. **`research_question`:** The central mystery, turning point, or investigative query.
3. **`period`:** Specific dates and era (e.g., *321–297 BCE*, *May 1576 CE*).
4. **`geographic_location`:** Ancient province/capital and modern district/country.
5. **`civilizations_involved`:** Dynasties, empires, or cultures involved.
6. **`key_figures`:** Historical rulers, generals, scholars, or archaeologists.
7. **`verified_timeline`:** Chronological sequence of verified milestones with source citations.
8. **`claims_and_evidence`:** Array of major assertions, each tagged with its `evidence_level` and `source_reference`.
9. **`conflicting_interpretations`:** Contrasting scholarly interpretations and their supporting data.
10. **`uncertain_facts`:** Elements where archaeological evidence is currently incomplete.
11. **`myths_and_legends`:** Popular cultural lore debunked or contextualized with verified facts.
12. **`confidence_score`:** Decimal from `0.0` to `1.0` reflecting source reliability.
13. **`missing_evidence`:** Lost texts, unexcavated mounds, or undeciphered scripts.
14. **`suggested_storytelling_angle`:** Guidance for pacing and documentary framing.

---

## 5. Automated Research Quality Gate

The pipeline executes `validate_research_quality_gate(research)` before any scriptwriting begins.

### Approval Rules:
* **Rule 1 — Claim Traceability:** At least 3 verified claims with explicit source references are required.
* **Rule 2 — Timeline Integrity:** A chronologically ordered timeline with at least 2 verified milestone dates is mandatory.
* **Rule 3 — Context Definition:** Era, period, and geographical location must not be empty or generic.
* **Rule 4 — Speculation Cap:** No more than 20% of claims may be classified as `SPECULATION`. If higher, the topic is rejected or flagged for re-research.
* **Rule 5 — Confidence Threshold:** The research `confidence_score` must meet or exceed `0.65`.

If a research dossier fails the Quality Gate, script generation is blocked and detailed diagnostic issues are reported.
