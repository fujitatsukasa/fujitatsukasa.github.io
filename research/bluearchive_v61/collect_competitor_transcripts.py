#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

OUT = Path("artifact_competitor_transcripts_v61")
OUT.mkdir(parents=True, exist_ok=True)
VIDEOS = [
    ("Ra9F56wUaCo", "SS・数値ルール", "『1回 先生の椅子』全員の今日の回数が見えるようになった"),
    ("TANvlLrVFi8", "SS・秘密発覚", "先生が実は元軍人で銃の達人だった"),
    ("DVXk71WMCEY", "SS・秘密暴露", "先生AIが開発されて生徒の秘密が全部バレた"),
    ("GYgI1itvJH8", "長尺SS・後悔", "先生の疲労を見ないようにし続けて後悔するノア"),
    ("9_hdj8AlsHA", "反応集・ドッキリ", "先生が血を吐いて倒れるドッキリ"),
    ("xXaodZ_bZVo", "長尺SS集・秘密", "先生が義手義足だった場合の反応集"),
    ("-6rDxHu87GU", "あにまん概念スレ反応", "ここだけミレニアムが存在しない世界線"),
    ("lZ7rtLvpavY", "解説・ミーム考察", "おいしいマシンガンとは何なのか"),
    ("5MGcVpEEzp4", "解説・画風分析", "絵をそれっぽくしてバズろう"),
]

ENDPOINTS = [
    {
        "name": "Outlyo",
        "method": "POST",
        "url": "https://www.outlyo.com/api/tools/youtube-transcript-generator",
        "referer": "https://www.outlyo.com/tools/youtube-transcript-generator",
        "payload": lambda u: {"url": u},
    },
    {
        "name": "TranscriptGrab",
        "method": "POST",
        "url": "https://transcriptgrab.com/api/transcript",
        "referer": "https://transcriptgrab.com/",
        "payload": lambda u: {"url": u},
    },
    {
        "name": "YTTools",
        "method": "GET",
        "url": "https://yttools.co/api/transcript",
        "referer": "https://yttools.co/",
        "params": lambda u: {"url": u},
    },
    {
        "name": "YouTubeToTranscriptAI",
        "method": "GET",
        "url": "https://youtubetotranscriptai.com/api/transcript",
        "referer": "https://youtubetotranscriptai.com/",
        "params": lambda u: {"url": u},
    },
]

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.7",
})


def parse_time(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        n = float(v)
        # Some services return milliseconds.
        return n / 1000.0 if n > 100000 else n
    s = str(v).strip().replace(",", ".")
    if not s:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    parts = s.split(":")
    try:
        nums = [float(x) for x in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0]


def flatten_candidates(obj: Any, path: str = "root") -> list[tuple[str, Any]]:
    out = [(path, obj)]
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(flatten_candidates(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):
            out.extend(flatten_candidates(v, f"{path}[{i}]"))
    return out


def normalize_json(obj: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta: dict[str, Any] = {}
    # Title/video metadata wherever commonly exposed.
    if isinstance(obj, dict):
        for k in ["title", "videoTitle", "video_title", "videoId", "video_id", "channel", "author", "language", "lang"]:
            if k in obj:
                meta[k] = obj[k]
        for container_key in ["result", "data", "video", "metadata"]:
            c = obj.get(container_key)
            if isinstance(c, dict):
                for k in ["title", "videoTitle", "video_title", "videoId", "video_id", "channel", "author", "language", "lang"]:
                    if k in c:
                        meta[k] = c[k]

    best: list[dict[str, Any]] = []
    best_path = None
    string_candidate = None
    for path, val in flatten_candidates(obj):
        if isinstance(val, list) and val:
            rows = []
            for item in val:
                if not isinstance(item, dict):
                    rows = []
                    break
                text = item.get("text") or item.get("content") or item.get("caption") or item.get("sentence") or item.get("transcript")
                if not isinstance(text, str) or not text.strip():
                    rows = []
                    break
                start = parse_time(item.get("start") if "start" in item else item.get("offset") if "offset" in item else item.get("time") if "time" in item else item.get("timestamp"))
                duration = parse_time(item.get("duration") if "duration" in item else item.get("dur"))
                end = parse_time(item.get("end"))
                if end is None and start is not None and duration is not None:
                    end = start + duration
                rows.append({"start": start, "end": end, "duration": duration, "text": re.sub(r"\s+", " ", text).strip()})
            if len(rows) > len(best):
                best, best_path = rows, path
        elif isinstance(val, str) and len(val) > 500 and any(word in path.lower() for word in ["transcript", "text", "content"]):
            if string_candidate is None or len(val) > len(string_candidate[1]):
                string_candidate = (path, val)
    if best:
        meta["normalized_from"] = best_path
        return best, meta
    if string_candidate:
        path, txt = string_candidate
        meta["normalized_from"] = path
        return [{"start": None, "end": None, "duration": None, "text": re.sub(r"\s+", " ", txt).strip()}], meta
    return [], meta


def request_endpoint(ep: dict[str, Any], youtube_url: str) -> tuple[requests.Response, Any | None]:
    headers = {"Referer": ep["referer"], "Origin": ep["referer"].rstrip("/")}
    if ep["method"] == "POST":
        r = S.post(ep["url"], json=ep["payload"](youtube_url), headers=headers, timeout=180)
    else:
        r = S.get(ep["url"], params=ep["params"](youtube_url), headers=headers, timeout=180)
    try:
        return r, r.json()
    except Exception:
        return r, None

summary = []
for vid, genre, title in VIDEOS:
    folder = OUT / vid
    folder.mkdir(exist_ok=True)
    youtube_url = f"https://www.youtube.com/watch?v={vid}"
    attempts = []
    chosen = None
    for ep in ENDPOINTS:
        rec = {"service": ep["name"], "endpoint": ep["url"]}
        try:
            r, obj = request_endpoint(ep, youtube_url)
            rec.update({"status": r.status_code, "content_type": r.headers.get("content-type"), "bytes": len(r.content), "response_head": r.text[:1000]})
            if obj is not None:
                (folder / f"raw_{ep['name']}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
                rows, meta = normalize_json(obj)
                rec["normalized_rows"] = len(rows)
                rec["normalized_meta"] = meta
                rec["normalized_chars"] = sum(len(x["text"]) for x in rows)
                if rows:
                    with (folder / f"normalized_{ep['name']}.jsonl").open("w", encoding="utf-8") as f:
                        for x in rows:
                            f.write(json.dumps(x, ensure_ascii=False) + "\n")
                    (folder / f"normalized_{ep['name']}.txt").write_text("\n".join(x["text"] for x in rows), encoding="utf-8")
                    if chosen is None or rec["normalized_chars"] > chosen[0]:
                        chosen = (rec["normalized_chars"], ep["name"], rows, meta)
            else:
                (folder / f"raw_{ep['name']}.txt").write_text(r.text, encoding="utf-8", errors="ignore")
        except Exception as e:
            rec["error"] = repr(e)
        attempts.append(rec)
        print(vid, ep["name"], rec.get("status"), rec.get("normalized_rows"), rec.get("error"), flush=True)
        time.sleep(1.0)
    result = {"video_id": vid, "genre": genre, "title": title, "youtube_url": youtube_url, "attempts": attempts, "success": bool(chosen)}
    if chosen:
        chars, service, rows, meta = chosen
        result.update({"chosen_service": service, "rows": len(rows), "chars": chars, "meta": meta})
        with (folder / "transcript.jsonl").open("w", encoding="utf-8") as f:
            for x in rows:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        (folder / "transcript.txt").write_text("\n".join(x["text"] for x in rows), encoding="utf-8")
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary.append(result)

(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"videos": len(summary), "success": sum(x["success"] for x in summary), "services": {s: sum(x.get("chosen_service") == s for x in summary) for s in [e["name"] for e in ENDPOINTS]}}, ensure_ascii=False))
