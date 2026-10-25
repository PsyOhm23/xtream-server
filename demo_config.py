"""Editable demo catalog. Change the counts, names, and stream URLs here.

The generator builds the French and English catalogs from these values.
It does not write a static library file.
"""

# How many generated items to add in each category.
# Hero movies below are extra and always stay at the front of VOD.
MOVIES_PER_CAT = 8
SERIES_PER_CAT = 8
LIVE_PER_CAT = 8

# Seasons and episodes are fixed so series screenshots stay predictable.
SEASONS_PER_SERIES = 2
EPISODES_PER_SEASON = 6
EPISODE_DURATION_SECS = 1800

# category_id values are part of the Xtream API. Keep them stable.
LIVE_CATEGORIES = [
    {"id": "10", "fr": "Divertissement", "en": "Entertainment"},
    {"id": "11", "fr": "Cinéma & Fiction", "en": "Movies & Drama"},
    {"id": "12", "fr": "Documentaires & Nature", "en": "Nature & Docs"},
    {"id": "13", "fr": "Sport & Action", "en": "Sports & Action"},
    {"id": "14", "fr": "Jeunesse", "en": "Kids & Toons"},
]

VOD_CATEGORIES = [
    {"id": "20", "fr": "Animation Open-Source", "en": "Open-Source Animation"},
    {"id": "21", "fr": "Science-Fiction", "en": "Sci-Fi"},
    {"id": "22", "fr": "Thriller & Suspense", "en": "Thriller & Suspense"},
    {"id": "23", "fr": "Documentaires", "en": "Documentaries"},
]

SERIES_CATEGORIES = [
    {"id": "30", "fr": "Créations Originales", "en": "Original Series"},
    {"id": "31", "fr": "Mystère & Enquêtes", "en": "Mystery & Crime"},
    {"id": "32", "fr": "Aventures & Voyage", "en": "Adventure & Travel"},
    {"id": "33", "fr": "Tech & Futur", "en": "Tech & Future"},
]

# Creative Commons films from the Blender Foundation.
# Only these rows carry a real TMDB id. Generated titles leave it empty.
HERO_MOVIES = [
    {
        "stream_id": 2001,
        "tmdb_id": "45745",
        "category_id": "20",
        "year": 2010,
        "duration_secs": 888,
        "poster": "https://image.tmdb.org/t/p/w500/l98Zns4oQe1BSvbF4hJ8oL6VSf0.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w1280/msqeiEyIRpPAtrCeRGFNZQ9tkJL.jpg",
        "fr": {
            "title": "Sintel",
            "overview": "Une jeune guerrière part à la recherche du dragon qu'elle a élevé.",
            "director": "Colin Levy",
            "cast": "Halina Reijn, Thom Hoffman",
        },
        "en": {
            "title": "Sintel",
            "overview": "A young warrior searches for the dragon she once raised.",
            "director": "Colin Levy",
            "cast": "Halina Reijn, Thom Hoffman",
        },
    },
    {
        "stream_id": 2002,
        "tmdb_id": "133701",
        "category_id": "21",
        "year": 2012,
        "duration_secs": 734,
        "poster": "https://image.tmdb.org/t/p/w500/8qy3jRmaHR7f8VZh3iXCqCWfFsH.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w1280/fOy6SL5Zs2PFcNXwqEPIDPrLB1q.jpg",
        "fr": {
            "title": "Tears of Steel",
            "overview": "À Amsterdam, un groupe tente de réparer un désastre venu du futur.",
            "director": "Ian Hubert",
            "cast": "Derek de Lint, Sergio Hasselbaink, Vanja Rukavina",
        },
        "en": {
            "title": "Tears of Steel",
            "overview": "In Amsterdam, a group tries to undo a disaster sent back from the future.",
            "director": "Ian Hubert",
            "cast": "Derek de Lint, Sergio Hasselbaink, Vanja Rukavina",
        },
    },
    {
        "stream_id": 2003,
        "tmdb_id": "10378",
        "category_id": "20",
        "year": 2008,
        "duration_secs": 600,
        "poster": "https://image.tmdb.org/t/p/w500/i9jJzvoXET4D9pOkoEwncSdNNER.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w1280/xtdybjRRZ15mCrPOvEld305myys.jpg",
        "fr": {
            "title": "Big Buck Bunny",
            "overview": "Un grand lapin décide de rendre la pareille à trois rongeurs moqueurs.",
            "director": "Sacha Goedegebure",
            "cast": "Big Buck Bunny",
        },
        "en": {
            "title": "Big Buck Bunny",
            "overview": "A giant rabbit decides to teach three bullying rodents a lesson.",
            "director": "Sacha Goedegebure",
            "cast": "Big Buck Bunny",
        },
    },
    {
        "stream_id": 2004,
        "tmdb_id": "358332",
        "category_id": "21",
        "year": 2015,
        "duration_secs": 720,
        "poster": "https://image.tmdb.org/t/p/w500/5ZXi0oitpEgAdoJglFTc5SZF9nt.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w1280/f2wABsgj2lIR2dkDEfBZX8p4Iyk.jpg",
        "fr": {
            "title": "Cosmos Laundromat",
            "overview": "Sur une île déserte, un mouton découragé rencontre un vendeur étrange.",
            "director": "Mathieu Auvray",
            "cast": "Franck, Victor",
        },
        "en": {
            "title": "Cosmos Laundromat",
            "overview": "On a lonely island, a discouraged sheep meets a mysterious salesman.",
            "director": "Mathieu Auvray",
            "cast": "Franck, Victor",
        },
    },
    {
        "stream_id": 2005,
        "tmdb_id": "593048",
        "category_id": "20",
        "year": 2019,
        "duration_secs": 450,
        "poster": "https://image.tmdb.org/t/p/w500/hDz3xAmqwAbJ1H3Zz4L0XuBM7yp.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w1280/lL04DVOu1b64Xoj1EuWHZdtcfaZ.jpg",
        "fr": {
            "title": "Spring",
            "overview": "Une bergère affronte les esprits de la nature pour protéger son troupeau.",
            "director": "Andy Goralczyk",
            "cast": "Spring",
        },
        "en": {
            "title": "Spring",
            "overview": "A shepherd faces the spirits of nature to protect her flock.",
            "director": "Andy Goralczyk",
            "cast": "Spring",
        },
    },
    {
        "stream_id": 2006,
        "tmdb_id": "891761",
        "category_id": "20",
        "year": 2021,
        "duration_secs": 600,
        "poster": "https://image.tmdb.org/t/p/w500/AjWJQOogG4Irpff6K49tzrUTb1s.jpg",
        "backdrop": "https://image.tmdb.org/t/p/w1280/aCMT1okuiKFnyKHdCOez66rJKyT.jpg",
        "fr": {
            "title": "Sprite Fright",
            "overview": "Des scouts en campement découvrent qu'une créature rôde dans les bois.",
            "director": "Blender Studio",
            "cast": "Scouts",
        },
        "en": {
            "title": "Sprite Fright",
            "overview": "Scouts on a camping trip discover a creature lurking in the woods.",
            "director": "Blender Studio",
            "cast": "Scouts",
        },
    },
]

# Appended to every Blender hero plot. CC-BY requires this credit.
BLENDER_CREDIT = "© Blender Foundation | cloud.blender.org (CC-BY)"

# Closed lists so generated titles cannot collide with a real work.
# French lists stay in the same order as the English ones.
TITLE_WORDS = {
    "en": {
        "adjectives": ["Silent", "Distant", "Hidden", "Bright", "Lost", "Neon", "Quiet", "Wild", "Frozen", "Golden"],
        "nouns": ["Horizon", "Odyssey", "Chronicles", "Echo", "Nebula", "Pixel", "Signal", "Voyage", "Harbor", "Drift"],
    },
    "fr": {
        "adjectives": ["silencieux", "lointain", "caché", "lumineux", "perdu", "néon", "calme", "sauvage", "gelé", "doré"],
        "nouns": ["Horizon", "Odyssée", "Chroniques", "Écho", "Nébuleuse", "Pixel", "Signal", "Voyage", "Port", "Dérive"],
    },
}

# Direct playback. One CC-BY file, about 15 minutes, so the player timeline
# stays usable. The 10-second clips are too short for the app.
MP4_STREAMS = [
    "https://archive.org/download/sintel_cc_by_2010/sintel-2048-stereo.mp4",
]

# Movie and series HLS. Big Buck Bunny on Mux is a finite VOD (about 10 min 34 s).
HLS_STREAMS = [
    "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
]

# Live TV only. These are sliding-window HLS lives: no EXT-X-ENDLIST,
# so the player keeps the "live" UI instead of a VOD progress bar.
LIVE_HLS_STREAMS = [
    "https://demo.unified-streaming.com/k8s/live/stable/live.isml/.m3u8",
    "https://cph-p2p-msl.akamaized.net/hls/live/2000341/test/master.m3u8",
    "https://demo.unified-streaming.com/k8s/live/stable/scte35.isml/.m3u8",
]
