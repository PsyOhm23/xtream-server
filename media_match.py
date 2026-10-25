"""Parse media filenames and accept a TMDB match only when it is unambiguous."""

import json
import os
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

JUNK_TOKENS = {
    "1080p", "720p", "2160p", "480p", "576p", "4k", "uhd", "hdr", "hdr10",
    "hdr10plus", "sdr", "dv", "bluray", "bdrip", "brrip", "dvdrip", "webrip",
    "webdl", "web", "hdtv", "hdrip", "remux", "hdlight", "mhd", "10bit",
    "10bits", "8bit", "x264", "x265", "h264", "h265", "hevc", "xvid", "divx",
    "avc", "av1", "ac3", "aac", "eac3", "dts", "truehd", "atmos", "ddp",
    "multi", "vf", "vff", "vf2", "vfq", "vostfr", "vost", "french",
    "truefrench", "eng", "vfi", "proper", "repack", "extended", "unrated",
    "remastered", "custom", "readnfo", "imax", "theatrical", "subforces",
    "ds4k", "complete", "hd", "3d", "sbs", "half", "blu", "ray",
    "dl", "fansub", "eac3", "remux", "dsnp", "amzn", "hdr10", "hdr10plus",
    "mkv", "avi", "mp4", "m4v", "dvix", "francais", "voa", "multitruefrench",
}

RELEASE_GROUPS = {"sybelius", "sprlove", "schumi", "mlive"}
LANGUAGE_PIECES = {"eng", "vo", "vf", "fr", "en", "qc", "france", "voa", "vost", "vostfr"}

ROMAN_WORDS = {
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
}

# A roman numeral is a sequel number only when it is the last word.
TRAILING_ROMAN = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
}

LEADING_ARTICLES = ("the", "le", "la", "les", "un", "une", "a", "an")
CURRENT_YEAR = 2026
ANIMATION_GENRE_ID = 16

# Earlier entries win over the order TMDB returns. Unlisted genres keep that order.
GENRE_PRIORITY = (
    "Animation",
)


class ParsedName:
    def __init__(self, title, year=None, alts=None, season=None, episode=None):
        self.title = title or ""
        self.year = year
        self.alts = alts or []
        self.season = season
        self.episode = episode

    def queries(self):
        seen = []
        for raw in [self.title] + list(self.alts):
            text = re.sub(r"\s+", " ", (raw or "")).strip(" -")
            if len(canon(text)) < 2:
                continue
            if text not in seen:
                seen.append(text)
        return seen


class Match:
    def __init__(self, tmdb_id, media_type, score, year, title, original_title, release_date):
        self.tmdb_id = tmdb_id
        self.media_type = media_type
        self.score = score
        self.year = year
        self.title = title
        self.original_title = original_title
        self.release_date = release_date


def _replace_trailing_roman(title):
    """Turn a final sequel number into digits. Part 1 drops the number.

    "Destination Finale II" becomes "Destination Finale 2". "I" becomes the
    bare title, because the first film is not named with a 1. A leading "I"
    such as "I, Robot" stays.
    """
    words = title.split()
    if len(words) < 2:
        return title
    number = TRAILING_ROMAN.get(words[-1].lower())
    if not number:
        return title
    if number == "1":
        return " ".join(words[:-1])
    return " ".join(words[:-1] + [number])


def canon(value):
    """Fold a title so punctuation, accents and articles do not change the score."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("'", " ").replace("’", " ").replace("`", " ")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for article in LEADING_ARTICLES:
        if text.startswith(article + " "):
            text = text[len(article) + 1:]
            break
    text = re.sub(
        r"\b(ii|iii|iv|vi|vii|viii|ix)\b",
        lambda match: ROMAN_WORDS[match.group(1)],
        text,
    )
    text = re.sub(r"\s+(?:part|partie)\s+(?:1|one|une)$", "", text)
    text = re.sub(r"\s+1$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _score_canon(value):
    """Ignore titles whose letters disappear when folded, such as a Cyrillic name leaving only a year."""
    folded = canon(value)
    letters = [char for char in (value or "") if char.isalpha()]
    compact = folded.replace(" ", "")
    if letters and len(compact) < max(2, int(len(letters) * 0.5)):
        return ""
    return folded


def title_score(left, right):
    folded_left = canon(left)
    folded_right = canon(right)
    # "Dune Part One" folds to "dune" and must still count as the same title.
    if folded_left and folded_right and folded_left == folded_right:
        return 1.0
    a = _score_canon(left)
    b = _score_canon(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _fold_token(token):
    """Lowercase a token and fold accents so HDR10+ and Français match the junk list."""
    text = unicodedata.normalize("NFKD", token or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower().replace("+", "plus")


def _hyphen_is_junk(token):
    """Drop AC-3, AC3-S, AC3-ACOOL, Qc-France-Vo and VFF-VFQ-VOA, not real hyphenated titles."""
    pieces = [piece for piece in token.split("-") if piece]
    if not pieces:
        return False
    if _fold_token("".join(pieces)) in JUNK_TOKENS:
        return True
    return all(
        _fold_token(piece) in JUNK_TOKENS
        or _fold_token(piece) in LANGUAGE_PIECES
        or (len(piece) == 1 and piece.isalpha())
        or _trailing_junk(piece)
        for piece in pieces
    )


def _trailing_junk(token):
    if re.fullmatch(r"[A-Z](?:[a-z]+)?(?:['’][A-Z][a-z]+)+", token):
        return False
    if _fold_token(token) in {"fr", "en", "vo", "by", "light"}:
        return True
    if token.lower() in ROMAN_WORDS or token.lower() in {"i", "v", "x"}:
        return False
    if re.fullmatch(r"(?:19|20)\d{2}", token):
        return False
    # Short all-caps tags (GHT, ACOOL). Longer all-caps words are title text (SOCIERE).
    if re.fullmatch(r"[A-Z][A-Z0-9]{1,4}", token):
        return True
    if re.search(r"[A-Za-z]", token) and re.search(r"\d", token) and re.fullmatch(r"[A-Za-z0-9]{2,14}", token):
        return True
    # Mixed-case release groups such as mHDgz or SPOiLER, not ordinary Title Case words.
    if re.fullmatch(r"[A-Z][a-z]+", token):
        return False
    has_upper = re.search(r"[A-Z]", token)
    has_lower = re.search(r"[a-z]", token)
    internal_caps = re.search(r"[A-Z].*[A-Z]", token)
    return bool(has_upper and has_lower and internal_caps and len(token) <= 14)


def _ssl_context():
    cafile = "/etc/ssl/cert.pem"
    if os.path.exists(cafile):
        return ssl.create_default_context(cafile=cafile)
    return ssl.create_default_context()


def _drop_last_year_token(text, year):
    matches = list(re.finditer(rf"\b{year}\b", text))
    if not matches:
        return text
    match = matches[-1]
    return text[:match.start()] + " " + text[match.end():]


def _plausible_year(year):
    return 1915 <= year <= CURRENT_YEAR + 1


def _extract_years(text):
    years = []
    for match in re.finditer(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text):
        year = int(match.group(1))
        if _plausible_year(year):
            years.append(year)
    return years


def _paren_is_junk(inner):
    lowered = inner.lower()
    if re.search(r"\d{3,4}p|\b(bluray|bdrip|web|multi|vff|vf2|vfq|french|x264|x265|h264|h265|ac3|dts)\b", lowered):
        return True
    tokens = re.findall(r"[a-z0-9]+", lowered)
    if tokens and all(token in JUNK_TOKENS or token in {"vff", "vo", "vfq", "eng", "multi"} for token in tokens):
        return True
    return False


def media_stem(name):
    """Drop a real video extension without cutting versions such as 7.1."""
    base = unicodedata.normalize("NFC", os.path.basename(name))
    stem, extension = os.path.splitext(base)
    if extension.lower() in {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".m2ts", ".srt", ".nfo"}:
        return stem
    return base


def parse_media_name(name):
    """Extract a searchable title, year and episode numbers from a file or folder name."""
    stem = media_stem(name)
    season = None
    episode = None
    episode_match = re.search(r"(?i)S(\d{1,2})[\s._-]*E(\d{1,3})", stem)
    if episode_match:
        season = int(episode_match.group(1))
        episode = int(episode_match.group(2))
        stem = stem[:episode_match.start()] + " " + stem[episode_match.end():]

    paren_years = []
    alts = []

    def replace_paren(match):
        inner = match.group(1).strip()
        if re.fullmatch(r"(?:19|20)\d{2}", inner) and _plausible_year(int(inner)):
            paren_years.append(int(inner))
            return " "
        if _paren_is_junk(inner):
            return " "
        if re.search(r"[A-Za-zÀ-ÿ]", inner) and len(inner) >= 3:
            alts.append(inner)
        return " "

    without_groups = re.sub(r"\(([^)]*)\)", replace_paren, stem)

    def replace_bracket(match):
        inner = match.group(1).strip()
        if re.fullmatch(r"(?:19|20)\d{2}", inner) and _plausible_year(int(inner)):
            paren_years.append(int(inner))
        return " "

    without_groups = re.sub(r"\[([^\]]*)\]", replace_bracket, without_groups)
    without_groups = re.sub(r"\{[^}]*\}", " ", without_groups)

    stripped = without_groups.strip()
    group_match = re.search(r"-([A-Za-z][A-Za-z0-9]{1,15})$", stripped)
    if group_match and not re.fullmatch(r"(?:19|20)\d{2}", group_match.group(1)):
        without_groups = stripped[:group_match.start()]
    else:
        without_groups = stripped

    loose_years = _extract_years(without_groups)
    if len(set(paren_years)) == 1:
        year = paren_years[0]
    elif len(loose_years) == 1:
        year = loose_years[0]
    elif len(loose_years) >= 2:
        # Scene names put the real release year last: "1917.2019", "Blade.Runner.2049.2017".
        year = loose_years[-1]
    else:
        year = None

    text = re.sub(r"(?i)\b[57]\.1\b", " ", without_groups)
    text = text.replace(".", " ").replace("_", " ")
    text = re.sub(r"(?i)\bac3-s\s+v\b", " ", text)
    text = re.sub(r"(?i)\b[57]\s+1\b", " ", text)
    text = re.sub(r"(?i)\b(?:ddp|dd|aac|eac3|e-ac3|he-aac|heaac)\s*\d*(?:\s+\d+)?\b", " ", text)
    text = re.sub(r"(?i)\b(?:8|10|12)\s*bits?\b", " ", text)
    text = re.sub(r"(?i)\b[hx]\s*26[45]\b", " ", text)
    text = re.sub(r"(?i)\b\d{3,4}x\d{3,4}\b", " ", text)
    text = re.sub(r"(?i)\b\d{3,4}p\b", " ", text)
    if year:
        text = _drop_last_year_token(text, year)
    text = text.replace(",", " ")
    text = re.sub(r"(?i)\bS\d{1,2}\b", " ", text)
    text = re.sub(r"(?i)\b(?:season|saison)\s+\d{1,2}\b", " ", text)
    parts = []
    for token in text.split():
        token = token.strip(".-_")
        if not token:
            continue
        folded = _fold_token(token)
        if folded in JUNK_TOKENS or folded in RELEASE_GROUPS:
            continue
        if token.isupper() and folded in {"en", "fr", "vo", "qc"}:
            continue
        if re.fullmatch(r"\d+bits?", folded):
            continue
        if "-" in token and _hyphen_is_junk(token):
            continue
        parts.append(token)
    if len(parts) >= 2 and parts[-2].lower() == "fix" and _fold_token(parts[-1]) == "son":
        parts = parts[:-2]
    while len(parts) > 1 and _trailing_junk(parts[-1]):
        parts.pop()
    title = re.sub(r"\s+", " ", " ".join(parts)).strip(" -")
    words = title.split()
    if len(words) > 2 and words[0].casefold() == words[1].casefold():
        title = " ".join([words[0]] + words[2:])
    title = _replace_trailing_roman(title)
    if not title and year:
        # The only token was the year itself ("2012"), so it is the title, not a release year.
        title = str(year)
        year = None

    if " - " in title:
        for piece in title.split(" - "):
            piece = piece.strip()
            if len(canon(piece)) >= 4 and piece not in alts and piece != title:
                alts.append(piece)

    # A leading catalog index ("60. Title") is a separate guess, never a replacement.
    index_match = re.match(r"^(\d{1,3})\s+(.+)$", title)
    if index_match and len(canon(index_match.group(2))) >= 4:
        alts.append(index_match.group(2))

    return ParsedName(title=title, year=year, alts=alts, season=season, episode=episode)


def _candidate_names(candidate):
    names = [
        candidate.get("title") or "",
        candidate.get("original_title") or "",
        candidate.get("name") or "",
        candidate.get("original_name") or "",
    ]
    names.extend(candidate.get("alt_titles") or [])
    return [name for name in names if name]


def _candidate_year(candidate):
    raw = candidate.get("release_date") or candidate.get("first_air_date") or ""
    match = re.match(r"((?:19|20)\d{2})", raw)
    if not match:
        return None
    year = int(match.group(1))
    if not _plausible_year(year):
        return None
    return year


def score_candidate(parsed, candidate):
    """Return (score, year_ok) for one TMDB result."""
    best = 0.0
    for query in parsed.queries():
        for name in _candidate_names(candidate):
            best = max(best, title_score(query, name))
    candidate_year = _candidate_year(candidate)
    if parsed.year is None:
        year_ok = candidate_year is not None or best >= 0.995
    elif candidate_year == parsed.year:
        year_ok = True
    elif candidate_year and abs(candidate_year - parsed.year) == 1 and best >= 0.995:
        # Exact title, release year off by one (festival date or regional premiere).
        year_ok = True
    else:
        year_ok = False
    return best, year_ok


def _prefer_same_work(exact):
    """Several TMDB ids can be the same film. Keep one only when every exact hit agrees."""
    def original(candidate):
        return canon(candidate.get("original_title") or candidate.get("original_name") or "")

    def title(candidate):
        return canon(candidate.get("title") or candidate.get("name") or "")

    originals = {original(candidate) for _, candidate in exact}
    titles = {title(candidate) for _, candidate in exact}
    years = [year for year in (_candidate_year(candidate) for _, candidate in exact) if year]
    if len(originals) != 1 or "" in originals or len(titles) != 1:
        return None
    if years and max(years) - min(years) > 1:
        return None
    _, chosen = max(exact, key=lambda item: item[1].get("vote_average") or 0)
    return chosen


def primary_genre(genres):
    """Category genre: a listed priority beats the order TMDB returns."""
    names = [genre.strip() for genre in (genres or []) if isinstance(genre, str) and genre.strip()]
    if not names:
        return ""
    by_key = {name.casefold(): name for name in names}
    for preferred in GENRE_PRIORITY:
        match = by_key.get(preferred.casefold())
        if match:
            return match
    return names[0]


def _is_animation(candidate):
    """True, False, or None when TMDB did not provide genres."""
    genres = candidate.get("genre_ids")
    if genres is None:
        raw = candidate.get("genres")
        if not raw:
            return None
        genres = [item.get("id") for item in raw if isinstance(item, dict) and item.get("id")]
    if not genres:
        return None
    return ANIMATION_GENRE_ID in genres


def _prefer_by_animation(exact, prefer_animation):
    """Break an exact-title tie using the file's folder: animation or live action.

    Accept only when every exact hit has genres and exactly one of them matches
    the folder. Two animations, or two live-action films, stay unresolved.
    """
    if prefer_animation is None:
        return None
    # The folder chooses the medium, not the year. Hits from different years stay unresolved.
    years = [year for year in (_candidate_year(candidate) for _, candidate in exact) if year]
    if len(years) != len(exact) or max(years) - min(years) > 1:
        return None
    flags = []
    for _, candidate in exact:
        flag = _is_animation(candidate)
        if flag is None:
            return None
        flags.append(flag)
    chosen = [
        candidate
        for (_, candidate), flag in zip(exact, flags)
        if flag is prefer_animation
    ]
    if len(chosen) != 1:
        return None
    return chosen[0]


def pick_match(parsed, candidates, media_type, prefer_animation=None):
    """Return a Match when one candidate is clearly the same work, else None."""
    ranked = []
    for candidate in candidates:
        score, year_ok = score_candidate(parsed, candidate)
        if not year_ok:
            continue
        ranked.append((score, candidate))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    exact = [item for item in ranked if item[0] >= 0.995]
    if len(exact) > 1:
        best = _prefer_same_work(exact)
        if best is None:
            best = _prefer_by_animation(exact, prefer_animation)
        if best is None:
            return None
        best_score = 1.0
        runner_up = 0.0
    query_compact = canon(parsed.title).replace(" ", "")
    margin = best_score - runner_up

    if best_score < 0.93:
        return None
    # A unique exact title stays certain. "Shrek 4D" is close to "Shrek 4" but not exact.
    if not exact and margin < 0.08 and runner_up >= 0.90:
        return None
    if parsed.year is None:
        # "Shrek 2" is exact and unique, but shorter than 8 characters.
        # A bare "Shrek" or "Shrek 1" has no digit left after folding and stays rejected.
        numbered_title = bool(re.search(r"\d", query_compact))
        if best_score < 0.995 or (len(query_compact) < 8 and not numbered_title):
            return None
    elif best_score < 0.995 and len(query_compact) < 4:
        return None

    title = best.get("title") or best.get("name") or ""
    original = best.get("original_title") or best.get("original_name") or title
    return Match(
        tmdb_id=best.get("id"),
        media_type=media_type,
        score=round(best_score, 4),
        year=_candidate_year(best),
        title=title,
        original_title=original,
        release_date=best.get("release_date") or best.get("first_air_date") or "",
    )


def choose_display_title(parsed, french_title, original_title):
    """Keep the title the file already uses, with official TMDB casing."""
    query = canon(parsed.title)
    french_folded = canon(french_title or "")
    original_folded = canon(original_title or "")
    if query and query == french_folded and french_title:
        return french_title
    if query and query == original_folded and original_title:
        return original_title
    # "Volt" is the start of the French title "Volt, star malgré lui".
    if query and french_title and french_folded.startswith(query) and query != original_folded:
        return french_title
    if query and original_title and original_folded.startswith(query) and query != french_folded:
        return original_title

    french_score = title_score(parsed.title, french_title or "")
    original_score = title_score(parsed.title, original_title or "")
    for alt in parsed.alts:
        french_score = max(french_score, title_score(alt, french_title or ""))
        original_score = max(original_score, title_score(alt, original_title or ""))
    if original_title and original_score > french_score:
        return original_title
    return french_title or original_title or parsed.title


def filesystem_name(title):
    text = unicodedata.normalize("NFC", title or "")
    text = text.replace(":", " - ").replace("/", " - ").replace("\\", " - ")
    text = re.sub(r'[<>"|?*]', "", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    encoded = text.encode("utf-8")
    if len(encoded) > 180:
        text = encoded[:180].decode("utf-8", errors="ignore").rstrip()
    return text or "Untitled"


def parent_is_usable(folder_name):
    if not folder_name:
        return False
    if re.search(r"(?i)trilog|pentalog|collection|complete|saga|integrale|intégrale", folder_name):
        return False
    years = set(_extract_years(folder_name))
    if len(years) > 1:
        return False
    return True


class TMDBClient:
    def __init__(self, api_key, cache_path):
        self.api_key = api_key
        self.cache_path = cache_path
        self.cache = {}
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as handle:
                    self.cache = json.load(handle)
            except (OSError, json.JSONDecodeError):
                self.cache = {}
        self._writes = 0

    def save(self):
        temporary = self.cache_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self.cache, handle, ensure_ascii=False)
        os.replace(temporary, self.cache_path)

    def _get(self, path, params):
        params = dict(params)
        params["api_key"] = self.api_key
        url = "https://api.themoviedb.org/3" + path + "?" + urllib.parse.urlencode(params)
        cache_key = path + "?" + urllib.parse.urlencode(sorted((k, v) for k, v in params.items() if k != "api_key"))
        if cache_key in self.cache:
            return self.cache[cache_key]
        delay = 0.2
        last_error = None
        for _ in range(4):
            try:
                with urllib.request.urlopen(url, timeout=20, context=_ssl_context()) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.cache[cache_key] = payload
                self._writes += 1
                if self._writes % 20 == 0:
                    self.save()
                return payload
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 404:
                    self.cache[cache_key] = {}
                    return {}
                if exc.code == 429:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"TMDB request failed for {path}: {last_error}")

    def search(self, media_type, query, year, language):
        params = {"query": query, "language": language, "include_adult": "false"}
        if year:
            if media_type == "tv":
                params["first_air_date_year"] = str(year)
            else:
                params["year"] = str(year)
        payload = self._get(f"/search/{media_type}", params)
        results = []
        for item in (payload or {}).get("results") or []:
            results.append({
                "id": item.get("id"),
                "title": item.get("title") or item.get("name") or "",
                "original_title": item.get("original_title") or item.get("original_name") or "",
                "release_date": item.get("release_date") or item.get("first_air_date") or "",
                "poster_path": item.get("poster_path") or "",
                "backdrop_path": item.get("backdrop_path") or "",
                "overview": item.get("overview") or "",
                "vote_average": item.get("vote_average") or 0,
                "genre_ids": list(item.get("genre_ids") or []),
            })
        return results

    def details(self, media_type, tmdb_id):
        return self._get(
            f"/{media_type}/{tmdb_id}",
            {"language": "fr-FR", "append_to_response": "credits,alternative_titles"},
        ) or {}

    def season(self, tmdb_id, season_number, language="fr-FR"):
        return self._get(
            f"/tv/{tmdb_id}/season/{season_number}",
            {"language": language},
        ) or {}


def _with_alternative_titles(client, media_type, candidates, limit=3):
    enriched = []
    for candidate in candidates[:limit]:
        if candidate.get("alt_titles"):
            enriched.append(candidate)
            continue
        details = client.details(media_type, candidate["id"])
        titles = []
        block = details.get("alternative_titles") or {}
        for item in block.get("titles") or block.get("results") or []:
            if item.get("iso_3166_1") in {"FR", "US", "GB", "CA"} and item.get("title"):
                titles.append(item["title"])
        copied = dict(candidate)
        copied["alt_titles"] = titles
        if details.get("title") or details.get("name"):
            copied["title"] = details.get("title") or details.get("name")
        if details.get("original_title") or details.get("original_name"):
            copied["original_title"] = details.get("original_title") or details.get("original_name")
        genre_ids = [item.get("id") for item in details.get("genres") or [] if item.get("id")]
        if genre_ids:
            copied["genre_ids"] = genre_ids
        enriched.append(copied)
    return enriched


def identify_parsed(client, parsed, media_type, prefer_animation=None):
    """Search TMDB and accept the hit only when pick_match is sure.

    prefer_animation is True for anims/, False for live-action folders, None
    when the folder does not say which medium the file is.
    """
    if not parsed.queries():
        return None
    candidates = {}

    def absorb(results):
        for item in results:
            if item.get("id"):
                candidates.setdefault(item["id"], item)

    def current_match():
        return pick_match(parsed, list(candidates.values()), media_type, prefer_animation)

    for query in parsed.queries()[:4]:
        french = client.search(media_type, query, parsed.year, "fr-FR")
        absorb(french)
        hit = current_match()
        if hit and hit.score >= 0.995:
            return hit
        english = client.search(media_type, query, parsed.year, "en-US")
        absorb(english)
        hit = current_match()
        if hit and hit.score >= 0.995:
            return hit
        if parsed.year and not hit:
            absorb(client.search(media_type, query, None, "fr-FR"))
            hit = current_match()
            if hit and hit.score >= 0.995:
                return hit

    hit = current_match()
    if hit:
        return hit

    numbered_title = bool(re.search(r"\d", canon(parsed.title).replace(" ", "")))
    # "Shrek 3" only matches once the US alternative title is loaded.
    score_floor = 0.45 if numbered_title else 0.55
    enrich_limit = 5 if numbered_title else 3
    year_filtered = []
    for candidate in candidates.values():
        score, year_ok = score_candidate(parsed, candidate)
        if year_ok and score >= score_floor:
            year_filtered.append(candidate)
    year_filtered.sort(key=lambda item: score_candidate(parsed, item)[0], reverse=True)
    if not year_filtered:
        return None
    for candidate in _with_alternative_titles(client, media_type, year_filtered, enrich_limit):
        if candidate.get("id"):
            candidates[candidate["id"]] = candidate
    return current_match()


def metadata_from_details(client, match, parsed):
    """Build the library record for a certain match, using French TMDB details."""
    details = client.details(match.media_type, match.tmdb_id)
    french_title = details.get("title") or details.get("name") or match.title
    original_title = details.get("original_title") or details.get("original_name") or match.original_title
    display = choose_display_title(parsed, french_title, original_title)
    genres = [genre.get("name") for genre in details.get("genres") or [] if genre.get("name")]
    credits = details.get("credits") or {}
    directors = [person.get("name") for person in credits.get("crew") or [] if person.get("job") == "Director" and person.get("name")]
    cast = [person.get("name") for person in (credits.get("cast") or [])[:5] if person.get("name")]
    poster_path = details.get("poster_path") or ""
    backdrop_path = details.get("backdrop_path") or ""
    release_date = details.get("release_date") or details.get("first_air_date") or match.release_date
    year = match.year
    if not year and release_date[:4].isdigit():
        year = int(release_date[:4])
    return {
        "tmdb_id": match.tmdb_id,
        "media_type": match.media_type,
        "title": display,
        "french_title": french_title,
        "original_title": original_title,
        "year": year,
        "score": match.score,
        "poster": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "",
        "backdrop": f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else "",
        "overview": details.get("overview") or "",
        "rating": str(details.get("vote_average") or 0),
        "release_date": release_date or "",
        "genres": genres,
        "genre_category": f"FR | {primary_genre(genres)}" if genres else "",
        "cast": ", ".join(cast),
        "director": ", ".join(directors),
        "certain": True,
    }
