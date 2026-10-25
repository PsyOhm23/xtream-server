import base64
import unittest
from datetime import datetime, timezone

import demo_config
import demo_epg
import demo_generator
import server


class TestDemoCatalog(unittest.TestCase):
    def test_same_id_stays_stable_across_builds(self):
        first = demo_generator.build_catalog("demo_fr")
        second = demo_generator.build_catalog("demo_fr")
        self.assertEqual(
            [(item["stream_id"], item["name"]) for item in first],
            [(item["stream_id"], item["name"]) for item in sles films et séries ne poinent econd],
        )

    def test_language_follows_the_username(self):
        self.assertEqual(demo_generator.language_for("demo_en"), "en")
        self.assertEqual(demo_generator.language_for("demo_fr"), "fr")
        self.assertEqual(demo_generator.language_for("demo"), "fr")
        french = demo_generator.build_catalog("demo_fr")
        english = demo_generator.build_catalog("demo_en")
        fr_live = next(item for item in french if item["kind"] == "live")
        en_live = next(item for item in english if item["stream_id"] == fr_live["stream_id"])
        self.assertEqual(fr_live["category_name"], "Divertissement")
        self.assertEqual(en_live["category_name"], "Entertainment")
        self.assertNotEqual(fr_live["name"], en_live["name"])

    def test_heroes_lead_vod_and_keep_real_tmdb_ids(self):
        movies = [item for item in demo_generator.build_catalog("demo") if item["kind"] == "movie"]
        heroes = movies[:6]
        self.assertEqual([item["stream_id"] for item in heroes], [2001, 2002, 2003, 2004, 2005, 2006])
        self.assertEqual(
            [item["meta"]["id"] for item in heroes],
            [45745, 133701, 10378, 358332, 593048, 891761],
        )
        self.assertEqual(heroes[0]["name"], "Sintel (2010)")
        self.assertTrue(heroes[0]["meta"]["overview"].endswith(demo_config.BLENDER_CREDIT))
        self.assertEqual(heroes[5]["name"], "Sprite Fright (2021)")
        self.assertTrue(heroes[0]["meta"]["poster"].startswith("https://image.tmdb.org/t/p/w500/"))
        generated = movies[6:]
        self.assertEqual(len(generated), len(demo_config.VOD_CATEGORIES) * demo_config.MOVIES_PER_CAT)
        self.assertTrue(all(item["meta"]["id"] == 0 for item in generated))
        self.assertTrue(all("/seed/movie_" in item["meta"]["poster"] for item in generated))
        allowed = set(demo_config.TITLE_WORDS["fr"]["adjectives"] + demo_config.TITLE_WORDS["fr"]["nouns"])
        for item in generated:
            parts = item["meta"]["title"].split()
            self.assertEqual(len(parts), 2)
            self.assertTrue(all(part in allowed for part in parts))

    def test_series_shape_and_channel_count(self):
        videos = demo_generator.build_catalog("demo_fr")
        live = [item for item in videos if item["kind"] == "live"]
        self.assertEqual(len(live), len(demo_config.LIVE_CATEGORIES) * demo_config.LIVE_PER_CAT)
        self.assertTrue(live[0]["meta"]["poster"].startswith("https://api.dicebear.com/"))
        self.assertEqual(live[0]["epg_channel_id"], f"ch_{live[0]['stream_id']}")
        series_id = 30000 + 30 * 100 + 1
        episodes = [item for item in videos if item["series_id"] == series_id]
        self.assertEqual(len(episodes), demo_config.SEASONS_PER_SERIES * demo_config.EPISODES_PER_SEASON)
        self.assertEqual(episodes[0]["duration_secs"], 1800)
        self.assertEqual(episodes[0]["container_extension"], "mp4")


class TestDemoApi(unittest.TestCase):
    def setUp(self):
        server._catalog_cache.clear()
        server._catalog_cache.update({
            "library_mtime": None,
            "built": 0,
            "refreshing": False,
            "videos": None,
            "categories": None,
            "by_id": {},
        })
        self.client = server.app.test_client()

    def test_login_categories_and_filtered_streams(self):
        login = self.client.get("/player_api.php?username=demo_fr&password=demo_fr")
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["user_info"]["status"], "Active")

        categories = self.client.get("/player_api.php?username=demo_fr&password=demo_fr&action=get_vod_categories")
        ids = [row["category_id"] for row in categories.get_json()]
        self.assertEqual(ids, ["20", "21", "22", "23"])
        self.assertEqual(categories.get_json()[0]["category_name"], "Animation Open-Source")

        english = self.client.get("/player_api.php?username=demo_en&password=demo_en&action=get_live_categories")
        self.assertEqual(
            [row["category_name"] for row in english.get_json()],
            ["Entertainment", "Movies & Drama", "Nature & Docs", "Sports & Action", "Kids & Toons"],
        )

        live = self.client.get("/player_api.php?username=demo_fr&password=demo_fr&action=get_live_streams&category_id=10")
        rows = live.get_json()
        self.assertEqual(len(rows), demo_config.LIVE_PER_CAT)
        self.assertTrue(all(row["epg_channel_id"].startswith("ch_") for row in rows))
        self.assertTrue(all(row["category_id"] == "10" for row in rows))
        self.assertTrue(all(row["direct_source"] in demo_config.LIVE_HLS_STREAMS for row in rows))

        admin = self.client.get("/player_api.php?username=admin&password=admin&action=get_live_streams")
        self.assertEqual(admin.get_json(), [])

    def test_vod_and_series_details(self):
        info = self.client.get("/player_api.php?username=demo&password=demo&action=get_vod_info&vod_id=2001")
        body = info.get_json()
        self.assertEqual(body["info"]["tmdb_id"], 45745)
        self.assertEqual(body["movie_data"]["container_extension"], "mp4")
        self.assertIn("duration_secs", body["info"])
        self.assertTrue(body["info"]["backdrop_path"][0].startswith("https://image.tmdb.org/t/p/"))

        plain = self.client.get("/player_api.php?username=demo&password=demo&action=get_vod_info&vod_id=22001")
        self.assertNotIn("tmdb_id", plain.get_json()["info"])

        series = self.client.get("/player_api.php?username=demo_en&password=demo_en&action=get_series_info&series_id=33001")
        payload = series.get_json()
        self.assertEqual(len(payload["seasons"]), 2)
        self.assertEqual(payload["seasons"][0]["name"], "Season 1")
        self.assertEqual(len(payload["episodes"]["1"]), 4)
        self.assertEqual(payload["episodes"]["1"][0]["container_extension"], "mp4")
        self.assertEqual(payload["episodes"]["1"][0]["info"]["duration_secs"], 1800)
        self.assertNotIn("tmdb", payload["info"])

    def test_epg_xmltv_and_redirects(self):
        epg = self.client.get("/player_api.php?username=demo_en&password=demo_en&action=get_short_epg&stream_id=11001")
        listings = epg.get_json()["epg_listings"]
        self.assertEqual(len(listings), 4)
        title = base64.b64decode(listings[0]["title"]).decode("utf-8")
        self.assertTrue(title)
        self.assertIn("start_timestamp", listings[0])
        self.assertIn("stop_timestamp", listings[0])

        guide = self.client.get("/xmltv.php?username=demo_fr&password=demo_fr")
        self.assertEqual(guide.status_code, 200)
        text = guide.get_data(as_text=True)
        self.assertIn("<tv", text)
        self.assertIn('id="ch_11001"', text)
        self.assertIn("+0000", text)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        self.assertGreater(text.count("<programme "), 25 * 20)

        movie = self.client.get("/movie/demo_fr/demo_fr/2001.mp4")
        self.assertEqual(movie.status_code, 302)
        self.assertIn(movie.headers["Location"], demo_config.MP4_STREAMS)

        hls = self.client.get("/movie/demo_fr/demo_fr/2001.m3u8")
        self.assertEqual(hls.status_code, 302)
        self.assertIn(hls.headers["Location"], demo_config.HLS_STREAMS)

        filler = self.client.get("/movie/demo_fr/demo_fr/22001.mp4")
        series = self.client.get("/series/demo_en/demo_en/3300111.mp4")
        live = self.client.get("/live/demo_fr/demo_fr/11001.m3u8")
        short = self.client.get("/demo/demo/11101")
        self.assertEqual(filler.status_code, 302)
        self.assertIn(filler.headers["Location"], demo_config.MP4_STREAMS)
        self.assertIn(series.headers["Location"], demo_config.MP4_STREAMS)
        self.assertIn(live.headers["Location"], demo_config.LIVE_HLS_STREAMS)
        self.assertNotIn(live.headers["Location"], demo_config.HLS_STREAMS)
        self.assertEqual(short.status_code, 302)
        self.assertIn(short.headers["Location"], demo_config.LIVE_HLS_STREAMS)
        self.assertEqual(self.client.get("/demo/demo/2001").status_code, 404)

    def test_epg_slot_is_stable_inside_the_same_hour(self):
        video = {"stream_id": 11001, "epg_channel_id": "ch_11001", "name": "Demo"}
        moment = datetime(2026, 10, 25, 18, 17, tzinfo=timezone.utc)
        later = datetime(2026, 10, 25, 18, 59, tzinfo=timezone.utc)
        left = demo_epg.short_epg(video, "en", now=moment)
        right = demo_epg.short_epg(video, "en", now=later)
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
