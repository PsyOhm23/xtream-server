import os
import json
import re
import unicodedata
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, request, send_file

import media_detail
import media_match

app = Flask(__name__)

# Constants & Paths
CONFIG_FILE = "config.json"
CACHE_FILE = "tmdb_cache.json"

DEFAULT_CONFIG = {
    "tmdb_api_key": "",
    "media_dirs": ["./media/videos"],
    "system_dirs": ["./media/system"],
    "users": {
        "admin": "admin",
        "system": "system",
        "all": "all",
        "demo": "demo"
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
TMDB_API_KEY = config.get("tmdb_api_key", "")
MEDIA_DIRS = config.get("media_dirs", ["/media/3To/videos"])
SYSTEM_DIRS = config.get("system_dirs", ["/media/3To/system/lost"])
USERS = config.get("users", {"admin": "admin", "system": "system", "all": "all", "demo": "demo"})

EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.m4v', '.m2ts', '.mp3', '.flac']
LIBRARY_FILES = config.get("library_files", {
    "admin": "library.json",
    "system": "library.json",
    "all": "library.json",
    "demo": "library_demo.json"
})
THUMB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)
try:
    # The thumbnail script writes some frames as user xpi.
    os.chmod(THUMB_DIR, 0o777)
except OSError:
    pass
_library_cache = {}
_catalog_lock = threading.Lock()
_catalog_cache = {
    "library_mtime": None,
    "built": 0,
    "refreshing": False,
    "videos": None,
    "categories": None,
    "by_id": {},
}
_duration_cache = {}
_scrape_lock = threading.Lock()
_scrape_failed = set()
_tmdb_client = None

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
    names = [part.strip() for part in genre_str.split(",") if part.strip()]
    chosen = media_match.primary_genre(names)
    if chosen:
        return f"FR | {chosen}"
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
                    genre_names = [g.get("name") for g in genres if g.get("name")]
                    primary = media_match.primary_genre(genre_names) or "Inconnu"
                    genre_str = f"FR | {primary}"

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

def stable_category_id(name, kind=None):
    """Stable category number. Kind keeps the same label unique per section."""
    import hashlib
    token = f"{kind}:{name}" if kind else name
    return str(int(hashlib.md5(token.encode("utf-8")).hexdigest()[:6], 16))

def load_library(username=None):
    filename = LIBRARY_FILES.get(username, "library.json") if username else "library.json"
    lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(lib_path):
        # Fallback to main library.json if specific one missing
        lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.json")
    if not os.path.exists(lib_path):
        return {"movies": {}, "shows": {}, "episodes": {}}
    mtime = os.path.getmtime(lib_path)
    cache_key = f"{username}_{lib_path}"
    if _library_cache.get(cache_key) is not None and _library_cache.get(f"{cache_key}_mtime") == mtime:
        return _library_cache[cache_key]
    try:
        with open(lib_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("movies", {})
    data.setdefault("shows", {})
    data.setdefault("episodes", {})
    _library_cache[f"{cache_key}_mtime"] = mtime
    _library_cache[cache_key] = data
    return data

def media_key(path, root):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return unicodedata.normalize("NFC", rel)

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


def movie_lookup(library):
    """Index library movies by folded title and year so a new file can join an existing film."""
    found = {}
    for record in (library.get("movies") or {}).values():
        try:
            year = int(record.get("year"))
        except (TypeError, ValueError):
            continue
        for raw in (record.get("title"), record.get("french_title"), record.get("original_title")):
            folded = media_match.canon(raw or "")
            if len(folded.replace(" ", "")) < 4:
                continue
            key = (folded, year)
            if key not in found:
                found[key] = record
            elif found[key] is not record:
                found[key] = None
    return found


def movie_record_for_name(lookup, filename):
    """Return the library movie a loose filename already belongs to."""
    parsed = media_match.parse_media_name(filename)
    if not parsed.year:
        return None
    hits = []
    for raw in [parsed.title, *list(parsed.alts)]:
        folded = media_match.canon(raw or "")
        if len(folded.replace(" ", "")) < 4:
            continue
        record = lookup.get((folded, int(parsed.year)))
        if record and all(record is not item for item in hits):
            hits.append(record)
    if len(hits) == 1:
        return hits[0]
    return None


def _file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


_QUALITY_RANK = {
    "2160p": 2160,
    "4k": 2160,
    "uhd": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "576p": 576,
    "480p": 480,
}


def _filename_quality(path):
    name = os.path.basename(path)
    match = re.search(r"(?i)\b(2160p|1080p|720p|576p|480p|4k|uhd)\b", name)
    if not match:
        return ""
    token = match.group(1).lower()
    if token in {"4k", "uhd"}:
        return "4K"
    return token


def copy_quality_rank(path):
    """Higher means a better picture. A probed file outranks its filename."""
    detail = media_detail.load_detail(path)
    if detail:
        video = detail.get("video") or {}
        quality = media_detail.quality_from_dimensions(video.get("width"), video.get("height")).lower()
        if quality in _QUALITY_RANK:
            return _QUALITY_RANK[quality]
    token = _filename_quality(path).lower()
    if token in _QUALITY_RANK:
        return _QUALITY_RANK[token]
    return 0


def copy_label(path):
    """Short label that tells two files of the same film apart."""
    detail = media_detail.load_detail(path)
    if detail:
        video = detail.get("video") or {}
        quality = media_detail.quality_from_dimensions(video.get("width"), video.get("height"))
        if quality:
            return quality
    filename_quality = _filename_quality(path)
    if filename_quality:
        return filename_quality
    size = _file_size(path)
    if size < 0:
        return ""
    if size >= 1024 ** 3:
        return f"{size / (1024 ** 3):.1f} GB"
    return f"{max(1, round(size / (1024 ** 2)))} MB"


def _bitrate_label(path, quality):
    """Disambiguate two copies that share a quality label, using the probed bitrate."""
    if not quality:
        return ""
    detail = media_detail.load_detail(path)
    bitrate = (detail or {}).get("bitrate") or 0
    if bitrate < 1000:
        return ""
    return f"{quality} {round(bitrate / 1000)} Mbps"


def expose_each_copy(videos):
    """Keep every file of the same work playable, with its own stream id."""
    groups = {}
    order = []
    for video in videos:
        identity = video.get("_identity")
        if identity not in groups:
            groups[identity] = []
            order.append(identity)
        groups[identity].append(video)
    exposed = []
    for identity in order:
        group = groups[identity]
        if len(group) == 1:
            group[0].pop("_indexed", None)
            exposed.append(group[0])
            continue
        labels = [copy_label(video["path"]) for video in group]
        if len(set(labels)) != len(group):
            richer = [_bitrate_label(video["path"], labels[index]) for index, video in enumerate(group)]
            if len(set(richer)) == len(group) and all(richer):
                labels = richer
            else:
                labels = []
                for video in group:
                    size = _file_size(video["path"])
                    if size >= 1024 ** 3:
                        labels.append(f"{size / (1024 ** 3):.1f} GB")
                    elif size >= 0:
                        labels.append(f"{max(1, round(size / (1024 ** 2)))} MB")
                    else:
                        labels.append("")
        primary = max(
            range(len(group)),
            key=lambda index: (copy_quality_rank(group[index]["path"]), _file_size(group[index]["path"])),
        )
        for index, video in enumerate(group):
            video.pop("_indexed", None)
            label = labels[index]
            if label:
                video["name"] = f"{video['name']} [{label}]"
            if index != primary:
                video["_identity"] = f"{identity}:{video['path']}"
                video["stream_id"] = numeric_id(video["_identity"])
            exposed.append(video)
    return exposed

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


def _library_mtime(username=None):
    filename = LIBRARY_FILES.get(username, "library.json") if username else "library.json"
    lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(lib_path):
        lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.json")
    try:
        return os.path.getmtime(lib_path)
    except OSError:
        return None


def movie_category_name(record):
    chosen = media_match.primary_genre(record.get("genres") or [])
    if chosen:
        return f"FR | {chosen}"
    return record.get("genre_category") or "FR | Films"


def show_category_name(record):
    """Genre category for series, same mechanics as VOD, separate fallback."""
    chosen = media_match.primary_genre(record.get("genres") or [])
    if chosen:
        return f"FR | {chosen}"
    return record.get("genre_category") or "FR | Séries"


def _directory_stamp():
    """Mtimes of media directories. A new file updates its parent folder."""
    stamps = []
    roots = []
    if MEDIA_DIRS:
        roots.append(MEDIA_DIRS[0])
    if SYSTEM_DIRS:
        roots.append(SYSTEM_DIRS[0])
    for root in roots:
        if not root or not os.path.isdir(root):
            stamps.append((root, None))
            continue
        for dirpath, dirnames, _filenames in os.walk(root):
            dirnames[:] = [
                name for name in dirnames
                if not name.startswith(".") and name != "doublons"
            ]
            try:
                stamps.append((dirpath, os.stat(dirpath).st_mtime_ns))
            except OSError:
                continue
    return tuple(stamps)


def _store_catalog(videos, categories, tree_stamp, username=None):
    by_id = {}
    for video in videos:
        by_id.setdefault(video["stream_id"], video)
    key = username or "default"
    _catalog_cache[f"videos_{key}"] = videos
    _catalog_cache[f"categories_{key}"] = categories
    _catalog_cache[f"by_id_{key}"] = by_id
    _catalog_cache[f"library_mtime_{key}"] = _library_mtime(username)
    _catalog_cache[f"tree_stamp_{key}"] = tree_stamp
    _catalog_cache[f"built_{key}"] = time.time()


def _refresh_catalog(username=None):
    tree_stamp = _directory_stamp()
    videos, categories = _build_catalog(username)
    with _catalog_lock:
        _store_catalog(videos, categories, tree_stamp, username)
    return videos, categories


def get_categorized_videos(ensure_fresh=False, username=None):
    """Return the catalog. App refreshes rebuild it when a folder or the library changed."""
    key = username or "default"
    with _catalog_lock:
        videos = _catalog_cache.get(f"videos_{key}")
        if videos is not None and not ensure_fresh:
            return videos, _catalog_cache.get(f"categories_{key}")
    if not ensure_fresh:
        return _refresh_catalog(username)
    library_mtime = _library_mtime(username)
    tree_stamp = _directory_stamp()
    with _catalog_lock:
        videos = _catalog_cache.get(f"videos_{key}")
        if (
            videos is not None
            and _catalog_cache.get(f"library_mtime_{key}") == library_mtime
            and _catalog_cache.get(f"tree_stamp_{key}") == tree_stamp
        ):
            return videos, _catalog_cache.get(f"categories_{key}")
    return _refresh_catalog(username)


def _build_catalog(username=None):
    library = load_library(username)
    videos = []

    if username == "demo":
        # Build catalog directly from demo library structure
        for path, movie in library.get("movies", {}).items():
            meta = meta_from_library(movie)
            name = display_movie_name(movie, movie.get("title", "Demo"))
            cat_name = movie_category_name(movie)
            stream_id = numeric_id(path)
            videos.append({
                "stream_id": stream_id,
                "_identity": f"demo:{path}",
                "name": name,
                "title": name,
                "category_name": cat_name,
                "category_id": stable_category_id("movie", cat_name),
                "kind": "movie",
                "container_extension": "mp4",
                "path": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
                "direct_source": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
                "meta": meta,
                "series_id": "",
                "season": None,
                "episode": None,
            })
        for show_key, show in library.get("shows", {}).items():
            show_title = show.get("title", "Demo Series")
            cat_name = show_category_name(show)
            meta = meta_from_library(show)
            series_id = str(show.get("tmdb_id") or stable_category_id(show_title))
            for rel, ep in library.get("episodes", {}).items():
                if ep.get("show") != show_key:
                    continue
                season = int(ep.get("season") or 1)
                episode_num = int(ep.get("episode") or 1)
                ep_title = ep.get("title") or f"Episode {episode_num}"
                name = f"{show_title} - S{season:02d}E{episode_num:02d} - {ep_title}"
                stream_id = numeric_id(rel)
                videos.append({
                    "stream_id": stream_id,
                    "_identity": f"demo:{rel}",
                    "name": name,
                    "title": name,
                    "category_name": cat_name,
                    "category_id": stable_category_id("show", cat_name),
                    "kind": "episode",
                    "container_extension": "mp4",
                    "path": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
                    "direct_source": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
                    "meta": meta,
                    "series_id": series_id,
                    "season": season,
                    "episode": episode_num,
                })
        categories = {}
        for video in videos:
            categories.setdefault(video["category_name"], []).append(video)
        return assign_stream_ids(videos), categories

    std_dir = MEDIA_DIRS[0] if MEDIA_DIRS else ""

    videos = expose_each_copy(videos)
    categories = {}
    for video in videos:
        categories.setdefault(video["category_name"], []).append(video)
    return assign_stream_ids(videos), categories

def filter_videos_for_user(videos, username, password):
    if username == "system":
        return [v for v in videos if "/system/lost" in v["path"]]
    elif username == "admin":
        return [v for v in videos if "/system/lost" not in v["path"]]
    elif username == "demo":
        return videos
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
        
    videos, _ = get_categorized_videos(ensure_fresh=True, username=username)
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

    if action == "get_live_categories" or action == "get_live_streams":
        # Movies and system files are VOD. This server has no live channels.
        return jsonify([])

    videos, _ = get_categorized_videos(ensure_fresh=True, username=username)
    user_videos = filter_videos_for_user(videos, username, password)

    if action == "get_vod_categories":
        cats = {}
        for video in user_videos:
            if video["kind"] == "episode":
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

    elif action == "get_vod_info":
        vod_id = request.args.get("vod_id")
        target = None
        for video in user_videos:
            if str(video["stream_id"]) == str(vod_id):
                target = video
                break
        if not target:
            return jsonify({"error": "VOD not found"}), 404

        scrape_unknown_movie(target)
        return jsonify(vod_info_payload(target))

    elif action == "get_series":
        cat_filter = request.args.get("category_id")
        series_list = []
        seen = set()
        for video in user_videos:
            if video["kind"] != "episode" or video["series_id"] in seen:
                continue
            if cat_filter and video["category_id"] != cat_filter:
                continue
            seen.add(video["series_id"])
            series_list.append(series_list_item(video, len(series_list) + 1))
        return jsonify(series_list)

    elif action == "get_series_info":
        series_id = request.args.get("series_id")
        episodes = [
            video for video in user_videos
            if video["kind"] == "episode" and str(video["series_id"]) == str(series_id)
        ]
        if not episodes:
            return jsonify({"error": "Series not found"}), 404
        return jsonify(series_info_payload(episodes))
        
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


def _thumb_path(name):
    if not re.fullmatch(r"\d+(?:_backdrop)?", name):
        return None
    path = os.path.join(THUMB_DIR, f"{name}.jpg")
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        return None
    return path


def thumb_url(stream_id):
    """Absolute URL of the small generated poster, when that file exists."""
    if not _thumb_path(str(stream_id)):
        return ""
    return f"http://{request.host}/thumbs/{stream_id}.jpg"


def backdrop_url(stream_id):
    """Absolute URL of the full-size generated backdrop, when that file exists."""
    name = f"{stream_id}_backdrop"
    if not _thumb_path(name):
        return ""
    return f"http://{request.host}/thumbs/{name}.jpg"


@app.route("/thumbs/<stream_id>.jpg")
@app.route("/thumbs/<stream_id>_backdrop.jpg")
def serve_thumb(stream_id):
    name = str(stream_id)
    if request.path.endswith("_backdrop.jpg") and not name.endswith("_backdrop"):
        name = f"{name}_backdrop"
    path = _thumb_path(name)
    if not path:
        return "Not Found", 404
    return send_file(path, mimetype="image/jpeg", conditional=True)


def rating_5based(value):
    try:
        return round(float(value or 0) / 2.0, 1)
    except (TypeError, ValueError):
        return 0.0


def series_genre_text(meta, separator=" / "):
    genres = [genre for genre in (meta.get("tmdb_genres") or []) if genre]
    if genres:
        return separator.join(genres)
    genre = meta.get("genre") or ""
    if genre.startswith("FR | "):
        return genre[5:]
    return genre


def tmdb_cover_path(url):
    """Relative TMDB image path when the URL is a TMDB CDN link."""
    if not url:
        return ""
    marker = "/t/p/"
    if marker not in url:
        return ""
    tail = url.split(marker, 1)[1]
    slash = tail.find("/")
    if slash < 0:
        return ""
    return tail[slash:]


def category_ids_for(category_id):
    try:
        return [int(category_id)]
    except (TypeError, ValueError):
        return [category_id]


def episode_xtream_info(video, meta):
    """Episode info block for get_series_info, with sidecar tech details when present."""
    poster = meta.get("poster") or ""
    tmdb_id = meta.get("id") or 0
    try:
        rating_value = float(meta.get("rating") or 0)
    except (TypeError, ValueError):
        rating_value = 0.0
    info = {
        "air_date": meta.get("release_date") or "",
        "crew": meta.get("director") or "",
        "rating": rating_value,
        "movie_image": poster,
        "plot": meta.get("overview") or "",
    }
    if tmdb_id:
        info["id"] = int(tmdb_id)
    detail = media_detail.load_detail(video["path"])
    if detail:
        video_info = media_detail.xtream_video(detail)
        audio_info = media_detail.xtream_audio(detail)
        if video_info:
            info["video"] = video_info
        if audio_info:
            info["audio"] = audio_info
        if detail.get("bitrate"):
            info["bitrate"] = int(detail["bitrate"])
        seconds = detail.get("duration_secs")
        if seconds:
            info["duration_secs"] = int(round(seconds))
            info["duration"] = detail.get("duration") or format_duration(seconds)
    return info


def series_info_payload(episodes):
    """Full get_series_info document, shaped like common Xtream providers."""
    meta = episodes[0]["meta"]
    series_name = meta.get("title") or "Series"
    release = meta.get("release_date") or ""
    poster = meta.get("poster") or ""
    backdrop = meta.get("backdrop") or ""
    tmdb_id = meta.get("id") or 0
    category_id = episodes[0]["category_id"]
    last_modified = max((video.get("added") or "0") for video in episodes)
    cover_tmdb = tmdb_cover_path(poster)

    episodes_by_season = {}
    for video in episodes:
        season = int(video["season"] or 1)
        number = int(video["episode_num"] or 0)
        episodes_by_season.setdefault(str(season), []).append((number, video))

    run_minutes = 0
    seasons = []
    payload = {}
    for season in sorted(int(key) for key in episodes_by_season):
        rows = sorted(episodes_by_season[str(season)], key=lambda item: (item[0] == 0, item[0]))
        seasons.append({
            "name": f"Saison {season}",
            "episode_count": str(len(rows)),
            "overview": meta.get("overview") or "",
            "air_date": release,
            "cover": poster,
            "cover_tmdb": cover_tmdb,
            "season_number": season,
            "cover_big": poster,
            "releaseDate": release,
            "duration": "0",
        })
        payload[str(season)] = []
        for index, (number, video) in enumerate(rows, start=1):
            ep_info = episode_xtream_info(video, meta)
            if not run_minutes and ep_info.get("duration_secs"):
                run_minutes = max(1, int(round(ep_info["duration_secs"] / 60.0)))
            title = video["episode_title"] or video["name"]
            if not video["episode_title"]:
                ep_num = number or index
                title = f"{series_name} - S{season:02d}E{ep_num:02d}"
            payload[str(season)].append({
                "id": str(video["stream_id"]),
                "episode_num": number or index,
                "title": title,
                "container_extension": video["container_extension"],
                "info": ep_info,
                "custom_sid": "",
                "added": video.get("added") or "0",
                "season": season,
                "direct_source": "",
            })

    if run_minutes:
        for season_row in seasons:
            season_row["duration"] = str(run_minutes)

    info = {
        "name": series_name,
        "cover": poster,
        "plot": meta.get("overview") or "",
        "cast": meta.get("cast") or "",
        "director": meta.get("director") or "",
        "genre": series_genre_text(meta, separator=", "),
        "releaseDate": release,
        "release_date": release,
        "last_modified": last_modified,
        "rating": str(meta.get("rating") or "0"),
        "rating_5based": str(rating_5based(meta.get("rating"))),
        "backdrop_path": [backdrop] if backdrop else [],
        "youtube_trailer": "",
        "episode_run_time": str(run_minutes),
        "category_id": str(category_id),
        "category_ids": category_ids_for(category_id),
    }
    if tmdb_id:
        info["tmdb"] = str(int(tmdb_id))
    return {
        "seasons": seasons,
        "info": info,
        "episodes": payload,
    }


def vod_stream_item(video, number):
    meta = video["meta"]
    item = {
        "num": number,
        "name": video["name"],
        "stream_type": "movie",
        "stream_id": video["stream_id"],
        "stream_icon": meta.get("poster") or thumb_url(video["stream_id"]),
        "rating": str(meta.get("rating") or "0"),
        "rating_5based": rating_5based(meta.get("rating")),
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


def series_list_item(video, number):
    """Xtream get_series row, aligned with common IPTV providers."""
    meta = video["meta"]
    series_name = meta.get("title") or "Series"
    release = meta.get("release_date") or ""
    backdrop = meta.get("backdrop") or ""
    try:
        series_id = int(video["series_id"])
    except (TypeError, ValueError):
        series_id = video["series_id"]
    category_id = video["category_id"]
    item = {
        "num": number,
        "name": series_name,
        "series_id": series_id,
        "cover": meta.get("poster") or "",
        "plot": meta.get("overview") or "",
        "cast": meta.get("cast") or "",
        "director": meta.get("director") or "",
        "genre": series_genre_text(meta),
        "releaseDate": release,
        "release_date": release,
        "last_modified": video.get("added") or "0",
        "rating": str(meta.get("rating") or "0"),
        "rating_5based": str(rating_5based(meta.get("rating"))),
        "backdrop_path": [backdrop] if backdrop else [],
        "youtube_trailer": "",
        "episode_run_time": "0",
        "category_id": str(category_id),
        "category_ids": category_ids_for(category_id),
    }
    tmdb_id = meta.get("id") or 0
    if tmdb_id:
        item["tmdb"] = str(int(tmdb_id))
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
    backdrop = meta.get("backdrop") or backdrop_url(video["stream_id"])
    plot = meta.get("overview") or ""
    cast = meta.get("cast") or ""
    seconds = None
    detail = media_detail.load_detail(video["path"])
    if detail and detail.get("duration_secs"):
        seconds = detail["duration_secs"]
    if not seconds:
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
    if detail:
        video_info = media_detail.xtream_video(detail)
        audio_info = media_detail.xtream_audio(detail)
        if video_info:
            info["video"] = video_info
        if audio_info:
            info["audio"] = audio_info
        if detail.get("bitrate"):
            info["bitrate"] = int(detail["bitrate"])
    if seconds:
        info["duration_secs"] = int(round(seconds))
        info["duration"] = format_duration(seconds)
    return {
        "info": info,
        "movie_data": {
            "stream_id": video["stream_id"],
            "name": video["name"],
            "added": video.get("added") or "0",
            "category_id": video["category_id"],
            "container_extension": video["container_extension"],
            "custom_sid": "",
            "direct_source": "",
        },
    }


def _match_client():
    global _tmdb_client
    if _tmdb_client is None:
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmdb_match_cache.json")
        _tmdb_client = media_match.TMDBClient(TMDB_API_KEY, cache_path)
    return _tmdb_client


def _write_library(library):
    temporary = LIBRARY_FILE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(library, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, LIBRARY_FILE)
    _library_cache["mtime"] = os.path.getmtime(LIBRARY_FILE)
    _library_cache["data"] = library


def _apply_movie_record(video, record):
    """Fill an in-memory movie from a new library record, keeping its current stream id."""
    video["meta"] = meta_from_library(record)
    video["name"] = display_movie_name(record, video["name"])
    video["category_name"] = movie_category_name(record)
    video["category_id"] = stable_category_id(video["category_name"], "vod")


def scrape_unknown_movie(video):
    """Identify one unindexed movie when its detail page is opened."""
    if video.get("kind") != "movie":
        return
    if "/system/lost" in video.get("path", ""):
        return
    if video.get("meta", {}).get("id"):
        return
    root = MEDIA_DIRS[0] if MEDIA_DIRS else ""
    if not root or not video["path"].startswith(root):
        return
    key = media_key(video["path"], root)
    if key in _scrape_failed:
        return
    with _scrape_lock:
        if video.get("meta", {}).get("id") or key in _scrape_failed:
            return
        try:
            import organize_library
            record = organize_library.identify_movie(_match_client(), video["path"], root)
            _match_client().save()
        except Exception as exc:
            print(f"Scrape failed for {key}: {exc}")
            _scrape_failed.add(key)
            return
        if not record or not record.get("tmdb_id"):
            _scrape_failed.add(key)
            print(f"Scrape uncertain, left unknown: {key}")
            return
        library = load_library()
        library.setdefault("movies", {})[key] = record
        _write_library(library)
        _apply_movie_record(video, record)
        print(f"Scraped {key} -> {record.get('title')} ({record.get('tmdb_id')})")


if __name__ == "__main__":
    print(f"Server starting with media dirs: {MEDIA_DIRS}")
    try:
        _refresh_catalog()
    except Exception as exc:
        print(f"Initial catalog build failed: {exc}")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
