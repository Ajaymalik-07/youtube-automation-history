"""
Stories Malik — YouTube Growth Intelligence Engine (Phase 19 Overhaul)
Repository: Ajaymalik-07/youtube-automation-history
Channel: Stories Malik

Scientific, analytics-driven growth intelligence based on real YouTube owner analytics:
1. Historical performance database integration (immutable, versioned).
2. Independent Shorts performance analysis (8 formats, hook styles, engagement, swipe retention).
3. Independent Long-form performance analysis (impressions, CTR, watch time, AVD, APV, packaging vs retention separation).
4. Topic performance intelligence across the 10 historical content pillars.
5. Title & thumbnail empirical pattern analysis (Search vs Story vs Curiosity, style traction).
6. Retention diagnostics & honest reporting of API granularity limitations.
7. Automated Weekly Growth Intelligence Report (output/weekly_growth_intelligence.json & .md).
8. Adaptive content directives for topic discovery, research, scriptwriting, SEO, and thumbnail design.
9. Controlled experimentation framework integration.
"""
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import config
from apis.growth_database import get_performance_db, HistoricalPerformanceDB
from agents.experiment_tracker import get_experiment_tracker
from agents.statistical_validator import (
    calculate_median,
    compute_publication_age_days,
    normalize_views_by_age,
)

REPORT_JSON_PATH = os.path.join(config.OUTPUT_DIR, "weekly_growth_intelligence.json")
REPORT_MD_PATH = os.path.join(config.OUTPUT_DIR, "weekly_growth_intelligence.md")

# The 10 Historical Content Pillars for Stories Malik
HISTORICAL_PILLARS = [
    "Ancient Indian Civilizations",
    "Indian Kings, Empires & Dynasties",
    "Historical Battles & Military Strategy",
    "Lost Cities & Archaeological Discoveries",
    "Ancient Technology, Architecture & Engineering",
    "Historical Mysteries & Unresolved Questions",
    "World Civilizations & Forgotten History",
    "Historical Personalities & Their Real Stories",
    "History Behind Famous Monuments & Places",
    "Myths, Legends & Their Historical Origins",
]

# 8 Standard Shorts Documentary Formats
SHORTS_FORMAT_CLASSES = [
    "historical_fact",
    "archaeological_discovery",
    "forgotten_personality",
    "battle_strategy",
    "ancient_engineering",
    "historical_mystery",
    "myth_vs_fact",
    "documentary_teaser",
]


def classify_content_pillar(title: str, topic: str = "") -> str:
    """Classifies a video into one of the 10 canonical historical content pillars."""
    text = f"{title} {topic}".lower()
    if any(k in text for k in ("indus", "harappa", "mohenjo", "rakhigarhi", "vedic", "saraswati", "dholavira")):
        return "Ancient Indian Civilizations"
    if any(k in text for k in ("maurya", "chola", "gupta", "maratha", "ashoka", "chandragupta", "shivaji", "samudragupta", "empire", "dynasty", "king", "samrat")):
        return "Indian Kings, Empires & Dynasties"
    if any(k in text for k in ("battle", "war", "haldighati", "tarain", "panipat", "kalinga", "warfare", "siege", "सेना", "युद्ध")):
        return "Historical Battles & Military Strategy"
    if any(k in text for k in ("dwarka", "submerged", "underwater", "keezhadi", "excavation", "lost city", "archaeolog")):
        return "Lost Cities & Archaeological Discoveries"
    if any(k in text for k in ("kailash", "iron pillar", "stepwell", "engineering", "architecture", "metallurgy", "temple acoustic", "वास्तुकला")):
        return "Ancient Technology, Architecture & Engineering"
    if any(k in text for k in ("mystery", "kuldhara", "undeciphered", "script", "disappearance", "secret", "रहस्य", "पहेली")):
        return "Historical Mysteries & Unresolved Questions"
    if any(k in text for k in ("mesopotamia", "egypt", "persia", "silk road", "alexandria", "sumer", "rome", "greece")):
        return "World Civilizations & Forgotten History"
    if any(k in text for k in ("chanakya", "xuanzang", "durgavati", "megasthenes", "aryabhata", "charak", "personality", "hero")):
        return "Historical Personalities & Their Real Stories"
    if any(k in text for k in ("nalanda", "konark", "brihadisvara", "chittorgarh", "ajanta", "ellora", "monument", "fort", "किला")):
        return "History Behind Famous Monuments & Places"
    if any(k in text for k in ("ram setu", "koh-i-noor", "myth", "legend", "folklore", "पौराणिक")):
        return "Myths, Legends & Their Historical Origins"

    return "Historical Mysteries & Unresolved Questions"


def classify_shorts_format(title: str, topic: str = "", metadata: Optional[dict] = None) -> str:
    """Classifies a Short into one of the 8 canonical Shorts documentary formats."""
    meta = metadata or {}
    explicit = meta.get("format") or meta.get("shorts_format")
    if explicit and str(explicit).lower() in SHORTS_FORMAT_CLASSES:
        return str(explicit).lower()

    text = f"{title} {topic}".lower()
    if any(k in text for k in ("fact", "सच", "did you know", "क्या आप जानते")):
        return "historical_fact"
    if any(k in text for k in ("discovery", "excavation", "found", "khoj", "खोज")):
        return "archaeological_discovery"
    if any(k in text for k in ("king", "queen", "hero", "who was", "personality", "chanakya", "durgavati")):
        return "forgotten_personality"
    if any(k in text for k in ("tactic", "strategy", "battle", "war", "weapon", "defense", "रणनीति")):
        return "battle_strategy"
    if any(k in text for k in ("how was", "built", "engineering", "carved", "iron", "architecture")):
        return "ancient_engineering"
    if any(k in text for k in ("myth", "debunk", "fake", "true or false", "lie", "झूठ")):
        return "myth_vs_fact"
    if any(k in text for k in ("teaser", "full documentary", "watch full", "trailer")):
        return "documentary_teaser"

    return "historical_mystery"


def classify_hook_style(title: str, metadata: Optional[dict] = None) -> str:
    """Classifies opening hook style for topic/hook performance tracking."""
    meta = metadata or {}
    explicit = meta.get("hook_style")
    if explicit:
        return str(explicit).lower()
    t = (title or "").lower()
    if "?" in t or any(w in t for w in ("why", "how", "did", "what", "क्यों", "कैसे", "क्या")):
        return "question_paradox"
    if any(w in t for w in ("secret", "hidden", "truth", "never", "myth", "रहस्य", "सच", "छुपा")):
        return "contradiction_secret"
    if any(w in t for w in ("found", "discovered", "submerged", "excavation", "carved", "खोज")):
        return "artifact_reveal"
    return "narrative_chronicle"


def _fmt_metric(val: Any, suffix: str = "", unavailable_label: str = "Unavailable") -> str:
    """Format metric value for Markdown, displaying unavailable_label when None instead of 0."""
    if val is None:
        return unavailable_label
    return f"{val}{suffix}"


def _summarize_dimension_buckets(groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Shared helper to summarize performance across topic, hook, or duration buckets."""
    summary: Dict[str, Dict[str, Any]] = {}
    for bucket, items in groups.items():
        if not items:
            continue
        views_list = [float(i["views"]) for i in items if i.get("views") is not None]
        apv_list = [float(i["apv"]) for i in items if i.get("apv") is not None and float(i["apv"]) > 0]
        avd_list = [float(i["avd"]) for i in items if i.get("avd") is not None and float(i["avd"]) > 0]
        wt_list = [float(i["watch_time"]) for i in items if i.get("watch_time") is not None]
        wt_total = round(sum(wt_list), 2) if wt_list else None
        summary[bucket] = {
            "count": len(items),
            "median_views": calculate_median(views_list) if views_list else None,
            "avg_views": int(sum(views_list) / len(views_list)) if views_list else None,
            "total_watch_time_minutes": wt_total,
            "avg_apv": round(sum(apv_list) / len(apv_list), 2) if apv_list else None,
            "avg_view_duration_seconds": round(sum(avd_list) / len(avd_list), 1) if avd_list else None,
            "confidence": "preliminary (sample < 3)" if len(items) < 3 else "directional (sample >= 3)",
        }
    return summary


def analyze_shorts_performance(shorts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Performs independent analysis of YouTube Shorts:
    - Median views per video, watch time, AVD, APV, subscriber conversion per 1,000 views
    - Returning viewers (where available)
    - Breakdown by format (8 classes), topic pillar, hook style, and duration bucket
    - Accounts for publication age via age-adjusted view velocity
    - Prevents premature conclusions if sample size < 3
    """
    if not shorts:
        return {
            "sample_size": 0,
            "status": "insufficient_data",
            "message": "No Shorts data recorded in the historical performance database.",
            "total_views": 0,
            "median_views_per_video": 0.0,
            "total_watch_time_minutes": 0.0,
            "avg_watch_time_minutes": 0.0,
            "avg_view_duration_seconds": 0.0,
            "median_view_duration_seconds": 0.0,
            "observed_avg_apv": 0.0,
            "median_apv": 0.0,
            "target_apv_benchmark": 70.0,
            "retention_benchmarks": {"target_apv": 70.0, "observed_avg_apv": 0.0},
            "total_subscribers_gained": 0,
            "sub_conversion_per_1k": 0.0,
            "returning_viewers": {"available": False, "total": None, "note": "No Shorts records available."},
            "format_breakdown": {},
            "topic_breakdown": {},
            "hook_breakdown": {},
            "duration_breakdown": {},
            "avg_publication_age_days": None,
            "median_age_adjusted_velocity": 0.0,
            "observations": ["Initial baseline phase: Produce and track at least 3 Shorts per format."],
        }

    format_groups: Dict[str, List[dict]] = {f: [] for f in SHORTS_FORMAT_CLASSES}
    topic_groups: Dict[str, List[dict]] = {}
    hook_groups: Dict[str, List[dict]] = {}
    duration_groups: Dict[str, List[dict]] = {"under_35s": [], "35_to_50s": [], "over_50s": [], "unknown_duration": []}

    total_views = 0
    views_present = False
    watch_samples: List[float] = []
    subs_samples: List[int] = []
    views_list: List[float] = []
    avd_list: List[float] = []
    apv_list: List[float] = []
    apv_present = False
    avd_present = False
    ret_viewers_list: List[int] = []
    age_days_list: List[float] = []
    age_velocities: List[float] = []

    for s in shorts:
        m = s.get("latest_metrics", {})
        raw_views = m.get("views")
        views = int(raw_views) if raw_views is not None else None
        raw_wt = m.get("watch_time_minutes")
        watch_min = float(raw_wt) if raw_wt is not None else None
        raw_avd = m.get("average_view_duration_seconds")
        avd = float(raw_avd) if raw_avd is not None else None
        raw_apv = m.get("average_percentage_viewed")
        apv = float(raw_apv) if raw_apv is not None else None
        raw_subs = m.get("subscribers_gained")
        subs = int(raw_subs) if raw_subs is not None else None
        ret_v = m.get("returning_viewers")
        dur = float(s.get("video_duration_seconds", 0.0) or 0.0)
        meta = s.get("metadata_extras", {})

        if views is not None:
            views_present = True
            total_views += views
            views_list.append(float(views))
        if watch_min is not None:
            watch_samples.append(watch_min)
        if subs is not None:
            subs_samples.append(subs)
        if avd is not None:
            avd_present = True
            if avd > 0:
                avd_list.append(avd)
        if apv is not None:
            apv_present = True
            if apv > 0:
                apv_list.append(apv)
        if ret_v is not None:
            ret_viewers_list.append(int(ret_v))

        age_days = compute_publication_age_days(s.get("publication_timestamp"))
        if age_days is not None and views is not None:
            age_days_list.append(age_days)
            age_velocities.append(normalize_views_by_age(views, age_days))

        title = s.get("title", "")
        topic = s.get("topic", "")
        pillar = s.get("content_pillar") or classify_content_pillar(title, topic)
        fmt = classify_shorts_format(title, topic, meta)
        hook_style = classify_hook_style(title, meta)

        item_summary = {
            "video_id": s.get("video_id"),
            "title": title,
            "topic": topic,
            "views": views,
            "watch_time": watch_min,
            "avd": avd,
            "apv": apv,
            "duration": dur,
            "subs": subs,
        }

        format_groups.setdefault(fmt, []).append(item_summary)
        topic_groups.setdefault(pillar, []).append(item_summary)
        hook_groups.setdefault(hook_style, []).append(item_summary)

        if dur > 0:
            if dur < 35.0:
                duration_groups["under_35s"].append(item_summary)
            elif dur <= 50.0:
                duration_groups["35_to_50s"].append(item_summary)
            else:
                duration_groups["over_50s"].append(item_summary)
        else:
            duration_groups["unknown_duration"].append(item_summary)

    total_watch_min = round(sum(watch_samples), 2) if watch_samples else None
    avg_watch_min = round(sum(watch_samples) / len(watch_samples), 2) if watch_samples else None
    total_subs = sum(subs_samples) if subs_samples else None
    median_views = calculate_median(views_list) if views_present else None
    observed_avg_apv = (round(sum(apv_list) / len(apv_list), 2) if apv_list else 0.0) if apv_present else None
    median_apv = (calculate_median(apv_list) if apv_list else 0.0) if apv_present else None
    avg_avd = (round(sum(avd_list) / len(avd_list), 1) if avd_list else 0.0) if avd_present else None
    median_avd = (calculate_median(avd_list) if avd_list else 0.0) if avd_present else None
    sub_conv = (round((total_subs / total_views * 1000), 2) if total_views > 0 else 0.0) if total_subs is not None else None
    returning_info = (
        {"available": True, "total": sum(ret_viewers_list)}
        if ret_viewers_list
        else {
            "available": False,
            "total": None,
            "note": "Returning viewers unavailable (requires YouTube Analytics API v2 audience-type support with yt-analytics.readonly scope).",
        }
    )

    format_summary = {}
    for fmt, vids in format_groups.items():
        if not vids:
            format_summary[fmt] = {
                "count": 0,
                "avg_views": 0,
                "median_views": 0.0,
                "avg_apv": None,
                "confidence": "no_data",
            }
            continue

        cnt = len(vids)
        v_vals = [float(v["views"]) for v in vids if v["views"] is not None]
        avg_v = int(sum(v_vals) / len(v_vals)) if v_vals else 0
        has_fmt_apv = any(v["apv"] is not None for v in vids)
        pcts = [v["apv"] for v in vids if v["apv"] is not None and v["apv"] > 0]
        avg_pct = (round(sum(pcts) / len(pcts), 2) if pcts else 0.0) if has_fmt_apv else None
        conf = "high (sample >= 3)" if cnt >= 3 else "preliminary (sample < 3)"
        format_summary[fmt] = {
            "count": cnt,
            "avg_views": avg_v,
            "median_views": calculate_median(v_vals) if v_vals else 0.0,
            "avg_apv": avg_pct,
            "confidence": conf,
        }

    # Formulate evidence-based observations
    observations = []
    if len(shorts) < 3:
        observations.append(f"Sample size is limited ({len(shorts)} Short(s)). Withhold definitive hook conclusions until >= 3 samples per format are logged.")
    else:
        viable_formats = {k: v for k, v in format_summary.items() if v["count"] >= 3}
        if viable_formats:
            best_fmt = max(viable_formats.items(), key=lambda x: (x[1]["avg_apv"] or 0.0, x[1]["median_views"]))
            if best_fmt[1]["avg_apv"] is not None and best_fmt[1]["avg_apv"] > 0:
                observations.append(
                    f"Strongest observed Shorts format (correlation, N={best_fmt[1]['count']}): "
                    f"'{best_fmt[0]}' (Avg APV: {best_fmt[1]['avg_apv']}%, Median Views: {best_fmt[1]['median_views']})."
                )
            else:
                observations.append(
                    f"Leading observed Shorts format by public views (retention APV unavailable — pending Analytics OAuth scope, N={best_fmt[1]['count']}): "
                    f"'{best_fmt[0]}' (Median Views: {best_fmt[1]['median_views']})."
                )
        else:
            observations.append("All individual Shorts formats currently have < 3 samples. Topic clusters are actively gathering data.")

    if observed_avg_apv is None:
        observations.append("Shorts APV, watch time, AVD, and subscriber conversion are currently unavailable (requires YouTube Analytics API v2 yt-analytics.readonly scope).")
    elif observed_avg_apv > 0 and observed_avg_apv < 70.0:
        observations.append(f"Average percentage viewed is {observed_avg_apv}%, below the 70.0% viral benchmark for Shorts. Pacing must eliminate slow preamble in the first 2.5 seconds.")

    return {
        "sample_size": len(shorts),
        "total_views": total_views,
        "median_views_per_video": median_views,
        "total_watch_time_minutes": total_watch_min,
        "avg_watch_time_minutes": avg_watch_min,
        "avg_view_duration_seconds": avg_avd,
        "median_view_duration_seconds": median_avd,
        "total_subscribers_gained": total_subs,
        "sub_conversion_per_1k": sub_conv,
        "observed_avg_apv": observed_avg_apv,
        "median_apv": median_apv,
        "target_apv_benchmark": 70.0,
        "metrics_availability": {
            "views": views_present,
            "watch_time_minutes": bool(watch_samples),
            "average_view_duration_seconds": avd_present,
            "average_percentage_viewed": apv_present,
            "subscribers_gained": bool(subs_samples),
            "returning_viewers": returning_info["available"],
        },
        "returning_viewers": returning_info,
        "avg_publication_age_days": round(sum(age_days_list) / len(age_days_list), 2) if age_days_list else None,
        "median_age_adjusted_velocity": calculate_median(age_velocities),
        "format_breakdown": format_summary,
        "topic_breakdown": _summarize_dimension_buckets(topic_groups),
        "hook_breakdown": _summarize_dimension_buckets(hook_groups),
        "duration_breakdown": _summarize_dimension_buckets(duration_groups),
        "observations": observations,
        "swiped_away_reporting": "API does not expose granular swiped-away ratios in v2 dimensions; engagement and APV proxy used.",
    }


def analyze_longform_performance(longform: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Performs independent analysis of long-form documentaries:
    - Median views per video, Watch Time, AVD, APV, Impressions, CTR, Subscriber conversion/1k, Returning viewers
    - Explicitly separates packaging diagnostics (Impressions / CTR) from storytelling/retention diagnostics (AVD / APV)
    - Breakdown by topic pillar, hook style, and duration bucket
    - Accounts for video publication age via age-adjusted velocity
    - Traffic source breakdown
    """
    if not longform:
        return {
            "sample_size": 0,
            "status": "insufficient_data",
            "message": "No long-form documentary data recorded in the historical performance database.",
            "total_views": 0,
            "median_views_per_video": 0.0,
            "total_watch_time_minutes": 0.0,
            "avg_view_duration_seconds": 0.0,
            "median_view_duration_seconds": 0.0,
            "total_subscribers_gained": 0,
            "sub_conversion_per_1k": 0.0,
            "returning_viewers": {"available": False, "total": None, "note": "No long-form records available."},
            "packaging_diagnostics": {},
            "storytelling_diagnostics": {},
            "topic_breakdown": {},
            "hook_breakdown": {},
            "duration_breakdown": {},
            "avg_publication_age_days": None,
            "median_age_adjusted_velocity": 0.0,
            "traffic_sources": {},
            "observations": ["Initial baseline phase: Produce and publish at least 3 long-form documentaries to gather retention data."],
        }

    total_views = 0
    views_present = False
    watch_samples: List[float] = []
    impr_samples: List[int] = []
    subs_samples: List[int] = []
    views_list: List[float] = []
    ctr_list: List[float] = []
    ctr_present = False
    avd_list: List[float] = []
    avd_present = False
    apv_list: List[float] = []
    apv_present = False
    ret_viewers_list: List[int] = []
    age_days_list: List[float] = []
    age_velocities: List[float] = []

    topic_groups: Dict[str, List[dict]] = {}
    hook_groups: Dict[str, List[dict]] = {}
    duration_groups: Dict[str, List[dict]] = {"under_8m": [], "8_to_11m": [], "11_to_15m": [], "over_15m": [], "unknown_duration": []}
    traffic_aggregate: Dict[str, int] = {}

    for lf in longform:
        m = lf.get("latest_metrics", {})
        raw_views = m.get("views")
        views = int(raw_views) if raw_views is not None else None
        raw_wt = m.get("watch_time_minutes")
        watch_min = float(raw_wt) if raw_wt is not None else None
        raw_impr = m.get("impressions")
        impr = int(raw_impr) if raw_impr is not None else None
        raw_ctr = m.get("ctr")
        ctr = float(raw_ctr) if raw_ctr is not None else None
        raw_avd = m.get("average_view_duration_seconds")
        avd = float(raw_avd) if raw_avd is not None else None
        raw_apv = m.get("average_percentage_viewed")
        apv = float(raw_apv) if raw_apv is not None else None
        raw_subs = m.get("subscribers_gained")
        subs = int(raw_subs) if raw_subs is not None else None
        ret_v = m.get("returning_viewers")
        dur = float(lf.get("video_duration_seconds", 0.0) or 0.0)
        meta = lf.get("metadata_extras", {})

        if views is not None:
            views_present = True
            total_views += views
            views_list.append(float(views))
        if watch_min is not None:
            watch_samples.append(watch_min)
        if impr is not None:
            impr_samples.append(impr)
        if subs is not None:
            subs_samples.append(subs)

        if ctr is not None:
            ctr_present = True
            if ctr > 0:
                ctr_list.append(ctr)
        if avd is not None:
            avd_present = True
            if avd > 0:
                avd_list.append(avd)
        if apv is not None:
            apv_present = True
            if apv > 0:
                apv_list.append(apv)
        if ret_v is not None:
            ret_viewers_list.append(int(ret_v))

        age_days = compute_publication_age_days(lf.get("publication_timestamp"))
        if age_days is not None and views is not None:
            age_days_list.append(age_days)
            age_velocities.append(normalize_views_by_age(views, age_days))

        title = lf.get("title", "")
        topic = lf.get("topic", "")
        pillar = lf.get("content_pillar") or classify_content_pillar(title, topic)
        hook_style = classify_hook_style(title, meta)

        item_summary = {
            "video_id": lf.get("video_id"),
            "title": title,
            "topic": topic,
            "views": views,
            "watch_time": watch_min,
            "avd": avd,
            "apv": apv,
            "duration": dur,
            "subs": subs,
        }
        topic_groups.setdefault(pillar, []).append(item_summary)
        hook_groups.setdefault(hook_style, []).append(item_summary)

        if dur > 0:
            if dur < 480.0:
                duration_groups["under_8m"].append(item_summary)
            elif dur <= 660.0:
                duration_groups["8_to_11m"].append(item_summary)
            elif dur <= 900.0:
                duration_groups["11_to_15m"].append(item_summary)
            else:
                duration_groups["over_15m"].append(item_summary)
        else:
            duration_groups["unknown_duration"].append(item_summary)

        for ts in lf.get("traffic_sources", []):
            src_name = ts.get("traffic_source", "OTHER")
            traffic_aggregate[src_name] = traffic_aggregate.get(src_name, 0) + ts.get("views", 0)

    total_watch_min = round(sum(watch_samples), 1) if watch_samples else None
    avg_watch_min = round(sum(watch_samples) / len(watch_samples), 2) if watch_samples else None
    total_impressions = sum(impr_samples) if impr_samples else None
    total_subs = sum(subs_samples) if subs_samples else None
    median_views = calculate_median(views_list) if views_present else None
    avg_ctr = (round(sum(ctr_list) / len(ctr_list), 4) if ctr_list else 0.0) if ctr_present else None
    median_ctr = (calculate_median(ctr_list) if ctr_list else 0.0) if ctr_present else None
    avg_avd = (round(sum(avd_list) / len(avd_list), 1) if avd_list else 0.0) if avd_present else None
    median_avd = (calculate_median(avd_list) if avd_list else 0.0) if avd_present else None
    avg_apv = (round(sum(apv_list) / len(apv_list), 2) if apv_list else 0.0) if apv_present else None
    median_apv = (calculate_median(apv_list) if apv_list else 0.0) if apv_present else None
    sub_conv = (round((total_subs / total_views * 1000), 2) if total_views > 0 else 0.0) if total_subs is not None else None
    returning_info = (
        {"available": True, "total": sum(ret_viewers_list)}
        if ret_viewers_list
        else {
            "available": False,
            "total": None,
            "note": "Returning viewers unavailable (requires YouTube Analytics API v2 audience-type support with yt-analytics.readonly scope).",
        }
    )

    ctr_avail = (total_impressions is not None and total_impressions > 0) or len(ctr_list) > 0
    # Diagnostic separation: Packaging vs Storytelling
    packaging_diag = {
        "total_impressions": total_impressions,
        "avg_ctr": avg_ctr,
        "median_ctr": median_ctr,
        "ctr_available": ctr_avail,
        "evaluation": (
            "Unavailable: Impressions and CTR are not exposed via standard YouTube Analytics API v2 reports.query."
            if not ctr_avail else
            "Healthy CTR (>= 4.0%)" if (avg_ctr or 0.0) >= 0.04 else
            "Low CTR (< 4.0%): Evaluate impressions volume and traffic source context before modifying thumbnail design."
            if (total_impressions or 0) > 500 else "Insufficient impressions volume to judge thumbnail packaging."
        ),
    }

    storytelling_diag = {
        "avg_view_duration_seconds": avg_avd,
        "median_view_duration_seconds": median_avd,
        "avg_percentage_viewed": avg_apv,
        "median_percentage_viewed": median_apv,
        "target_apv_benchmark": 45.0,
        "evaluation": (
            "Unavailable (requires YouTube Analytics API v2 yt-analytics.readonly scope)."
            if avg_apv is None else
            "Strong retention (>= 45.0% APV)" if avg_apv >= 45.0 else
            f"Retention bottleneck (Avg APV: {avg_apv}% < 45.0% benchmark). Pacing and chapter transitions require reinforcement."
            if avg_apv > 0 else "Pending retention observation."
        ),
        "first_30s_retention": "Granular second-by-second curve not exposed via API v2 standard queries; aggregate APV utilized.",
    }

    observations = []
    if len(longform) < 3:
        observations.append(f"Sample size is preliminary ({len(longform)} documentary video(s)). Gather >= 3 published long-form videos for full trend validity.")

    if ctr_avail and avg_ctr is not None and avg_ctr < 0.04 and (total_impressions or 0) > 1000:
        search_traffic = traffic_aggregate.get("YT_SEARCH", 0)
        browse_traffic = traffic_aggregate.get("BROWSE_FEATURES", 0)
        observations.append(
            f"Packaging observation: Impressions are substantial ({total_impressions}) with {avg_ctr*100:.1f}% CTR. "
            f"Browse share: {browse_traffic}, Search share: {search_traffic}. Consider testing Curiosity-oriented title angle in next scheduled run."
        )

    if avg_apv is None:
        observations.append("Long-form watch time, AVD, APV, and subscriber conversion are currently unavailable (requires YouTube Analytics API v2 yt-analytics.readonly scope).")
    elif avg_apv > 0 and avg_apv < 45.0:
        observations.append(
            f"Storytelling observation: APV is {avg_apv}% (< 45% standard). Reinforce Chapter 1 hook and align mid-video evidence reveals with topic."
        )

    return {
        "sample_size": len(longform),
        "total_views": total_views,
        "median_views_per_video": median_views,
        "total_watch_time_minutes": total_watch_min,
        "avg_watch_time_minutes": avg_watch_min,
        "avg_view_duration_seconds": avg_avd,
        "median_view_duration_seconds": median_avd,
        "total_subscribers_gained": total_subs,
        "sub_conversion_per_1k": sub_conv,
        "metrics_availability": {
            "views": views_present,
            "watch_time_minutes": bool(watch_samples),
            "average_view_duration_seconds": avd_present,
            "average_percentage_viewed": apv_present,
            "impressions_and_ctr": ctr_avail,
            "subscribers_gained": bool(subs_samples),
            "returning_viewers": returning_info["available"],
        },
        "returning_viewers": returning_info,
        "avg_publication_age_days": round(sum(age_days_list) / len(age_days_list), 2) if age_days_list else None,
        "median_age_adjusted_velocity": calculate_median(age_velocities),
        "packaging_diagnostics": packaging_diag,
        "storytelling_diagnostics": storytelling_diag,
        "topic_breakdown": _summarize_dimension_buckets(topic_groups),
        "hook_breakdown": _summarize_dimension_buckets(hook_groups),
        "duration_breakdown": _summarize_dimension_buckets(duration_groups),
        "traffic_sources": traffic_aggregate,
        "observations": observations,
    }


def analyze_topic_pillars(all_videos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates historical traction across the channel's 10 content pillars:
    - High-performing pillars
    - Underperforming pillars
    - Underexplored pillars (0 or few published videos)
    - Pillars leading in subscriber conversion & watch time
    - Guarantees popularity is never confused with historical research quality
    """
    pillar_stats: Dict[str, Dict[str, Any]] = {
        p: {
            "name": p,
            "video_count": 0,
            "total_views": 0,
            "total_watch_min": 0.0,
            "total_subs": 0,
            "avg_views": 0,
            "avg_apv": 0.0,
            "apv_samples": [],
            "titles": [],
        }
        for p in HISTORICAL_PILLARS
    }

    for v in all_videos:
        title = v.get("title", "")
        topic = v.get("topic", "")
        pillar = v.get("content_pillar") or classify_content_pillar(title, topic)
        if pillar not in pillar_stats:
            pillar = classify_content_pillar(title, topic)

        m = v.get("latest_metrics", {})
        views = int(m.get("views") or 0)
        watch_min = float(m.get("watch_time_minutes") or 0.0)
        subs = int(m.get("subscribers_gained") or 0)
        apv = float(m.get("average_percentage_viewed") or 0.0)

        p_entry = pillar_stats[pillar]
        p_entry["video_count"] += 1
        p_entry["total_views"] += views
        p_entry["total_watch_min"] += watch_min
        p_entry["total_subs"] += subs
        p_entry["titles"].append(title)
        if apv > 0:
            p_entry["apv_samples"].append(apv)

    # Compute averages
    for p, data in pillar_stats.items():
        cnt = data["video_count"]
        if cnt > 0:
            data["avg_views"] = int(data["total_views"] / cnt)
            data["avg_apv"] = round(sum(data["apv_samples"]) / len(data["apv_samples"]), 2) if data["apv_samples"] else 0.0
            data["sub_conv_per_1k"] = round((data["total_subs"] / data["total_views"] * 1000), 2) if data["total_views"] > 0 else 0.0
        else:
            data["avg_views"] = 0
            data["avg_apv"] = 0.0
            data["sub_conv_per_1k"] = 0.0

    # Categorize pillars
    active_pillars = [p for p in pillar_stats.values() if p["video_count"] > 0]
    underexplored = [p["name"] for p in pillar_stats.values() if p["video_count"] == 0]

    high_performing = sorted(active_pillars, key=lambda x: (x["avg_views"], x["avg_apv"]), reverse=True)[:3]
    weak_performing = sorted(active_pillars, key=lambda x: x["avg_views"])[:2] if len(active_pillars) >= 3 else []
    sub_leaders = sorted(active_pillars, key=lambda x: x["sub_conv_per_1k"], reverse=True)[:2] if active_pillars else []
    watch_leaders = sorted(active_pillars, key=lambda x: x["total_watch_min"], reverse=True)[:2] if active_pillars else []

    return {
        "evaluated_pillars_count": len(HISTORICAL_PILLARS),
        "active_pillars_count": len(active_pillars),
        "underexplored_pillars": underexplored,
        "high_performing_pillars": [h["name"] for h in high_performing if h["total_views"] > 0],
        "weak_performing_pillars": [w["name"] for w in weak_performing],
        "subscriber_conversion_leaders": [s["name"] for s in sub_leaders if s["sub_conv_per_1k"] > 0],
        "watch_time_leaders": [w["name"] for w in watch_leaders if w["total_watch_min"] > 0],
        "pillar_statistics": pillar_stats,
        "governance_note": "Research quality gate remains mandatory. Popularity never overrides verified archaeological evidence.",
    }


def analyze_title_and_thumbnail(all_videos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Studies empirical title and thumbnail patterns:
    - Title lengths, Hindi vs English phrasing, Search vs Story vs Curiosity patterns
    - Style traction across impact, cinematic, split, and studio
    - Note on official thumbnail testing: native Test & Compare feature is not in Data API v3;
      system executes controlled manual experiments.
    """
    title_styles = {"search_oriented": 0, "story_oriented": 0, "curiosity_oriented": 0}
    lengths = {"short (<50)": 0, "medium (50-75)": 0, "long (>75)": 0}

    for v in all_videos:
        title = v.get("title", "")
        t_len = len(title)
        if t_len < 50:
            lengths["short (<50)"] += 1
        elif t_len <= 75:
            lengths["medium (50-75)"] += 1
        else:
            lengths["long (>75)"] += 1

        t_low = title.lower()
        if any(w in t_low for w in ("?", "क्यों", "रहस्य", "छुपाया", "untold", "secret", "why")):
            title_styles["curiosity_oriented"] += 1
        elif any(w in t_low for w in ("दास्तान", "गाथा", "rise", "fall", "कथा", "war")):
            title_styles["story_oriented"] += 1
        else:
            title_styles["search_oriented"] += 1

    return {
        "title_length_distribution": lengths,
        "title_angle_distribution": title_styles,
        "recommended_title_practice": "Target 50–70 characters with Devanagari Hindi clarity; keep crucial historical entity in the first 35 characters.",
        "thumbnail_testing_status": "Manual controlled experiment framework active. Official YouTube native 'Test & Compare' is not supported via public Data API v3.",
    }


def analyze_production_and_quality_gates(
    production_db: Optional[Dict[str, Any]] = None,
    diagnostics_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates production failures and automated quality-gate rejection rates
    from uploader/safety.py (production_database.json) and output/diagnostics/.
    """
    from uploader.safety import load_production_db, PublishingState
    from uploader.quality_gates import DIAGNOSTICS_DIR

    prod_db = production_db if production_db is not None else load_production_db()
    diag_dir = diagnostics_dir or DIAGNOSTICS_DIR

    total_records = len(prod_db)
    blocked_count = 0
    failed_count = 0
    gate_failures: Dict[str, int] = {"research": 0, "script": 0, "video": 0, "metadata": 0}
    recent_blocking_reasons: List[str] = []

    for rec in prod_db.values():
        if not isinstance(rec, dict):
            continue
        state_val = rec.get("current_state", "")
        if state_val == PublishingState.BLOCKED_QUALITY_GATE.value:
            blocked_count += 1
        elif state_val == PublishingState.FAILED.value:
            failed_count += 1

        q_gate = rec.get("quality_gate") or rec.get("metadata", {}).get("quality_report")
        if isinstance(q_gate, dict) and not q_gate.get("passed", True):
            for gate_name, gate_res in q_gate.get("gates", {}).items():
                if isinstance(gate_res, dict) and not gate_res.get("passed", True):
                    gate_failures[gate_name] = gate_failures.get(gate_name, 0) + 1
            for iss in q_gate.get("blocking_issues", [])[:3]:
                if iss not in recent_blocking_reasons:
                    recent_blocking_reasons.append(iss)

    diag_total = 0
    diag_blocked = 0
    if diag_dir and os.path.exists(diag_dir):
        for fname in os.listdir(diag_dir):
            if not fname.endswith(".json"):
                continue
            diag_total += 1
            try:
                with open(os.path.join(diag_dir, fname), encoding="utf-8") as f:
                    d = json.load(f)
                if not d.get("passed", True):
                    diag_blocked += 1
            except Exception:
                pass

    effective_total = max(total_records, diag_total)
    effective_blocked = max(blocked_count, diag_blocked)
    rejection_rate_pct = round((effective_blocked / effective_total) * 100, 2) if effective_total > 0 else 0.0
    failure_rate_pct = round((failed_count / total_records) * 100, 2) if total_records > 0 else 0.0

    return {
        "total_tracked_productions": total_records,
        "diagnostics_evaluated": diag_total,
        "quality_gate_blocked_count": effective_blocked,
        "quality_gate_rejection_rate_pct": rejection_rate_pct,
        "production_failures_count": failed_count,
        "production_failure_rate_pct": failure_rate_pct,
        "gate_failure_breakdown": gate_failures,
        "recent_blocking_reasons": recent_blocking_reasons[:5],
        "quality_gate_enforcement": "Mandatory per-video enforcement; failing videos are blocked individually without lowering channel standards.",
    }


def generate_growth_intelligence_dossier(
    evaluation_window_days: Optional[int] = None,
    db_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Compiles the full weekly YouTube Growth Intelligence Dossier for Stories Malik
    over a rolling 30-day evaluation period:
    - Preserves established 5 Shorts + 1 Long-form daily publishing cadence (Asia/Kolkata)
    - Top 10 Shorts & Top 10 Long-form videos (with publication-age accounting)
    - Separate Shorts & Long-form analysis (median views, watch time, AVD, APV, CTR, sub conversion/1k, returning viewers)
    - Performance by topic, format, hook, and duration
    - Production failures & quality-gate rejection rates
    - Analytics capabilities & explicit limitations
    - Correlation vs demonstrated improvement distinction
    - Writes output/weekly_growth_intelligence.json and output/weekly_growth_intelligence.md
    """
    from apis.youtube_analytics import get_analytics_capabilities_and_limitations

    window_days = evaluation_window_days or getattr(config, "EVALUATION_WINDOW_DAYS", 30)
    db = db_override or get_performance_db()
    all_vids = db.get_videos_in_window(days=window_days)
    shorts = db.get_videos_in_window(days=window_days, video_format="short")
    longform = db.get_videos_in_window(days=window_days, video_format="longform")
    tracker = get_experiment_tracker()

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # Sort top performers accounting for publication age velocity
    def _age_sort_key(item: Dict[str, Any], primary_metric: str) -> Tuple[float, float]:
        m = item.get("latest_metrics", {})
        views = int(m.get("views", 0) or 0)
        age = compute_publication_age_days(item.get("publication_timestamp"), now_dt)
        vel = normalize_views_by_age(views, age) if age is not None else float(views)
        return (vel, float(m.get(primary_metric, 0.0) or 0.0))

    sorted_shorts = sorted(shorts, key=lambda x: _age_sort_key(x, "average_percentage_viewed"), reverse=True)
    sorted_longform = sorted(longform, key=lambda x: _age_sort_key(x, "watch_time_minutes"), reverse=True)

    top_10_shorts = [
        {
            "video_id": s["video_id"],
            "title": s["title"],
            "topic": s["topic"],
            "views": s.get("latest_metrics", {}).get("views", 0),
            "apv": s.get("latest_metrics", {}).get("average_percentage_viewed", 0.0),
            "avd_seconds": s.get("latest_metrics", {}).get("average_view_duration_seconds", 0.0),
            "subs": s.get("latest_metrics", {}).get("subscribers_gained", 0),
            "publication_age_days": compute_publication_age_days(s.get("publication_timestamp"), now_dt),
            "age_adjusted_velocity": normalize_views_by_age(
                int(s.get("latest_metrics", {}).get("views", 0) or 0),
                compute_publication_age_days(s.get("publication_timestamp"), now_dt) or 1.0,
            ),
        }
        for s in sorted_shorts[:10]
    ]

    top_10_longform = [
        {
            "video_id": lf["video_id"],
            "title": lf["title"],
            "topic": lf["topic"],
            "views": lf.get("latest_metrics", {}).get("views", 0),
            "watch_time_minutes": lf.get("latest_metrics", {}).get("watch_time_minutes", 0.0),
            "avd_seconds": lf.get("latest_metrics", {}).get("average_view_duration_seconds", 0.0),
            "apv": lf.get("latest_metrics", {}).get("average_percentage_viewed", 0.0),
            "ctr": lf.get("latest_metrics", {}).get("ctr", 0.0),
            "subs": lf.get("latest_metrics", {}).get("subscribers_gained", 0),
            "publication_age_days": compute_publication_age_days(lf.get("publication_timestamp"), now_dt),
            "age_adjusted_velocity": normalize_views_by_age(
                int(lf.get("latest_metrics", {}).get("views", 0) or 0),
                compute_publication_age_days(lf.get("publication_timestamp"), now_dt) or 1.0,
            ),
        }
        for lf in sorted_longform[:10]
    ]

    shorts_analysis = analyze_shorts_performance(shorts)
    longform_analysis = analyze_longform_performance(longform)
    topic_intelligence = analyze_topic_pillars(all_vids)
    packaging_analysis = analyze_title_and_thumbnail(all_vids)
    production_reliability = analyze_production_and_quality_gates()
    analytics_caps = get_analytics_capabilities_and_limitations()

    # Compute data completeness (requires actual views > 0 AND owner analytics availability for full completeness)
    total_tracked = len(all_vids)
    complete_records = sum(1 for v in all_vids if (v.get("latest_metrics", {}).get("views") or 0) > 0)
    owner_complete_records = sum(1 for v in all_vids if v.get("owner_analytics_available"))
    data_completeness = round((complete_records / max(1, total_tracked)) * 100, 1)
    owner_analytics_completeness = round((owner_complete_records / max(1, total_tracked)) * 100, 1)

    # Recommended next production topics
    recommended_topics = []
    if topic_intelligence["underexplored_pillars"]:
        recommended_topics.append({
            "pillar": topic_intelligence["underexplored_pillars"][0],
            "reason": "Underexplored historical pillar on Stories Malik; expands thematic breadth while maintaining evidence rigor.",
            "target_format": "longform",
        })
    if topic_intelligence["high_performing_pillars"]:
        recommended_topics.append({
            "pillar": topic_intelligence["high_performing_pillars"][0],
            "reason": "Validated high audience traction on Stories Malik; deepens channel authority.",
            "target_format": "short",
        })
    if not recommended_topics:
        recommended_topics.append({
            "pillar": "Ancient Indian Civilizations",
            "reason": "Core foundational pillar for Stories Malik.",
            "target_format": "longform",
        })

    active_exps = tracker.get_all_experiments()
    cadence_policy = dict(getattr(config, "PUBLISHING_CADENCE_POLICY", {
        "longform_per_day": 1,
        "shorts_per_day": 5,
        "total_per_day": 6,
        "timezone": "Asia/Kolkata",
        "auto_reduce_frequency": False,
        "require_human_approval": False,
    }))

    report = {
        "channel_name": config.CHANNEL_NAME,
        "report_generated_at": now_iso,
        "evaluation_window_days": window_days,
        "review_cadence": "weekly",
        "cadence_policy": cadence_policy,
        "data_completeness_pct": data_completeness,
        "owner_analytics_completeness_pct": owner_analytics_completeness,
        "total_videos_analyzed": total_tracked,
        "shorts_count": len(shorts),
        "longform_count": len(longform),
        "top_10_shorts": top_10_shorts,
        "top_10_longform": top_10_longform,
        "shorts_performance": shorts_analysis,
        "longform_performance": longform_analysis,
        "topic_intelligence": topic_intelligence,
        "packaging_and_titles": packaging_analysis,
        "production_reliability": production_reliability,
        "analytics_capabilities": analytics_caps,
        "analytics_limitations": analytics_caps["limitations"],
        "recommended_topics": recommended_topics,
        "active_experiments": active_exps,
        "correlation_vs_demonstrated_improvement": (
            "Observational pillar/format rankings represent correlation only and account for publication age. "
            "Causal improvement requires a completed single-variable controlled experiment with statistically sufficient samples."
        ),
        "confidence_limitations": {
            "sample_size_warning": len(all_vids) < 10,
            "message": (
                "Dataset contains fewer than 10 total videos in the 30-day window. Trend insights are directional hypotheses only; "
                "publishing cadence (5 Shorts + 1 Long-form daily) is preserved without automated reduction."
                if len(all_vids) < 10 else "Sufficient statistical sample available for directional evaluation; frequency changes still require controlled experiments."
            ),
        },
    }

    # Persist JSON
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(config.OUTPUT_DIR, "weekly_growth_intelligence.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # Generate Markdown Report
    _generate_markdown_report(report)

    return report


def _generate_markdown_report(report: dict) -> None:
    """Renders executive Markdown growth report for Stories Malik."""
    cad = report.get("cadence_policy", {})
    rel = report.get("production_reliability", {})
    sh = report["shorts_performance"]
    lf = report["longform_performance"]
    lf_story = lf.get("storytelling_diagnostics", {})
    lf_pkg = lf.get("packaging_diagnostics", {})

    lines = [
        "# 📊 Stories Malik — Weekly YouTube Growth Intelligence Report",
        f"**Generated:** {report['report_generated_at']}  ",
        f"**Channel:** {report['channel_name']}  ",
        f"**Evaluation Window:** Rolling {report.get('evaluation_window_days', 30)} days (Weekly Review)  ",
        f"**Published Cadence (Preserved):** {cad.get('longform_per_day', 1)} Long-form + {cad.get('shorts_per_day', 5)} Shorts = {cad.get('total_per_day', 6)}/day ({cad.get('timezone', 'Asia/Kolkata')})  ",
        f"**Total Videos Tracked:** {report['total_videos_analyzed']} ({report['shorts_count']} Shorts, {report['longform_count']} Long-form)  ",
        f"**Data Completeness:** {report['data_completeness_pct']}%  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Confidence Limitations",
        f"> **Confidence Status:** {report['confidence_limitations']['message']}",
        "",
        f"> **Correlation vs Demonstrated Improvement:** {report.get('correlation_vs_demonstrated_improvement', '')}",
        "",
        "## 2. Shorts Performance (Independent Analysis)",
        f"- **Total Shorts Analyzed:** {sh['sample_size']}",
        f"- **Median Views per Video:** {_fmt_metric(sh.get('median_views_per_video'))}",
        f"- **Watch Time (Total / Avg):** {_fmt_metric(sh.get('total_watch_time_minutes'), ' min', 'Unavailable (pending Analytics OAuth)')} / {_fmt_metric(sh.get('avg_watch_time_minutes'), ' min', 'Unavailable')}",
        f"- **Average View Duration (AVD):** {_fmt_metric(sh.get('avg_view_duration_seconds'), 's', 'Unavailable (pending Analytics OAuth)')} (Median: {_fmt_metric(sh.get('median_view_duration_seconds'), 's', 'Unavailable')})",
        f"- **Average Percentage Viewed (APV):** {_fmt_metric(sh.get('observed_avg_apv'), '%', 'Unavailable (pending Analytics OAuth)')} (Median: {_fmt_metric(sh.get('median_apv'), '%', 'Unavailable')}, Target: {sh['target_apv_benchmark']}%)",
        f"- **Subscriber Conversion:** {_fmt_metric(sh.get('sub_conversion_per_1k'), ' subs per 1,000 views', 'Unavailable (pending Analytics OAuth)')}",
        f"- **Returning Viewers:** {sh.get('returning_viewers', {}).get('total') if sh.get('returning_viewers', {}).get('available') else sh.get('returning_viewers', {}).get('note', 'Unavailable')}",
        "- **Key Observations:**",
    ]
    for obs in sh["observations"]:
        lines.append(f"  - {obs}")

    lf_ctr_str = (
        f"{round(lf_pkg['avg_ctr'] * 100, 2)}% avg CTR"
        if lf_pkg.get("ctr_available") and lf_pkg.get("avg_ctr") is not None
        else "Unavailable via standard Analytics API v2"
    )
    lf_impr_str = _fmt_metric(lf_pkg.get("total_impressions"), " impressions", "Unavailable via standard Analytics API v2")

    lines.extend([
        "",
        "## 3. Long-Form Documentaries (Independent Analysis)",
        f"- **Total Long-form Analyzed:** {lf['sample_size']}",
        f"- **Median Views per Video:** {_fmt_metric(lf.get('median_views_per_video'))}",
        f"- **Watch Time (Total / Avg):** {_fmt_metric(lf.get('total_watch_time_minutes'), ' min', 'Unavailable (pending Analytics OAuth)')} / {_fmt_metric(lf.get('avg_watch_time_minutes'), ' min', 'Unavailable')}",
        f"- **Average View Duration (AVD):** {_fmt_metric(lf_story.get('avg_view_duration_seconds'), 's', 'Unavailable (pending Analytics OAuth)')} (Median: {_fmt_metric(lf_story.get('median_view_duration_seconds'), 's', 'Unavailable')})",
        f"- **Average Percentage Viewed (APV):** {_fmt_metric(lf_story.get('avg_percentage_viewed'), '%', 'Unavailable (pending Analytics OAuth)')} (Median: {_fmt_metric(lf_story.get('median_percentage_viewed'), '%', 'Unavailable')})",
        f"- **Impressions / CTR:** {lf_impr_str} / {lf_ctr_str}",
        f"- **Subscriber Conversion:** {_fmt_metric(lf.get('sub_conversion_per_1k'), ' subs per 1,000 views', 'Unavailable (pending Analytics OAuth)')}",
        f"- **Returning Viewers:** {lf.get('returning_viewers', {}).get('total') if lf.get('returning_viewers', {}).get('available') else lf.get('returning_viewers', {}).get('note', 'Unavailable')}",
        f"- **Packaging Evaluation:** {lf_pkg.get('evaluation', 'N/A')}",
        f"- **Storytelling Evaluation:** {lf_story.get('evaluation', 'N/A')}",
        "- **Key Observations:**",
    ])
    for obs in lf["observations"]:
        lines.append(f"  - {obs}")

    lines.extend([
        "",
        "## 4. Production Failures & Quality-Gate Rejection Rates",
        f"- **Tracked Productions:** {rel.get('total_tracked_productions', 0)} (Diagnostics Evaluated: {rel.get('diagnostics_evaluated', 0)})",
        f"- **Quality-Gate Rejection Rate:** {rel.get('quality_gate_rejection_rate_pct', 0.0)}% ({rel.get('quality_gate_blocked_count', 0)} blocked individually)",
        f"- **Production Failure Rate:** {rel.get('production_failure_rate_pct', 0.0)}% ({rel.get('production_failures_count', 0)} failed)",
        "",
        "## 5. Historical Content Pillar Intelligence",
        f"- **Active Pillars:** {report['topic_intelligence']['active_pillars_count']} / {report['topic_intelligence']['evaluated_pillars_count']}",
        f"- **High-Performing Pillars:** {', '.join(report['topic_intelligence']['high_performing_pillars']) or 'Gathering baseline'}",
        f"- **Underexplored Pillars:** {', '.join(report['topic_intelligence']['underexplored_pillars'][:4])}...",
        "",
        "## 6. Analytics Scope & API Limitations",
    ])
    for lim in report.get("analytics_limitations", []):
        lines.append(f"- {lim}")

    lines.extend([
        "",
        "## 7. Recommended Production Topics",
    ])
    for rec in report["recommended_topics"]:
        lines.append(f"- **Pillar:** {rec['pillar']} ({rec['target_format']}) — *{rec['reason']}*")

    lines.extend([
        "",
        "## 8. Active Controlled Experiments",
    ])
    for exp in report["active_experiments"]:
        lines.append(f"- **[{exp['id']}] {exp['name']}** ({exp['category']}, {exp['status']}): {exp['hypothesis']} (Confidence: {exp.get('confidence_level', 'pending')})")

    lines.append("")
    md_path = os.path.join(config.OUTPUT_DIR, "weekly_growth_intelligence.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def get_adaptive_production_brief() -> Dict[str, Any]:
    """
    Returns concise, real-time directive for production agents based on historical intelligence.
    Influences topic discovery, researcher depth, scriptwriter pacing, SEO title angle, and thumbnail style.
    """
    dossier = generate_growth_intelligence_dossier()
    topic_intel = dossier.get("topic_intelligence", {})
    shorts_perf = dossier.get("shorts_performance", {})
    lf_perf = dossier.get("longform_performance", {})

    high_pillars = topic_intel.get("high_performing_pillars", [])
    underexplored = topic_intel.get("underexplored_pillars", [])

    # Topic discovery bias: prioritize high-traction and underexplored pillars
    preferred_pillars = high_pillars[:2] + underexplored[:2]

    # Scriptwriting pacing directives (never trigger false retention conclusions from unavailable None metrics)
    sh_apv = shorts_perf.get("observed_avg_apv")
    if sh_apv is None:
        shorts_pacing_rule = "Maintain crisp 2.5s visual hook and 4-part pacing (retention APV unavailable until Analytics OAuth scope is granted)."
    elif sh_apv < 70.0:
        shorts_pacing_rule = "High-contrast visual paradox in first 2.5s; eliminate slow narrative preamble."
    else:
        shorts_pacing_rule = "Maintain strong 4-part pacing and empirical conclusion."

    lf_apv = lf_perf.get("storytelling_diagnostics", {}).get("avg_percentage_viewed")
    if lf_apv is None:
        longform_pacing_rule = "Maintain chronological depth, evidence-grounded reveals, and archival citations (retention APV unavailable until Analytics OAuth scope is granted)."
    elif lf_apv < 45.0:
        longform_pacing_rule = "Reinforce Chapter 1 hook (under 90s) and align mid-video evidence reveals with topic."
    else:
        longform_pacing_rule = "Maintain chronological depth and archival quote citations."

    lf_pkg = lf_perf.get("packaging_diagnostics", {})
    ctr_avail = bool(lf_pkg.get("ctr_available"))
    avg_ctr = lf_pkg.get("avg_ctr")
    rec_title_style = (
        "curiosity_oriented"
        if (not ctr_avail or avg_ctr is None or avg_ctr < 0.04)
        else "story_oriented"
    )

    return {
        "brief_timestamp": datetime.now(timezone.utc).isoformat(),
        "preferred_pillars": preferred_pillars,
        "shorts_pacing_directive": shorts_pacing_rule,
        "longform_pacing_directive": longform_pacing_rule,
        "recommended_title_style": rec_title_style,
        "ctr_analytics_available": ctr_avail,
        "recommended_thumbnail_style": "cinematic" if len(high_pillars) > 0 else "impact",
        "governance": "All generated topics must strictly pass the research evidence quality gate.",
    }


# Backward compatibility aliases
def analyze_channel_growth_and_performance(history_runs: Optional[List[dict]] = None,
                                           snapshots: Optional[dict] = None) -> Dict[str, Any]:
    """Preserves backward-compatible function signature while leveraging Phase 19 engine."""
    runs = history_runs if history_runs is not None else []
    
    if runs:
        longform_runs = [r for r in runs if r.get("type") in ("longform", "normal")]
        shorts_runs = [r for r in runs if r.get("type") == "short"]
        cluster_scores = {}
        for r in runs:
            title = r.get("title", "")
            t_low = title.lower()
            if any(w in t_low for w in ("chola", "maurya", "gupta", "empire", "king", "queen", "samrat")):
                cluster = "Kings, Queens & Empires"
            elif any(w in t_low for w in ("battle", "war", "haldighati", "panipat", "tarain", "युद्ध")):
                cluster = "Battles & Military Strategy"
            elif any(w in t_low for w in ("dwarka", "excavation", "city", "mohenjo", "harappa", "kuldhara")):
                cluster = "Lost Cities & Archaeological Discoveries"
            elif any(w in t_low for w in ("kailash", "pillar", "temple", "engineering", "iron")):
                cluster = "Ancient Engineering & Architecture"
            else:
                cluster = "Other Historical Mysteries"

            if cluster not in cluster_scores:
                cluster_scores[cluster] = {"count": 0, "total_score": 0, "videos": []}
            cluster_scores[cluster]["count"] += 1
            cluster_scores[cluster]["total_score"] += r.get("score", 85)
            cluster_scores[cluster]["videos"].append(title)

        recs = [
            "Content Pillar traction: Maintain cluster authority while testing adjacent archaeological pillars.",
            "Retention standard: Prioritize strong visual artifact revelations in Chapter 1 (0:00–0:45) to minimize drop-off.",
        ]
        return {
            "channel_name": config.CHANNEL_NAME,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "total_videos_analyzed": len(runs),
            "longform_count": len(longform_runs),
            "shorts_count": len(shorts_runs),
            "cluster_distribution": cluster_scores,
            "analytics_snapshots_tracked": len(snapshots) if snapshots is not None else len(runs),
            "evidence_based_recommendations": recs,
            "governance_rule": "All editorial changes and uploads must receive human approval prior to release.",
        }

    dossier = generate_growth_intelligence_dossier()
    return {
        "channel_name": dossier["channel_name"],
        "analyzed_at": dossier["report_generated_at"],
        "total_videos_analyzed": dossier["total_videos_analyzed"],
        "longform_count": dossier["longform_count"],
        "shorts_count": dossier["shorts_count"],
        "cluster_distribution": dossier["topic_intelligence"]["pillar_statistics"],
        "analytics_snapshots_tracked": dossier["total_videos_analyzed"],
        "evidence_based_recommendations": [
            f"Recommended Pillar: {r['pillar']} ({r['reason']})" for r in dossier["recommended_topics"]
        ],
        "governance_rule": "All editorial changes and uploads must receive human approval prior to release.",
    }


def generate_weekly_growth_report() -> Dict[str, Any]:
    """Generates the weekly executive growth dossier for Stories Malik."""
    return generate_growth_intelligence_dossier()


def _classify_format_from_record(key: str, rec: dict) -> str:
    meta = rec.get("metadata", {}) or {}
    rtype = str(meta.get("type") or "").lower()
    if rtype in ("short", "shorts") or meta.get("is_shorts") is True:
        return "shorts"
    if rtype in ("longform", "long", "normal"):
        return "longform"
    fname = os.path.basename(key or rec.get("video_path", "")).lower()
    if "short" in fname or "shorts_batch" in str(rec.get("video_path", "")).lower():
        return "shorts"
    return "longform"


def _empty_reliability_bucket() -> Dict[str, Any]:
    return {
        "jobs_started": 0,
        "jobs_completed": 0,
        "jobs_failed": 0,
        "blocked_by_quality_gates": 0,
        "rendering_failures": 0,
        "upload_failures": 0,
        "scheduling_failures": 0,
        "retry_counts": 0,
        "recovery_success": 0,
        # Phase 22.1 explicit separated lifecycle stage counters
        "production_completed": 0,
        "quality_gate_passed": 0,
        "upload_completed": 0,
        "youtube_processing_completed": 0,
        "scheduled": 0,
        "actually_published": 0,
        "analytics_collected": 0,
        "failed": 0,
        "recovered": 0,
        "publication_status": {
            "SCHEDULED": 0,
            "PUBLISHED": 0,
            "UPLOADED_PRIVATE": 0,
            "ANALYTICS_PENDING": 0,
            "COMPLETED": 0,
            "UPLOAD_QUEUED": 0,
            "IN_PROGRESS": 0,
        },
        "quality_gate_reasons": [],
    }


def generate_production_reliability_report(output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Phase 22 Production Reliability Report:
    Aggregates separated telemetry for Shorts and Long-form from production_database.json,
    scheduled_queue, pending_uploads, diagnostics, and OAuth/analytics sync status.
    Persists JSON & Markdown summaries in output_dir (default config.OUTPUT_DIR).
    """
    base_dir = output_dir or getattr(config, "OUTPUT_DIR", "output")
    os.makedirs(base_dir, exist_ok=True)

    prod_db_path = os.path.join(base_dir, "production_database.json")
    prod_db = {}
    if os.path.exists(prod_db_path):
        try:
            with open(prod_db_path, encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    prod_db = raw
        except Exception:
            prod_db = {}

    buckets = {
        "shorts": _empty_reliability_bucket(),
        "longform": _empty_reliability_bucket(),
    }

    terminal_success_states = {"SCHEDULED", "PUBLISHED", "UPLOADED_PRIVATE", "ANALYTICS_PENDING", "COMPLETED"}
    in_progress_states = {
        "TOPIC_SELECTED", "RESEARCH_IN_PROGRESS", "RESEARCH_VALIDATED",
        "SCRIPT_GENERATED", "SCRIPT_VALIDATED", "VIDEO_RENDERING",
        "VIDEO_RENDERED", "VIDEO_VALIDATED", "METADATA_VALIDATED", "UPLOADING",
    }

    for key, rec in prod_db.items():
        if not isinstance(rec, dict):
            continue
        fmt = _classify_format_from_record(key, rec)
        b = buckets[fmt]
        b["jobs_started"] += 1

        curr = str(rec.get("current_state", "")).upper()
        meta = rec.get("metadata", {}) or {}
        hist = rec.get("history", []) or []
        visited_states = {str(h.get("from_state", "")).upper() for h in hist} | {str(h.get("to_state", "")).upper() for h in hist} | {curr}
        err_type = str(meta.get("error_type", "")).lower()
        err_msg = str(meta.get("error", "")).lower()

        b["retry_counts"] += int(rec.get("retry_count", 0))
        recov = int(rec.get("recovered_count", 0))
        b["recovery_success"] += recov
        b["recovered"] += recov

        # Separated 9-stage counters (Phase 22.1)
        if visited_states & {"VIDEO_RENDERED", "VIDEO_VALIDATED", "METADATA_VALIDATED", "UPLOAD_QUEUED", "UPLOADING", "UPLOADED_PRIVATE", "SCHEDULED", "PUBLISHED", "ANALYTICS_PENDING", "COMPLETED"}:
            b["production_completed"] += 1

        q_rep = rec.get("quality_gate") or meta.get("quality_report") or {}
        if q_rep.get("passed") is True or (visited_states & {"METADATA_VALIDATED", "UPLOAD_QUEUED", "UPLOADING", "UPLOADED_PRIVATE", "SCHEDULED", "PUBLISHED", "ANALYTICS_PENDING", "COMPLETED"} and curr != "BLOCKED_QUALITY_GATE" and q_rep.get("passed") is not False):
            b["quality_gate_passed"] += 1

        proc_ver = meta.get("processing_verification") or {}
        has_yt_id = bool(meta.get("youtube_id"))
        if has_yt_id and err_type != "processingfailure":
            b["upload_completed"] += 1
        if proc_ver.get("is_processing_complete") is True or meta.get("youtube_processing_completed") is True:
            b["youtube_processing_completed"] += 1

        pub_status = str(meta.get("publication_status", "")).upper()
        if not pub_status and curr == "ANALYTICS_PENDING":
            for h in reversed(hist):
                to_s = str(h.get("to_state", "")).upper()
                if to_s in ("SCHEDULED", "PUBLISHED", "UPLOADED_PRIVATE"):
                    pub_status = to_s
                    break

        is_actually_pub = bool(meta.get("actually_published") or curr == "PUBLISHED" or pub_status == "PUBLISHED")
        if is_actually_pub:
            b["actually_published"] += 1
        elif curr == "SCHEDULED" or pub_status == "SCHEDULED":
            b["scheduled"] += 1

        if curr == "COMPLETED" and meta.get("analytics_collected") is True:
            b["analytics_collected"] += 1

        if curr in terminal_success_states:
            b["jobs_completed"] += 1
            b["publication_status"][curr] = b["publication_status"].get(curr, 0) + 1
            # Also count the immediate pre-ANALYTICS_PENDING terminal state from history if applicable
            if curr == "ANALYTICS_PENDING":
                if pub_status in ("SCHEDULED", "PUBLISHED", "UPLOADED_PRIVATE"):
                    b["publication_status"][pub_status] += 1
        elif curr == "UPLOAD_QUEUED":
            b["publication_status"]["UPLOAD_QUEUED"] += 1
        elif curr == "BLOCKED_QUALITY_GATE":
            b["blocked_by_quality_gates"] += 1
            for iss in q_rep.get("blocking_issues", [])[:5]:
                b["quality_gate_reasons"].append(iss)
        elif curr == "FAILED":
            b["jobs_failed"] += 1
            b["failed"] += 1
            if "render" in err_type or "render" in str(meta.get("last_retry_stage", "")):
                b["rendering_failures"] += 1
            elif "schedul" in err_type or "publishat" in err_msg:
                b["scheduling_failures"] += 1
            elif "http" in err_type or "quota" in err_type or "upload" in err_type or "processing" in err_type or "channel" in err_type:
                b["upload_failures"] += 1
        elif curr in in_progress_states:
            b["publication_status"]["IN_PROGRESS"] += 1

    # Inspect pending_uploads queue and scheduled_queue on disk
    pending_dir = os.path.join(base_dir, "pending_uploads")
    pending_items = {"shorts": 0, "longform": 0, "total": 0}
    if os.path.isdir(pending_dir):
        for fname in os.listdir(pending_dir):
            if fname.endswith(".json"):
                pending_items["total"] += 1
                try:
                    pdata = json.load(open(os.path.join(pending_dir, fname), encoding="utf-8"))
                    if pdata.get("is_shorts") or "short" in fname.lower():
                        pending_items["shorts"] += 1
                    else:
                        pending_items["longform"] += 1
                except Exception:
                    pass

    sched_dir = os.path.join(base_dir, "scheduled_queue")
    queued_items = {"shorts": 0, "longform": 0, "total": 0}
    if os.path.isdir(sched_dir):
        for fname in os.listdir(sched_dir):
            if fname.endswith(".json"):
                queued_items["total"] += 1
                if fname.startswith("short"):
                    queued_items["shorts"] += 1
                else:
                    queued_items["longform"] += 1

    # Analytics & OAuth capability check (never fabricate live owner analytics)
    try:
        from apis.youtube_analytics import get_analytics_capabilities_and_limitations
        caps = get_analytics_capabilities_and_limitations()
    except Exception as cap_err:
        caps = {"owner_analytics_connected": False, "error": str(cap_err)}

    db_inst = get_performance_db()
    synced_videos = db_inst.get_all_videos() if db_inst else {}
    analytics_status = {
        "owner_analytics_connected": bool(caps.get("owner_analytics_connected", False)),
        "status": "CONNECTED" if caps.get("owner_analytics_connected") else "BLOCKED",
        "data_api_key_fallback_available": bool(caps.get("has_public_data_api_fallback", caps.get("data_api_key_available", False))),
        "missing_scopes": caps.get("missing_scopes", []),
        "tracked_videos_in_growth_db": len(synced_videos),
        "limitations": caps.get("limitations", []),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": getattr(config, "PUBLISHING_TIMEZONE", "Asia/Kolkata"),
        "cadence_policy": {
            "longform_per_day": getattr(config, "LONGFORM_DAILY_COUNT", 1),
            "shorts_per_day": getattr(config, "SHORTS_DAILY_COUNT", 5),
            "total_per_day": getattr(config, "TOTAL_DAILY_VIDEOS", 6),
        },
        "formats": buckets,
        "totals": {
            "jobs_started": buckets["shorts"]["jobs_started"] + buckets["longform"]["jobs_started"],
            "jobs_completed": buckets["shorts"]["jobs_completed"] + buckets["longform"]["jobs_completed"],
            "jobs_failed": buckets["shorts"]["jobs_failed"] + buckets["longform"]["jobs_failed"],
            "blocked_by_quality_gates": buckets["shorts"]["blocked_by_quality_gates"] + buckets["longform"]["blocked_by_quality_gates"],
            "rendering_failures": buckets["shorts"]["rendering_failures"] + buckets["longform"]["rendering_failures"],
            "upload_failures": buckets["shorts"]["upload_failures"] + buckets["longform"]["upload_failures"],
            "scheduling_failures": buckets["shorts"]["scheduling_failures"] + buckets["longform"]["scheduling_failures"],
            "retry_counts": buckets["shorts"]["retry_counts"] + buckets["longform"]["retry_counts"],
            "recovery_success": buckets["shorts"]["recovery_success"] + buckets["longform"]["recovery_success"],
            "production_completed": buckets["shorts"]["production_completed"] + buckets["longform"]["production_completed"],
            "quality_gate_passed": buckets["shorts"]["quality_gate_passed"] + buckets["longform"]["quality_gate_passed"],
            "upload_completed": buckets["shorts"]["upload_completed"] + buckets["longform"]["upload_completed"],
            "youtube_processing_completed": buckets["shorts"]["youtube_processing_completed"] + buckets["longform"]["youtube_processing_completed"],
            "scheduled": buckets["shorts"]["scheduled"] + buckets["longform"]["scheduled"],
            "actually_published": buckets["shorts"]["actually_published"] + buckets["longform"]["actually_published"],
            "analytics_collected": buckets["shorts"]["analytics_collected"] + buckets["longform"]["analytics_collected"],
            "failed": buckets["shorts"]["failed"] + buckets["longform"]["failed"],
            "recovered": buckets["shorts"]["recovered"] + buckets["longform"]["recovered"],
        },
        "queues": {
            "pending_uploads": pending_items,
            "scheduled_queue": queued_items,
        },
        "analytics_sync_status": analytics_status,
    }

    json_path = os.path.join(base_dir, "production_reliability_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Production Reliability Report — Stories Malik",
        f"Generated: {report['generated_at']} ({report['timezone']})",
        "",
        f"Cadence Policy: {report['cadence_policy']['longform_per_day']} Long-Form + {report['cadence_policy']['shorts_per_day']} Shorts = {report['cadence_policy']['total_per_day']}/day",
        "",
        "| Metric | Shorts | Long-Form | Total |",
        "|---|---:|---:|---:|",
    ]
    for label, key_name in [
        ("Jobs Started", "jobs_started"),
        ("Production Completed", "production_completed"),
        ("Quality-Gate Passed", "quality_gate_passed"),
        ("Upload Completed", "upload_completed"),
        ("YouTube Processing Completed", "youtube_processing_completed"),
        ("Scheduled", "scheduled"),
        ("Actually Published", "actually_published"),
        ("Analytics Collected", "analytics_collected"),
        ("Jobs Completed", "jobs_completed"),
        ("Failed", "failed"),
        ("Blocked by Quality Gates", "blocked_by_quality_gates"),
        ("Rendering Failures", "rendering_failures"),
        ("Upload Failures", "upload_failures"),
        ("Scheduling Failures", "scheduling_failures"),
        ("Retry Counts", "retry_counts"),
        ("Recovered", "recovered"),
    ]:
        sv = buckets["shorts"][key_name]
        lv = buckets["longform"][key_name]
        md_lines.append(f"| {label} | {sv} | {lv} | {sv + lv} |")

    md_lines.extend([
        "",
        "## Analytics Sync Status",
        f"- Owner Analytics Status: **{analytics_status['status']}**",
        f"- Missing OAuth Scopes: {', '.join(analytics_status['missing_scopes']) if analytics_status['missing_scopes'] else 'None'}",
        f"- Tracked Videos in Growth DB: {analytics_status['tracked_videos_in_growth_db']}",
    ])
    md_path = os.path.join(base_dir, "production_reliability_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    report["json_path"] = json_path
    report["markdown_path"] = md_path
    return report


def generate_phase23_reports(
    base_dir: Optional[str] = None,
    evaluation_window_days: int = 30,
    is_mock_or_test_data: bool = False,
) -> Dict[str, Any]:
    """
    Phase 23 Consolidated Reporting Suite:
    Produces and saves all 6 authoritative governance reports with explicit data provenance labels
    (`verified_live_data`, `public_data_api`, `private_owner_analytics`, `mock_or_test_data`, `unavailable`):
      1. output/persistent_state_health_report.json
      2. output/youtube_reconciliation_report.json
      3. output/weekly_shorts_performance_report.json
      4. output/weekly_longform_performance_report.json
      5. output/rolling_30day_growth_report.json
      6. output/experiment_evaluation_report.json
    """
    from apis.state_store import generate_persistent_state_health_report
    from uploader.youtube import reconcile_channel_publications
    from agents.experiment_tracker import get_experiment_tracker
    from apis.youtube_analytics import get_analytics_capabilities_and_limitations

    out_dir = base_dir or getattr(config, "OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    state_health = generate_persistent_state_health_report(base_dir=out_dir)
    reconciliation = reconcile_channel_publications(output_dir=out_dir)
    rel_report = generate_production_reliability_report(output_dir=out_dir)

    db_inst = get_performance_db()
    window_vids = db_inst.get_videos_in_window(days=evaluation_window_days) if db_inst else []
    shorts_vids = [v for v in window_vids if v.get("video_format") == "short"]
    longform_vids = [v for v in window_vids if v.get("video_format") != "short"]

    caps = get_analytics_capabilities_and_limitations()
    owner_connected = bool(caps.get("owner_analytics_connected"))

    shorts_perf = analyze_shorts_performance(shorts_vids)
    longform_perf = analyze_longform_performance(longform_vids)
    prod_qa_perf = analyze_production_and_quality_gates()

    provenance_summary = {
        "mode": "mock_or_test_data" if is_mock_or_test_data else "verified_live_data",
        "public_data_api": bool(caps.get("has_public_data_api_fallback")),
        "private_owner_analytics": "private_owner_analytics" if owner_connected else "unavailable (BLOCKED: missing yt-analytics.readonly)",
        "unavailable_metrics_preserved_as_null": True,
    }

    # Weekly Shorts Performance Report
    shorts_report = {
        "generated_at": now_iso,
        "evaluation_window_days": 7,
        "rolling_baseline_days": evaluation_window_days,
        "data_provenance": provenance_summary,
        "owner_analytics_status": "CONNECTED" if owner_connected else "BLOCKED",
        "cadence_target": {"shorts_per_day": getattr(config, "SHORTS_DAILY_COUNT", 5), "timezone": getattr(config, "PUBLISHING_TIMEZONE", "Asia/Kolkata")},
        "performance": shorts_perf,
    }
    shorts_path = os.path.join(out_dir, "weekly_shorts_performance_report.json")
    with open(shorts_path, "w", encoding="utf-8") as f:
        json.dump(shorts_report, f, indent=2, ensure_ascii=False)

    # Weekly Long-Form Performance Report
    longform_report = {
        "generated_at": now_iso,
        "evaluation_window_days": 7,
        "rolling_baseline_days": evaluation_window_days,
        "data_provenance": provenance_summary,
        "owner_analytics_status": "CONNECTED" if owner_connected else "BLOCKED",
        "cadence_target": {"longform_per_day": getattr(config, "LONGFORM_DAILY_COUNT", 1), "timezone": getattr(config, "PUBLISHING_TIMEZONE", "Asia/Kolkata")},
        "performance": longform_perf,
    }
    longform_path = os.path.join(out_dir, "weekly_longform_performance_report.json")
    with open(longform_path, "w", encoding="utf-8") as f:
        json.dump(longform_report, f, indent=2, ensure_ascii=False)

    # Rolling 30-Day Channel Growth Report
    totals = rel_report.get("totals", {})
    started = totals.get("jobs_started", 0)
    upload_ok = totals.get("upload_completed", 0)
    upload_rate = round(upload_ok / started, 4) if started > 0 else None
    target_daily = getattr(config, "TOTAL_DAILY_VIDEOS", 6)
    expected_30d = target_daily * evaluation_window_days
    observed_pub_count = reconciliation.get("live_videos_inspected", 0)
    pub_consistency = round(min(1.0, observed_pub_count / max(1, expected_30d)), 4)

    rolling_growth = {
        "generated_at": now_iso,
        "evaluation_window_days": evaluation_window_days,
        "data_provenance": provenance_summary,
        "shorts_analytics": shorts_perf,
        "longform_analytics": longform_perf,
        "operational_reliability": {
            "production_failure_rate": prod_qa_perf.get("production_failure_rate"),
            "quality_gate_rejection_rate": prod_qa_perf.get("quality_gate_rejection_rate"),
            "upload_success_rate": upload_rate,
            "actual_publication_consistency_ratio": pub_consistency,
            "live_videos_inspected": observed_pub_count,
            "expected_videos_at_6_per_day": expected_30d,
        },
        "reconciliation_coverage_pct": reconciliation.get("reconciliation_coverage_pct"),
        "reconciliation_category_counts": reconciliation.get("category_counts", {}),
        "analytics_limitations": caps.get("limitations", []),
    }
    rolling_path = os.path.join(out_dir, "rolling_30day_growth_report.json")
    with open(rolling_path, "w", encoding="utf-8") as f:
        json.dump(rolling_growth, f, indent=2, ensure_ascii=False)

    # Experiment Evaluation Report
    tracker = get_experiment_tracker()
    all_exps = tracker.get_all_experiments() if tracker else []
    exp_report = {
        "generated_at": now_iso,
        "evaluation_window_days": evaluation_window_days,
        "data_provenance": provenance_summary,
        "total_experiments": len(all_exps),
        "active_experiments": len([e for e in all_exps if e.get("status") == "in_progress"]),
        "completed_experiments": len([e for e in all_exps if e.get("status") == "completed"]),
        "auto_frequency_mutation_blocked": True,
        "multiple_comparison_policy": "bonferroni_0.05_over_active_experiments",
        "experiments": all_exps,
    }
    exp_path = os.path.join(out_dir, "experiment_evaluation_report.json")
    with open(exp_path, "w", encoding="utf-8") as f:
        json.dump(exp_report, f, indent=2, ensure_ascii=False)

    return {
        "persistent_state_health": state_health,
        "youtube_reconciliation": reconciliation,
        "weekly_shorts_performance": shorts_report,
        "weekly_longform_performance": longform_report,
        "rolling_30day_growth": rolling_growth,
        "experiment_evaluation": exp_report,
        "paths": {
            "persistent_state_health": state_health.get("report_path"),
            "youtube_reconciliation": reconciliation.get("report_path"),
            "weekly_shorts_performance": shorts_path,
            "weekly_longform_performance": longform_path,
            "rolling_30day_growth": rolling_path,
            "experiment_evaluation": exp_path,
        },
    }


def evaluate_packaging_candidate(
    title: str,
    thumbnail_spec: Optional[Dict[str, Any]] = None,
    documentary_topic: str = "",
    video_format: str = "longform",
) -> Dict[str, Any]:
    """
    Phase 24: Structured packaging evaluation for Titles & Thumbnails.
    Checks subject clarity, curiosity without generic clickbait, documentary alignment,
    Hindi/Hinglish readability, mobile thumbnail legibility, and historical authenticity
    (rejecting fabricated historical imagery presented as authentic photographs).
    """
    t = str(title or "").strip()
    t_low = t.lower()
    issues: List[str] = []

    if not t:
        issues.append("Title is empty.")

    generic_clickbait = (
        "you won't believe",
        "shocking truth",
        "100% real",
        "gone wrong",
        "mind blown",
        "watch till end",
        "wait for the end",
    )
    has_clickbait = any(p in t_low for p in generic_clickbait) or ("!!!" in t) or (len(t) >= 12 and t.isupper())
    if has_clickbait:
        issues.append("Title uses generic clickbait phrasing or excessive capitalization/punctuation.")

    max_len = 75 if video_format == "longform" else 85
    length_ok = 20 <= len(t) <= max_len
    if t and not length_ok:
        issues.append(f"Title length ({len(t)} chars) outside recommended 20-{max_len} char range.")

    topic_tokens = [w for w in str(documentary_topic or "").lower().split() if len(w) > 3]
    topic_aligned = True if not topic_tokens else any(tok in t_low for tok in topic_tokens)
    if not topic_aligned:
        issues.append("Title does not clearly reference the actual documentary topic.")

    title_score = 10.0
    if not t:
        title_score = 0.0
    else:
        if has_clickbait:
            title_score -= 4.0
        if not length_ok:
            title_score -= 1.5
        if not topic_aligned:
            title_score -= 2.5
        if not any(ch in t for ch in ("?", "क्यों", "कैसे", "रहस्य", ":", "—", "-")):
            title_score -= 0.5
    title_score = max(0.0, round(title_score, 2))

    thumb_issues: List[str] = []
    thumb_score = 8.0
    if thumbnail_spec is not None:
        concept = str(thumbnail_spec.get("visual_concept", "") or "").strip()
        overlay = str(thumbnail_spec.get("text_overlay", "") or "").strip()
        matches_content = bool(thumbnail_spec.get("matches_video_content", True))
        presents_ai_as_photo = bool(thumbnail_spec.get("presents_ai_as_authentic_photo", False))

        if not concept:
            thumb_issues.append("Thumbnail lacks one clear visual idea (visual_concept is empty).")
            thumb_score -= 2.5
        if len(overlay.split()) > 4:
            thumb_issues.append(f"Thumbnail text_overlay has {len(overlay.split())} words (maximum 4 for mobile legibility).")
            thumb_score -= 2.0
        if not matches_content:
            thumb_issues.append("Thumbnail does not match actual video content.")
            thumb_score -= 3.0
        if presents_ai_as_photo:
            thumb_issues.append("Historical authenticity violation: fabricated/AI imagery presented as an authentic historical photograph.")
            thumb_score -= 5.0
        thumb_score = max(0.0, round(thumb_score, 2))

    all_issues = issues + thumb_issues
    return {
        "title": t,
        "video_format": video_format,
        "title_score": title_score,
        "thumbnail_score": thumb_score if thumbnail_spec is not None else None,
        "passed": len(all_issues) == 0,
        "issues": all_issues,
        "has_clickbait": has_clickbait,
        "topic_aligned": topic_aligned,
    }


def diagnose_audience_growth(
    evaluation_window_days: int = 30,
    db_override: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Phase 24: Diagnoses Shorts and Long-form audience performance separately,
    distinguishing Discovery vs Packaging vs Storytelling bottlenecks.
    Excludes mock/test records, preserves unavailable private metrics as None,
    and reports analytics-dependent optimization as BLOCKED when OAuth scopes are incomplete.
    """
    from apis.youtube_analytics import get_analytics_capabilities_and_limitations
    from uploader.oauth_manager import audit_token_scopes

    caps = get_analytics_capabilities_and_limitations()
    oauth_audit = audit_token_scopes()
    owner_connected = bool(caps.get("owner_analytics_connected"))

    db = db_override or get_performance_db()
    raw_vids = db.get_videos_in_window(days=evaluation_window_days)
    # Exclude mock and test records strictly
    real_vids = [
        v for v in raw_vids
        if not v.get("is_test_fixture")
        and not (v.get("metadata_extras") or {}).get("is_test_fixture")
        and v.get("data_provenance") != "mock_or_test_data"
    ]
    shorts = [v for v in real_vids if v.get("video_format") == "short"]
    longform = [v for v in real_vids if v.get("video_format") == "longform"]

    shorts_perf = analyze_shorts_performance(shorts)
    longform_perf = analyze_longform_performance(longform)

    def _null_if_unconnected(val: Any) -> Any:
        return val if owner_connected else None

    shorts_diag = {
        "video_count": len(shorts),
        "public_metrics": {
            "total_views": shorts_perf.get("total_views"),
            "median_views": shorts_perf.get("median_views"),
            "total_likes": shorts_perf.get("total_likes"),
            "total_comments": shorts_perf.get("total_comments"),
        },
        "private_owner_metrics": {
            "watch_time_minutes": _null_if_unconnected(shorts_perf.get("total_watch_time_minutes")),
            "average_view_duration_seconds": _null_if_unconnected(shorts_perf.get("observed_avg_avd_seconds")),
            "average_percentage_viewed": _null_if_unconnected(shorts_perf.get("observed_avg_apv")),
            "viewed_vs_swiped_ratio": None,  # Unavailable in YouTube Analytics API v2
            "subscribers_gained": _null_if_unconnected(shorts_perf.get("total_subscribers_gained")),
        },
        "bottleneck_diagnosis": (
            "BLOCKED_PENDING_OWNER_ANALYTICS: Public Data API views alone cannot separate Shorts feed discovery from swipe-away retention."
            if not owner_connected
            else "EVALUATED_WITH_OWNER_ANALYTICS"
        ),
    }

    longform_diag = {
        "video_count": len(longform),
        "public_metrics": {
            "total_views": longform_perf.get("total_views"),
            "median_views": longform_perf.get("median_views"),
            "total_likes": longform_perf.get("total_likes"),
            "total_comments": longform_perf.get("total_comments"),
        },
        "private_owner_metrics": {
            "impressions": None,  # Unavailable in standard Analytics API v2
            "ctr": None,
            "watch_time_minutes": _null_if_unconnected(longform_perf.get("total_watch_time_minutes")),
            "average_view_duration_seconds": _null_if_unconnected(longform_perf.get("storytelling_diagnostics", {}).get("avg_view_duration_seconds")),
            "average_percentage_viewed": _null_if_unconnected(longform_perf.get("storytelling_diagnostics", {}).get("avg_percentage_viewed")),
            "subscribers_gained": _null_if_unconnected(longform_perf.get("total_subscribers_gained")),
        },
        "bottleneck_diagnosis": (
            "BLOCKED_PENDING_OWNER_ANALYTICS: Low public views do not prove poor documentary quality; impressions, CTR, AVD, and APV are required to separate discovery, packaging, and storytelling."
            if not owner_connected
            else "EVALUATED_WITH_OWNER_ANALYTICS"
        ),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_window_days": evaluation_window_days,
        "channel_id": getattr(config, "YOUTUBE_CHANNEL_ID", ""),
        "oauth_scopes_granted": oauth_audit.get("granted_scopes", []),
        "oauth_scopes_missing": oauth_audit.get("missing_scopes", []),
        "owner_analytics_connected": owner_connected,
        "analytics_dependent_optimization_status": "ACTIVE" if owner_connected else "BLOCKED",
        "records_inspected": len(real_vids),
        "excluded_mock_or_test_records": len(raw_vids) - len(real_vids),
        "shorts_diagnosis": shorts_diag,
        "longform_diagnosis": longform_diag,
        "data_provenance": {
            "actual_data": True,
            "public_metrics": "youtube_data_api_v3",
            "private_owner_analytics": "youtube_analytics_v2" if owner_connected else "unavailable (BLOCKED: missing yt-analytics.readonly)",
            "unavailable_metrics": [
                "impressions",
                "ctr",
                "viewed_vs_swiped_ratio",
                *([] if owner_connected else ["watch_time_minutes", "average_view_duration_seconds", "average_percentage_viewed", "subscribers_gained"]),
            ],
        },
        "limitations": caps.get("limitations", []),
    }


def generate_phase24_reports(
    output_dir: Optional[str] = None,
    evaluation_window_days: int = 30,
) -> Dict[str, Any]:
    """
    Phase 24: Generates all 7 audience growth & evidence-based optimization reports:
      1. audience_growth_diagnosis.json
      2. weekly_shorts_performance_report.json (via Phase 23/24 pipeline)
      3. weekly_longform_performance_report.json (via Phase 23/24 pipeline)
      4. topic_opportunity_report.json
      5. packaging_experiment_report.json
      6. storytelling_experiment_report.json
      7. phase24_30day_optimization_report.json
    """
    from agents.adaptive_engine import generate_adaptive_opportunity_report
    from agents.experiment_tracker import get_experiment_tracker

    out_dir = output_dir or getattr(config, "OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    diagnosis = diagnose_audience_growth(evaluation_window_days=evaluation_window_days)
    opp_report = generate_adaptive_opportunity_report()
    tracker = get_experiment_tracker()
    all_exps = tracker.get_all_experiments() if tracker else []

    packaging_exps = [e for e in all_exps if str(e.get("category", "")).lower() in ("packaging", "title", "thumbnail")]
    storytelling_exps = [e for e in all_exps if str(e.get("category", "")).lower() in ("storytelling", "hook", "pacing", "duration")]

    owner_ok = diagnosis["owner_analytics_connected"]
    opt_rec = (
        "Collect owner analytics via interactive OAuth reauthorization (`python authorize_youtube.py` with `youtube.readonly` and `yt-analytics.readonly`) before making packaging or retention changes."
        if not owner_ok
        else "Apply validated single-variable experiment winners with p < 0.05 (Bonferroni-adjusted)."
    )

    packaging_report = {
        "generated_at": now_iso,
        "data_provenance": diagnosis["data_provenance"],
        "experiment_type": "packaging (titles & thumbnails)",
        "total_experiments": len(packaging_exps),
        "experiments": packaging_exps,
        "multiple_comparison_policy": "bonferroni_0.05_over_active_experiments",
        "auto_frequency_mutation_blocked": True,
        "recommendation": opt_rec,
    }
    storytelling_report = {
        "generated_at": now_iso,
        "data_provenance": diagnosis["data_provenance"],
        "experiment_type": "storytelling (hooks, pacing & duration)",
        "total_experiments": len(storytelling_exps),
        "experiments": storytelling_exps,
        "multiple_comparison_policy": "bonferroni_0.05_over_active_experiments",
        "auto_frequency_mutation_blocked": True,
        "recommendation": opt_rec,
    }
    optimization_30d = {
        "generated_at": now_iso,
        "evaluation_window_days": evaluation_window_days,
        "cadence_preserved": {
            "longform_daily": getattr(config, "DAILY_LONGFORM_TARGET", 1),
            "shorts_daily": getattr(config, "DAILY_SHORTS_TARGET", 5),
            "timezone": getattr(config, "TIMEZONE", "Asia/Kolkata"),
            "auto_frequency_reduction": False,
        },
        "analytics_dependent_optimization_status": diagnosis["analytics_dependent_optimization_status"],
        "data_provenance": diagnosis["data_provenance"],
        "audience_diagnosis_summary": {
            "shorts_count": diagnosis["shorts_diagnosis"]["video_count"],
            "longform_count": diagnosis["longform_diagnosis"]["video_count"],
            "shorts_bottleneck": diagnosis["shorts_diagnosis"]["bottleneck_diagnosis"],
            "longform_bottleneck": diagnosis["longform_diagnosis"]["bottleneck_diagnosis"],
        },
        "top_topic_opportunities": {
            "shorts": opp_report.get("recommended_shorts", [])[:5],
            "longform": opp_report.get("recommended_longform", [])[:3],
        },
        "recommendations": [
            {
                "area": "analytics_readiness" if not owner_ok else "controlled_experiments",
                "action": opt_rec,
                "supporting_observation": f"{diagnosis['records_inspected']} real videos in 30d window; owner_analytics_connected={owner_ok}",
                "confidence": "high (verified_state)" if not owner_ok else "statistical_ci",
            }
        ],
    }

    paths = {}
    for key, fname, payload in [
        ("audience_growth_diagnosis", "audience_growth_diagnosis.json", diagnosis),
        ("topic_opportunity_report", "topic_opportunity_report.json", opp_report),
        ("packaging_experiment_report", "packaging_experiment_report.json", packaging_report),
        ("storytelling_experiment_report", "storytelling_experiment_report.json", storytelling_report),
        ("phase24_30day_optimization_report", "phase24_30day_optimization_report.json", optimization_30d),
    ]:
        p = os.path.join(out_dir, fname)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        paths[key] = p

    return {
        "audience_growth_diagnosis": diagnosis,
        "topic_opportunity_report": opp_report,
        "packaging_experiment_report": packaging_report,
        "storytelling_experiment_report": storytelling_report,
        "phase24_30day_optimization_report": optimization_30d,
        "paths": paths,
    }


def generate_phase25_execution_report(
    output_dir: Optional[str] = None,
    evaluation_window_days: int = 30,
) -> Dict[str, Any]:
    """
    Phase 25: 30-Day Audience Growth Execution & Controlled Experimentation Evaluation.
    Applies the Analytics Readiness Gate to all experiments, records separate Shorts and
    Long-form baselines, separates statistically supported findings from directional
    observations, and preserves missing metrics honestly without manufacturing conclusions.
    """
    from agents.experiment_tracker import get_experiment_tracker
    from agents.statistical_validator import calculate_median, compute_publication_age_days
    from apis.youtube_analytics import get_analytics_capabilities_and_limitations
    from uploader.oauth_manager import audit_token_scopes

    out_dir = output_dir or getattr(config, "OUTPUT_DIR", "output")
    os.makedirs(out_dir, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()

    caps = get_analytics_capabilities_and_limitations()
    oauth_audit = audit_token_scopes()
    owner_connected = bool(caps.get("owner_analytics_connected"))

    tracker = get_experiment_tracker()
    gate_summary = tracker.apply_analytics_readiness_gate(
        owner_analytics_connected=owner_connected,
        ctr_available=False,
    )

    db = get_performance_db()
    raw_vids = db.get_videos_in_window(days=evaluation_window_days)
    real_vids = [
        v for v in raw_vids
        if not v.get("is_test_fixture")
        and not (v.get("metadata_extras") or {}).get("is_test_fixture")
        and v.get("data_provenance") != "mock_or_test_data"
    ]
    shorts = [v for v in real_vids if v.get("video_format") == "short"]
    longform = [v for v in real_vids if v.get("video_format") == "longform"]

    def _baseline_bucket(vlist: List[Dict[str, Any]]) -> Dict[str, Any]:
        views = [
            float((v.get("latest_metrics") or {}).get("views"))
            for v in vlist
            if (v.get("latest_metrics") or {}).get("views") is not None
        ]
        ages = [
            compute_publication_age_days(v.get("publication_timestamp", ""))
            for v in vlist
            if v.get("publication_timestamp")
        ]
        return {
            "video_count": len(vlist),
            "median_views": calculate_median(views) if views else None,
            "total_views": int(sum(views)) if views else 0,
            "median_publication_age_days": round(calculate_median(ages), 2) if ages else None,
            "watch_time_minutes": None,
            "average_view_duration_seconds": None,
            "average_percentage_viewed": None,
            "impressions": None,
            "ctr": None,
            "subscribers_gained": None,
        }

    shorts_base = _baseline_bucket(shorts)
    lf_base = _baseline_bucket(longform)

    if owner_connected:
        sp = analyze_shorts_performance(shorts)
        lp = analyze_longform_performance(longform)
        shorts_base["watch_time_minutes"] = sp.get("total_watch_time_minutes")
        shorts_base["average_view_duration_seconds"] = sp.get("observed_avg_avd_seconds")
        shorts_base["average_percentage_viewed"] = sp.get("observed_avg_apv")
        shorts_base["subscribers_gained"] = sp.get("total_subscribers_gained")
        lf_base["watch_time_minutes"] = lp.get("total_watch_time_minutes")
        lf_base["average_view_duration_seconds"] = lp.get("storytelling_diagnostics", {}).get("avg_view_duration_seconds")
        lf_base["average_percentage_viewed"] = lp.get("storytelling_diagnostics", {}).get("avg_percentage_viewed")
        lf_base["subscribers_gained"] = lp.get("total_subscribers_gained")

    all_exps = tracker.get_all_experiments()
    completed_exps = [e for e in all_exps if e.get("status") == "completed"]
    inconclusive_or_blocked = [e for e in all_exps if e.get("status") in ("BLOCKED", "in_progress")]

    report = {
        "generated_at": now_iso,
        "evaluation_window_days": evaluation_window_days,
        "cadence_preserved": {
            "longform_daily": getattr(config, "DAILY_LONGFORM_TARGET", 1),
            "shorts_daily": getattr(config, "DAILY_SHORTS_TARGET", 5),
            "total_daily": getattr(config, "TOTAL_DAILY_VIDEOS", 6),
            "timezone": getattr(config, "TIMEZONE", "Asia/Kolkata"),
            "auto_frequency_reduction": False,
        },
        "analytics_readiness_gate": {
            "channel_id": getattr(config, "YOUTUBE_CHANNEL_ID", ""),
            "owner_analytics_connected": owner_connected,
            "granted_scopes": oauth_audit.get("granted_scopes", []),
            "missing_scopes": oauth_audit.get("missing_scopes", []),
            "gate_result": gate_summary,
        },
        "baseline": {
            "shorts": shorts_base,
            "longform": lf_base,
            "unavailable_baseline_metrics": [
                "impressions",
                "ctr",
                *([] if owner_connected else ["watch_time_minutes", "average_view_duration_seconds", "average_percentage_viewed", "subscribers_gained"]),
            ],
        },
        "experiment_register": all_exps,
        "thirty_day_findings": {
            "statistically_supported_findings": [
                e.get("conclusion") for e in completed_exps if e.get("conclusion")
            ],
            "directional_observations": [
                f"Observed {shorts_base['video_count']} Shorts (median {shorts_base['median_views']} views, total {shorts_base['total_views']}) and {lf_base['video_count']} Long-form videos (median {lf_base['median_views']} views, total {lf_base['total_views']}) via public Data API v3."
            ],
            "inconclusive_or_blocked_experiments": [
                {"id": e.get("id"), "status": e.get("status"), "reason": e.get("blocked_reason", "insufficient_samples")}
                for e in inconclusive_or_blocked
            ],
            "honesty_statement": (
                "No positive growth conclusion is manufactured where owner analytics are BLOCKED or samples are insufficient."
            ),
        },
        "next_30day_recommendations": [
            "Complete interactive OAuth reauthorization (`python authorize_youtube.py` with `youtube.readonly` and `yt-analytics.readonly`) to unblock EXP-001 and EXP-003.",
            "Preserve the 5 Shorts + 1 Long-form daily IST cadence while collecting comparable publication-age samples (>= 5 per variant).",
        ],
    }

    report_path = os.path.join(out_dir, "phase25_30day_growth_evaluation.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    report["report_path"] = report_path
    return report
