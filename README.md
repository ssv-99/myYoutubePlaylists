# Learning Resources (auto-updated)

A GitHub Action reads your YouTube playlist every day. New videos are fetched, categorized
by Gemini, added to the top, and both markdown files are regenerated and committed:

- `Learning-Resources-Original.md` — every video with full details (newest = #1)
- `Learning-Resources-n-Playlists-Categorized.md` — same data as tables by category, plus playlists

`data/videos.json` is the source of truth; both markdown files are generated from it, so they
can never drift apart. Entry numbers shift automatically whenever new videos are added.

## One-time setup

1. **Create a GitHub repo** and push this folder to it.
2. **YouTube API key** — [Google Cloud Console](https://console.cloud.google.com/) → create a project →
   enable *YouTube Data API v3* → *Credentials* → *Create credentials* → *API key*
   (restrict it to the YouTube Data API v3).
3. **Gemini API key** — create one in [Google AI Studio](https://aistudio.google.com/).
4. **Add them to the repo** — *Settings → Secrets and variables → Actions*:
   - Secrets: `YOUTUBE_API_KEY`, `GEMINI_API_KEY`
   - Variable: `PLAYLIST_ID` (the part after `list=` in the playlist URL)
   - Optional variable: `GEMINI_MODEL` (see below)
5. **Check permissions** — *Settings → Actions → General → Workflow permissions* must allow
   read and write (the workflow also requests `contents: write`).
6. **First run** — *Actions → Update learning resources → Run workflow*. Open the log and check
   which videos were added and how they were categorized.

Test locally first if you like (nothing is written with `--dry-run`):

```bash
pip install -r requirements.txt
export YOUTUBE_API_KEY=... GEMINI_API_KEY=... PLAYLIST_ID=...
python scripts/sync.py --dry-run
```

## Things to know

- **Playlist visibility:** public and unlisted playlists work with an API key. A **private**
  playlist does not (it needs OAuth, which this setup doesn't include).
- **First-run safety cap:** if more than 50 unknown videos are found (`MAX_NEW`), the run stops
  instead of adding them. This usually means a wrong `PLAYLIST_ID`, or a playlist with videos
  that aren't in `data/videos.json`. Raise the cap from the *Run workflow* form if it's expected.
- **Removed videos stay** in your files; the job only adds. Private or deleted videos are skipped.
- **Fixing a category:** edit `category` / `subcategory` in `data/videos.json` (pairs must exist in
  `data/taxonomy.json`; add new ones there). Pushing a change under `data/` regenerates the
  markdown automatically, or run `python scripts/render.py` locally. Existing entries are never
  re-categorized.
- **If Gemini fails** (bad key, quota, retired model) new videos go to *Other / General → General*
  and the log says so. Nothing is lost; fix them in `videos.json`.
- **Gemini model names change.** The script tries `GEMINI_MODEL` first, then `gemini-3.5-flash`,
  `gemini-3-flash`, `gemini-2.5-flash`. If categorization falls back, set the `GEMINI_MODEL`
  variable to a current Flash model from the Gemini docs.
- **Counts:** the YouTube API returns exact view, like and comment counts. Hidden likes or disabled
  comments show as `N/A`. Old entries keep the values they had when added.
- **Scheduled runs can pause:** GitHub disables scheduled workflows in public repos after a long
  period without repo activity. If that happens, re-enable it in the Actions tab.
- Quota: each run costs roughly 2–3 YouTube API units out of 10,000 free per day.

## Layout

```
.github/workflows/update.yml   daily job
data/videos.json               all videos, newest first (source of truth)
data/taxonomy.json             allowed categories / subcategories (also the Gemini prompt)
data/playlists.json            the playlists table (edit by hand)
scripts/sync.py                playlist -> new videos -> categorize -> render
scripts/youtube.py             YouTube Data API client
scripts/categorize.py          Gemini categorization (schema-constrained)
scripts/render.py              writes the two markdown files
tests/                         python -m unittest discover -s tests
```
