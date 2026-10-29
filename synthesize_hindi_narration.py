import sys
import os
import json
import shutil
import asyncio
import edge_tts
import config
from video.narrator import generate_narration

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main():
    script_path = os.path.join("output", "script.json")
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    output_dir = "output"
    voice_id = "hi-IN-MadhurNeural"
    print(f"Starting Hindi narration synthesis with {voice_id}...")

    # Generate primary Hindi narration audio and SRT
    audio_path = generate_narration(
        script,
        output_dir,
        voice_id=voice_id,
        filename="narration.mp3",
        srt_filename="narration.srt"
    )

    # Keep a copy as narration_hi.mp3 / narration_hi.srt
    shutil.copy2(os.path.join(output_dir, "narration.mp3"), os.path.join(output_dir, "narration_hi.mp3"))
    shutil.copy2(os.path.join(output_dir, "narration.srt"), os.path.join(output_dir, "narration_hi.srt"))

    # Also sync into library
    lib_dir = os.path.join("output", "library", "20261028-170406-lost-civilization-under-desert")
    if os.path.isdir(lib_dir):
        shutil.copy2(os.path.join(output_dir, "narration.mp3"), os.path.join(lib_dir, "narration.mp3"))
        shutil.copy2(os.path.join(output_dir, "narration.srt"), os.path.join(lib_dir, "narration.srt"))
        print(f"Synced Hindi audio and subtitles to library folder: {lib_dir}")

    print(f"SUCCESS: Hindi narration generated at {audio_path}")

if __name__ == "__main__":
    main()
