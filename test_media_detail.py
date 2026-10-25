import json
import os
import tempfile
import unittest

import media_detail


class MediaDetailTest(unittest.TestCase):
    def test_probe_keeps_every_track_and_the_picture_size(self):
        detail = media_detail.detail_from_probe(
            {
                "format": {"duration": "100.4", "bit_rate": "8000000"},
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "hevc",
                        "width": 3840,
                        "height": 2160,
                        "color_transfer": "smpte2084",
                        "side_data_list": [{"side_data_type": "DOVI configuration record"}],
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "eac3",
                        "channels": 6,
                        "channel_layout": "5.1",
                        "disposition": {"default": 1},
                        "tags": {"language": "fra", "title": "VFF"},
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "truehd",
                        "channels": 8,
                        "channel_layout": "7.1",
                        "tags": {"language": "eng", "title": "Atmos"},
                    },
                    {
                        "codec_type": "subtitle",
                        "codec_name": "subrip",
                        "disposition": {"forced": 1},
                        "tags": {"language": "fra"},
                    },
                ],
            },
            {"source_size": 1000, "source_mtime_ns": 5},
        )
        self.assertNotIn("quality", detail["video"])
        self.assertEqual(detail["video"]["codec_name"], "hevc")
        self.assertEqual(detail["video"]["width"], 3840)
        self.assertEqual(detail["video"]["color_transfer"], "smpte2084")
        self.assertEqual(detail["bitrate"], 8000)
        self.assertEqual(detail["duration_secs"], 100)
        self.assertEqual(detail["duration"], "00:01:40")
        self.assertEqual(detail["audio"]["codec_name"], "eac3")
        self.assertEqual(detail["audio"]["channels"], 6)
        self.assertEqual(detail["audio"]["tags"]["language"], "fra")
        self.assertNotIn("audios", detail)
        self.assertNotIn("subtitles", detail)
        audio = media_detail.xtream_audio(detail)
        self.assertEqual(audio["tags"]["title"], "VFF")

    def test_scope_4k_is_not_labeled_from_its_short_side(self):
        self.assertEqual(media_detail.quality_from_dimensions(3840, 1606), "2160p")
        self.assertEqual(media_detail.quality_from_dimensions(1920, 800), "1080p")
        self.assertEqual(media_detail.quality_from_dimensions(1280, 720), "720p")

    def test_stale_sidecar_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "Dune - Part Two (2024).mkv")
            with open(video, "wb") as handle:
                handle.write(b"abcd")
            detail = media_detail.detail_from_probe(
                {"format": {"duration": "10"}, "streams": []},
                media_detail.source_stamp(video),
            )
            media_detail.write_detail(video, detail)
            self.assertEqual(media_detail.load_detail(video)["duration_secs"], 10)
            with open(video, "ab") as handle:
                handle.write(b"e")
            self.assertIsNone(media_detail.load_detail(video))

    def test_sidecar_uses_the_video_stem(self):
        path = media_detail.sidecar_path("/films/Dune - Part Two (2024)/Dune - Part Two (2024) [2160p].mkv")
        self.assertTrue(path.endswith("Dune - Part Two (2024) [2160p].json"))


if __name__ == "__main__":
    unittest.main()
