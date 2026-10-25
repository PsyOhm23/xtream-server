import unittest

import media_match


class ParseTests(unittest.TestCase):
    def test_scene_name_keeps_title_and_year(self):
        parsed = media_match.parse_media_name("Doctor Sleep 2019 MULTi 1080p Bluray x265-BULMA.mkv")
        self.assertEqual(parsed.title, "Doctor Sleep")
        self.assertEqual(parsed.year, 2019)

    def test_number_in_title_is_kept(self):
        parsed = media_match.parse_media_name("1001 pattes (1998).mkv")
        self.assertIn("1001", parsed.title)
        self.assertIn("pattes", parsed.title.lower())
        self.assertEqual(parsed.year, 1998)

    def test_title_that_looks_like_a_year_is_kept(self):
        parsed = media_match.parse_media_name("1917.2019.MULTi.1080p.mkv")
        self.assertEqual(parsed.title, "1917")
        self.assertEqual(parsed.year, 2019)

    def test_cloverfield_keeps_its_number(self):
        parsed = media_match.parse_media_name("10 Cloverfield Lane (2016) MULTi [1080p] BluRay x264-PopHD.mkv")
        self.assertTrue(parsed.title.startswith("10 Cloverfield"))
        self.assertEqual(parsed.year, 2016)

    def test_leading_index_is_an_alternate_query(self):
        parsed = media_match.parse_media_name("60. Kuzco, L'Empereur Megalo (2000).mkv")
        self.assertEqual(parsed.year, 2000)
        self.assertTrue(any("Kuzco" in alt for alt in parsed.alts))

    def test_episode_numbers(self):
        parsed = media_match.parse_media_name("Game of Thrones S01E01 Winter Is Coming.mkv")
        self.assertEqual(parsed.season, 1)
        self.assertEqual(parsed.episode, 1)

    def test_french_subtitle_is_kept(self):
        parsed = media_match.parse_media_name(
            "Hunger Games 2 - L'Embrasement [1080p] MULTi 2013 BluRay x264-PopHD.mkv"
        )
        self.assertIn("Embrasement", parsed.title)
        self.assertEqual(parsed.year, 2013)

    def test_doubled_first_word_is_collapsed(self):
        parsed = media_match.parse_media_name("Kingsman Kingsman The Secret Service (2014).mkv")
        self.assertEqual(parsed.title, "Kingsman The Secret Service")

    def test_release_leftovers_are_removed(self):
        dune = media_match.parse_media_name(
            "Dune.Part.Two.2024.MULTI.VFF.2160p.WEBRip.DV.HDR10+.DDP.5.1.Atmos.x265.HEVC-ESPER.mkv"
        )
        self.assertEqual(dune.title, "Dune Part Two")
        self.assertEqual(dune.year, 2024)

        belle = media_match.parse_media_name("Belle.Et.Sebastien.2013.FRENCH.BRRip.XviD.AC3-S.V.avi")
        self.assertEqual(belle.title, "Belle Et Sebastien")
        self.assertEqual(belle.year, 2013)

        maze = media_match.parse_media_name(
            "Le labyrinthe la terre brulee 2015 1080p VFF EN X264 AC3 mHDgz fix son.mkv"
        )
        self.assertEqual(maze.title, "Le labyrinthe la terre brulee")
        self.assertNotIn("fix", maze.title)
        self.assertEqual(maze.year, 2015)

        neverland = media_match.parse_media_name(
            "Neverland.2004.Multi.1080p.x264.HD.Light.AC3.5.1.Sybelius.mkv"
        )
        self.assertEqual(neverland.title, "Neverland")
        self.assertEqual(neverland.year, 2004)

        nut = media_match.parse_media_name(
            "The.Nut.Job.2.Nutty.By.Nature.2017.MULTi.TRUEFRENCH.1080p.BluRay.Light.x264.AC3-ACOOL.mkv"
        )
        self.assertIn("By Nature", nut.title)
        self.assertNotIn("Light", nut.title)

        coraline = media_match.parse_media_name(
            "Coraline [2009] 1080p BRRip x264 - Qc-France-Vo By Max2Power (22).mp4"
        )
        self.assertEqual(coraline.title, "Coraline")
        self.assertEqual(coraline.year, 2009)

        ernest = media_match.parse_media_name(
            "Ernest et Celestine Mkv HD 720p FRENCH AAC 5.1 1280X720 Sprlove.mkv"
        )
        self.assertEqual(ernest.title, "Ernest et Celestine")

        kirikou = media_match.parse_media_name("KIRIKOU ET LA SOCIERE . FRENCH DVDRIP XVID AC-3 schumi.avi")
        self.assertEqual(kirikou.title, "KIRIKOU ET LA SOCIERE")

        prince = media_match.parse_media_name("Le Prince d'Egypte Dvix Français.avi")
        self.assertEqual(prince.title, "Le Prince d'Egypte")

        finale = media_match.parse_media_name("Destination Finale V - Multi.Bluray.1080p.HDlight.AAC.x265.mkv")
        self.assertEqual(finale.title, "Destination Finale 5")

    def test_trailing_roman_numeral_is_a_sequel_number(self):
        first = media_match.parse_media_name("Destination Finale I - Multi.Bluray.1080p.mkv")
        self.assertEqual(first.title, "Destination Finale")
        second = media_match.parse_media_name("Destination Finale II.mkv")
        self.assertEqual(second.title, "Destination Finale 2")
        fourth = media_match.parse_media_name("Destination Finale IV.mkv")
        self.assertEqual(fourth.title, "Destination Finale 4")
        robot = media_match.parse_media_name("I, Robot (2004).mkv")
        self.assertTrue(robot.title.lower().startswith("i"))

    def test_release_group_is_removed(self):
        parsed = media_match.parse_media_name("The Mummy (2017) VF2-ENG AC3 BluRay 1080p x264.GHT.mkv")
        self.assertEqual(parsed.title, "The Mummy")
        self.assertEqual(parsed.year, 2017)
        self.assertNotIn("GHT", parsed.title)


class MatchTests(unittest.TestCase):
    def test_exact_title_and_year_is_certain(self):
        parsed = media_match.parse_media_name("The Mummy (2017).mkv")
        candidates = [
            {"id": 1, "title": "La Momie", "original_title": "The Mummy", "release_date": "1999-05-07"},
            {"id": 2, "title": "La Momie", "original_title": "The Mummy", "release_date": "2017-06-06"},
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertIsNotNone(match)
        self.assertEqual(match.tmdb_id, 2)

    def test_duplicate_tmdb_entries_of_the_same_film_are_certain(self):
        parsed = media_match.parse_media_name("Aladdin (1992).mp4")
        candidates = [
            {"id": 1, "title": "Aladdin", "original_title": "Aladdin", "release_date": "1992-11-16", "vote_average": 6.0},
            {"id": 812, "title": "Aladdin", "original_title": "Aladdin", "release_date": "1992-11-25", "vote_average": 7.6},
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertEqual(match.tmdb_id, 812)

    def test_same_french_title_different_films_are_not_certain(self):
        parsed = media_match.parse_media_name("Rebelle (2012).mkv")
        candidates = [
            {"id": 1, "title": "Rebelle", "original_title": "Rebelle", "release_date": "2012-02-17", "vote_average": 5},
            {"id": 2, "title": "Rebelle", "original_title": "Brave", "release_date": "2012-06-21", "vote_average": 7},
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie"))

    def test_animation_folder_picks_the_only_animated_film(self):
        parsed = media_match.parse_media_name("Dragons - 2010.avi")
        candidates = [
            {
                "id": 10191,
                "title": "Dragons",
                "original_title": "How to Train Your Dragon",
                "release_date": "2010-03-18",
                "genre_ids": [16, 10751, 12],
            },
            {
                "id": 40911,
                "title": "Dragons",
                "original_title": "艋舺",
                "release_date": "2010-02-05",
                "genre_ids": [80, 18, 28],
            },
        ]
        match = media_match.pick_match(parsed, candidates, "movie", prefer_animation=True)
        self.assertEqual(match.tmdb_id, 10191)
        live = media_match.pick_match(parsed, candidates, "movie", prefer_animation=False)
        self.assertEqual(live.tmdb_id, 40911)
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie"))

    def test_two_films_of_the_same_medium_stay_uncertain(self):
        parsed = media_match.parse_media_name("Rebelle (2012).mkv")
        candidates = [
            {
                "id": 1,
                "title": "Rebelle",
                "original_title": "Rebelle",
                "release_date": "2012-02-17",
                "genre_ids": [18],
            },
            {
                "id": 2,
                "title": "Rebelle",
                "original_title": "Brave",
                "release_date": "2012-06-21",
                "genre_ids": [18, 36],
            },
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie", prefer_animation=False))

    def test_folder_does_not_choose_between_different_years(self):
        parsed = media_match.parse_media_name("La Famille Addams.mkv")
        candidates = [
            {
                "id": 2907,
                "title": "La Famille Addams",
                "original_title": "The Addams Family",
                "release_date": "1991-11-22",
                "genre_ids": [35, 14],
            },
            {
                "id": 481084,
                "title": "La Famille Addams",
                "original_title": "The Addams Family",
                "release_date": "2019-10-10",
                "genre_ids": [16, 35, 14],
            },
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie", prefer_animation=False))
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie", prefer_animation=True))

    def test_missing_genres_do_not_break_an_exact_tie(self):
        parsed = media_match.parse_media_name("Dragons - 2010.avi")
        candidates = [
            {
                "id": 10191,
                "title": "Dragons",
                "original_title": "How to Train Your Dragon",
                "release_date": "2010-03-18",
                "genre_ids": [16],
            },
            {
                "id": 40911,
                "title": "Dragons",
                "original_title": "艋舺",
                "release_date": "2010-02-05",
            },
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie", prefer_animation=True))

    def test_numbered_title_can_be_certain_without_a_year(self):
        parsed = media_match.parse_media_name("SHREK.2.TRUEFRENCH.DVDRIP.avi")
        candidates = [
            {"id": 809, "title": "Shrek 2", "original_title": "Shrek 2", "release_date": "2004-05-19"},
            {"id": 1, "title": "The Making of Shrek 2", "original_title": "The Making of Shrek 2", "release_date": "2004-05-19"},
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertEqual(match.tmdb_id, 809)

    def test_part_one_folds_like_part_1(self):
        parsed = media_match.parse_media_name("Dune - Part One (2021).mkv")
        self.assertEqual(media_match.canon(parsed.title), "dune")
        match = media_match.pick_match(
            parsed,
            [{"id": 438631, "title": "Dune", "original_title": "Dune", "release_date": "2021-09-15"}],
            "movie",
            prefer_animation=False,
        )
        self.assertEqual(match.tmdb_id, 438631)

    def test_short_title_without_a_number_or_year_is_not_certain(self):
        parsed = media_match.parse_media_name("SHREK.1.TRUEFRENCH.DVDRIP.avi")
        self.assertEqual(media_match.canon(parsed.title), "shrek")
        candidates = [
            {"id": 808, "title": "Shrek", "original_title": "Shrek", "release_date": "2001-05-18"},
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie"))
        home = media_match.parse_media_name("Home (2015).mkv".replace(" (2015)", ""))
        self.assertIsNone(media_match.pick_match(
            home,
            [{"id": 1, "title": "Home", "original_title": "Home", "release_date": "2015-03-27"}],
            "movie",
        ))

    def test_near_title_does_not_block_a_unique_exact_alternative(self):
        parsed = media_match.parse_media_name("SHREK.4.TRUEFRENCH.DVDRIP.avi")
        candidates = [
            {
                "id": 25523,
                "title": "Shrek 4-D",
                "original_title": "Shrek 3-D",
                "release_date": "2004-04-03",
                "alt_titles": ["Shrek 4D"],
            },
            {
                "id": 10192,
                "title": "Shrek 4 : Il était une fin",
                "original_title": "Shrek Forever After",
                "release_date": "2010-05-16",
                "alt_titles": ["Shrek 4"],
            },
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertEqual(match.tmdb_id, 10192)

    def test_numbered_alternative_title_beats_a_closer_partial_name(self):
        parsed = media_match.parse_media_name("SHREK.3.TRUEFRENCH.DVDRIP.avi")
        candidates = [
            {"id": 25523, "title": "Shrek 3-D", "original_title": "Shrek 3-D", "release_date": "2004-04-03"},
            {
                "id": 810,
                "title": "Shrek le troisième",
                "original_title": "Shrek the Third",
                "release_date": "2007-05-17",
                "alt_titles": ["Shrek 3"],
            },
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertEqual(match.tmdb_id, 810)

    def test_same_title_without_year_is_not_certain(self):
        parsed = media_match.parse_media_name("The Mummy.mkv")
        candidates = [
            {"id": 1, "title": "The Mummy", "original_title": "The Mummy", "release_date": "1999-05-07"},
            {"id": 2, "title": "The Mummy", "original_title": "The Mummy", "release_date": "2017-06-06"},
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie"))

    def test_exact_title_accepts_a_one_year_shift(self):
        parsed = media_match.parse_media_name("Mutafukaz (2017).mkv")
        candidates = [
            {"id": 461615, "title": "Mutafukaz", "original_title": "Mutafukaz", "release_date": "2018-05-23"},
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertIsNotNone(match)
        self.assertEqual(match.year, 2018)

    def test_fuzzy_title_rejects_a_one_year_shift(self):
        parsed = media_match.parse_media_name("Mutafukaz Returns (2017).mkv")
        candidates = [
            {"id": 1, "title": "Mutafukaz", "original_title": "Mutafukaz", "release_date": "2018-05-23"},
        ]
        self.assertIsNone(media_match.pick_match(parsed, candidates, "movie"))

    def test_sequel_does_not_match_the_first_film(self):
        parsed = media_match.parse_media_name("The Matrix Reloaded (2003).mkv")
        candidates = [
            {"id": 603, "title": "The Matrix", "original_title": "The Matrix", "release_date": "1999-03-31"},
            {"id": 604, "title": "The Matrix Reloaded", "original_title": "The Matrix Reloaded", "release_date": "2003-05-15"},
        ]
        match = media_match.pick_match(parsed, candidates, "movie")
        self.assertEqual(match.tmdb_id, 604)

    def test_french_punctuation_still_matches(self):
        self.assertEqual(media_match.title_score("Vice Versa", "Vice-versa"), 1.0)
        self.assertGreater(media_match.title_score("Hunger Games", "The Hunger Games"), 0.99)

    def test_display_title_follows_the_filename_language(self):
        parsed = media_match.parse_media_name("The Mummy (2017).mkv")
        self.assertEqual(
            media_match.choose_display_title(parsed, "La Momie", "The Mummy"),
            "The Mummy",
        )
        french = media_match.parse_media_name("Les aristochats - 1970.mkv")
        self.assertEqual(
            media_match.choose_display_title(french, "Les Aristochats", "The Aristocats"),
            "Les Aristochats",
        )
        volt = media_match.parse_media_name("Volt - 2008.avi")
        self.assertEqual(
            media_match.choose_display_title(volt, "Volt, star malgré lui", "Bolt"),
            "Volt, star malgré lui",
        )


class GenrePriorityTests(unittest.TestCase):
    def test_animation_beats_earlier_genres(self):
        self.assertEqual(
            media_match.primary_genre(["Familial", "Comédie", "Animation", "Aventure"]),
            "Animation",
        )

    def test_unlisted_genres_keep_tmdb_order(self):
        self.assertEqual(
            media_match.primary_genre(["Action", "Aventure", "Comédie"]),
            "Action",
        )

    def test_empty_genres(self):
        self.assertEqual(media_match.primary_genre([]), "")
        self.assertEqual(media_match.primary_genre(None), "")


if __name__ == "__main__":
    unittest.main()
