import os
import glob
import subprocess
from server import get_categorized_videos, THUMB_DIR

POSTER_WIDTH = 320
POSTER_SEEKS = ("00:01:00", "00:00:10")
BACKDROP_SEEKS = ("00:08:00", "00:03:00", "00:00:45")


def grab_frame(source, dest, seeks, scale=None, quality="3"):
    """Write one JPEG frame. scale is a width in pixels, or None for the full frame."""
    for seek in seeks:
        cmd = [
            "sudo", "-u", "xpi", "ffmpeg", "-ss", seek, "-i", source,
            "-frames:v", "1",
        ]
        if scale:
            cmd += ["-vf", f"scale={scale}:-2"]
        cmd += ["-q:v", quality, "-y", dest]
        try:
            subprocess.run(cmd, capture_output=True, timeout=20)
        except subprocess.TimeoutExpired:
            continue
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            subprocess.run(["sudo", "chmod", "644", dest], check=False)
            return True
    return False


def generate_all_thumbs():
    print("Starting thumbnail generation for personal media only...")
    videos, _ = get_categorized_videos()
    videos = [item for item in videos if item.get("source") == "other"]
    valid_ids = {str(item["stream_id"]) for item in videos}

    removed = 0
    for thumb in glob.glob(os.path.join(THUMB_DIR, "*.jpg")):
        stem = os.path.splitext(os.path.basename(thumb))[0]
        if stem.endswith("_backdrop"):
            stem = stem[: -len("_backdrop")]
        if stem in valid_ids:
            continue
        try:
            os.remove(thumb)
            removed += 1
        except OSError:
            pass
    if removed:
        print(f"Cleaned {removed} orphaned thumbnails from cache.")

    total = len(videos)
    for idx, item in enumerate(videos, start=1):
        stream_id = item["stream_id"]
        source = item["path"]
        poster = os.path.join(THUMB_DIR, f"{stream_id}.jpg")
        backdrop = os.path.join(THUMB_DIR, f"{stream_id}_backdrop.jpg")
        print(f"[{idx}/{total}] Generating images for: {item['name']}")
        try:
            if not grab_frame(source, poster, POSTER_SEEKS, scale=POSTER_WIDTH, quality="5"):
                print("  poster failed")
            if not grab_frame(source, backdrop, BACKDROP_SEEKS, quality="3"):
                print("  backdrop failed")
        except Exception as exc:
            print(f"  Error: {exc}")

    print("Thumbnail generation complete!")


if __name__ == "__main__":
    generate_all_thumbs()
