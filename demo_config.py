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

# List order is the home order. Sci-Fi stays first, ahead of open-source animation.
VOD_CATEGORIES = [
    {"id": "21", "fr": "Science-Fiction", "en": "Sci-Fi"},
    {"id": "20", "fr": "Animation Open-Source", "en": "Open-Source Animation"},
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
# added_offset is seconds above the catalog base. Higher means more recent.
# Sci-Fi is the row directly under "Recently added", then open-source animation.
# The newest films stay in later categories so those posters are not repeated.
# Posters and backdrops are served from demo_art. A full image.tmdb.org URL is
# rewritten by the app into a CDN request, and the test TV emulator rejects that
# certificate when its clock is behind. Root-relative paths become local URLs.
HERO_MOVIES = [
    {
        "stream_id": 2001,
        "tmdb_id": "45745",
        "stream": "https://archive.org/download/sintel_cc_by_2010/sintel-2048-stereo.mp4",
        "category_id": "20",
        "year": 2010,
        "duration_secs": 888,
        "poster": "/demo-art/movies/hero_sintel.jpg",
        "backdrop": "/demo-art/backdrops/hero_sintel.jpg",
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
        "stream": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8",
        "category_id": "21",
        "year": 2012,
        "duration_secs": 734,
        "poster": "/demo-art/movies/hero_tears_of_steel.jpg",
        "backdrop": "/demo-art/backdrops/hero_tears_of_steel.jpg",
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
        "stream": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
        "category_id": "20",
        "year": 2008,
        "duration_secs": 600,
        "poster": "/demo-art/movies/hero_big_buck_bunny.jpg",
        "backdrop": "/demo-art/backdrops/hero_big_buck_bunny.jpg",
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
        "stream": "https://archive.org/download/CosmosLaundromatFirstCycle/Cosmos%20Laundromat%20-%20First%20Cycle%20%281080p%29.mp4",
        "category_id": "21",
        "year": 2015,
        "duration_secs": 720,
        "poster": "/demo-art/movies/hero_cosmos_laundromat.jpg",
        "backdrop": "/demo-art/backdrops/hero_cosmos_laundromat.jpg",
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
        "stream": "https://archive.org/download/spring_blenderopenmovie/Spring%20-%20Blender%20Open%20Movie%20-%20YouTube.mp4",
        "category_id": "20",
        "year": 2019,
        "duration_secs": 450,
        "poster": "/demo-art/movies/hero_spring.jpg",
        "backdrop": "/demo-art/backdrops/hero_spring.jpg",
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
        # No stable public file for Sprite Fright. Elephants Dream is another CC-BY Blender film.
        "stream": "https://archive.org/download/ElephantsDream/ed_1024_512kb.mp4",
        "category_id": "22",
        "added_offset": 500,
        "year": 2021,
        "duration_secs": 600,
        "poster": "/demo-art/movies/hero_sprite_fright.jpg",
        "backdrop": "/demo-art/backdrops/hero_sprite_fright.jpg",
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

# Generated movies and episodes rotate through these URLs.
# Big Buck Bunny on Mux is the model: one finite public stream per title.
# Heroes above keep their own "stream" and are not taken from this rotation.
VOD_STREAMS = [hero["stream"] for hero in HERO_MOVIES]

# Live TV only. These are sliding-window HLS lives: no EXT-X-ENDLIST,
# so the player keeps the "live" UI instead of a VOD progress bar.
LIVE_HLS_STREAMS = [
    "https://demo.unified-streaming.com/k8s/live/stable/live.isml/.m3u8",
    "https://cph-p2p-msl.akamaized.net/hls/live/2000341/test/master.m3u8",
    "https://demo.unified-streaming.com/k8s/live/stable/scte35.isml/.m3u8",
]

# Curated showcase series keyed by series_id so the first series in the default
# category always renders realistic copy and avoids TMDB collisions.
HERO_SERIES = {
    33201: {
        "year": 2024,
        "rating": "8.4",
        "fr": {
            "title": "Crête boréale",
            "overview": "Une équipe de photographes traverse les hauts plateaux nordiques, entre refuges isolés et nuits sous les aurores.",
            "director": "Claire Moreau",
            "cast": "Camille Laurent, Julien Mercier, Nadia Benali",
            "episodes": {
                1: [
                    ("Camp de base", "L'équipe installe son premier bivouac au pied du massif avant la tombée de la nuit."),
                    ("La ligne de crête", "Un vent glacial impose un changement d'itinéraire le long des arêtes enneigées."),
                    ("Lumière d'altitude", "À l'aube, les nuages se dissipent et dévoilent la vallée glaciaire en contrebas."),
                    ("Refuge du col", "Une tempête force les voyageurs à partager un refuge avec deux glaciologues."),
                    ("Piste des fjords", "La descente vers la côte ouvre sur des eaux calmes où dérivent les premiers blocs de glace."),
                    ("Aurores d'hiver", "La dernière nuit en altitude offre un ciel dégagé et une aurore boréale inattendue."),
                ],
                2: [
                    ("Retour au nord", "Un an plus tard, l'expédition repart vers les îles les plus reculées de l'archipel."),
                    ("Brume matinale", "La traversée en bateau s'avance lentement dans un brouillard épais jusqu'au mouillage."),
                    ("Sentier oublié", "Une vieille carte maritime mène l'équipe vers un phare abandonné sur la falaise."),
                    ("Marée haute", "Il faut remonter le matériel avant que la mer ne coupe l'accès à la presqu'île."),
                    ("Horizon polaire", "Les journées raccourcissent tandis que la lumière rasante transforme le paysage."),
                    ("Dernier bivouac", "Avant le retour, l'équipe rassemble ses carnets et ses plus belles images du voyage."),
                ],
            },
        },
        "en": {
            "title": "Boreal Ridge",
            "overview": "A photojournalist team crosses remote northern ridges, documenting mountain shelters and shifting winter light.",
            "director": "Claire Moreau",
            "cast": "Hannah Reid, Liam Bennett, Maya Patel",
            "episodes": {
                1: [
                    ("Base Camp", "The team pitches its first camp beneath the ridge as twilight settles over the valley."),
                    ("The Ridge Line", "Rising winds force a detour along the narrow rocky spine above the treeline."),
                    ("High Altitude Light", "At sunrise, low clouds clear to reveal the glacial basin stretching below."),
                    ("Pass Shelter", "An early snowstorm brings the crew together with two field researchers in a stone hut."),
                    ("Fjord Trail", "Descending toward the coast opens onto quiet waters dotted with drifting ice."),
                    ("Winter Aurora", "On the final night at altitude, clear skies reward the crew with green auroras."),
                ],
                2: [
                    ("Back North", "One year later, the crew sets out again toward the outer islands of the archipelago."),
                    ("Morning Mist", "The supply boat threads through thick coastal fog on its way to the anchorage."),
                    ("Forgotten Path", "An archival sea chart leads the photographers to a weathered cliffside lighthouse."),
                    ("High Tide", "The team races the rising water to carry its gear off the tidal headland."),
                    ("Polar Horizon", "Shorter days bathe the snowfields in long, amber dusk light."),
                    ("Final Camp", "Before heading home, the crew reviews its field notes and favorite frames from the journey."),
                ],
            },
        },
    },
}

# Deterministic curated summaries replacing random Faker paragraphs across demo entries.
DEMO_OVERVIEWS = {
    "fr": {
        "movie": [
            "Sur une côte battue par les vents, un archiviste retrouve un enregistrement qui bouleverse l'histoire de sa ville.",
            "Deux scientifiques en mission polaire suivent un signal inconnu sous la banquise et remettent en question leur expédition.",
            "Une jeune navigatrice traverse l'archipel à la recherche d'un phare oublié avant la saison des tempêtes.",
            "Au cœur d'une métropole nocturne, un technicien son découvre un message caché dans des bandes magnétiques.",
            "Un documentaire immersif suit le quotidien d'artisans et d'explorateurs à travers quatre saisons.",
            "Lors d'un voyage ferroviaire hivernal, trois inconnus croisent leurs récits autour d'une mystérieuse carte ancienne.",
        ],
        "series": [
            "Chaque épisode suit le parcours croisé de voyageurs et d'observateurs confrontés à des paysages extrêmes.",
            "Une chronique en plusieurs saisons au plus près d'équipes techniques, de chercheurs et de témoins de terrain.",
            "Au fil des épisodes, une enquête patiente révèle les secrets d'une station isolée en haute montagne.",
            "Une série documentaire et de fiction explorant les liens entre mémoire collective, territoires et découvertes.",
            "Entre océan et sommets, une équipe relève de nouveaux défis logistiques et humains à chaque étape.",
            "Des récits indépendants reliés par un même fil conducteur et une attention particulière portée à l'image.",
        ],
        "episode": [
            "L'équipe analyse les relevés de la veille et prépare l'étape suivante avant le lever du jour.",
            "Un imprévu météorologique oblige le groupe à revoir son itinéraire et à improviser un abri.",
            "Les premières images captées sur le terrain confirment l'hypothèse avancée au début de la mission.",
            "Une rencontre inattendue apporte un éclairage nouveau sur l'origine des signaux enregistrés.",
            "La progression devient plus technique à mesure que le relief se resserre autour de la vallée.",
            "En fin de journée, le bilan des observations ouvre une piste décisive pour la suite du voyage.",
        ],
        "live": [
            "Émission en direct consacrée à l'actualité culturelle, aux documentaires et aux grands reportages.",
            "Magazine thématique avec invités en plateau, séquences filmées sur le terrain et analyses.",
            "Diffusion continue de formats courts, découvertes visuelles et programmes familiaux.",
            "Rendez-vous en direct dédié aux sciences, à la nature et aux expéditions contemporaines.",
            "Programmation spéciale mêlant cinéma indépendant, entretiens et coulisses de création.",
            "Journal d'information et sélection de reportages consacrés aux initiatives locales et internationales.",
        ],
    },
    "en": {
        "movie": [
            "Along a windswept coastline, an archivist uncovers a tape recording that reshapes the town's history.",
            "Two researchers on a polar station trace an unexplained signal beneath the ice shelf.",
            "A young sailor crosses the outer archipelago in search of a forgotten lighthouse before winter storms arrive.",
            "In a quiet midnight city, an audio engineer finds a hidden sequence inside restored reel-to-reel tapes.",
            "An immersive feature following craftspeople and field explorers through four changing seasons.",
            "During an overnight winter train journey, three strangers compare notes around a weathered regional map.",
        ],
        "series": [
            "Each episode follows travelers and field observers navigating remote terrain and shifting conditions.",
            "A multi-season chronicle spotlighting research crews, engineers, and everyday life off the beaten track.",
            "Across the season, a patient investigation uncovers the history behind a quiet mountain outpost.",
            "An anthology blending visual storytelling, exploration, and close portraits of remarkable places.",
            "From open ocean to high passes, a dedicated crew takes on fresh logistical challenges every week.",
            "Character-driven stories connected by shared routes, careful craft, and striking cinematography.",
        ],
        "episode": [
            "The crew reviews yesterday's readings and prepares the next leg before daybreak.",
            "Sudden weather forces the group to change course and set up a temporary shelter.",
            "Early footage gathered on location confirms the lead spotted at the start of the expedition.",
            "An unexpected encounter sheds new light on the origin of the recorded signals.",
            "The route grows steeper as the valley narrows toward the upper ridge.",
            "At dusk, the latest field notes point toward a decisive new direction for the team.",
        ],
        "live": [
            "Live broadcast featuring cultural stories, independent documentaries, and in-depth reporting.",
            "Studio magazine with guest conversations, field dispatches, and visual essays.",
            "Continuous stream of curated short features, travel reels, and family programming.",
            "Live programming devoted to science, wildlife, and modern exploration.",
            "Special showcase highlighting independent filmmaking, interviews, and behind-the-scenes craft.",
            "Hourly roundup of regional features, nature coverage, and international stories.",
        ],
    },
}
