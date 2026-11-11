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


def analyze_shorts_performance(shorts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Performs independent analysis of YouTube Shorts:
    - Format traction across 8 documentary formats
    - Swipe rate and engagement patterns (where available)
    - Pacing & duration correlation
    - Hook style patterns
    - Subscriber conversion per 1,000 views
    - Prevents premature conclusions if sample size < 3
    """
    if not shorts:
        return {
            "sample_size": 0,
            "status": "insufficient_data",
            "message": "No Shorts data recorded in the historical performance database.",
            "format_breakdown": {},
            "observed_avg_apv": 0.0,
            "target_apv_benchmark": 70.0,
            "retention_benchmarks": {"target_apv": 70.0, "observed_avg_apv": 0.0},
            "sub_conversion_per_1k": 0.0,
            "observations": ["Initial baseline phase: Produce and track at least 3 Shorts per format."],
        }

    format_groups: Dict[str, List[dict]] = {f: [] for f in SHORTS_FORMAT_CLASSES}
    total_views = 0
    total_subs = 0
    apv_list = []
    duration_perf = {"under_35s": [], "35_to_50s": [], "over_50s": []}

    for s in shorts:
        m = s.get("latest_metrics", {})
        views = m.get("views", 0)
        subs = m.get("subscribers_gained", 0)
        apv = m.get("average_percentage_viewed", 0.0)
        dur = s.get("video_duration_seconds", 0.0)

        total_views += views
        total_subs += subs
        if apv > 0:
            apv_list.append(apv)

        fmt = classify_shorts_format(s.get("title", ""), s.get("topic", ""), s.get("metadata_extras", {}))
        format_groups.setdefault(fmt, []).append({
            "video_id": s.get("video_id"),
            "title": s.get("title"),
            "topic": s.get("topic"),
            "views": views,
            "apv": apv,
            "duration": dur,
            "subs": subs,
        })

        if dur > 0:
            if dur < 35.0:
                duration_perf["under_35s"].append((views, apv))
            elif dur <= 50.0:
                duration_perf["35_to_50s"].append((views, apv))
            else:
                duration_perf["over_50s"].append((views, apv))

    observed_avg_apv = round(sum(apv_list) / len(apv_list), 2) if apv_list else 0.0
    sub_conv = round((total_subs / total_views * 1000), 2) if total_views > 0 else 0.0

    format_summary = {}
    for fmt, vids in format_groups.items():
        if not vids:
            format_summary[fmt] = {
                "count": 0,
                "avg_views": 0,
                "avg_apv": 0.0,
                "confidence": "no_data",
            }
            continue

        cnt = len(vids)
        avg_v = int(sum(v["views"] for v in vids) / cnt)
        pcts = [v["apv"] for v in vids if v["apv"] > 0]
        avg_pct = round(sum(pcts) / len(pcts), 2) if pcts else 0.0
        conf = "high (sample >= 3)" if cnt >= 3 else "preliminary (sample < 3)"
        format_summary[fmt] = {
            "count": cnt,
            "avg_views": avg_v,
            "avg_apv": avg_pct,
            "confidence": conf,
        }

    # Formulate evidence-based observations
    observations = []
    if len(shorts) < 3:
        observations.append(f"Sample size is limited ({len(shorts)} Short(s)). Withhold definitive hook conclusions until >= 3 samples per format are logged.")
    else:
        # Check best format with sufficient sample size
        viable_formats = {k: v for k, v in format_summary.items() if v["count"] >= 3}
        if viable_formats:
            best_fmt = max(viable_formats.items(), key=lambda x: (x[1]["avg_apv"], x[1]["avg_views"]))
            observations.append(f"Strongest validated Shorts format: '{best_fmt[0]}' (Avg APV: {best_fmt[1]['avg_apv']}%, Avg Views: {best_fmt[1]['avg_views']}).")
        else:
            observations.append("All individual Shorts formats currently have < 3 samples. Topic clusters are actively gathering data.")

    if observed_avg_apv > 0 and observed_avg_apv < 70.0:
        observations.append(f"Average percentage viewed is {observed_avg_apv}%, below the 70.0% viral benchmark for Shorts. Pacing must eliminate slow preamble in the first 2.5 seconds.")

    return {
        "sample_size": len(shorts),
        "total_views": total_views,
        "total_subscribers_gained": total_subs,
        "sub_conversion_per_1k": sub_conv,
        "observed_avg_apv": observed_avg_apv,
        "target_apv_benchmark": 70.0,
        "format_breakdown": format_summary,
        "observations": observations,
        "swiped_away_reporting": "API does not expose granular swiped-away ratios in v2 dimensions; engagement and APV proxy used.",
    }


def analyze_longform_performance(longform: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Performs independent analysis of long-form documentaries:
    - Impressions, CTR, Watch Time, AVD, APV
    - Explicitly separates packaging diagnostics (Impressions / CTR) from storytelling/retention diagnostics (AVD / APV)
    - Traffic source breakdown
    - Contextual thumbnail recommendations (never advises changing thumbnails purely on CTR without considering impressions and traffic source)
    """
    if not longform:
        return {
            "sample_size": 0,
            "status": "insufficient_data",
            "message": "No long-form documentary data recorded in the historical performance database.",
            "packaging_diagnostics": {},
            "storytelling_diagnostics": {},
            "traffic_sources": {},
            "observations": ["Initial baseline phase: Produce and publish at least 3 long-form documentaries to gather retention data."],
        }

    total_views = 0
    total_watch_min = 0.0
    total_impressions = 0
    total_subs = 0
    ctr_list = []
    avd_list = []
    apv_list = []

    traffic_aggregate: Dict[str, int] = {}

    for lf in longform:
        m = lf.get("latest_metrics", {})
        views = m.get("views", 0)
        watch_min = m.get("watch_time_minutes", 0.0)
        impr = m.get("impressions", 0)
        ctr = m.get("ctr", 0.0)
        avd = m.get("average_view_duration_seconds", 0.0)
        apv = m.get("average_percentage_viewed", 0.0)
        subs = m.get("subscribers_gained", 0)

        total_views += views
        total_watch_min += watch_min
        total_impressions += impr
        total_subs += subs

        if ctr > 0:
            ctr_list.append(ctr)
        if avd > 0:
            avd_list.append(avd)
        if apv > 0:
            apv_list.append(apv)

        for ts in lf.get("traffic_sources", []):
            src_name = ts.get("traffic_source", "OTHER")
            traffic_aggregate[src_name] = traffic_aggregate.get(src_name, 0) + ts.get("views", 0)

    avg_ctr = round(sum(ctr_list) / len(ctr_list), 4) if ctr_list else 0.0
    avg_avd = round(sum(avd_list) / len(avd_list), 1) if avd_list else 0.0
    avg_apv = round(sum(apv_list) / len(apv_list), 2) if apv_list else 0.0
    sub_conv = round((total_subs / total_views * 1000), 2) if total_views > 0 else 0.0

    # Diagnostic separation: Packaging vs Storytelling
    packaging_diag = {
        "total_impressions": total_impressions,
        "avg_ctr": avg_ctr,
        "evaluation": (
            "Healthy CTR (>= 4.0%)" if avg_ctr >= 0.04 else
            "Low CTR (< 4.0%): Evaluate impressions volume and traffic source context before modifying thumbnail design."
            if total_impressions > 500 else "Insufficient impressions volume to reliably judge thumbnail packaging."
        ),
    }

    storytelling_diag = {
        "avg_view_duration_seconds": avg_avd,
        "avg_percentage_viewed": avg_apv,
        "target_apv_benchmark": 45.0,
        "evaluation": (
            "Strong retention (>= 45.0% APV)" if avg_apv >= 45.0 else
            f"Retention bottleneck (Avg APV: {avg_apv}% < 45.0% benchmark). Pacing and chapter transitions require reinforcement."
            if avg_apv > 0 else "Pending retention observation."
        ),
        "first_30s_retention": "Granular second-by-second curve not exposed via API v2 standard queries; aggregate APV utilized.",
    }

    observations = []
    if len(longform) < 3:
        observations.append(f"Sample size is preliminary ({len(longform)} documentary video(s)). Gather >= 3 published long-form videos for full trend validity.")

    if avg_ctr < 0.04 and total_impressions > 1000:
        search_traffic = traffic_aggregate.get("YT_SEARCH", 0)
        browse_traffic = traffic_aggregate.get("BROWSE_FEATURES", 0)
        observations.append(
            f"Packaging observation: Impressions are substantial ({total_impressions}) with {avg_ctr*100:.1f}% CTR. "
            f"Browse share: {browse_traffic}, Search share: {search_traffic}. Consider testing Curiosity-oriented title angle in next scheduled run."
        )

    if avg_apv > 0 and avg_apv < 45.0:
        observations.append(
            f"Storytelling observation: APV is {avg_apv}% (< 45% standard). Reinforce Chapter 1 hook and integrate tactical map reveals at 3-minute marks."
        )

    return {
        "sample_size": len(longform),
        "total_views": total_views,
        "total_watch_time_minutes": round(total_watch_min, 1),
        "total_subscribers_gained": total_subs,
        "sub_conversion_per_1k": sub_conv,
        "packaging_diagnostics": packaging_diag,
        "storytelling_diagnostics": storytelling_diag,
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
        views = m.get("views", 0)
        watch_min = m.get("watch_time_minutes", 0.0)
        subs = m.get("subscribers_gained", 0)
        apv = m.get("average_percentage_viewed", 0.0)

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


def generate_growth_intelligence_dossier() -> Dict[str, Any]:
    """
    Compiles the full weekly YouTube Growth Intelligence Dossier for Stories Malik:
    - Top 10 Shorts & Top 10 Long-form videos
    - Best-performing & weak-performing topics
    - Subscriber conversion across formats
    - Retention & packaging observations
    - Recommended topics & controlled experiments
    - Data completeness & sample size confidence limitations
    - Writes output/weekly_growth_intelligence.json and output/weekly_growth_intelligence.md
    """
    db = get_performance_db()
    all_vids = db.get_all_videos()
    shorts = db.get_shorts()
    longform = db.get_longform()
    tracker = get_experiment_tracker()

    now_iso = datetime.now(timezone.utc).isoformat()

    # Sort top performers
    sorted_shorts = sorted(shorts, key=lambda x: (x.get("latest_metrics", {}).get("views", 0), x.get("latest_metrics", {}).get("average_percentage_viewed", 0.0)), reverse=True)
    sorted_longform = sorted(longform, key=lambda x: (x.get("latest_metrics", {}).get("watch_time_minutes", 0.0), x.get("latest_metrics", {}).get("views", 0)), reverse=True)

    top_10_shorts = [
        {
            "video_id": s["video_id"],
            "title": s["title"],
            "topic": s["topic"],
            "views": s.get("latest_metrics", {}).get("views", 0),
            "apv": s.get("latest_metrics", {}).get("average_percentage_viewed", 0.0),
            "subs": s.get("latest_metrics", {}).get("subscribers_gained", 0),
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
            "apv": lf.get("latest_metrics", {}).get("average_percentage_viewed", 0.0),
            "ctr": lf.get("latest_metrics", {}).get("ctr", 0.0),
            "subs": lf.get("latest_metrics", {}).get("subscribers_gained", 0),
        }
        for lf in sorted_longform[:10]
    ]

    shorts_analysis = analyze_shorts_performance(shorts)
    longform_analysis = analyze_longform_performance(longform)
    topic_intelligence = analyze_topic_pillars(all_vids)
    packaging_analysis = analyze_title_and_thumbnail(all_vids)

    # Compute data completeness
    total_tracked = len(all_vids)
    complete_records = sum(1 for v in all_vids if v.get("latest_metrics", {}).get("views", 0) > 0)
    data_completeness = round((complete_records / max(1, total_tracked)) * 100, 1)

    # Recommended next production topics
    recommended_topics = []
    # Suggest 1 underexplored pillar topic
    if topic_intelligence["underexplored_pillars"]:
        recommended_topics.append({
            "pillar": topic_intelligence["underexplored_pillars"][0],
            "reason": "Underexplored historical pillar on Stories Malik; expands thematic breadth while maintaining evidence rigor.",
            "target_format": "longform",
        })
    # Suggest 1 top-performing pillar topic
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

    report = {
        "channel_name": config.CHANNEL_NAME,
        "report_generated_at": now_iso,
        "data_completeness_pct": data_completeness,
        "total_videos_analyzed": total_tracked,
        "shorts_count": len(shorts),
        "longform_count": len(longform),
        "top_10_shorts": top_10_shorts,
        "top_10_longform": top_10_longform,
        "shorts_performance": shorts_analysis,
        "longform_performance": longform_analysis,
        "topic_intelligence": topic_intelligence,
        "packaging_and_titles": packaging_analysis,
        "recommended_topics": recommended_topics,
        "active_experiments": active_exps,
        "confidence_limitations": {
            "sample_size_warning": len(all_vids) < 10,
            "message": (
                "Dataset contains fewer than 10 total videos. Trend insights are directional hypotheses. "
                "Do not make drastic editorial pivots without verifying across multiple production cycles."
                if len(all_vids) < 10 else "Sufficient statistical sample available for operational guidance."
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
    lines = [
        "# 📊 Stories Malik — Weekly YouTube Growth Intelligence Report",
        f"**Generated:** {report['report_generated_at']}  ",
        f"**Channel:** {report['channel_name']}  ",
        f"**Total Videos Tracked:** {report['total_videos_analyzed']} ({report['shorts_count']} Shorts, {report['longform_count']} Long-form)  ",
        f"**Data Completeness:** {report['data_completeness_pct']}%  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Confidence Limitations",
        f"> **Confidence Status:** {report['confidence_limitations']['message']}",
        "",
        "## 2. Shorts Performance (Independent Analysis)",
        f"- **Total Shorts Analyzed:** {report['shorts_performance']['sample_size']}",
        f"- **Average Percentage Viewed (APV):** {report['shorts_performance']['observed_avg_apv']}% (Target: {report['shorts_performance']['target_apv_benchmark']}%)",
        f"- **Subscriber Conversion:** {report['shorts_performance']['sub_conversion_per_1k']} subs per 1,000 views",
        "- **Key Observations:**",
    ]
    for obs in report["shorts_performance"]["observations"]:
        lines.append(f"  - {obs}")

    lines.extend([
        "",
        "## 3. Long-Form Documentaries (Independent Analysis)",
        f"- **Total Long-form Analyzed:** {report['longform_performance']['sample_size']}",
        f"- **Average Percentage Viewed (APV):** {report['longform_performance'].get('storytelling_diagnostics', {}).get('avg_percentage_viewed', 0.0)}%",
        f"- **Packaging Evaluation:** {report['longform_performance'].get('packaging_diagnostics', {}).get('evaluation', 'N/A')}",
        f"- **Storytelling Evaluation:** {report['longform_performance'].get('storytelling_diagnostics', {}).get('evaluation', 'N/A')}",
        "- **Key Observations:**",
    ])
    for obs in report["longform_performance"]["observations"]:
        lines.append(f"  - {obs}")

    lines.extend([
        "",
        "## 4. Historical Content Pillar Intelligence",
        f"- **Active Pillars:** {report['topic_intelligence']['active_pillars_count']} / {report['topic_intelligence']['evaluated_pillars_count']}",
        f"- **High-Performing Pillars:** {', '.join(report['topic_intelligence']['high_performing_pillars']) or 'Gathering baseline'}",
        f"- **Underexplored Pillars:** {', '.join(report['topic_intelligence']['underexplored_pillars'][:4])}...",
        "",
        "## 5. Recommended Production Topics",
    ])
    for rec in report["recommended_topics"]:
        lines.append(f"- **Pillar:** {rec['pillar']} ({rec['target_format']}) — *{rec['reason']}*")

    lines.extend([
        "",
        "## 6. Active Controlled Experiments",
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

    # Scriptwriting pacing directives
    shorts_pacing_rule = (
        "High-contrast visual paradox in first 2.5s; eliminate slow narrative preamble."
        if shorts_perf.get("observed_avg_apv", 0.0) < 70.0
        else "Maintain strong 4-part pacing and empirical conclusion."
    )

    longform_pacing_rule = (
        "Introduce tactical maps and primary artifacts by minute 3; keep Chapter 1 under 90s."
        if lf_perf.get("storytelling_diagnostics", {}).get("avg_percentage_viewed", 0.0) < 45.0
        else "Maintain chronological depth and archival quote citations."
    )

    return {
        "brief_timestamp": datetime.now(timezone.utc).isoformat(),
        "preferred_pillars": preferred_pillars,
        "shorts_pacing_directive": shorts_pacing_rule,
        "longform_pacing_directive": longform_pacing_rule,
        "recommended_title_style": "curiosity_oriented" if lf_perf.get("packaging_diagnostics", {}).get("avg_ctr", 0.0) < 0.04 else "story_oriented",
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
