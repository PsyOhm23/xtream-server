import os
import sys
import unittest
sys.path.append("/home/pi/xtream-server")
import organize_library
import server

class TestXtreamCleaningAndTMDB(unittest.TestCase):
    
    def test_clean_query_name_basic(self):
        # Test basic cleaning
        name = "Doctor Sleep 2019 MULTi 1080p Bluray x265-BULMA"
        cleaned = server.clean_query_name(name)
        self.assertIn("Doctor Sleep", cleaned)
        self.assertIn("2019", cleaned)
        
    def test_clean_query_name_number(self):
        name = "1001 pattes (1998)"
        cleaned = server.clean_query_name(name)
        self.assertIn("1001 pattes", cleaned)
        self.assertIn("1998", cleaned)
        
    def test_clean_query_name_extras(self):
        self.assertIn("Angry Birds", server.clean_query_name("Angry Birds (2016) [MULTI] 1080p BRrip x264 AC3 [AKS]"))
        self.assertIn("Atlantide l empire perdu", server.clean_query_name("Atlantide, l'empire perdu (2001)"))
        self.assertIn("Mutafukaz", server.clean_query_name("Mutafukaz.2017.FRENCH.BDRip.XviD-EXTREME"))

    def test_scene_file_joins_the_indexed_movie(self):
        library = {"movies": {
            "films/Dune - Part Two (2024)/Dune - Part Two (2024).mkv": {
                "tmdb_id": 693134,
                "title": "Dune: Part Two",
                "french_title": "Dune : Deuxième partie",
                "original_title": "Dune: Part Two",
                "year": 2024,
            },
            "films/Dune - Part One (2021)/Dune - Part One (2021).mkv": {
                "tmdb_id": 438631,
                "title": "Dune",
                "french_title": "Dune",
                "original_title": "Dune",
                "year": 2021,
            },
        }}
        lookup = server.movie_lookup(library)
        record = server.movie_record_for_name(
            lookup,
            "Dune.Part.Two.2024.MULTi.FRENCH.HDR.DV.2160p.WEB-DL.H265-Slay3R.mkv",
        )
        self.assertEqual(record["tmdb_id"], 693134)
        first = server.movie_record_for_name(lookup, "Dune (2021).mkv")
        self.assertEqual(first["tmdb_id"], 438631)

    def test_each_copy_stays_playable(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            small = os.path.join(tmp, "Dune - Part Two (2024).mkv")
            large = os.path.join(tmp, "Dune.Part.Two.2024.2160p.mkv")
            with open(small, "wb") as handle:
                handle.write(b"a" * 1024)
            with open(large, "wb") as handle:
                handle.write(b"a" * 4096)
            exposed = server.expose_each_copy([
                {
                    "_identity": "tmdb:693134",
                    "_indexed": True,
                    "path": small,
                    "name": "Dune: Part Two (2024)",
                    "stream_id": 693134,
                },
                {
                    "_identity": "tmdb:693134",
                    "_indexed": False,
                    "path": large,
                    "name": "Dune: Part Two (2024)",
                    "stream_id": 693134,
                },
            ])
        self.assertEqual(len(exposed), 2)
        best = next(item for item in exposed if "2160p" in item["name"])
        other = next(item for item in exposed if "2160p" not in item["name"])
        self.assertEqual(best["stream_id"], 693134)
        self.assertNotEqual(other["stream_id"], 693134)
        self.assertNotIn("_indexed", best)

    def test_second_copy_stays_in_the_movie_folder(self):
        plain = "/videos/films/Dune - Part Two (2024)/Dune - Part Two (2024).mkv"
        items = [
            {"src": "/videos/films/Dune.Part.Two.2024.2160p.mkv", "dest": plain},
            {"src": plain, "dest": plain},
        ]
        separated = organize_library.separate_quality_copies(items)
        dests = [item["dest"] for item in separated]
        self.assertIn(
            "/videos/films/Dune - Part Two (2024)/Dune - Part Two (2024) [2160p].mkv",
            dests,
        )
        self.assertIn(plain, dests)

    def test_fetch_metadata_known_movies(self):
        # Test specific known troublesome movies
        movies = [
            "1001 pattes (1998)",
            "Dragons - 2010",
            "Doctor Sleep 2019 MULTi 1080p Bluray x265-BULMA"
        ]
        for m in movies:
            meta = server.fetch_tmdb_metadata(m, is_series=False)
            self.assertTrue(meta and meta.get("poster"), f"Failed to scrape metadata/poster for: {m}")

    def test_show_category_name_uses_primary_genre(self):
        record = {
            "genres": ["Drame", "Crime"],
            "genre_category": "FR | Drame",
        }
        self.assertEqual(server.show_category_name(record), "FR | Drame")
        self.assertEqual(
            server.show_category_name({"genre_category": "FR | Animation"}),
            "FR | Animation",
        )
        self.assertEqual(server.show_category_name({}), "FR | Séries")

    def test_series_and_vod_share_label_but_not_id(self):
        label = "FR | Animation"
        vod_id = server.stable_category_id(label, "vod")
        series_id = server.stable_category_id(label, "series")
        self.assertNotEqual(vod_id, series_id)
        self.assertEqual(server.movie_category_name({"genres": ["Animation"]}), label)
        self.assertEqual(server.show_category_name({"genres": ["Animation"]}), label)

    def test_series_list_item_includes_tmdb_fields(self):
        video = {
            "series_id": "12609",
            "category_id": "4942033",
            "added": "1700000000",
            "meta": {
                "id": 12609,
                "title": "Dragon Ball",
                "poster": "https://image.tmdb.org/t/p/w500/poster.jpg",
                "backdrop": "https://image.tmdb.org/t/p/original/back.jpg",
                "overview": "Plot",
                "cast": "Goku",
                "director": "",
                "tmdb_genres": ["Animation", "Action & Adventure"],
                "genre": "FR | Animation",
                "release_date": "1986-02-26",
                "rating": "8.2",
            },
        }
        item = server.series_list_item(video, 1)
        self.assertEqual(item["num"], 1)
        self.assertEqual(item["series_id"], 12609)
        self.assertEqual(item["tmdb"], "12609")
        self.assertEqual(item["name"], "Dragon Ball")
        self.assertEqual(item["releaseDate"], "1986-02-26")
        self.assertEqual(item["release_date"], "1986-02-26")
        self.assertEqual(item["genre"], "Animation / Action & Adventure")
        self.assertEqual(item["backdrop_path"], ["https://image.tmdb.org/t/p/original/back.jpg"])
        self.assertEqual(item["category_ids"], [4942033])
        self.assertIn("rating_5based", item)
        self.assertIn("last_modified", item)

    def test_series_info_payload_matches_xtream_shape(self):
        episodes = [
            {
                "series_id": "12609",
                "category_id": "4942033",
                "added": "1700000001",
                "season": 1,
                "episode_num": 1,
                "episode_title": "Bulma",
                "name": "Dragon Ball - S01E01 - Bulma",
                "container_extension": "mkv",
                "stream_id": 1001,
                "path": "/tmp/missing.mkv",
                "meta": {
                    "id": 12609,
                    "title": "Dragon Ball",
                    "poster": "https://image.tmdb.org/t/p/w500/ea8V.jpg",
                    "backdrop": "https://image.tmdb.org/t/p/original/30L4.jpg",
                    "overview": "Plot text",
                    "cast": "Goku",
                    "director": "Toriyama",
                    "tmdb_genres": ["Animation", "Action & Adventure"],
                    "release_date": "1986-02-26",
                    "rating": "8.3",
                },
            },
            {
                "series_id": "12609",
                "category_id": "4942033",
                "added": "1700000002",
                "season": 1,
                "episode_num": 2,
                "episode_title": "",
                "name": "Dragon Ball - S01E02",
                "container_extension": "mkv",
                "stream_id": 1002,
                "path": "/tmp/missing2.mkv",
                "meta": {
                    "id": 12609,
                    "title": "Dragon Ball",
                    "poster": "https://image.tmdb.org/t/p/w500/ea8V.jpg",
                    "backdrop": "https://image.tmdb.org/t/p/original/30L4.jpg",
                    "overview": "Plot text",
                    "cast": "Goku",
                    "director": "Toriyama",
                    "tmdb_genres": ["Animation", "Action & Adventure"],
                    "release_date": "1986-02-26",
                    "rating": "8.3",
                },
            },
        ]
        payload = server.series_info_payload(episodes)
        info = payload["info"]
        self.assertEqual(sorted(payload.keys()), ["episodes", "info", "seasons"])
        self.assertEqual(info["tmdb"], "12609")
        self.assertEqual(info["category_ids"], [4942033])
        self.assertEqual(info["rating_5based"], "4.2")
        self.assertEqual(info["last_modified"], "1700000002")
        self.assertEqual(info["genre"], "Animation, Action & Adventure")
        season = payload["seasons"][0]
        self.assertEqual(season["episode_count"], "2")
        self.assertEqual(season["cover_tmdb"], "/ea8V.jpg")
        self.assertIn("overview", season)
        ep = payload["episodes"]["1"][0]
        self.assertEqual(ep["id"], "1001")
        self.assertEqual(ep["season"], 1)
        self.assertEqual(ep["added"], "1700000001")
        self.assertIn("direct_source", ep)
        self.assertEqual(ep["info"]["id"], 12609)
        self.assertEqual(ep["info"]["movie_image"], "https://image.tmdb.org/t/p/w500/ea8V.jpg")

if __name__ == "__main__":
    unittest.main()
