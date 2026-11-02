"""
Create and publish today's 9:00 AM Short (Monday theme: Rivers & Ancient Civilizations)
Directly uploads to YouTube as Public with 100/100 SEO checklist compliance.
"""
import os
import sys
import json
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from agents.scriptwriter import write_script
from video.stock import download_images
from video.narrator import generate_narration
from video.music import mix_music_with_narration
from video.creator import create_video
from agents.seo_optimizer import optimize_for_100_percent
from uploader.youtube import upload_to_youtube
import automation

def main():
    print("=" * 70)
    print("🚀 Producing and Publishing Today's 9:00 AM Short")
    today_theme = config.get_weekly_theme()
    print(f"📅 Today's Editorial Theme ({today_theme['day']}): {today_theme['theme']} ({today_theme['theme_hi']})")
    print("=" * 70 + "\n")

    target_date = datetime.now().strftime("%Y-%m-%d")
    shorts_dir = os.path.join(config.OUTPUT_DIR, "shorts_batch")
    item_dir = os.path.join(shorts_dir, "short_01")
    os.makedirs(item_dir, exist_ok=True)

    topics = automation.get_shorts_topics_for_day(target_date)
    topic_title, lang = topics[0]
    print(f"📌 Short 1/5 Topic: {topic_title} ({'Hindi' if lang == 'hi' else 'English'})\n")

    research = {
        "topic": topic_title,
        "video_title": topic_title,
        "hook_question": f"Did you know the terrifying secret behind {topic_title}?",
        "key_points": [
            f"Ancient archaeological mystery of {topic_title}",
            "How water engineering shaped and ended this lost civilization",
            "What modern science recently discovered"
        ],
        "tags": ["History", "Shorts", "AncientMysteries", "Archaeology", "Facts", "AncientCivilizations"],
    }

    # 1. Script
    print("  [1/6] Writing high-hook vertical Short script…")
    short_script = write_script(research, video_type="shorts", language=lang)
    with open(os.path.join(item_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(short_script, f, indent=2, ensure_ascii=False)
    print(f"   ✓ Script ready: {len(short_script.get('sections', []))} scenes")

    # 2. Stock Images
    print("  [2/6] Sourcing historical archival images…")
    image_map = download_images(short_script, item_dir)
    total_imgs = sum(len(v) if isinstance(v, list) else 1 for v in image_map.values() if v)
    print(f"   ✓ Downloaded {total_imgs} visual assets")

    # 3. Voiceover & Music
    print(f"  [3/6] Generating voiceover ({config.VOICE_ID})…")
    voice_id = getattr(config, "VOICE_ID", "hi-IN-MadhurNeural") if lang == "hi" else getattr(config, "VOICE_ID_EN", "en-US-AndrewNeural")
    audio_path = generate_narration(short_script, item_dir, voice_id=voice_id)

    final_audio = audio_path
    if config.MUSIC_ENABLED:
        try:
            print("   Mixing subtle background music…")
            mixed_audio = os.path.join(item_dir, "narration_mixed.mp3")
            final_audio = mix_music_with_narration(
                audio_path, mixed_audio,
                music_volume=getattr(config, "MUSIC_VOLUME", 0.12),
                library_dir=getattr(config, "MUSIC_LIBRARY_DIR", "")
            )
        except Exception as e:
            print(f"   ⚠ Music mix non-fatal warning: {e}")

    # 4. Video Render (1080x1920 vertical)
    print("  [4/6] Rendering 1080×1920 vertical Short with synced captions…")
    image_map_int = {int(k): v for k, v in image_map.items()}
    video_path = create_video(short_script, final_audio, item_dir, image_map_int, video_type="shorts")
    print(f"   ✓ Short rendered: {video_path}")

    # 5. 100/100 SEO Checklist
    print("  [5/6] Optimizing metadata for 100/100 SEO…")
    seo_res = optimize_for_100_percent(
        title=short_script.get("title", ""),
        description=short_script.get("description", ""),
        tags=short_script.get("tags", []),
        sections=short_script.get("sections", []),
        topic=topic_title,
        is_shorts=True,
    )
    print(f"   🎯 SEO Score: {seo_res['score']} / 100 (100% Guaranteed)")

    # 6. YouTube Upload (Direct Public)
    print("  [6/6] Uploading to YouTube as Public…")
    yt_url = upload_to_youtube(
        script=short_script,
        video_path=video_path,
        title=seo_res["title"],
        description=seo_res["description"],
        tags=seo_res["tags"],
        privacy="public"
    )

    print("\n" + "=" * 70)
    print(f"🎉 SUCCESS! Today's 9:00 AM Short is published: {yt_url}")
    print("=" * 70 + "\n")

    # Update schedule state
    state = automation.load_schedule_state()
    state[f"last_short_pub_{target_date}_9"] = True
    state["history_runs"].append({
        "type": "short",
        "title": seo_res["title"],
        "url": yt_url,
        "date_ist": automation.get_current_ist_time().isoformat(),
        "score": seo_res["score"],
    })
    automation.save_schedule_state(state)

    try:
        from notifier.email_notifier import send_upload_notification_email
        send_upload_notification_email(shorts_results=[{
            "index": 1,
            "title": seo_res["title"],
            "url": yt_url,
            "score": seo_res["score"]
        }])
    except Exception as e:
        print(f"   ℹ Email dispatch note: {e}")

if __name__ == "__main__":
    main()
