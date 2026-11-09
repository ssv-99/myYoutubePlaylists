"""Render the two markdown files from data/*.json.

Run on its own to regenerate them after hand-editing the data:
    python scripts/render.py
"""
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ORIGINAL_MD = ROOT / "Learning-Resources-Original.md"
CATEGORIZED_MD = ROOT / "Learning-Resources-n-Playlists-Categorized.md"


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save_json(name, obj):
    (DATA / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------- original md
def _entry(number, v):
    s = (
        f"### {number}. {v['title']}\n"
        f"- **URL**: [{v['url']}]({v['url']})\n"
        f"- **Channel**: {v['channel']}\n"
        f"- **Duration**: {v['duration']}\n"
        f"- **Views**: {v['views']}\n"
        f"- **Likes**: {v['likes']}\n"
        f"- **Comments**: {v['comments']}\n"
        f"- **Thumbnail**: [View Image]({v['thumbnail']})\n"
    )
    desc = v.get("description", "")
    if desc:
        s += "- **Description**:\n" + "\n".join("  " + l for l in desc.split("\n")) + "\n"
    return s + "\n"


def render_original(videos):
    """videos[0] is the newest and becomes entry 1."""
    return "# Learning Resources\n\n" + "".join(
        _entry(i, v) for i, v in enumerate(videos, 1)
    )


# ------------------------------------------------------------ categorized md
def esc(s):
    s = str(s).strip().replace("\\", "\\\\")
    for ch in "|*[]`$<>":
        s = s.replace(ch, "\\" + ch)
    return re.sub(r"(?<!\w)_|_(?!\w)", r"\\_", s)


def slug(heading):  # GitHub-style heading anchor
    h = re.sub(r"[^\w\- ]", "", heading.lower().strip(), flags=re.UNICODE)
    return h.replace(" ", "-")


def render_categorized(videos, taxonomy, playlists):
    numbered = [(i, v) for i, v in enumerate(videos, 1)]
    cat_order = [c["name"] for c in taxonomy["categories"]]
    for _, v in numbered:  # categories missing from the taxonomy go last
        if v["category"] not in cat_order:
            cat_order.append(v["category"])
    by_cat = collections.OrderedDict((c, []) for c in cat_order)
    for n, v in numbered:
        by_cat[v["category"]].append((n, v))
    cats = [c for c in cat_order if by_cat[c]]

    L = ["# Learning Resources — Categorized\n"]
    L.append(
        f"**{len(videos)} resources** across **{len(cats)} categories**, plus "
        f"**{len(playlists)} saved playlists**. The **#** column is the entry number "
        "in `Learning-Resources-Original.md` (newest = 1).\n"
    )
    L.append("## Contents\n")
    L += ["| Category | Resources |", "|:--|--:|"]
    for c in cats:
        L.append(f"| [{esc(c)}](#{slug(c)}) | {len(by_cat[c])} |")
    L.append(f"| **Total** | **{len(videos)}** |")
    L.append(f"| [Playlists](#playlists) | {len(playlists)} |")
    L.append("")
    for c in cats:
        L += ["---\n", f"## {c}\n"]
        subs = collections.defaultdict(list)
        for n, v in by_cat[c]:
            subs[v["subcategory"]].append((n, v))
        for s in sorted(subs):
            items = sorted(subs[s], key=lambda t: t[0])
            L.append(f"### {s} ({len(items)})\n")
            L.append("| # | Title | Channel | Duration | Views | Likes | Comments |")
            L.append("|--:|:--|:--|:-:|--:|--:|--:|")
            for n, v in items:
                L.append(
                    f"| {n} | [{esc(v['title'])}]({v['url']}) | {esc(v['channel'])} | "
                    f"{v['duration']} | {v['views']} | {v['likes']} | {v['comments']} |"
                )
            L.append("")
    L += ["---\n", "## Playlists\n", "| Playlist | Channel |", "|:--|:--|"]
    for p in playlists:
        L.append(f"| {esc(p['name'])} | {esc(p['channel'])} |")
    L.append("")
    return "\n".join(L)


def write_all(videos=None):
    videos = videos if videos is not None else load_json("videos.json")
    ORIGINAL_MD.write_text(render_original(videos), encoding="utf-8", newline="")
    CATEGORIZED_MD.write_text(
        render_categorized(videos, load_json("taxonomy.json"), load_json("playlists.json")),
        encoding="utf-8",
        newline="",
    )


if __name__ == "__main__":
    write_all()
    print("Regenerated both markdown files.")
