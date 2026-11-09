"""Guards against the committed markdown drifting from data/*.json (run locally)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import render  # noqa: E402


class Committed(unittest.TestCase):
    def test_markdown_matches_data(self):
        v = render.load_json("videos.json")
        self.assertEqual(render.ORIGINAL_MD.read_bytes().decode("utf-8"), render.render_original(v))
        self.assertEqual(
            render.CATEGORIZED_MD.read_bytes().decode("utf-8"),
            render.render_categorized(v, render.load_json("taxonomy.json"), render.load_json("playlists.json")),
        )


if __name__ == "__main__":
    unittest.main()
