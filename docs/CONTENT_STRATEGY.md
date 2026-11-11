# Historical Content Strategy and Topic Discovery Standard
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/CONTENT_STRATEGY.md`  

---

## 1. Overview & Audience Positioning

Stories Malik delivers immersive, evidence-backed historical documentaries and high-velocity YouTube Shorts for Hindi-speaking audiences in India and globally.

The content strategy is engineered to avoid repetitive topics, prevent generic clickbait, and anchor every video to verifiable historical turning points, military clashes, lost civilizations, and archaeological breakthroughs.

---

## 2. The 10 Historical Content Pillars

Every topic must naturally belong to one of the ten established content pillars. If a proposed topic cannot genuinely fit into a pillar, it is rejected or refined rather than forced.

1. **Ancient Indian Civilizations:** Indus Valley, Saraswati River system, Vedic archaeology, Megalithic burial mounds, and earliest urban planning.
2. **Indian Kings, Empires & Dynasties:** Mauryan administration, Gupta golden age, Chola maritime navy, Maratha swarajya, Ahom resistance against Mughals, and Rashtrakuta empires.
3. **Historical Battles & Military Strategy:** Haldighati, Tarain, Panipat, Kalinga, battle formations, siegecraft, elephant armor, and guerilla warfare.
4. **Lost Cities & Archaeological Discoveries:** Marine archaeology of Dwarka, submerged Khambhat structures, Keezhadi sangam urban sites, Rakhigarhi DNA findings, and LiDAR surveys.
5. **Ancient Technology, Architecture & Engineering:** Kailash Temple top-down mountain carving, rustless iron metallurgy of Delhi, Chand Baori subterranean cooling stepwells, and Chola granite lifting.
6. **Historical Mysteries & Unresolved Questions:** Undeciphered Indus Valley script, disappearance of Kuldhara village, undeciphered Harappan seals, and lost royal fortunes.
7. **World Civilizations & Forgotten History:** Ancient Mesopotamia, Egyptian pharaonic waterways, Persian engineering, Roman trading posts in South India (Arikamedu), and Silk Road chronicles.
8. **Historical Personalities & Their Real Stories:** Chanakya, Xuanzang, Megasthenes, Rani Durgavati, Aryabhata, Charaka, and primary traveler chronicles.
9. **History Behind Famous Monuments & Places:** Nalanda Mahavihara, Konark Sun Temple wheels, Chittorgarh Fort sieges, and Tanjore Brihadisvara vimana.
10. **Myths, Legends & Their Historical Origins:** Demarcating geological/archaeological reality from mythology (Ram Setu, Koh-i-Noor diamond chronicle, Padmavati vs Khilji historical chronicles).

---

## 3. Transparent Topic Opportunity Scoring Model

Topics are evaluated across eight distinct dimensions on a 1–10 scale. These separate dimensional scores are preserved transparently to guide production decisions:

| Evaluation Dimension | Scoring Criteria (1 to 10) | Weight |
| :--- | :--- | :--- |
| **Audience Relevance** | Resonance with Hindi-speaking history enthusiasts and curiosity interest. | 20% |
| **Search Demand** | Measurable keyword search volume on YouTube/Google in India. | 15% |
| **Historical Significance** | Magnitude of civilizational or strategic impact of the event or figure. | 15% |
| **Storytelling Potential** | Inherent dramatic tension, conflict, betrayals, revelations, and paradoxes. | 15% |
| **Source Availability** | Existence of primary epigraphy, ASI reports, academic books, and museum data. | 15% |
| **Visual Richness** | Availability of archaeological photos, ancient coins, maps, and ruins. | 10% |
| **Content Differentiation** | Unique storytelling angle compared to saturated competing YouTube videos. | 10% |

> [!NOTE]
> The resulting Composite Opportunity Score (0–100) serves as an editorial guide, not an arbitrary ranking guarantee.

---

## 4. Automated Topic Deduplication Engine

To ensure Stories Malik never repeatedly releases identical topics disguised under different titles, the system executes an automated deduplication check prior to script generation:

1. **Title Token Normalization:** Removes stop words (`the`, `why`, `how`, `के`, `का`, `रहस्य`, etc.) and strips punctuation.
2. **Jaccard Similarity Index:** Computes token intersection over token union against all previously published and scheduled topics in `automation_schedule.json`.
3. **Collision Threshold:** Any proposed candidate with a Jaccard index $\ge 0.55$ against an existing topic is flagged as a collision and rejected from the active candidate pool.

---

## 5. Weekly Topic Research Report Format

Each week, the engine generates an actionable editorial dossier containing:
* **10 Scored Long-Form Candidates:** Covering diverse pillars with distinct angles.
* **20 Scored Shorts Concepts:** High-intrigue, standalone 25–60 second stories.
* **Top 3 Recommended Long-Form Topics:** Ready for immediate research and scripting.
* **Top 5 Recommended Shorts Topics:** Ready for production across mobile scroll windows.
* **Deduplication Verification:** Confirmation of zero overlap with channel archives.
