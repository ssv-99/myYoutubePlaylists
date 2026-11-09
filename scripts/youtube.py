"""Minimal YouTube Data API v3 client (API key, read-only)."""
import re

import requests

API = "https://www.googleapis.com/youtube/v3"


class YouTubeError(RuntimeError):
    pass


def api_get(path, params, key):
    r = requests.get(f"{API}/{path}", params={**params, "key": key}, timeout=30)
    if r.status_code != 200:
        try:
            msg = r.json()["error"]["message"]
        except Exception:  # noqa: BLE001
            msg = r.text[:300]
        raise YouTubeError(f"YouTube API '{path}' failed ({r.status_code}): {msg}")
    return r.json()


def playlist_items(playlist_id, key, get=api_get):
    """Return [(video_id, added_to_playlist_at)] in the order the API returns them."""
    out, token = [], None
    while True:
        params = {"part": "snippet,contentDetails", "maxResults": 50, "playlistId": playlist_id}
        if token:
            params["pageToken"] = token
        data = get("playlistItems", params, key)
        for it in data.get("items", []):
            out.append((it["contentDetails"]["videoId"], it["snippet"].get("publishedAt", "")))
        token = data.get("nextPageToken")
        if not token:
            return out


def parse_duration(iso):
    """ISO 8601 (PT1H2M3S) -> '1:02:03' / '2:03' / '0:38', the format used in the data."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", iso or "")
    if not m:
        return "0:00"
    d, h, mi, s = (int(x or 0) for x in m.groups())
    h += d * 24
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def fmt_count(value):
    return "N/A" if value is None else f"{int(value):,}"


def fetch_videos(ids, key, get=api_get):
    """Return {video_id: record}. Private/deleted videos are simply absent."""
    out = {}
    for i in range(0, len(ids), 50):
        data = get(
            "videos",
            {"part": "snippet,contentDetails,statistics", "id": ",".join(ids[i : i + 50])},
            key,
        )
        for it in data.get("items", []):
            vid, sn, st = it["id"], it["snippet"], it.get("statistics", {})
            out[vid] = {
                "id": vid,
                "title": sn["title"].strip(),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "channel": sn.get("channelTitle", "").strip(),
                "duration": parse_duration(it.get("contentDetails", {}).get("duration")),
                "views": fmt_count(st.get("viewCount")),
                "likes": fmt_count(st.get("likeCount")),
                "comments": fmt_count(st.get("commentCount")),
                "thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
                "description": (sn.get("description") or "").replace("\r\n", "\n").replace("\r", "\n").rstrip(),
            }
    return out
