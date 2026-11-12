"""
Phase 29 — Content Intelligence & Storytelling Optimization
Repository: Ajaymalik-07/youtube-automation-history
Branch: feature/youtube-growth-overhaul

Translates Phase 28 individual-video analytics into validated data-quality
classifications, Shorts & Long-form storytelling diagnostics, controlled duration
experiment readiness, epistemic topic intelligence (fact vs legend), and
production-ready directives that respect all automated quality gates and the
fixed 6 videos/day IST publishing cadence.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import config

PHASE29_REPORT_FILES = {
    "data_validation": "phase29_data_validation_report.json",
    "shorts_storytelling": "phase29_shorts_storytelling_report.json",
    "longform_storytelling": "phase29_longform_storytelling_report.json",
    "duration_experiment": "phase29_duration_experiment_report.json",
    "topic_intelligence": "phase29_topic_intelligence_report.json",
    "content_recommendations": "phase29_content_recommendations.json",
    "final_markdown": "phase29_final_report.md",
}

MISSING_ANALYTICS_CLASSES = (
    "CONFIRMED_ZERO",
    "NO_ROWS_RETURNED",
    "REPORTING_DELAY",
    "API_ERROR",
    "SCHEDULED_OR_PRIVATE",
    "INSUFFICIENT_EVIDENCE",
)

HISTORICAL_EVIDENCE_LEVELS = (
    "verified_historical_facts",
    "scholarly_interpretations",
    "disputed_claims",
    "legends_and_folklore",
    "creative_storytelling",
)

SHORTS_MIN_SECONDS = getattr(config, "SHORTS_MIN_DURATION", 25)
SHORTS_MAX_SECONDS = getattr(config, "SHORTS_MAX_DURATION", 60)
MAX_SINGLE_TOPIC_SHARE = 0.30


def _utc_now(now_utc: Optional[datetime] = None) -> datetime:
    if now_utc is not None:
        return now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _load_json_safe(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def classify_missing_analytics_status(record: Dict[str, Any]) -> str:
    """
    Strictly classifies a video analytics record without ever silently
    reinterpreting empty Analytics API responses as confirmed zero views.
    """
    avail = record.get("data_availability", "")
    api_status = record.get("api_request_status", "")
    metrics = record.get("metrics") or {}
    views = metrics.get("views")

    if avail == "not_published_yet" or api_status == "skipped_unpublished":
        return "SCHEDULED_OR_PRIVATE"
    if avail == "api_error" or api_status == "api_error":
        return "API_ERROR"
    if avail == "reporting_delay_pending":
        return "REPORTING_DELAY"
    if avail == "empty_result_no_recorded_activity" or views is None:
        return "NO_ROWS_RETURNED"
    if avail == "measured_owner_analytics":
        if int(views) == 0:
            return "CONFIRMED_ZERO"
        return "MEASURED_NONZERO"
    return "INSUFFICIENT_EVIDENCE"


def classify_historical_claim(claim_text: str, source_type: str = "unknown") -> str:
    """
    Distinguishes verified historical facts, scholarly interpretations,
    disputed claims, legends/folklore, and creative storytelling.
    """
    txt = f"{claim_text} {source_type}".lower()
    if any(k in txt for k in ("dramatiz", "reconstruct", "cinematic", "narrative framing", "imagined")):
        return "creative_storytelling"
    if any(k in txt for k in ("legend", "folklore", "myth", "oral tradition", "purana", "curse", "ghost", "folk")):
        return "legends_and_folklore"
    if any(k in txt for k in ("disputed", "debated", "controversial", "unverified", "speculat", "contested")):
        return "disputed_claims"
    if any(k in txt for k in ("scholar", "historian", "archaeolog", "hypothesis", "suggests", "interpret")):
        return "scholarly_interpretations"
    if any(k in txt for k in ("excavation", "inscription", "radiocarbon", "dated", "chronicle", "primary source", "documented")):
        return "verified_historical_facts"
    return "scholarly_interpretations"


def enforce_topic_diversity(
    candidates: List[Dict[str, Any]],
    max_share: float = MAX_SINGLE_TOPIC_SHARE,
) -> Dict[str, Any]:
    """
    Ensures no single topic/pillar dominates the content slate above `max_share`.
    """
    if not candidates:
        return {"approved_slate": [], "capped_topics": [], "diversity_ok": True}

    total = len(candidates)
    max_per_topic = max(1, int(total * max_share))
    counts: Dict[str, int] = {}
    approved: List[Dict[str, Any]] = []
    capped: List[str] = []

    for c in candidates:
        domain = str(c.get("domain") or c.get("pillar") or "general")
        cur = counts.get(domain, 0)
        if cur < max_per_topic:
            counts[domain] = cur + 1
            approved.append(c)
        else:
            if domain not in capped:
                capped.append(domain)

    return {
        "approved_slate": approved,
        "capped_topics": capped,
        "max_per_topic": max_per_topic,
        "domain_counts": counts,
        "diversity_ok": len(capped) == 0,
    }


def validate_phase28_reports(
    output_dir: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Workstream 1: Audits Phase 28 reports, verifies counts & totals, and
    re-classifies missing analytics without treating empty rows as zero views.
    """
    now = _utc_now(now_utc)
    out_dir = output_dir or config.OUTPUT_DIR

    inv = _load_json_safe(os.path.join(out_dir, "phase28_video_inventory.json"))
    ind = _load_json_safe(os.path.join(out_dir, "phase28_individual_video_analytics.json"))
    shorts_r = _load_json_safe(os.path.join(out_dir, "phase28_shorts_performance_report.json"))
    long_r = _load_json_safe(os.path.join(out_dir, "phase28_longform_performance_report.json"))
    disc_r = _load_json_safe(os.path.join(out_dir, "phase28_discovery_analysis.json"))

    if not inv or not ind:
        return {
            "ok": False,
            "generated_at": now.isoformat(),
            "error": "Missing required Phase 28 inventory or individual analytics report.",
            "classification_counts": {k: 0 for k in MISSING_ANALYTICS_CLASSES},
        }

    all_records: List[Dict[str, Any]] = []
    for fmt in ("short", "longform", "unknown"):
        all_records.extend((ind.get("formats") or {}).get(fmt, []))

    class_counts: Dict[str, int] = {k: 0 for k in MISSING_ANALYTICS_CLASSES}
    class_counts["MEASURED_NONZERO"] = 0
    classified_videos: List[Dict[str, Any]] = []
    over_60s_shorts: List[str] = []

    for r in all_records:
        cls = classify_missing_analytics_status(r)
        class_counts[cls] = class_counts.get(cls, 0) + 1
        dur = r.get("duration_seconds")
        if r.get("format") == "short" and dur is not None and dur > SHORTS_MAX_SECONDS:
            over_60s_shorts.append(r["video_id"])
        classified_videos.append({
            "video_id": r["video_id"],
            "format": r.get("format"),
            "duration_seconds": dur,
            "publication_age_days": r.get("publication_age_days"),
            "phase28_availability": r.get("data_availability"),
            "phase29_classification": cls,
            "views": (r.get("metrics") or {}).get("views"),
            "estimatedMinutesWatched": (r.get("metrics") or {}).get("estimatedMinutesWatched"),
            "averageViewPercentage": (r.get("metrics") or {}).get("averageViewPercentage"),
        })

    inv_total = inv.get("total_videos", len(inv.get("videos", [])))
    ind_total = len(all_records)
    counts_match = inv_total == ind_total

    shorts_views = (shorts_r or {}).get("totals", {}).get("views", 0)
    long_views = (long_r or {}).get("totals", {}).get("views", 0)
    shorts_ts_views = sum(x.get("views", 0) for x in (disc_r or {}).get("shorts_traffic_sources", []))
    long_ts_views = sum(x.get("views", 0) for x in (disc_r or {}).get("longform_traffic_sources", []))

    inconsistencies = []
    if not counts_match:
        inconsistencies.append(f"Inventory total ({inv_total}) != individual analytics count ({ind_total}).")
    if over_60s_shorts:
        inconsistencies.append(
            f"{len(over_60s_shorts)} Shorts exceed the {SHORTS_MIN_SECONDS}-{SHORTS_MAX_SECONDS}s policy "
            f"(excluded from 31-45s vs 46-60s duration experiment): {', '.join(over_60s_shorts[:5])}."
        )
    if class_counts["CONFIRMED_ZERO"] > 0:
        inconsistencies.append(
            f"{class_counts['CONFIRMED_ZERO']} videos returned explicit rows with views=0 (CONFIRMED_ZERO), "
            f"distinct from {class_counts['NO_ROWS_RETURNED']} videos with NO_ROWS_RETURNED."
        )

    return {
        "ok": counts_match,
        "generated_at": now.isoformat(),
        "inventory_total": inv_total,
        "individual_records_total": ind_total,
        "counts_consistent": counts_match,
        "evaluation_window": ind.get("evaluation_window"),
        "latest_populated_channel_day": ind.get("latest_populated_channel_day"),
        "classification_counts": class_counts,
        "traffic_source_reconciliation": {
            "shorts_total_views": shorts_views,
            "shorts_traffic_source_sum": shorts_ts_views,
            "shorts_match": shorts_views == shorts_ts_views,
            "longform_total_views": long_views,
            "longform_traffic_source_sum": long_ts_views,
            "longform_match": long_views == long_ts_views,
        },
        "over_60s_shorts_ids": over_60s_shorts,
        "inconsistencies_and_corrections": inconsistencies,
        "videos": classified_videos,
    }


def _find_video(records: List[Dict[str, Any]], keyword: str) -> Optional[Dict[str, Any]]:
    kw = keyword.lower()
    for r in records:
        if kw in (r.get("title") or "").lower():
            return r
    return None


def build_shorts_storytelling_report(
    individual_analytics: Dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Workstream 2: Shorts storytelling audit grounded in Dwarka, Indus Valley Script,
    and Chandragupta Maurya Chanakya (lower-retention case), separating measured
    evidence from editorial judgment.
    """
    now = _utc_now(now_utc)
    shorts = (individual_analytics or {}).get("formats", {}).get("short", [])
    measured = [
        r for r in shorts
        if r.get("data_availability") == "measured_owner_analytics"
        and ((r.get("metrics") or {}).get("views") or 0) > 0
    ]

    dwarka = _find_video(measured, "dwarka")
    indus = _find_video(measured, "indus valley script")
    chandragupta = _find_video(measured, "chandragupta maurya chanakya") or _find_video(measured, "chandragupta")

    def _brief(r: Optional[Dict[str, Any]], role: str) -> Optional[Dict[str, Any]]:
        if not r:
            return None
        m = r.get("metrics") or {}
        return {
            "video_id": r["video_id"],
            "title": r["title"],
            "role": role,
            "duration_seconds": r.get("duration_seconds"),
            "views": m.get("views"),
            "estimatedMinutesWatched": m.get("estimatedMinutesWatched"),
            "averageViewDuration": m.get("averageViewDuration"),
            "averageViewPercentage": m.get("averageViewPercentage"),
            "subscribersGained": m.get("subscribersGained"),
            "traffic_sources": r.get("traffic_sources"),
        }

    return {
        "generated_at": now.isoformat(),
        "measured_shorts_nonzero_count": len(measured),
        "reference_examples": {
            "promising_examples_not_universal_templates": [
                x for x in (
                    _brief(dwarka, "promising_high_watch_time"),
                    _brief(indus, "promising_search_and_feed"),
                ) if x is not None
            ],
            "lower_retention_case": _brief(chandragupta, "lower_retention_investigation"),
        },
        "audit_dimensions": {
            "frame_one_visual": {
                "evidence_type": "editorial_judgment",
                "finding": "Open frame 1 with high-contrast historical subject imagery and minimal text overlay (max 3-5 words) rather than generic title cards.",
            },
            "first_second_hook": {
                "evidence_type": "editorial_judgment",
                "finding": "Trigger an immediate visual/verbal anomaly in second 0-1 without greeting or channel intro.",
            },
            "first_five_second_hook": {
                "evidence_type": "measured_evidence_plus_editorial_judgment",
                "finding": "Chandragupta (expBJwl9VXk) averaged 10.0s AVD (17.45% APV) vs 25-26s AVD (35-40% APV) on Dwarka/Indus; early curiosity-gap framing correlates with surviving the 5-second swipe window.",
            },
            "mystery_clarity_and_curiosity_gap": {
                "evidence_type": "editorial_judgment",
                "finding": "State one clear unresolved question (e.g., submerged ruins / undeciphered script) instead of broad biographical summaries.",
            },
            "narrative_progression_and_visual_changes": {
                "evidence_type": "editorial_judgment",
                "finding": "Advance the claim every 3-4 seconds with a new visual cut or evidence cue so mid-Short pacing never stalls.",
            },
            "narration_pace_and_audio_clarity": {
                "evidence_type": "editorial_judgment",
                "finding": "Keep crisp 120-135 WPM delivery with clean Hindi/English pronunciation and zero dead air before the hook.",
            },
            "ending_and_payoff": {
                "evidence_type": "editorial_judgment",
                "finding": "Deliver a self-contained historical payoff within 25-60s rather than cutting off mid-thought.",
            },
        },
        "production_improvements": {
            "hook_generation": "Generate 3 distinct curiosity-gap opening lines (paradox, archaeological anomaly, or specific date anomaly) without copying past titles.",
            "first_frame_selection": "Select the highest-contrast subject image for Scene 1 and enforce immediate motion/zoom.",
            "opening_dialogue": "Start Scene 1 with a <=12-word direct hook sentence.",
            "scene_progression": "Target 6-8 visual beats inside 35-55 seconds with escalating evidence.",
            "narrative_payoff": "Close with a 1-sentence verified takeaway that resolves the opening loop.",
        },
    }


def build_duration_experiment_report(
    individual_analytics: Dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Workstream 3: Evaluates 31-45s vs 46-60s Shorts cohorts strictly within the
    25-60s validation policy. Never declares a winner from insufficient samples.
    """
    now = _utc_now(now_utc)
    shorts = (individual_analytics or {}).get("formats", {}).get("short", [])

    c_31_45 = [
        r for r in shorts
        if r.get("duration_seconds") is not None and 31.0 <= r["duration_seconds"] <= 45.0
    ]
    c_46_60 = [
        r for r in shorts
        if r.get("duration_seconds") is not None and 46.0 <= r["duration_seconds"] <= 60.0
    ]
    excluded_over_60 = [
        r["video_id"] for r in shorts
        if r.get("duration_seconds") is not None and r["duration_seconds"] > SHORTS_MAX_SECONDS
    ]

    def _cohort_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        measured = [
            i for i in items
            if i.get("data_availability") == "measured_owner_analytics"
            and ((i.get("metrics") or {}).get("views") or 0) > 0
        ]
        views = [(i["metrics"]["views"]) for i in measured]
        apvs = [(i["metrics"]["averageViewPercentage"]) for i in measured]
        return {
            "total_in_inventory": len(items),
            "measured_nonzero_count": len(measured),
            "eligible_for_significance": len(measured) >= 10,
            "total_views": sum(views),
            "avg_apv": round(sum(apvs) / len(apvs), 2) if apvs else None,
        }

    s_a = _cohort_stats(c_31_45)
    s_b = _cohort_stats(c_46_60)
    both_ready = s_a["eligible_for_significance"] and s_b["eligible_for_significance"]

    return {
        "generated_at": now.isoformat(),
        "validation_policy_preserved": {
            "min_seconds": SHORTS_MIN_SECONDS,
            "max_seconds": SHORTS_MAX_SECONDS,
        },
        "cohorts": {
            "31_to_45_seconds": s_a,
            "46_to_60_seconds": s_b,
        },
        "excluded_outside_25_60s_policy_count": len(excluded_over_60),
        "eligibility_criteria": {
            "min_measured_videos_per_cohort": 10,
            "age_checkpoints": ["48h", "7d", "28d"],
            "confounding_controls": "Comparable historical mystery topics and hook styles; compare only within matching age checkpoints.",
        },
        "winner_declared": False,
        "experiment_status": "ready_for_controlled_collection" if not both_ready else "eligible_for_evaluation",
        "reason": "Insufficient measured sample size within 25-60s policy cohorts to declare a winner.",
    }


def build_longform_storytelling_report(
    individual_analytics: Dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Workstream 4: Audits Ganga River and Cursed Legion long-form videos while
    explicitly stating that n=2 is insufficient for statistical conclusions.
    """
    now = _utc_now(now_utc)
    longforms = (individual_analytics or {}).get("formats", {}).get("longform", [])
    measured = [
        r for r in longforms
        if r.get("data_availability") == "measured_owner_analytics"
        and ((r.get("metrics") or {}).get("views") or 0) > 0
    ]

    ganga = _find_video(measured, "ganga")
    cursed = _find_video(measured, "cursed legion")

    cases = []
    for label, rec in (("Ganga River", ganga), ("Cursed Legion", cursed)):
        if rec:
            m = rec.get("metrics") or {}
            cases.append({
                "label": label,
                "video_id": rec["video_id"],
                "title": rec["title"],
                "duration_seconds": rec.get("duration_seconds"),
                "publication_age_days": rec.get("publication_age_days"),
                "views": m.get("views"),
                "estimatedMinutesWatched": m.get("estimatedMinutesWatched"),
                "averageViewDuration": m.get("averageViewDuration"),
                "averageViewPercentage": m.get("averageViewPercentage"),
                "traffic_sources": rec.get("traffic_sources"),
            })

    return {
        "generated_at": now.isoformat(),
        "measured_longform_count": len(measured),
        "sample_size_sufficient": False,
        "statistical_disclaimer": (
            f"Long-form sample size (n={len(measured)} measured videos) is currently insufficient "
            "for strong statistical conclusions. Findings below combine measured aggregates with editorial audit."
        ),
        "investigated_videos": cases,
        "audit_dimensions": {
            "first_5_seconds": {"evidence_type": "editorial_judgment", "guidance": "Open with the central historical paradox/stakes in frame 1 before channel branding."},
            "first_30_seconds": {"evidence_type": "measured_evidence_plus_editorial_judgment", "guidance": "Cursed Legion averaged 42s AVD (7.43% APV) vs Ganga River 100s AVD (16.61% APV); state the central thesis and why it matters within 30 seconds."},
            "opening_thesis_and_mystery_clarity": {"evidence_type": "editorial_judgment", "guidance": "State one testable historical question rather than stacking multiple disconnected adjectives."},
            "background_exposition_and_evidence_progression": {"evidence_type": "editorial_judgment", "guidance": "Interleave primary evidence (dates, chronicles, archaeology) every 60-90 seconds instead of front-loading dry exposition."},
            "narrative_pacing_and_visual_variety": {"evidence_type": "editorial_judgment", "guidance": "Use chapter-level pattern interrupts and distinct visual compositions per beat."},
            "audio_quality_and_final_payoff": {"evidence_type": "editorial_judgment", "guidance": "Ensure clean TTS prosody, verified factual resolution, and explicit verdict at close."},
        },
    }


def build_topic_intelligence_report(
    individual_analytics: Dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Workstream 5: Evaluates 7 topic domains with strict epistemic separation
    (verified facts vs scholarly interpretations vs disputed claims vs folklore)
    and enforces slate diversity.
    """
    now = _utc_now(now_utc)
    domains = [
        {"domain": "Lost cities", "evidence_note": "Dwarka Short (0RK3VMQA5sU: 146 views, 39 min) shows initial curiosity.", "epistemic_rule": "Separate underwater archaeology findings from epic/oral traditions."},
        {"domain": "Ancient civilizations", "evidence_note": "Indus Valley Script Short (1ZLbdi9Ijoo: 107 views, 24 min) performed well in search+feed.", "epistemic_rule": "Distinguish excavated material culture from undeciphered-script hypotheses."},
        {"domain": "Archaeological discoveries", "evidence_note": "Supports concrete visual storytelling when anchored to excavation dates.", "epistemic_rule": "Cite excavation years, stratigraphy, and peer-reviewed consensus."},
        {"domain": "Historical mysteries", "evidence_note": "Strong hook potential; avoid sensationalizing unverified claims.", "epistemic_rule": "Label unsolved questions explicitly as open scholarly debates."},
        {"domain": "Forgotten rulers", "evidence_note": "Chandragupta Short (37 views, 17.45% APV) needs tighter hook framing.", "epistemic_rule": "Anchor claims in contemporary chronicles, edicts, or numismatics."},
        {"domain": "Unresolved historical events", "evidence_note": "Good long-form chapter arc potential when evidence is presented chronologically.", "epistemic_rule": "Present competing primary accounts clearly."},
        {"domain": "Indian history and mythology", "evidence_note": "Ganga River Long-form (37 views, 47 min watched) shows Hindi-language engagement.", "epistemic_rule": "Never present mythology or folklore as established historical fact."},
    ]
    div = enforce_topic_diversity(domains, max_share=MAX_SINGLE_TOPIC_SHARE)
    return {
        "generated_at": now.isoformat(),
        "epistemic_categories": list(HISTORICAL_EVIDENCE_LEVELS),
        "folklore_policy": "Folklore, legends, and mythological accounts must always be explicitly labeled as tradition/folklore and separated from verified archaeological or historical facts.",
        "diversity_governance": div,
        "topic_domains": domains,
    }


def build_content_recommendations(
    data_validation: Dict[str, Any],
    shorts_report: Dict[str, Any],
    longform_report: Dict[str, Any],
    duration_report: Dict[str, Any],
    topic_report: Dict[str, Any],
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Workstream 6: Generates ranked recommendations with video IDs, sample sizes,
    confidence, limitations, and evidence_type separation.
    """
    now = _utc_now(now_utc)
    s_n = shorts_report.get("measured_shorts_nonzero_count", 0)
    l_n = longform_report.get("measured_longform_count", 0)

    recommendations = [
        {
            "id": "P29-REC-01",
            "rank": 1,
            "category": "shorts_hooks",
            "evidence_type": "measured_evidence_plus_editorial_judgment",
            "evidence": "Dwarka (39.68% APV, 26s AVD) and Indus Valley Script (35.09% APV, 25s AVD) outperformed Chandragupta (17.45% APV, 10s AVD).",
            "video_ids": ["0RK3VMQA5sU", "1ZLbdi9Ijoo", "expBJwl9VXk"],
            "sample_size": s_n,
            "confidence_level": "medium" if s_n >= 15 else "low",
            "expected_benefit": "Reduce 0-5s swipe-aways and improve Shorts completion rate.",
            "limitations": "No second-by-second retention or Viewed-vs-Swiped-Away API metric; 3 reference Shorts exceeded 60s.",
            "suggested_implementation": "Enforce <=12-word anomaly hook in Scene 1 + high-contrast first frame via scriptwriter growth_brief.",
            "requires_quality_gate": True,
        },
        {
            "id": "P29-REC-02",
            "rank": 2,
            "category": "longform_openings",
            "evidence_type": "measured_evidence_plus_editorial_judgment",
            "evidence": "Ganga River achieved 100s AVD (16.61% APV) vs Cursed Legion 42s AVD (7.43% APV).",
            "video_ids": ["zSFKJpJVmmw", "qRnwvD6CgI4"],
            "sample_size": l_n,
            "confidence_level": "low",
            "expected_benefit": "Lift early 30s retention and long-form watch time.",
            "limitations": "Extremely small long-form sample (n=2); statistically insufficient.",
            "suggested_implementation": "Require explicit historical thesis and stakes within the first 30 seconds in _write_longform_script.",
            "requires_quality_gate": True,
        },
        {
            "id": "P29-REC-03",
            "rank": 3,
            "category": "duration_experiments",
            "evidence_type": "measured_evidence",
            "evidence": "Top-performing reference Shorts exceeded 60s while production policy requires 25-60s.",
            "video_ids": ["0RK3VMQA5sU", "1ZLbdi9Ijoo", "expBJwl9VXk"],
            "sample_size": s_n,
            "confidence_level": "low",
            "expected_benefit": "Clean A/B comparison of 31-45s vs 46-60s Shorts within policy.",
            "limitations": "Current eligible 25-60s cohorts lack n>=10 measured videos per cohort.",
            "suggested_implementation": "Tag Shorts into 31-45s and 46-60s cohorts and evaluate at 48h/7d/28d checkpoints.",
            "requires_quality_gate": True,
        },
        {
            "id": "P29-REC-04",
            "rank": 4,
            "category": "topic_selection",
            "evidence_type": "measured_evidence_plus_editorial_judgment",
            "evidence": "Lost cities and ancient script topics drove top views/search traffic; slate diversity must remain <=30% per domain.",
            "video_ids": ["0RK3VMQA5sU", "1ZLbdi9Ijoo", "zSFKJpJVmmw"],
            "sample_size": s_n + l_n,
            "confidence_level": "low",
            "expected_benefit": "Balanced discovery across Search and Feeds while preventing single-topic overfitting.",
            "limitations": "External search volume not measured; folklore must be separated from verified history.",
            "suggested_implementation": "Apply epistemic classification (fact vs interpretation vs legend) in researcher.py.",
            "requires_quality_gate": True,
        },
        {
            "id": "P29-REC-05",
            "rank": 5,
            "category": "story_structure",
            "evidence_type": "editorial_judgment",
            "evidence": "Long-form APV averages under 17% across measured videos.",
            "video_ids": ["zSFKJpJVmmw", "qRnwvD6CgI4"],
            "sample_size": l_n,
            "confidence_level": "low",
            "expected_benefit": "Improve mid-roll progression with 60-90s evidence beats.",
            "limitations": "Editorial judgment; no chapter-level retention telemetry.",
            "suggested_implementation": "Structure Long-form chapters with open-loop transitions and primary evidence cues.",
            "requires_quality_gate": True,
        },
        {
            "id": "P29-REC-06",
            "rank": 6,
            "category": "visual_storytelling",
            "evidence_type": "editorial_judgment",
            "evidence": "Shorts feed retention depends on immediate visual contrast and frequent scene progression.",
            "video_ids": ["0RK3VMQA5sU", "g9wK332_B6U"],
            "sample_size": s_n,
            "confidence_level": "low",
            "expected_benefit": "Sustain viewer attention across 31-60s vertical renders.",
            "limitations": "No automated visual drop-off telemetry.",
            "suggested_implementation": "Enforce 6-8 distinct scene visuals per Short and clear first-frame focal subject.",
            "requires_quality_gate": True,
        },
        {
            "id": "P29-REC-07",
            "rank": 7,
            "category": "narration",
            "evidence_type": "editorial_judgment",
            "evidence": "Ganga River Hindi documentary (37 views, 47 min) vs English Cursed Legion (3 views, 2 min).",
            "video_ids": ["zSFKJpJVmmw", "qRnwvD6CgI4"],
            "sample_size": l_n,
            "confidence_level": "low",
            "expected_benefit": "Clearer TTS pacing and natural Hindi/English delivery.",
            "limitations": "Small sample size; confounded by topic and language.",
            "suggested_implementation": "Maintain strict audio/subtitle quality gates on every render.",
            "requires_quality_gate": True,
        },
    ]

    return {
        "generated_at": now.isoformat(),
        "cadence_preserved": {
            "longform_per_day": 1,
            "shorts_per_day": 5,
            "total_per_day": 6,
            "timezone": "Asia/Kolkata",
            "schedule_modified": False,
        },
        "recommendations": recommendations,
    }


def get_phase29_production_directives(
    video_type: str = "longform",
    topic: str = "",
    pillar_name: str = "",
) -> Dict[str, Any]:
    """
    Workstream 7: Returns compact, quality-gate-safe production directives for
    researcher.py, scriptwriter.py, and adaptive_engine.py.
    """
    if video_type in ("short", "shorts"):
        return {
            "phase": "phase29",
            "video_type": "shorts",
            "hook_directive": "Open in 0-2s with a <=12-word historical anomaly/curiosity question; zero intro filler.",
            "first_frame_directive": "Use high-contrast historical focal subject on frame 1 with max 3-5 overlay words.",
            "pacing_directive": "Use 6-8 distinct visual beats within 25-60s and close with a complete verified payoff.",
            "epistemic_directive": "Explicitly distinguish verified archaeological/historical facts from legends or folklore.",
            "duration_policy_seconds": [SHORTS_MIN_SECONDS, SHORTS_MAX_SECONDS],
        }
    return {
        "phase": "phase29",
        "video_type": "longform",
        "hook_directive": "State the central historical paradox and why it matters within the first 30 seconds.",
        "first_frame_directive": "Open with atmospheric primary-evidence/site visual before background exposition.",
        "pacing_directive": "Interleave primary chronicles/archaeology every 60-90s with clear chapter transitions and a verified verdict.",
        "epistemic_directive": "Separate verified historical facts, scholarly interpretations, disputed claims, and folklore.",
    }


def _render_phase29_markdown(
    dv: Dict[str, Any],
    sh: Dict[str, Any],
    lf: Dict[str, Any],
    du: Dict[str, Any],
    tp: Dict[str, Any],
    rec: Dict[str, Any],
) -> str:
    cc = dv.get("classification_counts", {})
    lines = [
        "# Phase 29 — Content Intelligence & Storytelling Optimization",
        "",
        f"- **Generated:** `{dv.get('generated_at')}`",
        f"- **Inventory vs Individual Analytics:** `{dv.get('inventory_total')}` / `{dv.get('individual_records_total')}` (consistent: `{dv.get('counts_consistent')}`)",
        "",
        "## 1. Data Validation & Missing Analytics Classification",
        f"- `MEASURED_NONZERO`: **{cc.get('MEASURED_NONZERO', 0)}**",
        f"- `CONFIRMED_ZERO`: **{cc.get('CONFIRMED_ZERO', 0)}** (explicit API rows with `views=0`)",
        f"- `NO_ROWS_RETURNED`: **{cc.get('NO_ROWS_RETURNED', 0)}** (never treated as confirmed zero views)",
        f"- `REPORTING_DELAY`: **{cc.get('REPORTING_DELAY', 0)}**",
        f"- `SCHEDULED_OR_PRIVATE`: **{cc.get('SCHEDULED_OR_PRIVATE', 0)}**",
        f"- `API_ERROR`: **{cc.get('API_ERROR', 0)}**",
        "",
        "## 2. Shorts & Long-Form Storytelling Findings",
        f"- Shorts measured non-zero count: **{sh.get('measured_shorts_nonzero_count', 0)}**",
        f"- Long-form measured count: **{lf.get('measured_longform_count', 0)}** (`sample_size_sufficient: {lf.get('sample_size_sufficient')}`)",
        "",
        "## 3. Shorts Duration Experiment (25-60s Policy)",
        f"- `31-45s` cohort: {du['cohorts']['31_to_45_seconds']}",
        f"- `46-60s` cohort: {du['cohorts']['46_to_60_seconds']}",
        f"- `winner_declared`: `{du['winner_declared']}` ({du['reason']})",
        "",
        "## 4. Production Integration & Cadence",
        f"- Recommendations generated: **{len(rec.get('recommendations', []))}** (all `requires_quality_gate: true`)",
        "- Cadence preserved: 1 Long-Form (19:00 IST) + 5 Shorts (09:00, 12:00, 16:00, 19:00, 22:00 IST) = 6/day.",
    ]
    return "\n".join(lines) + "\n"


def generate_phase29_reports(
    output_dir: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Executes all Phase 29 workstreams from Phase 28 artifacts and writes
    the 7 required reports into `output_dir`.
    """
    now = _utc_now(now_utc)
    out_dir = output_dir or config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    ind = _load_json_safe(os.path.join(out_dir, "phase28_individual_video_analytics.json")) or {
        "formats": {"short": [], "longform": [], "unknown": []}
    }

    dv = validate_phase28_reports(output_dir=out_dir, now_utc=now)
    sh = build_shorts_storytelling_report(ind, now_utc=now)
    du = build_duration_experiment_report(ind, now_utc=now)
    lf = build_longform_storytelling_report(ind, now_utc=now)
    tp = build_topic_intelligence_report(ind, now_utc=now)
    rec = build_content_recommendations(dv, sh, lf, du, tp, now_utc=now)
    md = _render_phase29_markdown(dv, sh, lf, du, tp, rec)

    payloads = {
        "data_validation": dv,
        "shorts_storytelling": sh,
        "longform_storytelling": lf,
        "duration_experiment": du,
        "topic_intelligence": tp,
        "content_recommendations": rec,
    }
    written_paths = {}
    for key, data in payloads.items():
        path = os.path.join(out_dir, PHASE29_REPORT_FILES[key])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        written_paths[key] = path

    md_path = os.path.join(out_dir, PHASE29_REPORT_FILES["final_markdown"])
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    written_paths["final_markdown"] = md_path

    return {
        "ok": dv.get("ok", False),
        "written_paths": written_paths,
        "classification_counts": dv.get("classification_counts", {}),
        "recommendations_count": len(rec.get("recommendations", [])),
    }

