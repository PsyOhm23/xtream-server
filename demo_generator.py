"""Deterministic French and English demo catalogs.

The same stream id always yields the same titles. Nothing is written to disk.
"""

import threading

from faker import Faker

import demo_config

_LOCK = threading.Lock()
_FAKERS = {
    "fr": Faker("fr_FR"),
    "en": Faker("en_US"),
}

_ADDED = "1700000000"


def is_demo_user(username):
    """Demo accounts are demo, demo_fr, demo_en, and any future demo_* user."""
    return bool(username) and username.lower().startswith("demo")


def language_for(username):
    """English when the username contains 'en' (demo_en). Every other demo user is French."""
    if username and "en" in username.lower():
        return "en"
    return "fr"


def stream_extension(url):
    """Container suffix the app should request for this playback URL."""
    path = (url or "").split("?", 1)[0].lower()
    if path.endswith(".m3u8"):
        return "m3u8"
    if path.endswith(".mov"):
        return "mov"
    return "mp4"


def playback_url(route, stream_id, extension):
    """Live stays on an endless HLS window. Each VOD title keeps its own stream."""
    if route == "live":
        pool = demo_config.LIVE_HLS_STREAMS
        return pool[int(stream_id) % len(pool)]
    for hero in demo_config.HERO_MOVIES:
        if int(hero["stream_id"]) == int(stream_id):
            return hero["stream"]
    pool = demo_config.VOD_STREAMS
    return pool[int(stream_id) % len(pool)]


def build_catalog(username):
    """Return movie, episode, and live rows in the shape the Xtream server already uses."""
    lang = language_for(username)
    videos = []
    videos.extend(_hero_movies(lang))
    videos.extend(_generated_movies(lang))
    videos.extend(_series(lang))
    videos.extend(_live_channels(lang))
    return videos


def _hero_movies(lang):
    rows = []
    for hero in demo_config.HERO_MOVIES:
        copy = hero[lang]
        category = _category(demo_config.VOD_CATEGORIES, hero["category_id"])
        stream_id = int(hero["stream_id"])
        rows.append(_movie_row(
            stream_id=stream_id,
            name=copy["title"],
            year=hero["year"],
            category=category,
            lang=lang,
            overview=_with_credit(copy["overview"]),
            director=copy["director"],
            cast=copy["cast"],
            rating="8.0",
            poster=hero["poster"],
            backdrop=hero.get("backdrop") or "",
            tmdb_id=int(hero["tmdb_id"]),
            duration_secs=int(hero["duration_secs"]),
        ))
    return rows


def _generated_movies(lang):
    rows = []
    for category in demo_config.VOD_CATEGORIES:
        for index in range(1, demo_config.MOVIES_PER_CAT + 1):
            stream_id = 20000 + int(category["id"]) * 100 + index
            fields = _seeded(lang, stream_id, "movie")
            rows.append(_movie_row(
                stream_id=stream_id,
                name=fields["title"],
                year=fields["year"],
                category=category,
                lang=lang,
                overview=fields["overview"],
                director=fields["director"],
                cast=fields["cast"],
                rating=fields["rating"],
                poster=_poster("movie", stream_id),
                tmdb_id=0,
                duration_secs=fields["duration_secs"],
            ))
    return rows


def _series(lang):
    rows = []
    for category in demo_config.SERIES_CATEGORIES:
        for index in range(1, demo_config.SERIES_PER_CAT + 1):
            series_id = 30000 + int(category["id"]) * 100 + index
            show = _seeded(lang, series_id, "series")
            show_meta = _meta(
                title=show["title"],
                overview=show["overview"],
                director=show["director"],
                cast=show["cast"],
                rating=show["rating"],
                year=show["year"],
                poster=_poster("series", series_id),
                backdrop=_backdrop(series_id),
                genre=category[lang],
                tmdb_id=0,
            )
            for season in range(1, demo_config.SEASONS_PER_SERIES + 1):
                for episode in range(1, demo_config.EPISODES_PER_SEASON + 1):
                    episode_id = series_id * 100 + season * 10 + episode
                    ep = _seeded(lang, episode_id, "episode")
                    title = f"{show['title']} - S{season:02d}E{episode:02d} - {ep['title']}"
                    source = playback_url("series", episode_id, "")
                    rows.append({
                        "stream_id": episode_id,
                        "_identity": f"demo:episode:{episode_id}",
                        "name": title,
                        "title": title,
                        "episode_title": ep["title"],
                        "episode_num": episode,
                        "episode_plot": ep["overview"],
                        "episode_image": _poster("episode", episode_id),
                        "episode_rating": ep["rating"],
                        "category_name": category[lang],
                        "category_id": category["id"],
                        "kind": "episode",
                        "lang": lang,
                        "container_extension": stream_extension(source),
                        "path": source,
                        "direct_source": "",
                        "added": _ADDED,
                        "duration_secs": demo_config.EPISODE_DURATION_SECS,
                        "meta": show_meta,
                        "series_id": series_id,
                        "season": season,
                        "episode": episode,
                    })
    return rows


def _live_channels(lang):
    rows = []
    for category in demo_config.LIVE_CATEGORIES:
        for index in range(1, demo_config.LIVE_PER_CAT + 1):
            stream_id = 10000 + int(category["id"]) * 100 + index
            fields = _seeded(lang, stream_id, "live")
            rows.append({
                "stream_id": stream_id,
                "_identity": f"demo:live:{stream_id}",
                "name": fields["title"],
                "title": fields["title"],
                "category_name": category[lang],
                "category_id": category["id"],
                "kind": "live",
                "lang": lang,
                "container_extension": "m3u8",
                "path": playback_url("live", stream_id, "m3u8"),
                "direct_source": "",
                "added": _ADDED,
                "epg_channel_id": f"ch_{stream_id}",
                "meta": _meta(
                    title=fields["title"],
                    overview=fields["overview"],
                    director="",
                    cast="",
                    rating="0",
                    year="",
                    poster=_channel_logo(stream_id),
                    backdrop=_backdrop(stream_id),
                    genre=category[lang],
                    tmdb_id=0,
                ),
                "series_id": "",
                "season": None,
                "episode": None,
            })
    return rows


def describe(lang, seed):
    """One deterministic title and description for an EPG slot."""
    title = synthetic_title(lang, int(seed))
    with _LOCK:
        fake = _FAKERS[lang]
        fake.seed_instance(int(seed))
        description = fake.paragraph(nb_sentences=2)
    return title, description


def synthetic_title(lang, seed):
    """Adjective plus noun from a closed list. Never a published title."""
    words = demo_config.TITLE_WORDS[lang]
    adjective = words["adjectives"][int(seed) % len(words["adjectives"])]
    noun = words["nouns"][(int(seed) // 7) % len(words["nouns"])]
    if lang == "fr":
        return f"{noun} {adjective}"
    return f"{adjective} {noun}"


def _with_credit(overview):
    credit = demo_config.BLENDER_CREDIT
    text = (overview or "").rstrip()
    if text.endswith(credit):
        return text
    return f"{text} {credit}"


def _movie_row(stream_id, name, year, category, lang, overview, director, cast, rating, poster, tmdb_id, duration_secs, backdrop=""):
    display = f"{name} ({year})" if year else name
    source = playback_url("movie", stream_id, "")
    return {
        "stream_id": stream_id,
        "_identity": f"demo:movie:{stream_id}",
        "name": display,
        "title": display,
        "category_name": category[lang],
        "category_id": category["id"],
        "kind": "movie",
        "lang": lang,
        "container_extension": stream_extension(source),
        "path": source,
        "direct_source": "",
        "added": _ADDED,
        "duration_secs": int(duration_secs),
        "meta": _meta(
            title=name,
            overview=overview,
            director=director,
            cast=cast,
            rating=rating,
            year=year,
            poster=poster,
            backdrop=backdrop or _backdrop(stream_id),
            genre=category[lang],
            tmdb_id=tmdb_id,
        ),
        "series_id": "",
        "season": None,
        "episode": None,
    }


def _meta(title, overview, director, cast, rating, year, poster, backdrop, genre, tmdb_id):
    release = f"{int(year)}-01-01" if year else ""
    return {
        "id": int(tmdb_id) if tmdb_id else 0,
        "title": title,
        "poster": poster,
        "backdrop": backdrop,
        "overview": overview,
        "rating": str(rating),
        "release_date": release,
        "genre": genre,
        "tmdb_genres": [genre] if genre else [],
        "original_title": title,
        "cast": cast,
        "director": director,
        "year": year or "",
    }


def _seeded(lang, seed, kind):
    with _LOCK:
        fake = _FAKERS[lang]
        fake.seed_instance(int(seed))
        title = synthetic_title(lang, int(seed))
        overview = fake.paragraph(nb_sentences=2 if kind != "episode" else 1)
        director = fake.name() if kind != "live" else ""
        cast = ", ".join(fake.name() for _ in range(3)) if kind != "live" else ""
        rating = f"{fake.random_int(60, 90) / 10:.1f}"
        year = fake.random_int(1998, 2024)
        duration_secs = fake.random_int(20, 40) * 60
    return {
        "title": title,
        "overview": overview,
        "director": director,
        "cast": cast,
        "rating": rating,
        "year": year,
        "duration_secs": duration_secs,
    }


def _category(categories, category_id):
    for category in categories:
        if category["id"] == str(category_id):
            return category
    return categories[0]


def _poster(kind, stream_id):
    return f"https://picsum.photos/seed/{kind}_{stream_id}/400/600"


def _backdrop(stream_id):
    return f"https://picsum.photos/seed/bg_{stream_id}/1280/720"


def _channel_logo(stream_id):
    return f"https://api.dicebear.com/9.x/shapes/png?seed=channel_{stream_id}&size=300"
