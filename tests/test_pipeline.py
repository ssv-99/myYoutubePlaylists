import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import categorize as cat  # noqa: E402
import render  # noqa: E402
import sync  # noqa: E402
import youtube as yt  # noqa: E402

TAX = render.load_json("taxonomy.json")
EXISTING = render.load_json("videos.json")


def fake_get(path, params, key):
    if path == "playlistItems":
        pages = {
            None: {"items": [item("NEW_B______", "2026-11-09T10:00:00Z"),
                             item(EXISTING[0]["id"], "2026-11-01T00:00:00Z")],
                   "nextPageToken": "p2"},
            "p2": {"items": [item("NEW_A______", "2026-11-08T10:00:00Z"),
                             item("PRIVATE____", "2026-11-07T10:00:00Z"),
                             item("NEW_B______", "2026-11-09T10:00:00Z")]},
        }
        return pages[params.get("pageToken")]
    if path == "videos":
        ids = params["id"].split(",")
        items = []
        for i in ids:
            if i == "PRIVATE____":
                continue
            items.append({"id": i,
                          "snippet": {"title": f" Title {i} ", "channelTitle": "Chan",
                                      "description": "line1\r\nline2\r\n\r\n"},
                          "contentDetails": {"duration": "PT1H2M3S" if i == "NEW_A______" else "PT38S"},
                          "statistics": {"viewCount": "1234567", "likeCount": "10"}})  # no commentCount
        return {"items": items}
    raise AssertionError(path)


def item(vid, added):
    return {"contentDetails": {"videoId": vid}, "snippet": {"publishedAt": added}}


class Pipeline(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(yt.parse_duration("PT38S"), "0:38")
        self.assertEqual(yt.parse_duration("PT3M53S"), "3:53")
        self.assertEqual(yt.parse_duration("PT1H14M51S"), "1:14:51")
        self.assertEqual(yt.parse_duration("PT3H"), "3:00:00")
        self.assertEqual(yt.parse_duration("P1DT1H"), "25:00:00")

    def test_find_new_order_and_dedupe(self):
        items = yt.playlist_items("x", "k", get=fake_get)
        self.assertEqual(len(items), 5)
        self.assertEqual(sync.find_new(EXISTING, items), ["NEW_B______", "NEW_A______", "PRIVATE____"])

    def test_end_to_end(self):
        items = yt.playlist_items("x", "k", get=fake_get)
        c0, s0 = TAX["categories"][0]["name"], TAX["categories"][0]["subcategories"][0]

        def gen(model, prompt, schema):
            self.assertIn(c0, prompt)
            return json.dumps([
                {"id": "NEW_A______", "category": c0, "subcategory": s0},
                {"id": "NEW_B______", "category": c0, "subcategory": "Not A Real Subcategory"},
            ])

        logs = []
        new = sync.collect_new(EXISTING, TAX, items, lambda ids: yt.fetch_videos(ids, "k", get=fake_get),
                               gen, log=logs.append)
        self.assertEqual([v["id"] for v in new], ["NEW_B______", "NEW_A______"])  # PRIVATE skipped
        b, a = new
        self.assertEqual((a["category"], a["subcategory"]), (c0, s0))
        self.assertEqual((b["category"], b["subcategory"]), cat.FALLBACK)  # invalid -> fallback
        self.assertEqual(a["duration"], "1:02:03")
        self.assertEqual(a["views"], "1,234,567")
        self.assertEqual(a["comments"], "N/A")
        self.assertEqual(a["title"], "Title NEW_A______")
        self.assertEqual(a["description"], "line1\nline2")
        self.assertTrue(any("private or deleted" in l for l in logs))
        videos = new + EXISTING
        md = render.render_original(videos)
        self.assertTrue(md.startswith("# Learning Resources\n\n### 1. Title NEW_B______\n"))
        self.assertIn(f"### 3. {EXISTING[0]['title']}\n", md)  # old entries shift down
        cm = render.render_categorized(videos, TAX, render.load_json("playlists.json"))
        self.assertIn(f"**{len(videos)} resources**", cm)

    def test_model_fallback_and_missing_key(self):
        v = [{"id": "X", "title": "t", "channel": "c", "description": ""}]
        c0, s0 = TAX["categories"][0]["name"], TAX["categories"][0]["subcategories"][0]
        calls = []

        def gen(model, prompt, schema):
            calls.append(model)
            if model == "bad-model":
                raise RuntimeError("404 models/bad-model is not found")
            return json.dumps([{"id": "X", "category": c0, "subcategory": s0}])

        out = cat.categorize(v, TAX, EXISTING, gen, models=["bad-model", "good"], sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(out["X"], (c0, s0))
        self.assertEqual(calls, ["bad-model", "good"])  # 404 -> no retries on the bad model
        self.assertEqual(cat.categorize(v, TAX, EXISTING, None, log=lambda m: None)["X"], cat.FALLBACK)

    def test_all_models_fail_falls_back(self):
        v = [{"id": "X", "title": "t", "channel": "c", "description": ""}]

        def gen(model, prompt, schema):
            raise RuntimeError("boom")

        out = cat.categorize(v, TAX, EXISTING, gen, models=["m"], sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(out["X"], cat.FALLBACK)

    def test_max_new_cap(self):
        items = [(f"ID{i:09d}", "2026-01-01T00:00:00Z") for i in range(5)]
        with self.assertRaises(SystemExit):
            sync.collect_new(EXISTING, TAX, items, lambda ids: {}, None, max_new=3)

    def test_taxonomy_covers_data(self):
        pairs = cat.valid_pairs(TAX)
        self.assertTrue(all((v["category"], v["subcategory"]) in pairs for v in EXISTING))
        self.assertIn(cat.FALLBACK, pairs)


if __name__ == "__main__":
    unittest.main()
