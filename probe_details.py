"""Write a technical JSON beside each video that is missing or stale.

Dry-run is the default. Pass --apply to probe files and write the sidecars.
"""

import argparse
import json
import os
import sys

import media_detail

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".m2ts"}


def iter_videos(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames
            if not name.startswith(".") and name != "doublons"
        ]
        for filename in filenames:
            if filename.startswith("."):
                continue
            if os.path.splitext(filename)[1].lower() not in VIDEO_EXTENSIONS:
                continue
            yield os.path.join(dirpath, filename)


def configured_media_root():
    """First TMDB directory from config.json. There is no built-in path."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.isfile(config_path):
        return ""
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return ""
    libraries = data.get("libraries") if isinstance(data, dict) else None
    if not isinstance(libraries, list):
        return ""
    for item in libraries:
        if isinstance(item, dict) and item.get("type") == "tmdb" and isinstance(item.get("path"), str):
            return item["path"]
    return ""


def main():
    parser = argparse.ArgumentParser(description="Probe videos and write a JSON sidecar.")
    parser.add_argument("--root", help="Library directory. Defaults to the first tmdb library in config.json.")
    parser.add_argument("--apply", action="store_true", help="Probe files and write sidecars")
    parser.add_argument("--limit", type=int, default=0, help="Max files to consider, 0 means all")
    args = parser.parse_args()
    root = args.root or configured_media_root()
    if not root:
        print(
            "No library directory.\n"
            "Pass --root /your/library, or add a tmdb library in config.json.\n"
            "  cp config.example.json config.json",
            file=sys.stderr,
        )
        return 1
    args.root = root

    if not os.path.isdir(args.root):
        print(f"media root not found: {args.root}", file=sys.stderr)
        return 1

    considered = 0
    written = 0
    skipped = 0
    failed = 0
    for path in iter_videos(args.root):
        if args.limit and considered >= args.limit:
            break
        considered += 1
        if media_detail.load_detail(path):
            skipped += 1
            continue
        print(path, flush=True)
        if not args.apply:
            continue
        if media_detail.probe_file(path):
            written += 1
        else:
            failed += 1
            print(f"  probe failed", flush=True)

    print(
        f"considered={considered} skipped={skipped} written={written} failed={failed}",
        flush=True,
    )
    if not args.apply:
        print("dry-run only, no files probed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
