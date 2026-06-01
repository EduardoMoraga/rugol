"""Custom YouTube MCP server (stdio).

Why this script exists
----------------------
The npm ecosystem of YouTube MCP servers is fragmented and unreliable
(`youtube-mcp-server` doesn't expose a binary, `zubeid-youtube-mcp-server`
ships with a broken CommonJS bundle that fails to resolve
`@modelcontextprotocol/sdk`). We need this for delichul to do real
discovery, so v0.6 ships our own — ~200 lines, stdlib only, talks the
plain MCP JSON-RPC handshake, calls the YouTube Data API v3 directly.

Tools exposed
-------------
- `search_videos(query, max_results=5, published_after=None, order="date", region_code=None, lang=None)`
- `get_channel_recent(channel_handle_or_id, max_results=5, after_iso=None)`
- `get_video_details(video_id)`

Auth
----
Reads `YOUTUBE_API_KEY` from env. If absent, falls back to
`<repo_root>/data/secrets/google-api-key.txt` (the file written by
config-assistant's `set_google_api_key` action).

Entry point
-----------
Run as: `<python> scripts/mcp/youtube_server.py`. The Rugol agent
uses the venv's python and the absolute path to this file.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Config / API key resolution
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SECRET_FILE = REPO_ROOT / "data" / "secrets" / "google-api-key.txt"
API_BASE = "https://www.googleapis.com/youtube/v3"


def _resolve_api_key() -> str | None:
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if key:
        return key
    if SECRET_FILE.exists():
        try:
            return SECRET_FILE.read_text(encoding="utf-8").strip() or None
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Thin YouTube Data API client (urllib only — no extra deps)
# ---------------------------------------------------------------------------


def _http_get(path: str, params: dict[str, Any]) -> dict:
    api_key = _resolve_api_key()
    if not api_key:
        raise RuntimeError(
            "No encontré YOUTUBE_API_KEY. Pegala en /config-assistant "
            f"o ponela en {SECRET_FILE}"
        )
    params = {k: v for k, v in params.items() if v is not None}
    params["key"] = api_key
    qs = urllib.parse.urlencode(params, doseq=True)
    url = f"{API_BASE}/{path}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YouTube API HTTP {e.code}: {body[:300]}")


# Tool implementations -------------------------------------------------------


def search_videos(args: dict[str, Any]) -> dict:
    query = args.get("query") or ""
    if not query.strip():
        raise ValueError("query is required")
    max_results = int(args.get("max_results") or 5)
    max_results = min(max(max_results, 1), 25)
    order = (args.get("order") or "date").strip()
    if order not in {"date", "rating", "relevance", "title", "viewCount"}:
        order = "date"
    published_after = args.get("published_after")
    if published_after is None and args.get("recent_days"):
        try:
            days = int(args["recent_days"])
            published_after = (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            published_after = None

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": order,
        "publishedAfter": published_after,
        "regionCode": args.get("region_code"),
        "relevanceLanguage": args.get("lang"),
    }
    raw = _http_get("search", params)

    items = []
    for it in raw.get("items", []):
        snip = it.get("snippet", {}) or {}
        vid_id = (it.get("id") or {}).get("videoId")
        if not vid_id:
            continue
        items.append(
            {
                "video_id": vid_id,
                "title": snip.get("title"),
                "channel": snip.get("channelTitle"),
                "channel_id": snip.get("channelId"),
                "published_at": snip.get("publishedAt"),
                "description": (snip.get("description") or "")[:300],
                "url": f"https://www.youtube.com/watch?v={vid_id}",
            }
        )

    # If the user asked for max_results we may want durations too — fetch in
    # one extra call (videos endpoint returns contentDetails.duration).
    if items and args.get("with_details", True):
        ids = ",".join(i["video_id"] for i in items)
        det = _http_get("videos", {"part": "contentDetails,statistics", "id": ids})
        details_by_id = {d["id"]: d for d in det.get("items", [])}
        for entry in items:
            d = details_by_id.get(entry["video_id"])
            if not d:
                continue
            entry["duration"] = (d.get("contentDetails") or {}).get("duration")
            stats = d.get("statistics") or {}
            entry["view_count"] = int(stats.get("viewCount") or 0)
            entry["like_count"] = int(stats.get("likeCount") or 0) if stats.get("likeCount") else None

    return {"results": items, "result_count": len(items)}


def get_channel_recent(args: dict[str, Any]) -> dict:
    handle_or_id = (args.get("channel_handle_or_id") or "").strip()
    if not handle_or_id:
        raise ValueError("channel_handle_or_id is required")
    max_results = int(args.get("max_results") or 10)
    max_results = min(max(max_results, 1), 50)

    # Resolve handle (e.g. @la_inteligencia_artificial) → channelId.
    channel_id: str | None = None
    if handle_or_id.startswith("UC") and len(handle_or_id) > 5:
        channel_id = handle_or_id
    else:
        handle = handle_or_id.lstrip("@")
        ch = _http_get("channels", {"part": "id", "forHandle": handle})
        items = ch.get("items") or []
        if not items:
            # Fallback: search for the channel by name.
            sr = _http_get(
                "search", {"part": "snippet", "type": "channel", "q": handle, "maxResults": 1}
            )
            sitems = sr.get("items") or []
            if sitems:
                channel_id = (sitems[0].get("id") or {}).get("channelId")
        else:
            channel_id = items[0]["id"]
    if not channel_id:
        raise ValueError(f"Could not resolve channel: {handle_or_id}")

    # Use search ordered by date for recency. (channels.uploads is more
    # reliable but requires two extra calls; this works fine for low volume.)
    after = args.get("after_iso")
    return search_videos(
        {
            "query": " ",
            "max_results": max_results,
            "order": "date",
            "published_after": after,
            "with_details": True,
            "_channel_id": channel_id,  # not used by search currently — see below
        }
    ) if False else _channel_search(channel_id, max_results, after)


def _channel_search(channel_id: str, max_results: int, after_iso: str | None) -> dict:
    """search.list with channelId filter — equivalent to 'most recent uploads from a channel'."""
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "maxResults": max_results,
        "order": "date",
        "publishedAfter": after_iso,
    }
    raw = _http_get("search", params)
    items = []
    for it in raw.get("items", []):
        snip = it.get("snippet", {}) or {}
        vid_id = (it.get("id") or {}).get("videoId")
        if not vid_id:
            continue
        items.append(
            {
                "video_id": vid_id,
                "title": snip.get("title"),
                "channel": snip.get("channelTitle"),
                "channel_id": snip.get("channelId"),
                "published_at": snip.get("publishedAt"),
                "description": (snip.get("description") or "")[:300],
                "url": f"https://www.youtube.com/watch?v={vid_id}",
            }
        )
    if items:
        ids = ",".join(i["video_id"] for i in items)
        det = _http_get("videos", {"part": "contentDetails,statistics", "id": ids})
        by_id = {d["id"]: d for d in det.get("items", [])}
        for e in items:
            d = by_id.get(e["video_id"])
            if d:
                e["duration"] = (d.get("contentDetails") or {}).get("duration")
                stats = d.get("statistics") or {}
                e["view_count"] = int(stats.get("viewCount") or 0)
    return {"results": items, "channel_id": channel_id, "result_count": len(items)}


def get_video_details(args: dict[str, Any]) -> dict:
    video_id = (args.get("video_id") or "").strip()
    if not video_id:
        raise ValueError("video_id is required")
    raw = _http_get(
        "videos",
        {"part": "snippet,contentDetails,statistics", "id": video_id},
    )
    items = raw.get("items") or []
    if not items:
        return {"error": f"No video found with id={video_id}"}
    v = items[0]
    snip = v.get("snippet") or {}
    cd = v.get("contentDetails") or {}
    stats = v.get("statistics") or {}
    return {
        "video_id": video_id,
        "title": snip.get("title"),
        "channel": snip.get("channelTitle"),
        "channel_id": snip.get("channelId"),
        "published_at": snip.get("publishedAt"),
        "description": snip.get("description"),
        "duration": cd.get("duration"),
        "view_count": int(stats.get("viewCount") or 0),
        "like_count": int(stats.get("likeCount") or 0) if stats.get("likeCount") else None,
        "comment_count": int(stats.get("commentCount") or 0) if stats.get("commentCount") else None,
        "tags": snip.get("tags") or [],
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


# ---------------------------------------------------------------------------
# MCP JSON-RPC server (stdio)
# ---------------------------------------------------------------------------


TOOLS_SCHEMA = [
    {
        "name": "search_videos",
        "description": "Search YouTube for videos matching a query. Optionally filter by recency (recent_days), order (date/relevance/viewCount), region/language. Returns top results with title, channel, duration, view count, URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 25, "default": 5},
                "recent_days": {"type": "integer", "description": "Limit to videos published in the last N days"},
                "published_after": {"type": "string", "description": "ISO 8601 timestamp; only videos published after this. Mutually exclusive with recent_days."},
                "order": {"type": "string", "enum": ["date", "rating", "relevance", "title", "viewCount"], "default": "date"},
                "region_code": {"type": "string", "description": "ISO 3166-1 alpha-2 country code, e.g. CL, AR, US"},
                "lang": {"type": "string", "description": "Relevance language, e.g. es, en"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_channel_recent",
        "description": "Get the most recent videos uploaded by a YouTube channel. Accepts either a handle (with or without @, e.g. @la_inteligencia_artificial) or a channel ID (UC...).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel_handle_or_id": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "after_iso": {"type": "string", "description": "Optional ISO 8601 — only videos published after this timestamp"},
            },
            "required": ["channel_handle_or_id"],
        },
    },
    {
        "name": "get_video_details",
        "description": "Get full details for a single video by its video_id (the 11-char id in the YouTube URL).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string"},
            },
            "required": ["video_id"],
        },
    },
]


def _make_response(req_id: Any, result: Any | None = None, error: dict | None = None) -> dict:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    return msg


def _handle_request(method: str, params: dict | None, req_id: Any) -> dict | None:
    params = params or {}

    if method == "initialize":
        return _make_response(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "rugol-youtube-mcp", "version": "0.6.1"},
            },
        )

    if method == "notifications/initialized":
        # No response for notifications.
        return None

    if method == "tools/list":
        return _make_response(req_id, {"tools": TOOLS_SCHEMA})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "search_videos":
                payload = search_videos(args)
            elif name == "get_channel_recent":
                payload = get_channel_recent(args)
            elif name == "get_video_details":
                payload = get_video_details(args)
            else:
                return _make_response(
                    req_id,
                    error={"code": -32601, "message": f"Unknown tool: {name}"},
                )
        except Exception as e:
            return _make_response(
                req_id,
                result={
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            )
        return _make_response(
            req_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}
                ]
            },
        )

    if method.startswith("notifications/"):
        return None

    return _make_response(
        req_id,
        error={"code": -32601, "message": f"Unknown method: {method}"},
    )


def main() -> int:
    # Force UTF-8 on stdio. Windows defaults to cp1252 which crashes on
    # non-Latin-1 characters that YouTube titles often contain (emojis,
    # non-ASCII punctuation). reconfigure() is Py 3.7+.
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Line-delimited JSON-RPC over stdio.
    stdin = sys.stdin
    stdout = sys.stdout
    while True:
        line = stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, list):
            # Batch — handle individually.
            responses = [
                _handle_request(m.get("method", ""), m.get("params"), m.get("id"))
                for m in msg
                if isinstance(m, dict)
            ]
            responses = [r for r in responses if r is not None]
            if responses:
                stdout.write(json.dumps(responses, ensure_ascii=False) + "\n")
                stdout.flush()
            continue
        if not isinstance(msg, dict):
            continue
        resp = _handle_request(msg.get("method", ""), msg.get("params"), msg.get("id"))
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
