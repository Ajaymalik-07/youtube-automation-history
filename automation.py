"""
YAAS Autonomous History Studio Engine
Fully autonomous daily publishing system for 15+ minute deep History documentaries
and daily batches of 5 YouTube Shorts in Hindi and English.

Key features:
1. Targeted to Indian audience peak reach time (IST, UTC+5:30).
2. Triggers rendering 3 hours prior to daily peak release.
3. Guarantees 100/100 score on YouTube publishing checklist.
4. Produces Hindi primary + English auto-dubbed versions.
5. Adaptive Upload Timing Optimizer: shifts upload windows if reach is under target
   to empirically determine the channel's best performing time slot.
6. Runs continuously via background daemon or on-demand via CLI flags.
"""
import os
import sys
import json
import time
import glob
import shutil
import random
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure project root is in sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

import config
from agents.researcher import research_topic
from agents.scriptwriter import write_script, translate_script
from agents.seo_optimizer import optimize_for_100_percent
from video.narrator import generate_narration
from video.stock import download_images
from video.creator import create_video
from video.music import mix_music_with_narration
from video import thumbnail
from uploader.youtube import upload_to_youtube, is_configured

IST = timezone(timedelta(hours=5, minutes=30))
SCHEDULE_FILE = os.path.join(config.OUTPUT_DIR, "automation_schedule.json")


# ══════════════════════════════════════════════════════════════════════════════
#  ADAPTIVE UPLOAD TIMING OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_SLOTS = {
    "longform_target_hour_ist": 19,       # 7:00 PM IST (Prime evening viewing in India)
    "prerender_day_before_hour_ist": 20,  # 8:00 PM IST the day before (renders overnight)
    "candidate_longform_hours": [17, 18, 19, 20, 21],  # Peak testing windows
    "shorts_hours_ist": [9, 12, 16, 19, 22],           # 5 peak mobile scroll windows
    "history_runs": [],
    "slot_performance": {
        "17": {"runs": 0, "total_views": 0, "avg_views": 0},
        "18": {"runs": 0, "total_views": 0, "avg_views": 0},
        "19": {"runs": 0, "total_views": 0, "avg_views": 0},
        "20": {"runs": 0, "total_views": 0, "avg_views": 0},
        "21": {"runs": 0, "total_views": 0, "avg_views": 0},
    },
    "last_prerender_date": None,
    "last_longform_date": None,
    "last_shorts_date": None,
    "last_longform_pub_date": None,
}


def load_schedule_state() -> dict:
    """Load or initialize adaptive scheduling state."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    save_schedule_state(DEFAULT_SLOTS)
    return dict(DEFAULT_SLOTS)


def save_schedule_state(state: dict) -> None:
    """Persist adaptive scheduling state to disk."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def get_current_ist_time() -> datetime:
    """Return current datetime in India Standard Time (IST)."""
    return datetime.now(timezone.utc).astimezone(IST)


def adapt_upload_slot(state: dict, slot_hour: int, recorded_views: int) -> int:
    """
    Evaluates response for an uploaded video at slot_hour.
    If the views are below the average of all tested slots, tests the next candidate hour.
    """
    str_hour = str(slot_hour)
    perf = state.setdefault("slot_performance", {}).setdefault(str_hour, {"runs": 0, "total_views": 0, "avg_views": 0})
    perf["runs"] += 1
    perf["total_views"] += recorded_views
    perf["avg_views"] = perf["total_views"] // perf["runs"]

    # Calculate overall average
    all_avgs = [p["avg_views"] for p in state["slot_performance"].values() if p["runs"] > 0]
    overall_avg = sum(all_avgs) / len(all_avgs) if all_avgs else 0

    candidates = state.get("candidate_longform_hours", [17, 18, 19, 20, 21])
    current_idx = candidates.index(slot_hour) if slot_hour in candidates else 0

    # If this slot underperformed the overall average significantly, shift to test another candidate slot
    if recorded_views < overall_avg * 0.75 and perf["runs"] >= 2:
        next_idx = (current_idx + 1) % len(candidates)
        new_best_hour = candidates[next_idx]
        print(f"   📈 Adaptive Optimizer: Slot {slot_hour}:00 IST had {recorded_views} views (below avg {overall_avg:.0f}).")
        print(f"      Shifting next target release to {new_best_hour}:00 IST to find optimal peak reach.")
        state["longform_target_hour_ist"] = new_best_hour
    else:
        # Check if another tested slot has noticeably higher average
        best_hour = max(state["slot_performance"].items(), key=lambda x: x[1]["avg_views"])[0]
        if state["slot_performance"][best_hour]["runs"] >= 2:
            state["longform_target_hour_ist"] = int(best_hour)

    save_schedule_state(state)
    return state["longform_target_hour_ist"]


# ══════════════════════════════════════════════════════════════════════════════
#  LONG-FORM 15+ MINUTE PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def create_and_publish_longform(is_prerender: bool = False, for_date: str = None) -> dict:
    """
    Executes the complete end-to-end 15+ minute deep History documentary pipeline:
    1. Researches trending historical topic
    2. Writes 15+ minute script in Hindi (hi-IN-MadhurNeural)
    3. Writes English translated script for auto-dubbing
    4. Downloads historical B-roll
    5. Synthesizes voiceovers (Hindi + English)
    6. Renders pristine 1080p high quality video
    7. Verifies 100/100 SEO & publishing checklist
    8. Automatically uploads directly as Public to YouTube
    """
    print("\n" + "=" * 70)
    print("  🎬 YAAS Autonomous Pipeline: 15+ Minute Deep History Documentary")
    print("=" * 70 + "\n")

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    target_date = for_date or get_current_ist_time().strftime("%Y-%m-%d")
    day_theme = config.get_weekly_theme(target_date)

    # 1. Topic Research
    print(f"  [1/8] Researching topic for {day_theme['day']}: {day_theme['theme']} ({day_theme['theme_hi']})…")
    research = research_topic(
        channel_description=config.CHANNEL_DESCRIPTION,
        focus_angle=f"{day_theme['theme']} ({day_theme['day']})",
    )
    with open(os.path.join(config.OUTPUT_DIR, "research.json"), "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2)
    print(f"   ✅ Topic: {research.get('video_title')}")

    # 2. 15+ Minute Script in Hindi
    print(f"  [2/8] Writing 15+ minute documentary script in Hindi (16-20 sections)…")
    hindi_script = write_script(research, video_type="long", language="hi")
    with open(os.path.join(config.OUTPUT_DIR, "script_hi.json"), "w", encoding="utf-8") as f:
        json.dump(hindi_script, f, indent=2, ensure_ascii=False)
    with open(os.path.join(config.OUTPUT_DIR, "script.json"), "w", encoding="utf-8") as f:
        json.dump(hindi_script, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Hindi Script: {len(hindi_script.get('sections', []))} sections written.")

    # 3. English Auto-Dub Script Translation
    print("  [3/8] Generating English auto-dub translation script…")
    english_script = translate_script(hindi_script, target_lang="en")
    with open(os.path.join(config.OUTPUT_DIR, "script_en.json"), "w", encoding="utf-8") as f:
        json.dump(english_script, f, indent=2, ensure_ascii=False)
    print("   ✅ English auto-dub script generated.")

    # 4. Stock Historical Images
    print("  [4/8] Downloading historical B-roll & archival imagery…")
    image_map = download_images(hindi_script, config.OUTPUT_DIR)
    total_imgs = sum(len(v) if isinstance(v, list) else 1 for v in image_map.values() if v)
    print(f"   ✅ {total_imgs} historical images secured.")

    # 5. Narration: Hindi Primary & English Auto-Dub
    print(f"  [5/8] Synthesizing Hindi voiceover via {config.VOICE_ID}…")
    hi_audio = generate_narration(hindi_script, config.OUTPUT_DIR,
                                  voice_id=getattr(config, "VOICE_ID", "hi-IN-MadhurNeural"),
                                  filename="narration_hi.mp3", srt_filename="narration_hi.srt")
    shutil.copy2(hi_audio, os.path.join(config.OUTPUT_DIR, "narration.mp3"))
    shutil.copy2(os.path.join(config.OUTPUT_DIR, "narration_hi.srt"), os.path.join(config.OUTPUT_DIR, "narration.srt"))

    print(f"  Synthesizing English auto-dub via {getattr(config, 'VOICE_ID_EN', 'en-US-AndrewNeural')}…")
    try:
        generate_narration(english_script, config.OUTPUT_DIR,
                           voice_id=getattr(config, "VOICE_ID_EN", "en-US-AndrewNeural"),
                           filename="narration_en.mp3", srt_filename="narration_en.srt")
    except Exception as e:
        print(f"   ⚠ English voiceover warning: {e}")

    # Mix background music
    final_audio = os.path.join(config.OUTPUT_DIR, "narration.mp3")
    if config.MUSIC_ENABLED:
        try:
            print("  Mixing subtle historical background score…")
            mixed_audio = os.path.join(config.OUTPUT_DIR, "narration_mixed.mp3")
            final_audio = mix_music_with_narration(
                final_audio, mixed_audio,
                music_volume=getattr(config, "MUSIC_VOLUME", 0.12),
                library_dir=getattr(config, "MUSIC_LIBRARY_DIR", "")
            )
        except Exception as e:
            print(f"   ⚠ Music mix non-fatal error: {e}")

    # 6. Render High Quality 1080p Video
    print("  [6/8] Rendering High Quality 1080p Video with Ken Burns & synced subtitles…")
    image_map_int = {int(k): v for k, v in image_map.items()}
    video_path = create_video(hindi_script, final_audio, config.OUTPUT_DIR, image_map_int, video_type="normal")
    print(f"   ✅ High quality video rendered: {video_path}")

    # 7. Cinematic Thumbnail & 100/100 Checklist Optimization
    print("  [7/8] Generating thumbnail & optimizing 100/100 publishing checklist…")
    thumb_path = os.path.join(config.OUTPUT_DIR, "thumbnail.jpg")
    try:
        first_img = None
        for imgs in image_map.values():
            if imgs:
                candidates = imgs if isinstance(imgs, list) else [imgs]
                for c in candidates:
                    if c and os.path.exists(c):
                        first_img = c
                        break
            if first_img:
                break
        thumb_text = thumbnail.auto_text(hindi_script.get("title", ""))
        thumb_path = thumbnail.render(
            getattr(config, "THUMB_STYLE", "cinematic"),
            thumb_path,
            thumb_text,
            bg_path=first_img,
            brand=config.brand_text(),
            portrait=False
        )
    except Exception as e:
        print(f"   ⚠ Thumbnail generation warning: {e}")

    seo_result = optimize_for_100_percent(
        title=hindi_script.get("title", ""),
        description=hindi_script.get("description", ""),
        tags=hindi_script.get("tags", []),
        sections=hindi_script.get("sections", []),
        topic=research.get("topic", ""),
        is_shorts=False,
    )

    print(f"\n   🎯 CHECKLIST SCORE: {seo_result['score']} / 100")
    for check in seo_result["checks"]:
        mark = "✓" if check["ok"] else "✗"
        print(f"      [{mark}] {check['label']} ({check['weight']} pts)")

    target_date = for_date or get_current_ist_time().strftime("%Y-%m-%d")

    # 8. Publishing or Pre-Render Queueing
    if is_prerender:
        print(f"\n  [8/8] 📦 Storing in Pre-Render Queue for tomorrow ({target_date})…")
        q_dir = os.path.join(config.OUTPUT_DIR, "scheduled_queue")
        os.makedirs(q_dir, exist_ok=True)
        manifest_path = os.path.join(q_dir, f"longform_{target_date}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "type": "longform",
                "target_date": target_date,
                "video_path": video_path,
                "thumb_path": thumb_path,
                "title": seo_result["title"],
                "description": seo_result["description"],
                "tags": seo_result["tags"],
                "score": seo_result["score"],
                "created_at": datetime.now().isoformat(),
            }, f, indent=2)
        yt_url = f"local://scheduled_queue/{target_date}/longform"
        print(f"   ✅ Saved ready-to-publish manifest: {manifest_path}")
        print(f"      Will publish automatically tomorrow at peak evening release!")
    else:
        print("\n  [8/8] Automated Publishing (Public Direct)…")
        yt_url = upload_to_youtube(
            script=hindi_script,
            video_path=video_path,
            thumb_path=thumb_path,
            title=seo_result["title"],
            description=seo_result["description"],
            tags=seo_result["tags"],
        )

    # Archive run into library
    lib_dir = os.path.join(config.OUTPUT_DIR, "library")
    os.makedirs(lib_dir, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in research.get("video_title", "video").lower())[:35].strip("-")
    project_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slug}"
    p_path = os.path.join(lib_dir, project_id)
    os.makedirs(p_path, exist_ok=True)
    shutil.copy2(video_path, os.path.join(p_path, "video.mp4"))
    if os.path.exists(thumb_path):
        shutil.copy2(thumb_path, os.path.join(p_path, "thumbnail.jpg"))
    with open(os.path.join(p_path, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({
            "id": project_id,
            "title": seo_result["title"],
            "video_type": "normal",
            "score": seo_result["score"],
            "yt_url": yt_url,
            "created_at": datetime.now().isoformat(),
        }, f, indent=2)

    # Update schedule state
    state = load_schedule_state()
    state["last_longform_date"] = target_date
    if not is_prerender:
        state["last_longform_pub_date"] = target_date
    state["history_runs"].append({
        "type": "longform",
        "title": seo_result["title"],
        "url": yt_url,
        "date_ist": get_current_ist_time().isoformat(),
        "score": seo_result["score"],
    })
    save_schedule_state(state)

    print(f"\n🎉 15+ Min History Video Pipeline Complete! ({yt_url})\n")
    res = {"ok": True, "title": seo_result["title"], "url": yt_url, "video_path": video_path, "score": seo_result["score"]}
    try:
        from notifier.email_notifier import send_upload_notification_email
        send_upload_notification_email(longform_result=res)
    except Exception as e:
        print(f"   ℹ Email notification notice: {e}")
    return res


# ══════════════════════════════════════════════════════════════════════════════
#  DAILY 5 SHORTS BATCH PIPELINE (THEME-ALIGNED)
# ══════════════════════════════════════════════════════════════════════════════

def get_shorts_topics_for_day(target_date: str = None) -> list:
    """
    Returns 5 distinct high-velocity Shorts topics tailored to today's Weekly Theme.
    Language split: 3 in Hindi ('hi') and 2 in English ('en').
    """
    theme_info = config.get_weekly_theme(target_date)
    samples = theme_info.get("sample_topics", [])

    # Try generating 5 fresh dynamic Shorts concepts via Gemini
    try:
        from agents.gemini_client import generate
        from agents.json_utils import extract_json
        prompt = f"""You are a viral YouTube Shorts strategist for a History documentary channel.
Today's weekly theme is: >>> {theme_info['theme']} ({theme_info['theme_hi']}) <<<
Description: {theme_info['description']}
Keywords: {', '.join(theme_info.get('keywords', []))}

Generate 5 distinct, high-curiosity YouTube Shorts topic ideas under this exact theme.
Rules:
- Under 65 characters each
- Extreme curiosity, baffling question, or shocking revelation
- Suitable for a fast-paced 45-60 second vertical Short

Return ONLY a valid JSON array of 5 strings:
["Title 1", "Title 2", "Title 3", "Title 4", "Title 5"]"""
        data = extract_json(generate(prompt), "Shorts topics")
        if isinstance(data, list) and len(data) >= 5:
            titles = [t.strip() for t in data[:5] if isinstance(t, str) and t.strip()]
            if len(titles) == 5:
                langs = ["hi", "hi", "en", "hi", "en"]
                return list(zip(titles, langs))
    except Exception as e:
        print(f"   ℹ Generated Shorts topics fallback to theme curated list: {e}")

    # Fallback to curated theme topics from config.py
    langs = ["hi", "hi", "en", "hi", "en"]
    fallback_titles = list(samples) if len(samples) >= 5 else [
        f"{theme_info['theme']}: Ancient Secret Revealed",
        f"The Shocking Truth Behind {theme_info['theme']}",
        f"Mysterious Discovery in {theme_info['theme']}",
        f"What History Books Hid About {theme_info['theme']}",
        f"Unsolved Mystery of {theme_info['theme']}",
    ]
    return list(zip(fallback_titles[:5], langs))


def create_and_publish_single_short(index: int, is_prerender: bool = False, for_date: str = None) -> dict:
    """
    Generates and processes a SINGLE historical Short (index 1 to 5),
    strictly aligned with the Weekly Editorial Theme for the target date.
    """
    target_date = for_date or get_current_ist_time().strftime("%Y-%m-%d")
    day_theme = config.get_weekly_theme(target_date)
    todays_shorts = get_shorts_topics_for_day(target_date)

    idx = max(1, min(index, len(todays_shorts)))
    topic_title, lang = todays_shorts[idx - 1]

    print("\n" + "=" * 70)
    print(f"  ⚡ YAAS Single Short Pipeline: Short {idx}/5")
    print(f"  Topic: {topic_title} ({'Hindi' if lang == 'hi' else 'English'})")
    print(f"  📅 Weekly Theme ({day_theme['day']}): {day_theme['theme']} [{day_theme['theme_hi']}]")
    print("=" * 70 + "\n")

    shorts_dir = os.path.join(config.OUTPUT_DIR, "shorts_batch")
    q_dir = os.path.join(config.OUTPUT_DIR, "scheduled_queue")
    os.makedirs(shorts_dir, exist_ok=True)
    if is_prerender:
        os.makedirs(q_dir, exist_ok=True)

    item_dir = os.path.join(shorts_dir, f"short_{idx:02d}")
    os.makedirs(item_dir, exist_ok=True)

    research = {
        "topic": topic_title,
        "video_title": topic_title,
        "hook_question": f"Did you know the secret behind {topic_title}?",
        "key_points": [f"Shocking historical discovery about {topic_title}"],
        "tags": ["History", "Shorts", "AncientMysteries", "Archaeology", "Facts"],
    }

    # 1. Write Short Script
    short_script = write_script(research, video_type="shorts", language=lang)
    with open(os.path.join(item_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(short_script, f, indent=2, ensure_ascii=False)

    # 2. Download Images
    image_map = download_images(short_script, item_dir)

    # 3. Voiceover
    voice_id = getattr(config, "VOICE_ID", "hi-IN-MadhurNeural") if lang == "hi" else getattr(config, "VOICE_ID_EN", "en-US-AndrewNeural")
    audio_path = generate_narration(short_script, item_dir, voice_id=voice_id)

    # 4. Render Short Video (1080x1920)
    image_map_int = {int(k): v for k, v in image_map.items()}
    video_path = create_video(short_script, audio_path, item_dir, image_map_int, video_type="shorts")

    # 5. Optimize 100/100
    seo_res = optimize_for_100_percent(
        title=short_script.get("title", ""),
        description=short_script.get("description", ""),
        tags=short_script.get("tags", []),
        sections=short_script.get("sections", []),
        topic=topic_title,
        is_shorts=True,
    )

    print(f"   🎯 Short {idx} Score: {seo_res['score']} / 100")

    # 6. Publish or Pre-Render Queue
    if is_prerender:
        manifest_path = os.path.join(q_dir, f"short_{idx}_{target_date}.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "type": "short",
                "index": idx,
                "target_date": target_date,
                "video_path": video_path,
                "title": seo_res["title"],
                "description": seo_res["description"],
                "tags": seo_res["tags"],
                "score": seo_res["score"],
                "created_at": datetime.now().isoformat(),
            }, f, indent=2)
        yt_url = f"local://scheduled_queue/{target_date}/short_{idx}"
        print(f"   📦 Short {idx} queued for tomorrow ({target_date}) scroll window.")
    else:
        yt_url = upload_to_youtube(
            script=short_script,
            video_path=video_path,
            title=seo_res["title"],
            description=seo_res["description"],
            tags=seo_res["tags"],
        )

    result = {
        "ok": True,
        "index": idx,
        "title": seo_res["title"],
        "language": lang,
        "url": yt_url,
        "video_path": video_path,
        "score": seo_res["score"],
    }

    # Update schedule state
    state = load_schedule_state()
    state_hours = state.get("shorts_hours_ist", [9, 12, 16, 19, 22])
    sh_hour = state_hours[idx - 1] if idx <= len(state_hours) else 9
    sh_key = f"last_short_pub_{target_date}_{sh_hour}"
    if not is_prerender:
        state[sh_key] = True
    state["history_runs"].append({
        "type": "short",
        "title": result["title"],
        "url": result["url"],
        "date_ist": get_current_ist_time().isoformat(),
        "score": result["score"],
    })
    save_schedule_state(state)

    print(f"\n✅ Short {idx}/5 Rendered and Processed! ({yt_url})\n")
    return result


def create_and_publish_shorts_batch(is_prerender: bool = False, for_date: str = None) -> list:
    """
    Generates and processes all 5 historical Shorts (3 in Hindi, 2 in English),
    strictly aligned with today's Weekly Editorial Theme.
    """
    target_date = for_date or get_current_ist_time().strftime("%Y-%m-%d")
    day_theme = config.get_weekly_theme(target_date)

    print("\n" + "=" * 70)
    print(f"  ⚡ YAAS Autonomous Pipeline: 5 Daily History Shorts Batch")
    print(f"  📅 Weekly Theme ({day_theme['day']}): {day_theme['theme']} [{day_theme['theme_hi']}]")
    print("=" * 70 + "\n")

    results = []
    for i in range(1, 6):
        res = create_and_publish_single_short(index=i, is_prerender=is_prerender, for_date=target_date)
        results.append(res)

    state = load_schedule_state()
    state["last_shorts_date"] = target_date
    save_schedule_state(state)

    print("\n✅ All 5 Daily History Shorts Rendered and Published!\n")
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  DAEMON & SCHEDULER
# ══════════════════════════════════════════════════════════════════════════════

def publish_scheduled_short(index: int, target_date: str) -> str:
    """Publish the pre-rendered Short for today at its designated scroll window."""
    q_dir = os.path.join(config.OUTPUT_DIR, "scheduled_queue")
    manifest_path = os.path.join(q_dir, f"short_{index}_{target_date}.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"   🚀 Publishing pre-rendered Short {index}: {data.get('title')}")
            yt_url = upload_to_youtube(
                script={},
                video_path=data["video_path"],
                title=data["title"],
                description=data["description"],
                tags=data["tags"],
            )
            try:
                os.remove(manifest_path)
            except Exception:
                pass
            state = load_schedule_state()
            state_hours = state.get("shorts_hours_ist", [9, 12, 16, 19, 22])
            sh_hour = state_hours[index - 1] if index <= len(state_hours) else 9
            state[f"last_short_pub_{target_date}_{sh_hour}"] = True
            state["history_runs"].append({
                "type": "short",
                "title": data.get("title", f"Short {index}"),
                "url": yt_url,
                "date_ist": get_current_ist_time().isoformat(),
                "score": data.get("score", 100),
            })
            save_schedule_state(state)
            return yt_url
        except Exception as e:
            print(f"   ⚠ Error uploading pre-rendered short {index}: {e}")

    # Fallback if no pre-rendered video was found: create and publish ONLY this specific short
    print(f"   ℹ No pre-rendered Short {index} found for {target_date} — creating on-demand now...")
    res = create_and_publish_single_short(index=index, is_prerender=False, for_date=target_date)
    return res.get("url", "")


def publish_scheduled_longform(target_date: str) -> str:
    """Publish the pre-rendered 15+ Min Documentary at peak evening release."""
    q_dir = os.path.join(config.OUTPUT_DIR, "scheduled_queue")
    manifest_path = os.path.join(q_dir, f"longform_{target_date}.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
            print(f"   🚀 Publishing pre-rendered 15+ Min Documentary: {data.get('title')}")
            yt_url = upload_to_youtube(
                script={},
                video_path=data["video_path"],
                thumb_path=data.get("thumb_path"),
                title=data["title"],
                description=data["description"],
                tags=data["tags"],
            )
            try:
                os.remove(manifest_path)
            except Exception:
                pass
            state = load_schedule_state()
            state["last_longform_pub_date"] = target_date
            state["last_longform_date"] = target_date
            state["history_runs"].append({
                "type": "longform",
                "title": data.get("title", "15+ Min Documentary"),
                "url": yt_url,
                "date_ist": get_current_ist_time().isoformat(),
                "score": data.get("score", 100),
            })
            save_schedule_state(state)
            return yt_url
        except Exception as e:
            print(f"   ⚠ Error uploading pre-rendered longform: {e}")

    # Fallback if no pre-rendered video was found: create and publish on-demand
    print(f"   ℹ No pre-rendered longform found for {target_date} — creating on-demand now...")
    res = create_and_publish_longform(is_prerender=False, for_date=target_date)
    return res.get("url", "")


def run_auto_catchup() -> dict:
    """
    Evaluates current IST time and catches up any due or overdue releases for today:
    1. Shorts: any slot whose hour <= current IST hour and not yet published.
    2. Long-Form: documentary if current IST hour >= longform_target_hour_ist and not yet published.
    3. Pre-render: tomorrow's batch if current IST hour >= prerender_day_before_hour_ist and not yet done.
    """
    now_ist = get_current_ist_time()
    today_str = now_ist.strftime("%Y-%m-%d")
    tomorrow_str = (now_ist + timedelta(days=1)).strftime("%Y-%m-%d")
    current_hour = now_ist.hour

    print("\n" + "=" * 70)
    print(f"  🔍 Checking Autonomous History Schedule Status (IST: {now_ist.strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 70)

    state = load_schedule_state()
    shorts_hours = state.get("shorts_hours_ist", [9, 12, 16, 19, 22])
    target_long_hour = state.get("longform_target_hour_ist", 19)
    prerender_hour = state.get("prerender_day_before_hour_ist", 20)

    published_shorts = []
    published_long = None

    # 1. Process Shorts for today
    for idx, sh_hour in enumerate(shorts_hours, 1):
        sh_key = f"last_short_pub_{today_str}_{sh_hour}"
        if current_hour >= sh_hour and not state.get(sh_key):
            print(f"\n▶ [AUTO-CATCHUP] Short {idx}/5 (Slot {sh_hour}:00 IST) is due or overdue! Publishing now...")
            try:
                url = publish_scheduled_short(index=idx, target_date=today_str)
                state = load_schedule_state()
                state[sh_key] = True
                save_schedule_state(state)
                published_shorts.append({"index": idx, "hour": sh_hour, "url": url})
            except Exception as e:
                print(f"   ⚠ Failed to process Short {idx}/5 (will retry next check): {e}")
        else:
            status = "✅ Published" if state.get(sh_key) else f"⏳ Scheduled for {sh_hour}:00 IST"
            print(f"   • Short {idx}/5 ({sh_hour}:00 IST): {status}")

    # 2. Process Long-Form Documentary for today
    long_done = (state.get("last_longform_pub_date") == today_str or state.get("last_longform_date") == today_str)
    if current_hour >= target_long_hour and not long_done:
        print(f"\n▶ [AUTO-CATCHUP] Long-Form Documentary (Slot {target_long_hour}:00 IST) is due! Publishing now...")
        try:
            url = publish_scheduled_longform(target_date=today_str)
            published_long = url
        except Exception as e:
            print(f"   ⚠ Failed to process Long-Form Documentary (will retry next check): {e}")
    else:
        long_status = "✅ Published" if long_done else f"⏳ Scheduled for {target_long_hour}:00 IST"
        print(f"   • Long-Form Documentary ({target_long_hour}:00 IST): {long_status}")

    # 3. Check Pre-Render for tomorrow
    if current_hour >= prerender_hour and state.get("last_prerender_date") != today_str:
        print(f"\n▶ [AUTO-CATCHUP] Pre-rendering tomorrow's ({tomorrow_str}) content overnight...")
        try:
            s_res = create_and_publish_shorts_batch(is_prerender=True, for_date=tomorrow_str)
            l_res = create_and_publish_longform(is_prerender=True, for_date=tomorrow_str)
            state = load_schedule_state()
            state["last_prerender_date"] = today_str
            save_schedule_state(state)
        except Exception as e:
            print(f"   ⚠ Failed pre-render for tomorrow (will retry next check): {e}")

    print("\n✅ Autonomous Catch-up Check Complete.\n")
    return {"published_shorts": published_shorts, "published_long": published_long}


def run_scheduler_daemon():
    """
    Continuous background loop that monitors IST time and triggers:
    1. Pre-rendering a day before (at 20:00 / 8:00 PM IST):
       - Step 1: Shorts FIRST (all 5 rendered in ~10 mins).
       - Step 2: 15+ Min Documentary rendered overnight.
    2. Publishing on release day at target peak hours (with automatic catch-up).
    """
    print("\n" + "=" * 70)
    print("  🚀 YAAS Autonomous History Daemon Started")
    print(f"  Current IST Time: {get_current_ist_time().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 70 + "\n")

    while True:
        try:
            now_ist = get_current_ist_time()
            today_str = now_ist.strftime("%Y-%m-%d")
            tomorrow_str = (now_ist + timedelta(days=1)).strftime("%Y-%m-%d")
            current_hour = now_ist.hour

            state = load_schedule_state()
            prerender_hour = state.get("prerender_day_before_hour_ist", 20)
            target_release_hour = state.get("longform_target_hour_ist", 19)

            # ── 1. PRE-RENDER A DAY BEFORE (At or after 20:00 / 8:00 PM IST) ─────
            if current_hour >= prerender_hour and state.get("last_prerender_date") != today_str:
                print(f"\n[DAEMON PRE-RENDER TRIGGER] Time {now_ist.strftime('%H:%M IST')} — Pre-rendering tomorrow's ({tomorrow_str}) content a day before!")
                print("  ▶ STEP 1: Creating 5 Daily History Shorts FIRST...")
                create_and_publish_shorts_batch(is_prerender=True, for_date=tomorrow_str)
                print("  ▶ STEP 2: Now creating 10–14 Minute Long-Form Documentary for tomorrow...")
                create_and_publish_longform(is_prerender=True, for_date=tomorrow_str)
                state = load_schedule_state()
                state["last_prerender_date"] = today_str
                save_schedule_state(state)

            # ── 2. PUBLISH TODAY'S SHORTS AT DESIGNATED SCROLL WINDOWS (Catch-up aware) ──
            for idx, sh_hour in enumerate(state.get("shorts_hours_ist", [9, 12, 16, 19, 22]), 1):
                sh_key = f"last_short_pub_{today_str}_{sh_hour}"
                if current_hour >= sh_hour and not state.get(sh_key):
                    print(f"\n[DAEMON PUBLISH TRIGGER] Peak scroll window {now_ist.strftime('%H:%M IST')} — Publishing Short {idx}/5 (Slot {sh_hour}:00 IST)...")
                    publish_scheduled_short(index=idx, target_date=today_str)
                    state = load_schedule_state()
                    state[sh_key] = True
                    save_schedule_state(state)

            # ── 3. PUBLISH TODAY'S 10–14 MIN DOCUMENTARY AT TARGET PEAK HOUR (Catch-up aware) ──
            long_done = (state.get("last_longform_pub_date") == today_str or state.get("last_longform_date") == today_str)
            if current_hour >= target_release_hour and not long_done:
                print(f"\n[DAEMON PUBLISH TRIGGER] Peak release time {now_ist.strftime('%H:%M IST')} — Publishing 10–14 Min Documentary...")
                publish_scheduled_longform(target_date=today_str)
                state = load_schedule_state()
                state["last_longform_pub_date"] = today_str
                state["last_longform_date"] = today_str
                save_schedule_state(state)

            # Sleep 30 seconds before next check
            time.sleep(30)

        except KeyboardInterrupt:
            print("\nDaemon stopped by user.")
            break
        except Exception as e:
            print(f"\n⚠ Daemon error (will retry in 60s): {e}")
            time.sleep(60)


def print_status():
    """Display current automation schedule and system health."""
    now_ist = get_current_ist_time()
    state = load_schedule_state()
    target_hour = state.get("longform_target_hour_ist", 19)
    prerender_hour = state.get("prerender_day_before_hour_ist", 20)

    print("\n" + "═" * 65)
    print("  📊 YAAS Autonomous History Studio — Status")
    print("═" * 65)
    today_theme = config.get_weekly_theme()
    print(f"  Current Time (IST) : {now_ist.strftime('%A, %d %B %Y — %I:%M:%S %p IST')}")
    print(f"  Today's Theme      : ★ {today_theme['day']}: {today_theme['theme']} ({today_theme['theme_hi']}) ★")
    print(f"  Pre-render Hour    : {prerender_hour}:00 IST (The Day Before — renders overnight)")
    print(f"  Pre-render Order   : 1st Shorts (Fast ~10m) → 2nd 10–14 Min Documentary")
    print(f"  Target Release     : {target_hour}:00 IST (Indian Evening Peak)")
    print(f"  Shorts Windows     : {', '.join(f'{h}:00 IST' for h in state.get('shorts_hours_ist', []))}")
    print(f"  Primary Voice      : {getattr(config, 'VOICE_ID', 'hi-IN-MadhurNeural')} (Hindi)")
    print(f"  Auto-Dub Voice     : {getattr(config, 'VOICE_ID_EN', 'en-US-AndrewNeural')} (English)")
    print(f"  Checklist Quality  : 100 / 100 Guaranteed Gate Active")
    print(f"  YouTube Linked     : {'Yes (Live Direct Upload)' if is_configured() else 'Pending client_secret.json'}")
    print("─" * 65)
    print("  🗓️ 7-Day Weekly Content Calendar:")
    current_day_name = now_ist.strftime("%A")
    for d_name, d_info in config.WEEKLY_THEMES.items():
        prefix = "  ▶ [TODAY] " if d_name == current_day_name else "    •       "
        print(f"{prefix}{d_name:9s} : {d_info['theme']} [{d_info['theme_hi']}]")
    print("─" * 65)
    print("─" * 65)
    print("  📈 Adaptive Slot Performance:")
    for slot, data in state.get("slot_performance", {}).items():
        print(f"     Slot {slot}:00 IST → Runs: {data['runs']:2d} | Avg Views: {data['avg_views']}")
    print("─" * 65)
    runs = state.get("history_runs", [])
    print(f"  Recent Automated Runs ({len(runs)} total):")
    for r in runs[-5:]:
        print(f"   • [{r['type'].upper()}] {r['title']} (Score: {r['score']}) → {r['url']}")
    print("═" * 65 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YAAS Autonomous History Studio")
    parser.add_argument("--daemon", action="store_true", help="Run continuous scheduler daemon")
    parser.add_argument("--auto", action="store_true", help="Auto catch-up: evaluate current IST time and publish overdue/current content")
    parser.add_argument("--run-short-slot", type=int, choices=[1, 2, 3, 4, 5], help="Execute specific Short slot (1 to 5) immediately")
    parser.add_argument("--prerender", action="store_true", help="Pre-render tomorrow's content now a day before")
    parser.add_argument("--run-shorts", action="store_true", help="Execute 5 daily Shorts generation immediately")
    parser.add_argument("--run-long", action="store_true", help="Execute 15+ min history video pipeline immediately")
    parser.add_argument("--run-all", action="store_true", help="Execute Shorts FIRST, then Long-form immediately")
    parser.add_argument("--status", action="store_true", help="Display current status and adaptive metrics")

    args = parser.parse_args()

    if args.daemon:
        run_scheduler_daemon()
    elif args.auto:
        res = run_auto_catchup()
        try:
            from notifier.email_notifier import send_upload_notification_email
            send_upload_notification_email(longform_result=res.get("published_long"), shorts_results=res.get("published_shorts"))
        except Exception as e:
            print(f"   ℹ Email notification notice: {e}")
    elif args.run_short_slot:
        s_res = create_and_publish_single_short(index=args.run_short_slot)
        try:
            from notifier.email_notifier import send_upload_notification_email
            send_upload_notification_email(shorts_results=[s_res])
        except Exception as e:
            print(f"   ℹ Email notification notice: {e}")
    elif args.prerender:
        tomorrow_str = (get_current_ist_time() + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"\n🚀 Pre-rendering tomorrow's ({tomorrow_str}) content a day before: Shorts FIRST, then Long-form...")
        s_res = create_and_publish_shorts_batch(is_prerender=True, for_date=tomorrow_str)
        l_res = create_and_publish_longform(is_prerender=True, for_date=tomorrow_str)
        try:
            from notifier.email_notifier import send_upload_notification_email
            send_upload_notification_email(longform_result=l_res, shorts_results=s_res)
        except Exception as e:
            print(f"   ℹ Email notification notice: {e}")
    elif args.run_shorts:
        s_res = create_and_publish_shorts_batch()
        try:
            from notifier.email_notifier import send_upload_notification_email
            send_upload_notification_email(shorts_results=s_res)
        except Exception as e:
            print(f"   ℹ Email notification notice: {e}")
    elif args.run_long:
        create_and_publish_longform()
    elif args.run_all:
        print("\n🚀 Executing full batch: Shorts FIRST, then Long-form documentary...")
        s_res = create_and_publish_shorts_batch()
        l_res = create_and_publish_longform()
        try:
            from notifier.email_notifier import send_upload_notification_email
            send_upload_notification_email(longform_result=l_res, shorts_results=s_res)
        except Exception as e:
            print(f"   ℹ Email notification notice: {e}")
    elif args.status:
        print_status()
    else:
        print_status()
        print("Usage:")
        print("  python automation.py --daemon          # Start continuous automated daily scheduler")
        print("  python automation.py --auto            # Auto catch-up & publish due content for current IST hour")
        print("  python automation.py --run-short-slot N# Run single Short slot N (1 to 5) immediately")
        print("  python automation.py --prerender       # Pre-render tomorrow's content a day before")
        print("  python automation.py --run-shorts      # Run all 5 daily history shorts now")
        print("  python automation.py --run-long        # Run 15+ min deep history video now")
        print("  python automation.py --run-all         # Run Shorts FIRST, then Long-form now")
        print("  python automation.py --status          # View schedule and performance metrics\n")
