"""Rename movies and episodes only when the TMDB match is certain.

Dry-run is the default. Pass --apply to rename files and write library.json.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

import media_match

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".m2ts"}
SIDECAR_EXTENSIONS = {".srt", ".nfo", ".jpg", ".jpeg", ".sub", ".idx", ".ass", ".txt", ".json"}
SKIP_NAME = re.compile(r"(?i)\b(sample|trailer|story-?board|storyboard|deleted|making of|bonus)\b")
GENERIC_EPISODE = re.compile(r"(?i)^(episode|épisode|ep)\s*\d+$")
DEFAULT_API_KEY = ""


def load_api_key():
    if os.environ.get("TMDB_API_KEY"):
        return os.environ["TMDB_API_KEY"]
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                return json.load(handle).get("tmdb_api_key") or DEFAULT_API_KEY
        except (OSError, json.JSONDecodeError):
            pass
    return DEFAULT_API_KEY


def is_video(name):
    return os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS and not name.startswith(".")


def should_skip(name):
    return bool(SKIP_NAME.search(name))


def relative(path, root):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return unicodedata.normalize("NFC", rel)


def movie_bucket(rel_path):
    parts = rel_path.split("/")
    if len(parts) >= 2 and parts[0] == "anims" and parts[1] == "films":
        return "anims/films"
    if parts and parts[0] == "films":
        return "films"
    return None


def series_bucket(rel_path):
    parts = rel_path.split("/")
    if len(parts) >= 2 and parts[0] == "anims" and parts[1] == "series":
        return "anims/series", parts[2] if len(parts) > 2 else None
    if parts and parts[0] == "series":
        return "series", parts[1] if len(parts) > 1 else None
    return None, None


def filename_is_weak(parsed):
    compact = media_match.canon(parsed.title).replace(" ", "")
    return compact == "" or len(compact) < 6


def parent_can_help(file_parsed, parent_parsed):
    if filename_is_weak(file_parsed):
        return True
    file_title = media_match.canon(file_parsed.title)
    parent_title = media_match.canon(parent_parsed.title)
    if not file_title or not parent_title:
        return False
    # A longer filename carries the real title. Do not let a short folder override it.
    if len(file_title) > len(parent_title) + 1:
        return False
    return file_title == parent_title or parent_title.startswith(file_title)


def iter_videos(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames
            if not name.startswith(".") and name not in {"tv", "doublons"}
        ]
        for filename in filenames:
            if is_video(filename):
                yield os.path.join(dirpath, filename)


def quality_label(path):
    """Resolution token carried by a filename, such as 2160p or 4K."""
    name = os.path.basename(path)
    match = re.search(r"(?i)\b(2160p|1080p|720p|576p|480p)\b", name)
    if match:
        return match.group(1).lower()
    if re.search(r"(?i)\b(4k|uhd)\b", name):
        return "4K"
    return ""


def movie_destination(root, bucket, meta, extension, quality=""):
    title = media_match.filesystem_name(meta["title"])
    folder = f"{title} ({meta['year']})" if meta.get("year") else title
    stem = f"{folder} [{quality}]" if quality else folder
    filename = stem + extension.lower()
    return os.path.join(root, bucket, folder, filename)


def separate_quality_copies(items):
    """Keep a second copy in the movie folder, with the quality in the filename."""
    grouped = {}
    for item in items:
        grouped.setdefault(item["dest"], []).append(item)
    separated = []
    for group in grouped.values():
        if len(group) == 1:
            separated.extend(group)
            continue
        for item in group:
            quality = quality_label(item["src"])
            if quality:
                folder = os.path.dirname(item["dest"])
                stem, extension = os.path.splitext(os.path.basename(item["dest"]))
                item["dest"] = os.path.join(folder, f"{stem} [{quality}]{extension}")
            separated.append(item)
    return separated


def animation_preference(rel_path):
    """True under anims/films, False under films, None elsewhere."""
    bucket = movie_bucket(rel_path)
    if bucket == "anims/films":
        return True
    if bucket == "films":
        return False
    return None


def identify_movie(client, path, root):
    filename = os.path.basename(path)
    parsed = media_match.parse_media_name(filename)
    prefer_animation = animation_preference(relative(path, root))
    hit = media_match.identify_parsed(client, parsed, "movie", prefer_animation)
    chosen = parsed
    if not hit:
        parent = os.path.basename(os.path.dirname(path))
        rel_parent = relative(os.path.dirname(path), root)
        if parent and rel_parent not in {"films", "anims/films"} and media_match.parent_is_usable(parent):
            parent_parsed = media_match.parse_media_name(parent)
            if parent_can_help(parsed, parent_parsed):
                if filename_is_weak(parsed) and parent_parsed.year is None and parsed.year:
                    parent_parsed.year = parsed.year
                parent_hit = media_match.identify_parsed(client, parent_parsed, "movie", prefer_animation)
                if parent_hit:
                    hit = parent_hit
                    chosen = parent_parsed
    if not hit:
        return None
    meta = media_match.metadata_from_details(client, hit, chosen)
    if not meta.get("year"):
        return None
    return meta


def show_year_from_files(folder, filenames):
    years = []
    for filename in filenames:
        if not is_video(filename) or should_skip(filename):
            continue
        parsed = media_match.parse_media_name(filename)
        if parsed.year:
            years.append(parsed.year)
    unique = set(years)
    if len(unique) == 1:
        return unique.pop()
    return None


def identify_show(client, folder_name, filenames):
    parsed = media_match.parse_media_name(folder_name)
    if parsed.year is None:
        parsed.year = show_year_from_files("", filenames)
    hit = media_match.identify_parsed(client, parsed, "tv")
    if not hit:
        return None, parsed
    meta = media_match.metadata_from_details(client, hit, parsed)
    if not meta.get("year"):
        return None, parsed
    return meta, parsed


def episode_language(meta):
    french_score = media_match.title_score(meta["title"], meta.get("french_title") or "")
    original_score = media_match.title_score(meta["title"], meta.get("original_title") or "")
    if original_score > french_score:
        return "en-US"
    return "fr-FR"


def episode_title(client, meta, season_number, episode_number, cache):
    language = episode_language(meta)
    key = (meta["tmdb_id"], season_number, language)
    if key not in cache:
        payload = client.season(meta["tmdb_id"], season_number, language)
        episodes = {}
        for item in payload.get("episodes") or []:
            number = item.get("episode_number")
            name = (item.get("name") or "").strip()
            if number and name and not GENERIC_EPISODE.match(name):
                episodes[number] = name
        cache[key] = episodes
    return cache[key].get(episode_number) or ""


def episode_destination(root, bucket, meta, season_number, episode_number, episode_name, extension):
    show = media_match.filesystem_name(meta["title"])
    folder = f"{show} ({meta['year']})" if meta.get("year") else show
    season_folder = f"Season {season_number:02d}"
    stem = f"{show} - S{season_number:02d}E{episode_number:02d}"
    if episode_name:
        stem += " - " + media_match.filesystem_name(episode_name)
    filename = stem + extension.lower()
    return os.path.join(root, bucket, folder, season_folder, filename)


def plan_library(root, client, only, limit):
    movies = []
    episodes = []
    uncertain_movies = []
    uncertain_episodes = []
    shows = {}
    season_cache = {}
    seen_movies = 0

    videos = list(iter_videos(root))
    series_files = {}
    for path in videos:
        rel = relative(path, root)
        bucket, show_folder = series_bucket(rel)
        if bucket and show_folder:
            series_files.setdefault((bucket, show_folder), []).append(path)

    for path in videos:
        rel = relative(path, root)
        bucket = movie_bucket(rel)
        if not bucket or only == "series":
            continue
        if should_skip(os.path.basename(path)):
            uncertain_movies.append({"path": rel, "reason": "extra"})
            continue
        if limit and seen_movies >= limit:
            break
        seen_movies += 1
        print(f"[movie {seen_movies}] {rel}", flush=True)
        try:
            meta = identify_movie(client, path, root)
        except Exception as exc:
            uncertain_movies.append({"path": rel, "reason": f"error: {exc}"})
            print(f"  error: {exc}", flush=True)
            continue
        if not meta:
            parsed = media_match.parse_media_name(os.path.basename(path))
            uncertain_movies.append({
                "path": rel,
                "reason": "uncertain",
                "query": parsed.title,
                "year": parsed.year,
            })
            print(f"  uncertain: {parsed.title} ({parsed.year})", flush=True)
            continue
        extension = os.path.splitext(path)[1]
        dest = movie_destination(root, bucket, meta, extension)
        movies.append({
            "src": path,
            "dest": dest,
            "rel": rel,
            "size": os.path.getsize(path),
            "meta": meta,
        })
        print(f"  certain {meta['score']}: {meta['title']} ({meta['year']})", flush=True)

    if only != "movies":
        for (bucket, show_folder), paths in sorted(series_files.items()):
            print(f"[show] {bucket}/{show_folder} ({len(paths)} files)", flush=True)
            names = [os.path.basename(path) for path in paths]
            try:
                meta, _parsed = identify_show(client, show_folder, names)
            except Exception as exc:
                uncertain_episodes.append({"path": f"{bucket}/{show_folder}", "reason": f"error: {exc}"})
                print(f"  error: {exc}", flush=True)
                continue
            if not meta:
                uncertain_episodes.append({"path": f"{bucket}/{show_folder}", "reason": "uncertain show"})
                print("  uncertain show", flush=True)
                continue
            show_dir = os.path.join(root, bucket, media_match.filesystem_name(
                f"{meta['title']} ({meta['year']})" if meta.get("year") else meta["title"]
            ))
            show_key = relative(show_dir, root)
            shows[show_key] = meta
            print(f"  certain {meta['score']}: {meta['title']} ({meta['year']})", flush=True)
            for path in paths:
                filename = os.path.basename(path)
                if should_skip(filename):
                    uncertain_episodes.append({"path": relative(path, root), "reason": "extra"})
                    continue
                parsed = media_match.parse_media_name(filename)
                if not parsed.season or not parsed.episode:
                    uncertain_episodes.append({"path": relative(path, root), "reason": "no episode number"})
                    continue
                try:
                    name = episode_title(client, meta, parsed.season, parsed.episode, season_cache)
                except Exception as exc:
                    name = ""
                    print(f"  episode title error: {exc}", flush=True)
                extension = os.path.splitext(path)[1]
                dest = episode_destination(root, bucket, meta, parsed.season, parsed.episode, name, extension)
                episodes.append({
                    "src": path,
                    "dest": dest,
                    "rel": relative(path, root),
                    "size": os.path.getsize(path),
                    "show": show_key,
                    "season": parsed.season,
                    "episode": parsed.episode,
                    "episode_title": name,
                    "meta": meta,
                })

    return {
        "movies": resolve_collisions(separate_quality_copies(movies)),
        "episodes": resolve_collisions(episodes),
        "shows": shows,
        "uncertain_movies": uncertain_movies,
        "uncertain_episodes": uncertain_episodes,
    }


def resolve_collisions(items):
    grouped = {}
    for item in items:
        grouped.setdefault(item["dest"], []).append(item)
    kept = []
    for dest, group in grouped.items():
        group.sort(key=lambda item: item["size"], reverse=True)
        winner = group[0]
        winner["duplicates"] = [item["rel"] for item in group[1:]]
        kept.append(winner)
        for loser in group[1:]:
            print(f"  duplicate kept larger file, skipped {loser['rel']}", flush=True)
    return kept


def same_path(left, right):
    if os.path.abspath(left) == os.path.abspath(right):
        return True
    if os.path.exists(left) and os.path.exists(right):
        try:
            return os.path.samefile(left, right)
        except OSError:
            return False
    return False


def move_file(src, dest):
    if same_path(src, dest):
        return False
    if os.path.exists(dest):
        raise FileExistsError(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    os.rename(src, dest)
    return True


def cleanup_empty_dirs(root):
    protected = {
        os.path.abspath(root),
        os.path.abspath(os.path.join(root, "films")),
        os.path.abspath(os.path.join(root, "anims")),
        os.path.abspath(os.path.join(root, "anims", "films")),
        os.path.abspath(os.path.join(root, "anims", "series")),
        os.path.abspath(os.path.join(root, "series")),
        os.path.abspath(os.path.join(root, "tv")),
        os.path.abspath(os.path.join(root, "sys")),
    }
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) in protected:
            continue
        try:
            entries = os.listdir(dirpath)
        except OSError:
            continue
        real = [entry for entry in entries if not entry.startswith(".")]
        if real:
            continue
        for entry in entries:
            try:
                os.remove(os.path.join(dirpath, entry))
            except OSError:
                pass
        try:
            os.rmdir(dirpath)
        except OSError:
            pass


def apply_plan(root, plan):
    log = []
    for item in plan["movies"] + plan["episodes"]:
        src = item["src"]
        dest = item["dest"]
        if not os.path.exists(src):
            print(f"missing, skipped {src}", flush=True)
            item["moved"] = False
            continue
        try:
            moved = move_file(src, dest)
        except FileExistsError:
            print(f"target exists, skipped {relative(dest, root)}", flush=True)
            item["moved"] = False
            item["blocked"] = True
            continue
        item["moved"] = True
        item["final"] = dest
        if moved:
            log.append({"from": relative(src, root), "to": relative(dest, root)})
            print(f"renamed {relative(src, root)} -> {relative(dest, root)}", flush=True)
        for duplicate in item.get("duplicates") or []:
            duplicate_src = os.path.join(root, duplicate)
            duplicate_dest = os.path.join(root, "doublons", duplicate)
            if not os.path.exists(duplicate_src):
                continue
            try:
                if move_file(duplicate_src, duplicate_dest):
                    log.append({"from": duplicate, "to": relative(duplicate_dest, root), "duplicate": True})
                    print(f"duplicate set aside {duplicate}", flush=True)
            except FileExistsError:
                print(f"duplicate target exists, skipped {duplicate}", flush=True)
        if moved:
            # Re-scan the source folder for sidecars that still use the old stem.
            old_folder = os.path.dirname(src)
            old_stem = os.path.splitext(os.path.basename(src))[0]
            new_stem = os.path.splitext(os.path.basename(dest))[0]
            if os.path.isdir(old_folder):
                for name in list(os.listdir(old_folder)):
                    extension = os.path.splitext(name)[1].lower()
                    if extension not in SIDECAR_EXTENSIONS:
                        continue
                    if name.startswith(old_stem + ".") or name.startswith(old_stem + " "):
                        sidecar_src = os.path.join(old_folder, name)
                        suffix = name[len(old_stem):]
                        sidecar_dest = os.path.join(os.path.dirname(dest), new_stem + suffix)
                        try:
                            if move_file(sidecar_src, sidecar_dest):
                                log.append({
                                    "from": relative(sidecar_src, root),
                                    "to": relative(sidecar_dest, root),
                                })
                        except FileExistsError:
                            print(f"sidecar target exists, skipped {name}", flush=True)
    cleanup_empty_dirs(root)
    return log


def library_document(root, plan, in_place=False):
    movies = {}
    episodes = {}
    shows = {}
    for show_key, meta in plan["shows"].items():
        shows[show_key] = {key: value for key, value in meta.items() if key != "score"}
        shows[show_key]["score"] = meta.get("score")
    for item in plan["movies"]:
        if item.get("blocked"):
            continue
        final_path = item["src"] if in_place else (item.get("final") or item["dest"])
        if not os.path.exists(final_path):
            continue
        movies[relative(final_path, root)] = item["meta"]
    for item in plan["episodes"]:
        if item.get("blocked"):
            continue
        final_path = item["src"] if in_place else (item.get("final") or item["dest"])
        if not os.path.exists(final_path):
            continue
        episodes[relative(final_path, root)] = {
            "show": item["show"],
            "season": item["season"],
            "episode": item["episode"],
            "title": item.get("episode_title") or "",
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "movies": movies,
        "shows": shows,
        "episodes": episodes,
    }


def write_json(path, payload):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def summary_payload(root, plan):
    def movie_row(item):
        return {
            "from": item["rel"],
            "to": relative(item["dest"], root),
            "title": item["meta"]["title"],
            "year": item["meta"]["year"],
            "tmdb_id": item["meta"]["tmdb_id"],
            "score": item["meta"]["score"],
            "duplicates": item.get("duplicates") or [],
        }

    def episode_row(item):
        return {
            "from": item["rel"],
            "to": relative(item["dest"], root),
            "show": item["meta"]["title"],
            "season": item["season"],
            "episode": item["episode"],
            "title": item.get("episode_title") or "",
            "score": item["meta"]["score"],
        }

    movie_rows = [movie_row(item) for item in plan["movies"]]
    episode_rows = [episode_row(item) for item in plan["episodes"]]
    low = [row for row in movie_rows if row["score"] < 0.98]
    return {
        "movies_certain": len(movie_rows),
        "movies_uncertain": len(plan["uncertain_movies"]),
        "episodes_certain": len(episode_rows),
        "episodes_uncertain": len(plan["uncertain_episodes"]),
        "shows": [
            {"path": key, "title": meta["title"], "year": meta.get("year"), "tmdb_id": meta["tmdb_id"], "score": meta.get("score")}
            for key, meta in sorted(plan["shows"].items())
        ],
        "low_score_movies": low,
        "movies": movie_rows,
        "uncertain_movies": plan["uncertain_movies"],
        "uncertain_episodes": plan["uncertain_episodes"],
        "episodes_sample": episode_rows[:30],
    }


def library_has_entries(path):
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("movies") or data.get("episodes"))


def main():
    parser = argparse.ArgumentParser(description="Organize the video library from certain TMDB matches.")
    parser.add_argument("--root", default="/Volumes/3To/videos")
    parser.add_argument("--apply", action="store_true", help="Rename files and write library.json")
    parser.add_argument("--index", action="store_true", help="Write library.json from current paths, without renaming")
    parser.add_argument("--limit", type=int, default=0, help="Max movies to identify, 0 means all")
    parser.add_argument("--only", choices=["all", "movies", "series"], default="all")
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"media root not found: {args.root}", file=sys.stderr)
        return 1

    here = os.path.dirname(os.path.abspath(__file__))
    library_path = os.path.join(here, "library.json")
    client = media_match.TMDBClient(load_api_key(), os.path.join(here, "tmdb_match_cache.json"))
    plan = plan_library(args.root, client, args.only, args.limit)
    client.save()

    report = summary_payload(args.root, plan)
    report_path = os.path.join(here, "organize_plan.json")
    write_json(report_path, report)
    print(
        f"certain movies={report['movies_certain']} uncertain movies={report['movies_uncertain']} "
        f"certain episodes={report['episodes_certain']} uncertain episodes={report['episodes_uncertain']}",
        flush=True,
    )
    print(f"plan written to {report_path}", flush=True)

    if args.index:
        library = library_document(args.root, plan, in_place=True)
        write_json(library_path, library)
        print(
            f"indexed {len(library['movies'])} movies and {len(library['episodes'])} episodes",
            flush=True,
        )
        return 0

    if not args.apply:
        print("dry-run only, no files renamed", flush=True)
        return 0

    if not plan["movies"] and not plan["episodes"] and library_has_entries(library_path):
        print("refusing to replace the existing library with an empty scan", file=sys.stderr)
        return 1

    log = apply_plan(args.root, plan)
    library = library_document(args.root, plan)
    write_json(library_path, library)
    write_json(os.path.join(here, "rename_log.json"), {"moves": log})
    print(f"applied {len(log)} renames, indexed {len(library['movies'])} movies and {len(library['episodes'])} episodes", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
