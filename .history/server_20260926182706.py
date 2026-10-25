import os
import json
import re
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, request, send_file

import media_match

app = Flask(__name__)

# Constants & Paths
CONFIG_FILE = "config.json"
CACHE_FILE = "tmdb_cache.json"

DEFAULT_CONFIG = {
    "tmdb_api_key": "575cb3ac1ab74666f6ddb19b7cd21c19",
    "media_dirs": ["/media/3To/videos"],
    "system_dirs": ["/media/3To/system/lost"],
    "users": {
        "admin": "admin",
        "system": "system",
        "all": "all"
    }
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_CONFIG

config = load_config()
TMDB_API_KEY = config.get("tmdb_api_key", "575cb3ac1ab74666f6ddb19b7cd21c19")
MEDIA_DIRS = config.get("media_dirs", ["/media/3To/videos"])
SYSTEM_DIRS = config.get("system_dirs", ["/media/3To/system/lost"])
USERS = config.get("users", {"admin": "admin", "system": "system", "all": "all"})

EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.m4v', '.m2ts', '.mp3', '.flac']
LIBRARY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.json")
THUMB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)
try:
    # The thumbnail script writes some frames as user xpi.
    os.chmod(THUMB_DIR, 0o777)
except OSError:
    pass
_library_cache = {"mtime": None, "data": None}
_catalog_lock = threading.Lock()
_catalog_cache = {
    "library_mtime": None,
    "built": 0,
    "refreshing": False,
    "videos": None,
    "categories": None,
    "by_id": {},
}
_CATALOG_REFRESH_SECONDS = 60
_duration_cache = {}

# Load TMDB cache
tmdb_cache = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as f:
            tmdb_cache = json.load(f)
    except Exception as e:
        print(f"Error loading cache: {e}")

def save_tmdb_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(tmdb_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")

def clean_query_name(name):
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
    year = year_match.group(1) if year_match else ""

    cleaned = re.sub(r'[\.\-\_]', ' ', name)
    cleaned = re.sub(r'\[.*?\]', '', cleaned)
    cleaned = re.sub(r'\{.*?\}', '', cleaned)
    cleaned = re.sub(r'\(\s*\)', '', cleaned)
    
    if year:
        cleaned = cleaned.replace(f"({year})", "___YEAR_MARKER___")
    
    cleaned = re.sub(r'\(.*?\)', '', cleaned)
    
    if year:
        cleaned = cleaned.replace("___YEAR_MARKER___", f"({year})")
    
    cleaned = re.sub(r'\b(1080p|720p|4K|UHD|HDR|DVDRip|BDRip|BRrip|WEB-DL|HDRip|XviD|AC3|AAC|TRUEFRENCH|MULTi|MULTI|FRENCH|VOSTFR|VF2|VFF|VOST|BluRay|x264|x265|x244|AVC|H264|H265|Half|SBS|3D|PopHD|FR|EN|VFI|EAC3|WEB|EXTENDED|AKS|Ulysse|Max2Power|Sprlove|Qc|France|Vo|By|Gossip25|AM84|iTunes|GHT|BULMA|Bits|TrueHD|Atmos|EXTREME)\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?!1001)\d+\b', '', cleaned)
    cleaned = re.sub(r'\b(ENG|VF|VO)\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*-\s*[A-Za-z0-9_-]+$', '', cleaned)
    cleaned = re.sub(r'[\,\:\!\?\;\"]', ' ', cleaned)
    cleaned = cleaned.replace("'", " ").replace("’", " ")
    
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if year and year not in cleaned:
        cleaned = f"{cleaned} {year}"
        
    return cleaned

def get_genre_category(genre_str):
    if not genre_str:
        return None
    first_genre = genre_str.split(",")[0].strip()
    if first_genre:
        return f"FR | {first_genre}"
    return None

def fetch_tmdb_metadata(name, is_series=False):
    cleaned = clean_query_name(name)
    cache_key = f"{'tv' if is_series else 'movie'}:{cleaned}"
    cached = tmdb_cache.get(cache_key)
    # Empty cache entries are failed lookups from older runs. Do not trust them.
    if cached and cached.get("poster"):
        return cached

    media_type = "tv" if is_series else "movie"
    
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
    year = year_match.group(1) if year_match else ""
    
    base_cleaned = re.sub(r'\b(19\d{2}|20\d{2})\b', '', cleaned).strip()
    queries_to_try = [base_cleaned]
    if " - " in name:
        parts = name.split(" - ")[0]
        p_clean = clean_query_name(parts)
        if p_clean and p_clean not in queries_to_try:
            queries_to_try.append(p_clean)

    metadata = {
        "title": name,
        "poster": "",
        "backdrop": "",
        "overview": "Aucun résumé disponible.",
        "rating": "0",
        "release_date": "",
        "genre": "",
        "cast": "",
        "director": ""
    }

    results = []
    for q in queries_to_try:
        url = f"https://api.themoviedb.org/3/search/{media_type}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(q)}&language=fr-FR"
        if year:
            if is_series:
                url += f"&first_air_date_year={year}"
            else:
                url += f"&year={year}"
        try:
            req = urllib.request.urlopen(url, timeout=5)
            data = json.loads(req.read().decode())
            results = data.get("results", [])
            if results:
                break
            if not results and year:
                url_no_year = f"https://api.themoviedb.org/3/search/{media_type}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(q)}&language=fr-FR"
                req2 = urllib.request.urlopen(url_no_year, timeout=5)
                data2 = json.loads(req2.read().decode())
                results = data2.get("results", [])
                if results:
                    break
        except Exception as e:
            print(f"TMDB Error for {q}: {e}")

    try:
        if results:
            item = results[0]
            if year:
                for res in results:
                    r_date = res.get("release_date") or res.get("first_air_date") or ""
                    if year in r_date:
                        item = res
                        break

            title = item.get("title") or item.get("name") or name
            poster_path = item.get("poster_path")
            backdrop_path = item.get("backdrop_path")
            poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
            backdrop = f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else ""
            overview = item.get("overview") or "Aucun résumé disponible."
            vote_average = str(item.get("vote_average", 0))
            release_date = item.get("release_date") or item.get("first_air_date") or ""

            item_id = item.get("id")
            genre_str = ""
            cast_str = ""
            director_str = ""
            if item_id:
                try:
                    details_url = f"https://api.themoviedb.org/3/{media_type}/{item_id}?api_key={TMDB_API_KEY}&language=fr-FR&append_to_response=credits"
                    d_req = urllib.request.urlopen(details_url, timeout=5)
                    details = json.loads(d_req.read().decode())
                    
                    genres = details.get("genres", [])
                    genre_names = [g.get("name") for g in genres]
                    primary_genre = genre_names[0] if genre_names else "Inconnu"
                    genre_str = f"FR | {primary_genre}"

                    credits = details.get("credits", {})
                    crew = credits.get("crew", [])
                    directors = [cr.get("name") for cr in crew if cr.get("job") == "Director"]
                    director_str = ", ".join(directors)
                    
                    cast = [c.get("name") for c in credits.get("cast", [])[:5]]
                    cast_str = ", ".join(cast)
                    
                    if details.get("overview"):
                        overview = details.get("overview")
                    if details.get("vote_average"):
                        vote_average = str(details.get("vote_average"))
                except Exception as e:
                    print(f"Error fetching details for ID {item_id}: {e}")

            metadata = {
                "id": item_id,
                "title": title,
                "poster": poster,
                "backdrop": backdrop,
                "overview": overview,
                "rating": vote_average,
                "release_date": release_date,
                "genre": genre_str,
                "cast": cast_str,
                "director": director_str
            }
            tmdb_cache[cache_key] = metadata
            save_tmdb_cache()
    except Exception as e:
        print(f"Error processing results for {name}: {e}")

    return metadata

MIME_TYPES = {
    "mp4": "video/mp4",
    "mkv": "video/x-matroska",
    "avi": "video/x-msvideo",
    "mov": "video/quicktime",
    "m4v": "video/x-m4v",
    "m2ts": "video/mp2t",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
}


def container_extension(path):
    """Return the file suffix clients append to the Xtream stream URL."""
    return os.path.splitext(path)[1].lstrip(".").lower() or "mp4"


def numeric_id(text):
    """Stable Xtream integer for a title or episode identity, independent of the path."""
    import hashlib
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def assign_stream_ids(videos):
    """Keep one number per work. A second file of the same work shares it."""
    claimed = {}
    for video in videos:
        identity = video.pop("_identity")
        stream_id = video["stream_id"]
        while stream_id in claimed and claimed[stream_id] != identity:
            stream_id = numeric_id(f"{identity}:{stream_id}")
        claimed[stream_id] = identity
        video["stream_id"] = stream_id
    return videos

def stable_category_id(name):
    import hashlib
    return str(int(hashlib.md5(name.encode("utf-8")).hexdigest()[:6], 16))

def load_library():
    if not os.path.exists(LIBRARY_FILE):
        return {"movies": {}, "shows": {}, "episodes": {}}
    mtime = os.path.getmtime(LIBRARY_FILE)
    if _library_cache["data"] is not None and _library_cache["mtime"] == mtime:
        return _library_cache["data"]
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("movies", {})
    data.setdefault("shows", {})
    data.setdefault("episodes", {})
    _library_cache["mtime"] = mtime
    _library_cache["data"] = data
    return data

def media_key(path, root):
    return os.path.relpath(path, root).replace(os.sep, "/")

def list_videos(directory):
    import glob
    files = []
    if not directory or not os.path.exists(directory):
        return files
    for ext in EXTENSIONS:
        files.extend(glob.glob(os.path.join(directory, "**", f"*{ext}"), recursive=True))
    return [
        path for path in files
        if not os.path.basename(path).startswith(".") and f"{os.sep}doublons{os.sep}" not in path
    ]

def display_movie_name(meta, fallback):
    title = meta.get("title") or fallback
    if meta.get("year"):
        return f"{title} ({meta['year']})"
    return title

def empty_meta():
    return {
        "title": "",
        "poster": "",
        "backdrop": "",
        "overview": "",
        "rating": "0",
        "release_date": "",
        "genre": "",
        "cast": "",
        "director": "",
        "id": 0,
    }

def meta_from_library(record):
    return {
        "id": record.get("tmdb_id") or 0,
        "title": record.get("title") or "",
        "poster": record.get("poster") or "",
        "backdrop": record.get("backdrop") or "",
        "overview": record.get("overview") or "",
        "rating": record.get("rating") or "0",
        "release_date": record.get("release_date") or "",
        "genre": record.get("genre_category") or "",
        "tmdb_genres": [genre for genre in (record.get("genres") or []) if genre],
        "original_title": record.get("original_title") or record.get("title") or "",
        "cast": record.get("cast") or "",
        "director": record.get("director") or "",
        "year": record.get("year") or "",
    }

def file_added_stamp(path):
    """Unix mtime of the file, which stays put across a rename."""
    try:
        st = os.stat(path)
    except OSError:
        return "0"
    birth = getattr(st, "st_birthtime", None)
    stamp = birth if birth else st.st_mtime
    return str(int(stamp))


def _library_mtime():
    try:
        return os.path.getmtime(LIBRARY_FILE)
    except OSError:
        return None


def _store_catalog(videos, categories):
    by_id = {}
    for video in videos:
        by_id.setdefault(video["stream_id"], video)
    _catalog_cache["videos"] = videos
    _catalog_cache["categories"] = categories
    _catalog_cache["by_id"] = by_id
    _catalog_cache["library_mtime"] = _library_mtime()
    _catalog_cache["built"] = time.time()


def _refresh_catalog():
    videos, categories = _build_catalog()
    with _catalog_lock:
        _store_catalog(videos, categories)
        _catalog_cache["refreshing"] = False
    return videos, categories


def _catalog_refresh_loop():
    while True:
        time.sleep(_CATALOG_REFRESH_SECONDS)
        try:
            _refresh_catalog()
        except Exception as exc:
            print(f"Catalog refresh failed: {exc}")
            with _catalog_lock:
                _catalog_cache["refreshing"] = False


def get_categorized_videos():
    """Return the in-memory catalog. A stale catalog refreshes in the background."""
    library_mtime = _library_mtime()
    with _catalog_lock:
        videos = _catalog_cache["videos"]
        if videos is not None:
            stale = (
                _catalog_cache["library_mtime"] != library_mtime
                or time.time() - _catalog_cache["built"] > _CATALOG_REFRESH_SECONDS
            )
            if stale and not _catalog_cache["refreshing"]:
                _catalog_cache["refreshing"] = True
                threading.Thread(target=_refresh_catalog, daemon=True).start()
            return videos, _catalog_cache["categories"]
    return _refresh_catalog()


def _build_catalog():
    std_dir = MEDIA_DIRS[0] if MEDIA_DIRS else ""
    sys_dir = SYSTEM_DIRS[0] if SYSTEM_DIRS else ""
    library = load_library()
    all_files = list_videos(std_dir) + list_videos(sys_dir)

    videos = []
    categories = {}

    for fpath in all_files:
        filename = os.path.basename(fpath)
        name, _ = os.path.splitext(filename)
        kind = "movie"
        meta = empty_meta()
        series_id = ""
        season = None
        episode_num = None
        episode_title = ""
        cat_name = "Divers & Vidéos"
        tmdb_stream = None
        identity = None

        if sys_dir and fpath.startswith(sys_dir):
            kind = "system"
            rel = os.path.relpath(fpath, sys_dir)
            parts = rel.split(os.sep)
            # Top-level folder is the category. No TMDB lookup for this library.
            if len(parts) > 1:
                cat_name = parts[0]
                name = " - ".join(parts[1:-1] + [name])
            else:
                cat_name = "Non classé"
            identity = "system:" + rel.replace(os.sep, "/")
        elif std_dir and fpath.startswith(std_dir):
            rel = media_key(fpath, std_dir)
            parts = rel.split("/")
            episode = library["episodes"].get(rel)
            movie = library["movies"].get(rel)
            is_series = any(part.lower() in ["series", "série", "séries"] for part in parts)

            if episode:
                kind = "episode"
                show = library["shows"].get(episode.get("show"), {})
                show_title = show.get("title") or "Series"
                season = int(episode.get("season") or 1)
                episode_num = int(episode.get("episode") or 0)
                episode_title = episode.get("title") or ""
                name = f"{show_title} - S{season:02d}E{episode_num:02d}"
                if episode_title:
                    name += f" - {episode_title}"
                cat_name = f"FR | Séries - {show_title}"
                series_id = str(show.get("tmdb_id") or stable_category_id(show_title))
                meta = meta_from_library(show)
                show_key = str(show.get("tmdb_id")) if show.get("tmdb_id") else media_match.canon(show_title)
                identity = f"episode:{show_key}:{season}:{episode_num}"
            elif movie:
                kind = "movie"
                meta = meta_from_library(movie)
                name = display_movie_name(movie, name)
                cat_name = movie.get("genre_category") or "FR | Films"
                if meta.get("id"):
                    tmdb_stream = int(meta["id"])
                    identity = f"tmdb:{tmdb_stream}"
                else:
                    identity = "title:" + media_match.canon(name)
            elif is_series:
                kind = "episode"
                series_idx = next(
                    (idx for idx, part in enumerate(parts) if part.lower() in ["series", "série", "séries"]),
                    -1,
                )
                if series_idx != -1 and len(parts) > series_idx + 1:
                    show_name = parts[series_idx + 1]
                else:
                    show_name = parts[-2] if len(parts) > 1 else "Series"
                parsed = media_match.parse_media_name(filename)
                season = parsed.season
                episode_num = parsed.episode
                cat_name = f"FR | Séries - {show_name}"
                series_id = stable_category_id(show_name)
                show_key = media_match.canon(show_name)
                if season and episode_num:
                    name = f"{show_name} - S{season:02d}E{episode_num:02d}"
                    identity = f"episode:{show_key}:{season}:{episode_num}"
                else:
                    identity = "title:" + media_match.canon(media_match.parse_media_name(filename).title or name)
            else:
                kind = "movie"
                cat_name = "FR | Inconnu"
                parsed = media_match.parse_media_name(filename)
                label = parsed.title or name
                if parsed.year:
                    label = f"{label} ({parsed.year})"
                identity = "title:" + media_match.canon(label)

        if cat_name not in categories:
            categories[cat_name] = []

        if tmdb_stream:
            stream_id = tmdb_stream
            identity = f"tmdb:{tmdb_stream}"
        else:
            stream_id = numeric_id(identity or ("title:" + media_match.canon(name)))
            identity = identity or ("title:" + media_match.canon(name))

        stream_info = {
            "stream_id": stream_id,
            "_identity": identity,
            "name": name,
            "path": fpath,
            "added": file_added_stamp(fpath),
            "container_extension": container_extension(fpath),
            "category_name": cat_name,
            "category_id": stable_category_id(cat_name),
            "kind": kind,
            "meta": meta,
            "series_id": series_id,
            "season": season,
            "episode_num": episode_num,
            "episode_title": episode_title,
        }
        categories[cat_name].append(stream_info)
        videos.append(stream_info)

    return assign_stream_ids(videos), categories

def filter_videos_for_user(videos, username, password):
    if username == "system":
        return [v for v in videos if "/system/lost" in v["path"]]
    elif username == "admin":
        return [v for v in videos if "/system/lost" not in v["path"]]
    return videos

@app.route("/")
def index():
    return "Xtream IPTV Flask Server is running."

@app.route("/get.php")
def get_php():
    username = request.args.get("username")
    password = request.args.get("password")
    ptype = request.args.get("type")
    
    if username not in USERS or USERS[username] != password:
        return jsonify({"error": "Unauthorized"}), 401
        
    videos, _ = get_categorized_videos()
    user_videos = filter_videos_for_user(videos, username, password)
    
    if ptype == "media":
        user_videos = [v for v in user_videos if "/system/lost" not in v["path"]]
    elif ptype == "system":
        user_videos = [v for v in user_videos if "/system/lost" in v["path"]]
        
    m3u = "#EXTM3U\n"
    for v in user_videos:
        m3u += f'#EXTINF:-1 tvg-id="" tvg-name="{v["name"]}" group-title="{v["category_name"]}",{v["name"]}\n'
        m3u += f"http://{request.host}/movie/{username}/{password}/{v['stream_id']}.{v['container_extension']}\n"
    return m3u, 200, {"Content-Type": "audio/x-mpegurl"}

@app.route("/player_api.php")
def player_api():
    username = request.args.get("username")
    password = request.args.get("password")
    action = request.args.get("action")
    
    if username not in USERS or USERS[username] != password:
        return jsonify({"user_info": {"auth": 0}, "categories": []}), 401

    if not action:
        return jsonify(xtream_auth_payload(username))

    videos, _ = get_categorized_videos()
    user_videos = filter_videos_for_user(videos, username, password)
        
    if action == "get_vod_categories" or action == "get_live_categories":
        # System folders are films only. Live keeps the other non-episode rows.
        allowed = {"movie", "system"} if action == "get_vod_categories" else {"movie"}
        cats = {}
        for video in user_videos:
            if video["kind"] not in allowed:
                continue
            cats[video["category_name"]] = video["category_id"]
        return jsonify([
            {"category_id": cid, "category_name": name, "parent_id": 0}
            for name, cid in sorted(cats.items())
        ])

    elif action == "get_series_categories":
        cats = {}
        for video in user_videos:
            if video["kind"] != "episode":
                continue
            cats[video["category_name"]] = video["category_id"]
        return jsonify([
            {"category_id": cid, "category_name": name, "parent_id": 0}
            for name, cid in sorted(cats.items())
        ])

    elif action == "get_vod_streams":
        cat_filter = request.args.get("category_id")
        streams = []
        for video in user_videos:
            if video["kind"] == "episode":
                continue
            if cat_filter and video["category_id"] != cat_filter:
                continue
            streams.append(vod_stream_item(video, len(streams) + 1))
        return jsonify(streams)

    elif action == "get_live_streams":
        cat_filter = request.args.get("category_id")
        streams = []
        for video in user_videos:
            if video["kind"] != "movie":
                continue
            if cat_filter and video["category_id"] != cat_filter:
                continue
            meta = video["meta"]
            try:
                rating_5based = float(meta.get("rating") or 0) / 2.0
            except (TypeError, ValueError):
                rating_5based = 0.0
            streams.append({
                "num": video["stream_id"],
                "name": video["name"],
                "stream_type": "movie",
                "stream_id": video["stream_id"],
                "stream_icon": meta.get("poster", ""),
                "rating": meta.get("rating", "0"),
                "rating_5based": rating_5based,
                "added": video.get("added") or "0",
                "category_name": video["category_name"],
                "category_id": video["category_id"],
                "container_extension": video["container_extension"],
                "custom_sid": "",
                "direct_source": ""
            })
        return jsonify(streams)

    elif action == "get_vod_info":
        vod_id = request.args.get("vod_id")
        target = None
        for video in user_videos:
            if str(video["stream_id"]) == str(vod_id):
                target = video
                break
        if not target:
            return jsonify({"error": "VOD not found"}), 404

        return jsonify(vod_info_payload(target))

    elif action == "get_series":
        series_list = []
        seen = set()
        for video in user_videos:
            if video["kind"] != "episode" or video["series_id"] in seen:
                continue
            seen.add(video["series_id"])
            meta = video["meta"]
            series_name = video["category_name"].replace("FR | Séries - ", "")
            series_list.append({
                "series_id": video["series_id"],
                "name": series_name,
                "title": meta.get("title") or series_name,
                "cover": meta.get("poster", ""),
                "plot": meta.get("overview", ""),
                "cast": meta.get("cast", ""),
                "director": meta.get("director", ""),
                "genre": meta.get("genre", ""),
                "releaseDate": meta.get("release_date", ""),
                "rating": meta.get("rating", "0"),
                "category_id": video["category_id"]
            })
        return jsonify(series_list)

    elif action == "get_series_info":
        series_id = request.args.get("series_id")
        episodes = [video for video in user_videos if video["kind"] == "episode" and video["series_id"] == series_id]
        if not episodes:
            return jsonify({"error": "Series not found"}), 404

        meta = episodes[0]["meta"]
        series_name = episodes[0]["category_name"].replace("FR | Séries - ", "")
        episodes_by_season = {}
        for video in episodes:
            season = int(video["season"] or 1)
            number = int(video["episode_num"] or 0)
            bucket = episodes_by_season.setdefault(str(season), [])
            bucket.append((number, video))

        payload = {}
        seasons = []
        for season in sorted(int(key) for key in episodes_by_season):
            rows = sorted(episodes_by_season[str(season)], key=lambda item: (item[0] == 0, item[0]))
            seasons.append({"season_number": season, "name": f"Saison {season}"})
            payload[str(season)] = []
            for index, (number, video) in enumerate(rows, start=1):
                payload[str(season)].append({
                    "id": str(video["stream_id"]),
                    "episode_num": number or index,
                    "title": video["episode_title"] or video["name"],
                    "container_extension": video["container_extension"],
                    "info": {
                        "plot": meta.get("overview", ""),
                        "movie_image": meta.get("poster", ""),
                    },
                    "season": season,
                })

        return jsonify({
            "seasons": seasons,
            "episodes": payload,
            "info": {
                "name": meta.get("title") or series_name,
                "cover": meta.get("poster", ""),
                "plot": meta.get("overview", ""),
                "cast": meta.get("cast", ""),
                "director": meta.get("director", ""),
                "genre": meta.get("genre", ""),
                "rating": meta.get("rating", "0"),
                "tmdb_id": meta.get("id", 0),
            }
        })
        
    return jsonify({"error": "Unknown action"}), 400

def serve_stream(username, password, stream_id, extension):
    """Send the media file for a numeric Xtream stream id.

    The id selects the file. Some clients keep requesting .mp4 even when
    container_extension says mkv, so a mismatched suffix still returns the file.
    """
    if username not in USERS or USERS[username] != password:
        return "Unauthorized", 401
    get_categorized_videos()
    with _catalog_lock:
        video = _catalog_cache["by_id"].get(stream_id)
    if not video:
        return "Not Found", 404
    mime = MIME_TYPES.get(video["container_extension"], "application/octet-stream")
    return send_file(video["path"], conditional=True, mimetype=mime)


@app.route("/movie/<username>/<password>/<int:stream_id>.<extension>")
@app.route("/series/<username>/<password>/<int:stream_id>.<extension>")
def serve_movie(username, password, stream_id, extension):
    return serve_stream(username, password, stream_id, extension)

def xtream_auth_payload(username):
    now = time.time()
    local = datetime.now(ZoneInfo("Europe/Paris"))
    host = (request.host or "").split(":")[0]
    port = str(request.environ.get("SERVER_PORT") or "5000")
    return {
        "user_info": {
            "username": username,
            "password": USERS.get(username, ""),
            "auth": 1,
            "status": "Active",
            "exp_date": "1893452400",
            "is_trial": "0",
            "active_cons": "1",
            "created_at": "1700000000",
            "max_connections": "10",
            "allowed_output_formats": ["m3u8", "ts", "rtmp"],
        },
        "server_info": {
            "url": host,
            "port": port,
            "server_protocol": "http",
            "timezone": "Europe/Paris",
            "timestamp_now": int(now),
            "time_now": local.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }


def thumb_url(stream_id):
    """Absolute URL of a generated frame, when that file exists."""
    name = f"{stream_id}.jpg"
    path = os.path.join(THUMB_DIR, name)
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        return ""
    return f"http://{request.host}/thumbs/{name}"


@app.route("/thumbs/<stream_id>.jpg")
def serve_thumb(stream_id):
    path = os.path.join(THUMB_DIR, f"{stream_id}.jpg")
    if not os.path.isfile(path):
        return "Not Found", 404
    return send_file(path, mimetype="image/jpeg", conditional=True)


def vod_stream_item(video, number):
    meta = video["meta"]
    try:
        rating_5based = round(float(meta.get("rating") or 0) / 2.0, 1)
    except (TypeError, ValueError):
        rating_5based = 0.0
    item = {
        "num": number,
        "name": video["name"],
        "stream_type": "movie",
        "stream_id": video["stream_id"],
        "id": video["stream_id"],
        "stream_icon": meta.get("poster") or thumb_url(video["stream_id"]),
        "rating": str(meta.get("rating") or "0"),
        "rating_5based": rating_5based,
        "added": video.get("added") or "0",
        "category_id": video["category_id"],
        "container_extension": video["container_extension"],
        "custom_sid": "",
        "direct_source": "",
    }
    tmdb_id = meta.get("id") or 0
    if tmdb_id:
        item["tmdb"] = int(tmdb_id)
    return item


def format_duration(seconds):
    whole = int(round(seconds))
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def duration_secs(path):
    try:
        stamp = (os.path.getmtime(path), os.path.getsize(path))
    except OSError:
        return None
    key = (path, stamp)
    if key in _duration_cache:
        return _duration_cache[key]
    value = None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        value = float((result.stdout or "").strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        value = None
    _duration_cache[key] = value
    return value


def vod_info_payload(video):
    meta = video["meta"]
    tmdb_id = meta.get("id") or 0
    poster = meta.get("poster") or thumb_url(video["stream_id"])
    backdrop = meta.get("backdrop") or ""
    plot = meta.get("overview") or ""
    cast = meta.get("cast") or ""
    seconds = duration_secs(video["path"])
    info = {
        "name": video["name"],
        "o_name": meta.get("original_title") or meta.get("title") or video["name"],
        "cover_big": poster,
        "movie_image": poster,
        "releasedate": meta.get("release_date") or "",
        "youtube_trailer": "",
        "director": meta.get("director") or "",
        "actors": cast,
        "cast": cast,
        "description": plot,
        "plot": plot,
        "genre": ", ".join(meta.get("tmdb_genres") or []),
        "backdrop_path": [backdrop] if backdrop else [],
        "rating": str(meta.get("rating") or "0"),
    }
    if tmdb_id:
        info["tmdb_id"] = int(tmdb_id)
    if seconds:
        info["duration_secs"] = int(round(seconds))
        info["duration"] = format_duration(seconds)
    return {
        "info": info,
        "movie_data": {
            "stream_id": video["stream_id"],
            "id": video["stream_id"],
            "name": video["name"],
            "added": video.get("added") or "0",
            "category_id": video["category_id"],
            "container_extension": video["container_extension"],
            "custom_sid": "",
            "direct_source": "",
        },
    }


if __name__ == "__main__":
    print(f"Server starting with media dirs: {MEDIA_DIRS}")
    try:
        _refresh_catalog()
    except Exception as exc:
        print(f"Initial catalog build failed: {exc}")
    threading.Thread(target=_catalog_refresh_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
