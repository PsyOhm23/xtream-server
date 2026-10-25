"""Technical details stored beside a video file.

The JSON uses the video stem. It is rewritten when the file size or mtime changes.
"""

import json
import os
import subprocess
from datetime import datetime, timezone

DETAIL_VERSION = 4


def sidecar_path(video_path):
    folder, name = os.path.split(video_path)
    stem, _extension = os.path.splitext(name)
    return os.path.join(folder, stem + ".json")


def source_stamp(video_path):
    stat = os.stat(video_path)
    return {"source_size": stat.st_size, "source_mtime_ns": stat.st_mtime_ns}


def quality_from_dimensions(width, height):
    """Map picture size to a quality label. Scope 4K is about 3840x1600, not 2160 tall."""
    try:
        width = int(width or 0)
        height = int(height or 0)
    except (TypeError, ValueError):
        return ""
    if width <= 0 and height <= 0:
        return ""
    long_side = max(width, height)
    short_side = min(width, height) if width and height else long_side
    if long_side >= 3000 or short_side >= 1600:
        return "2160p"
    if long_side >= 1800 or short_side >= 900:
        return "1080p"
    if short_side >= 700 or long_side >= 1200:
        return "720p"
    if short_side >= 540:
        return "576p"
    if short_side >= 400 or long_side >= 600:
        return "480p"
    return f"{short_side or long_side}p"


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_attached_picture(stream):
    return bool((stream.get("disposition") or {}).get("attached_pic"))


def _format_duration(seconds):
    whole = int(round(seconds or 0))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _stream_document(stream):
    """Copy one ffprobe stream, which is what Xtream puts in info.video and info.audio."""
    if not stream:
        return {}
    return {key: value for key, value in stream.items() if key != "extradata"}


def _default_stream(streams):
    for stream in streams:
        if (stream.get("disposition") or {}).get("default"):
            return stream
    return streams[0] if streams else None


def detail_from_probe(probe, stamp):
    """Build the sidecar document from an ffprobe JSON payload."""
    streams = probe.get("streams") or []
    videos = [
        stream for stream in streams
        if stream.get("codec_type") == "video" and not _is_attached_picture(stream)
    ]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    video = videos[0] if videos else {}
    fmt = probe.get("format") or {}
    duration = _as_float(fmt.get("duration") or video.get("duration"))
    bitrate = _as_int(fmt.get("bit_rate"))
    if not bitrate and duration and stamp.get("source_size"):
        bitrate = int(stamp["source_size"] * 8 / duration)
    seconds = int(round(duration)) if duration else 0
    primary_audio = _default_stream(audios)
    return {
        "version": DETAIL_VERSION,
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "source_size": stamp.get("source_size") or 0,
        "source_mtime_ns": stamp.get("source_mtime_ns") or 0,
        "duration_secs": seconds,
        "duration": _format_duration(seconds) if seconds else "",
        "bitrate": int(round(bitrate / 1000)) if bitrate else 0,
        "video": _stream_document(video),
        "audio": _stream_document(primary_audio),
    }


def as_xtream_detail(data):
    """Keep the ffprobe video and audio objects Xtream already exposes."""
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    video = data.get("video") if isinstance(data.get("video"), dict) else {}
    audio = data.get("audio") if isinstance(data.get("audio"), dict) else {}
    if not video.get("codec_name") and not video.get("codec_type"):
        video = info.get("video") if isinstance(info.get("video"), dict) else {}
    if not audio.get("codec_name") and not audio.get("codec_type"):
        nested = info.get("audio")
        audio = nested if isinstance(nested, dict) else {}
    seconds = _as_int(data.get("duration_secs"))
    return {
        "version": DETAIL_VERSION,
        "probed_at": data.get("probed_at") or "",
        "source_size": data.get("source_size") or 0,
        "source_mtime_ns": data.get("source_mtime_ns") or 0,
        "duration_secs": seconds,
        "duration": data.get("duration") or (_format_duration(seconds) if seconds else ""),
        "bitrate": _as_int(data.get("bitrate")),
        "video": video,
        "audio": audio,
    }


def load_detail(video_path):
    """Return the sidecar when it still matches the video file."""
    path = sidecar_path(video_path)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        stamp = source_stamp(video_path)
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if data.get("version") not in {3, DETAIL_VERSION}:
        return None
    if data.get("source_size") != stamp["source_size"]:
        return None
    if data.get("source_mtime_ns") != stamp["source_mtime_ns"]:
        return None
    return as_xtream_detail(data)


def write_detail(video_path, detail):
    path = sidecar_path(video_path)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(detail, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)
    return path


def probe_file(video_path, timeout=30):
    """Run ffprobe and write the sidecar. Return the document, or None on failure."""
    try:
        stamp = source_stamp(video_path)
    except OSError:
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_format", "-show_streams",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        probe = json.loads(result.stdout or "{}")
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return None
    if not probe.get("streams") and not probe.get("format"):
        return None
    detail = detail_from_probe(probe, stamp)
    write_detail(video_path, detail)
    return detail


def xtream_video(detail):
    """The video object Xtream returns in info.video."""
    video = (detail or {}).get("video") or {}
    if video.get("codec_name") or video.get("codec_type") or video.get("width"):
        return video
    return None


def xtream_audio(detail):
    """The audio object Xtream returns in info.audio."""
    audio = (detail or {}).get("audio") or {}
    if audio.get("codec_name") or audio.get("codec_type") or audio.get("channels"):
        return audio
    return None
