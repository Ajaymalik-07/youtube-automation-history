# Data-Driven Growth Analysis Standard
**YouTube Agentic AI Studio (YAAS)**  
**Channel:** Stories Malik  
**Canonical Specification Reference:** `docs/GROWTH_ANALYSIS_STANDARD.md`  

---

## 1. Empirical Content Improvement

The growth engine for Stories Malik analyzes real performance data to inform content planning. The purpose is to understand what works, why it works, and what hypothesis to test next.

### Anti-Patterns Strictly Forbidden:
* **No Single-Video Causal Leaps:** Never declare a topic cluster a "failure" or "viral secret" based on a single video's performance. Meaningful statistical patterns require sample sizes of at least 3–5 videos per cluster.
* **No Unreviewed Automated Changes:** The analytics engine generates recommendations; it NEVER changes video titles, thumbnails, or metadata on live published videos without human authorization.
* **No Vanity Score Obsession:** 100/100 checklist scores are not correlated with watch time. Focus strictly on Average Percentage Viewed (APV) and First-30-Second Retention.

---

## 2. Long-Form vs. Shorts Comparative Evaluation

### Long-Form Evaluation Dimensions:
1. **First 30-Second Retention:** Did Chapter 1 establish the core mystery and historical contradiction before the 45-second mark?
2. **Average View Duration (AVD):** For an 8–13 minute documentary, target an AVD of $\ge 5:00$ (APV $\ge 45\%$).
3. **Chapter Drop-Off:** Pinpoint which narrative transition caused viewers to leave.
4. **Title/Thumbnail CTR:** Measure if curiosity-oriented concepts outperform search-oriented titles.

### Shorts Evaluation Dimensions:
1. **Viewed vs. Swiped Away:** The initial 0–2 second hook must achieve a viewed rate $\ge 75\%$.
2. **Completion Rate:** Target an Average Percentage Viewed $\ge 90\%$.
3. **Loop Rate:** Measure re-watches prompted by unresolved historical paradoxes.

---

## 3. Weekly Executive Growth Dossier

Every week, the studio compiles an automated performance report in `output/growth_report.json`:
* **Top 3 & Bottom 3 Videos:** Evaluated by retention and engagement.
* **Topic Cluster Health:** Tracking performance across the 10 Content Pillars.
* **Format Comparison:** Long-form retention vs. Shorts subscriber conversion.
* **Hypothesis Testing Recommendations:** Specific single-variable experiments for upcoming production runs.
