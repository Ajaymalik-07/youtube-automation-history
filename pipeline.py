#!/usr/bin/env python3
"""
YAAS — Stories Malik · Autonomous Historical Video Pipeline (CLI)
Phase 17 Overhaul: Fully automated create -> validate -> upload -> schedule workflow.
Removes manual human approval dependencies and enforces automated quality gates.
"""
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import config
from agents.researcher   import research_topic
from agents.scriptwriter import write_script
from video.narrator      import generate_narration
from video.stock         import download_images
from video.creator       import create_video
from video               import thumbnail
from uploader.youtube    import upload_to_youtube
from uploader.safety     import record_production_state, PublishingState


def banner(text: str):
    print("\n" + "─" * 62)
    print(f"  {text}")
    print("─" * 62)


def run():
    Path(config.OUTPUT_DIR).mkdir(exist_ok=True)
    Path(config.IMAGES_DIR).mkdir(exist_ok=True)

    print("\n🎬  Stories Malik — Autonomous Historical Documentary Pipeline\n")

    # ── 1. Research ───────────────────────────────────────────
    banner("1 / 6  ·  Researching topic with multi-tier evidence [Gemini / Archives]")
    record_production_state("in_progress", PublishingState.TOPIC_SELECTED.value)
    research = research_topic(config.CHANNEL_DESCRIPTION)
    print(f"\n  ✅  Topic : {research['topic']}")
    print(f"      Title : {research['video_title']}")
    print(f"      Hook  : {research.get('hook_question', '')[:90]}")
    with open(f"{config.OUTPUT_DIR}/research.json", "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2, ensure_ascii=False)

    # ── 2. Script ─────────────────────────────────────────────
    banner("2 / 6  ·  Generating structured Hindi documentary script")
    script = write_script(research, language=getattr(config, "DEFAULT_LANGUAGE", "hi"))
    print(f"\n  ✅  {len(script['sections'])} sections written")
    for s in script["sections"]:
        words = len(s.get("narration", "").split())
        title = s.get("title", "Untitled")
        print(f"      [{s.get('id', 9):02d}] {title:<42} {words:3d} words")
    with open(f"{config.OUTPUT_DIR}/script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    # ── 3. Stock Images ───────────────────────────────────────
    banner("3 / 6  ·  Acquiring historical imagery & architectural fallbacks")
    image_map = download_images(script, config.OUTPUT_DIR)
    found = sum(1 for v in image_map.values() if v)
    print(f"\n  ✅  {found}/{len(image_map)} images downloaded")

    # ── 4. Narration ──────────────────────────────────────────
    banner("4 / 6  ·  Generating Devanagari voiceover [Edge TTS — free]")
    audio_path = generate_narration(
        script, config.OUTPUT_DIR,
        voice_id=getattr(config, "VOICE_ID", "hi-IN-MadhurNeural")
    )
    print(f"\n  ✅  Audio: {audio_path}")

    # ── 5. Video ──────────────────────────────────────────────
    banner("5 / 6  ·  Rendering documentary video [MoviePy + HarfBuzz/Pango]")
    record_production_state("in_progress", PublishingState.VIDEO_RENDERING.value)
    video_path = create_video(script, audio_path, config.OUTPUT_DIR, image_map)
    record_production_state(video_path, PublishingState.VIDEO_RENDERED.value)
    print(f"\n  ✅  Video rendered: {video_path}")

    # ── 6. Thumbnail & Autonomous Publishing ──────────────────
    banner("6 / 6  ·  Quality gates & autonomous scheduled publishing [YouTube API]")
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
        thumb_text = thumbnail.auto_text(script.get("title", ""))
        thumb_path = thumbnail.render(
            getattr(config, "THUMB_STYLE", "cinematic"),
            thumb_path,
            thumb_text,
            bg_path=first_img,
            brand=config.brand_text(),
            portrait=False,
        )
        print(f"  ✅  Thumbnail: {thumb_path}")
    except Exception as e:
        print(f"  ⚠  Thumbnail non-fatal warning: {e}")

    # Direct autonomous upload with quality gate enforcement
    yt_result = upload_to_youtube(
        script=script,
        video_path=video_path,
        thumb_path=thumb_path,
        research=research,
        is_shorts=False,
    )

    if "blocked_quality_gate" in yt_result:
        print(f"\n  🚨  Autonomous Quality Gate Blocked Publication: {yt_result}")
        print("      Check output/diagnostics/ for the comprehensive failure report.\n")
    elif yt_result.startswith("https://"):
        print(f"\n  🎉  Autonomous Publishing Successful: {yt_result}\n")
    else:
        print(f"\n  📦  Video Preserved in Queue: {yt_result}\n")


if __name__ == "__main__":
    run()
