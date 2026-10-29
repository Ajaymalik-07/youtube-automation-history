import os
import json
import glob
import subprocess
import shutil
import imageio_ffmpeg
from moviepy.editor import AudioFileClip

def build_documentary():
    exe = imageio_ffmpeg.get_ffmpeg_exe()

    script_path = os.path.join("output", "script.json")
    audio_path = os.path.join("output", "narration.mp3")
    srt_path = os.path.join("output", "narration.srt")
    images_dir = os.path.join("output", "images")
    output_video = os.path.join("output", "final_video.mp4")

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    with AudioFileClip(audio_path) as a:
        total_audio_dur = a.duration

    sections = script.get("sections", [])
    word_counts = [max(1, len(s.get("narration", "").split())) for s in sections]
    total_words = sum(word_counts)

    section_durs = [(w / total_words) * total_audio_dur for w in word_counts]

    slideshow_lines = []
    all_used_imgs = []

    for i, (sec, sec_dur) in enumerate(zip(sections, section_durs), 1):
        sec_imgs = sorted(glob.glob(os.path.join(images_dir, f"section_{i:02d}_img*.jpg")))
        if not sec_imgs:
            sec_imgs = sorted(glob.glob(os.path.join(images_dir, "*.jpg")))[:1]

        img_dur = sec_dur / max(1, len(sec_imgs))
        for img_path in sec_imgs:
            p = os.path.abspath(img_path).replace("\\", "/")
            slideshow_lines.append(f"file '{p}'\nduration {img_dur:.3f}")
            all_used_imgs.append(img_path)

    if all_used_imgs:
        p_last = os.path.abspath(all_used_imgs[-1]).replace("\\", "/")
        slideshow_lines.append(f"file '{p_last}'")

    slideshow_file = os.path.join("output", "slideshow.txt")
    with open(slideshow_file, "w", encoding="utf-8") as f:
        f.write("\n".join(slideshow_lines) + "\n")

    print(f"Generated slideshow.txt with {len(all_used_imgs)} images covering {total_audio_dur:.1f}s")

    srt_clean = os.path.abspath(srt_path).replace("\\", "/")
    # Use relative or cleaned path for subtitles filter to avoid drive letter colon syntax issues
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,"
        f"subtitles=output/narration.srt:force_style='FontName=Nirmala UI,FontSize=24,PrimaryColour=&H00FFFFFF,BorderStyle=4,BackColour=&H80000000,MarginV=45',"
        "format=yuv420p"
    )

    cmd = [
        exe, "-y",
        "-f", "concat", "-safe", "0", "-i", slideshow_file,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_video,
    ]

    print("Running ffmpeg render...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg error:", res.stderr[-500:])
        return False

    size_mb = os.path.getsize(output_video) / (1024 * 1024)
    print(f"SUCCESS: Video rendered cleanly -> {output_video} ({size_mb:.1f} MB)")

    # Also sync into library directory
    lib_dir = os.path.join("output", "library", "20261028-170406-lost-civilization-under-desert")
    if os.path.isdir(lib_dir):
        lib_video = os.path.join(lib_dir, "video.mp4")
        shutil.copy2(output_video, lib_video)
        print(f"Copied to library: {lib_video}")

    return True

if __name__ == "__main__":
    build_documentary()
