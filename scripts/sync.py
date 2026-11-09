"""Sync the YouTube playlist into data/videos.json and regenerate both markdown files.

Env: YOUTUBE_API_KEY, PLAYLIST_ID (required); GEMINI_API_KEY, GEMINI_MODEL, MAX_NEW (optional).
Flags: --dry-run  show what would be added without writing anything.
"""
import argparse
import os
import sys

import categorize as cat
import render
import youtube as yt

KEYS = ["id", "title", "url", "channel", "duration", "views", "likes", "comments",
        "thumbnail", "description", "category", "subcategory"]


def find_new(existing, items):
    """Playlist ids not in the data yet, newest-added first (ties keep playlist order)."""
    known, seen, new = {v["id"] for v in existing}, set(), []
    for vid, added in items:
        if vid in known or vid in seen:
            continue
        seen.add(vid)
        new.append((vid, added))
    new.sort(key=lambda t: t[1], reverse=True)
    return [vid for vid, _ in new]


def collect_new(existing, taxonomy, items, fetch, generate, models=None, max_new=50, log=print):
    ids = find_new(existing, items)
    if not ids:
        return []
    if len(ids) > max_new:
        raise SystemExit(
            f"Found {len(ids)} new videos, above the safety cap of {max_new}. "
            "Check PLAYLIST_ID, or re-run with a higher MAX_NEW."
        )
    meta = fetch(ids)
    for vid in ids:
        if vid not in meta:
            log(f"Skipping {vid}: private or deleted (will be retried next run).")
    fresh = [meta[vid] for vid in ids if vid in meta]
    cats = cat.categorize(fresh, taxonomy, existing, generate, models=models, log=log)
    out = []
    for v in fresh:
        v = dict(v)
        v["category"], v["subcategory"] = cats[v["id"]]
        out.append({k: v[k] for k in KEYS})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    yt_key, playlist = os.environ.get("YOUTUBE_API_KEY"), os.environ.get("PLAYLIST_ID")
    if not yt_key or not playlist:
        sys.exit("YOUTUBE_API_KEY and PLAYLIST_ID must be set.")
    g_key = os.environ.get("GEMINI_API_KEY")
    generate = cat.gemini_generate(g_key) if g_key else None
    models = [os.environ.get("GEMINI_MODEL", "").strip()] + cat.DEFAULT_MODELS
    max_new = int(os.environ.get("MAX_NEW") or 50)

    existing, taxonomy = render.load_json("videos.json"), render.load_json("taxonomy.json")
    items = yt.playlist_items(playlist, yt_key)
    print(f"Playlist has {len(items)} items; data has {len(existing)} videos.")
    new = collect_new(existing, taxonomy, items, lambda ids: yt.fetch_videos(ids, yt_key),
                      generate, models, max_new)
    for v in new:
        print(f"+ {v['title']}  ->  {v['category']} / {v['subcategory']}")
    if args.dry_run:
        print(f"Dry run: {len(new)} new video(s), nothing written.")
        return
    videos = new + existing
    if new:
        render.save_json("videos.json", videos)
    render.write_all(videos)
    print(f"Added {len(new)} video(s); {len(videos)} total.")


if __name__ == "__main__":
    main()
