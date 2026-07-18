#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "artifact_bluearchive_competitor_v61")
OUT.mkdir(parents=True, exist_ok=True)

VIDEOS = [
    {"id":"Ra9F56wUaCo","genre":"SS・数値ルール","channel":"ブルアカ教室","title":"『1回 先生の椅子』全員の今日の回数が見えるようになった"},
    {"id":"TANvlLrVFi8","genre":"SS・秘密発覚","channel":"ブルアカ教室","title":"先生が実は元軍人で銃の達人だった"},
    {"id":"DVXk71WMCEY","genre":"SS・秘密暴露","channel":"ブルアカ教室","title":"先生AIが開発されて生徒の秘密が全部バレた"},
    {"id":"GYgI1itvJH8","genre":"長尺SS・後悔","channel":"ブルアカ先生の反応集","title":"先生の疲労を見ないようにし続けて後悔するノア"},
    {"id":"9_hdj8AlsHA","genre":"反応集・ドッキリ","channel":"ブルアカ先生の反応集","title":"先生が血を吐いて倒れるドッキリ"},
    {"id":"xXaodZ_bZVo","genre":"長尺SS集・秘密","channel":"ブルアカ先生の反応集","title":"先生が義手義足だった場合の反応集"},
    {"id":"-6rDxHu87GU","genre":"あにまん概念スレ反応","channel":"ななしさん","title":"ここだけミレニアムが存在せず生徒がゲヘナ所属の世界線"},
]


def run(cmd: list[str], *, check: bool = True, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check, timeout=timeout)


def read_info(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_timestamp(text: str) -> float:
    parts = text.replace(",", ".").split(":")
    try:
        nums = [float(x) for x in parts]
    except ValueError:
        return 0.0
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0] if nums else 0.0


def parse_vtt(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    segments: list[dict[str, Any]] = []
    i = 0
    timing = re.compile(r"(?P<s>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})\s+-->\s+(?P<e>\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})")
    while i < len(lines):
        m = timing.search(lines[i])
        if not m:
            i += 1
            continue
        start, end = parse_timestamp(m.group("s")), parse_timestamp(m.group("e"))
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            t = re.sub(r"<[^>]+>", "", lines[i]).strip()
            if t:
                text_lines.append(t)
            i += 1
        text = " ".join(text_lines).strip()
        if text:
            if segments and segments[-1]["text"] == text and abs(segments[-1]["end"] - start) < 0.25:
                segments[-1]["end"] = end
            else:
                segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        i += 1
    return segments


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def make_contact_sheet(frames: list[Path], output: Path, title: str, cols: int = 5, cell_w: int = 400, cell_h: int = 250) -> None:
    if not frames:
        return
    rows = math.ceil(len(frames) / cols)
    top = 70
    canvas = Image.new("RGB", (cols * cell_w, top + rows * cell_h), "white")
    d = ImageDraw.Draw(canvas)
    d.text((15, 12), title, font=font(28), fill="black")
    for idx, p in enumerate(frames):
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        im.thumbnail((cell_w - 8, cell_h - 28), Image.Resampling.LANCZOS)
        x = (idx % cols) * cell_w + (cell_w - im.width) // 2
        y = top + (idx // cols) * cell_h + 2
        canvas.paste(im, (x, y))
        label = p.stem.replace("frame_", "")
        d.rectangle((idx % cols * cell_w, top + (idx // cols) * cell_h + cell_h - 24, idx % cols * cell_w + cell_w, top + (idx // cols) * cell_h + cell_h), fill="white")
        d.text((idx % cols * cell_w + 6, top + (idx // cols) * cell_h + cell_h - 22), label, font=font(16), fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=90)


def ffprobe(video: Path) -> dict[str, Any]:
    cp = run(["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate", "-of", "json", str(video)], check=False, timeout=120)
    try:
        return json.loads(cp.stdout)
    except Exception:
        return {"raw": cp.stdout}


def sample_frames(video: Path, folder: Path, duration: float, hook: bool = False) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    if hook:
        times = [float(x) for x in range(0, min(91, max(1, int(duration))), 3)]
    else:
        target = 60
        step = max(5.0, duration / target) if duration else 15.0
        times = [round(i * step, 2) for i in range(min(target, max(1, math.ceil(duration / step))))]
    out: list[Path] = []
    for n, t in enumerate(times):
        p = folder / f"frame_{t:07.2f}s.jpg"
        cp = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=720:-2", "-q:v", "3", "-y", str(p)], check=False, timeout=120)
        if p.exists() and p.stat().st_size > 1000:
            out.append(p)
    return out


def scene_changes(video: Path) -> list[float]:
    cp = run(["ffmpeg", "-hide_banner", "-i", str(video), "-filter:v", "select='gt(scene,0.28)',showinfo", "-f", "null", "-"], check=False, timeout=1800)
    times = []
    for m in re.finditer(r"pts_time:([0-9.]+)", cp.stdout):
        try:
            times.append(round(float(m.group(1)), 3))
        except ValueError:
            pass
    return times


def silence_ranges(video: Path) -> list[dict[str, float]]:
    cp = run(["ffmpeg", "-hide_banner", "-i", str(video), "-af", "silencedetect=noise=-38dB:d=0.5", "-f", "null", "-"], check=False, timeout=1800)
    starts: list[float] = []
    out: list[dict[str, float]] = []
    for line in cp.stdout.splitlines():
        ms = re.search(r"silence_start: ([0-9.]+)", line)
        if ms:
            starts.append(float(ms.group(1)))
        me = re.search(r"silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)", line)
        if me:
            start = starts.pop(0) if starts else max(0.0, float(me.group(1)) - float(me.group(2)))
            out.append({"start": round(start, 3), "end": round(float(me.group(1)), 3), "duration": round(float(me.group(2)), 3)})
    return out


def captions_at(segments: list[dict[str, Any]], start: float, end: float) -> str:
    parts = [s["text"] for s in segments if s["end"] >= start and s["start"] <= end]
    # YouTube auto captions often repeat rolling text; dedupe consecutive fragments.
    clean: list[str] = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip()
        if p and (not clean or p != clean[-1]):
            clean.append(p)
    return " ".join(clean)


rows: list[dict[str, Any]] = []
failures: list[dict[str, Any]] = []

for item in VIDEOS:
    vid = item["id"]
    vdir = OUT / "競合動画" / vid
    vdir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={vid}"
    output_tpl = str(vdir / "video.%(ext)s")
    cmd = [
        "yt-dlp", url,
        "--no-playlist", "--no-warnings",
        "--write-info-json", "--write-thumbnail", "--convert-thumbnails", "jpg",
        "--write-subs", "--write-auto-subs", "--sub-langs", "ja,ja-orig", "--sub-format", "vtt",
        "--extractor-args", "youtube:player_client=android,web",
        "-f", "bv*[height<=360]+ba/b[height<=360]/b",
        "--merge-output-format", "mp4",
        "-o", output_tpl,
    ]
    cp = run(cmd, check=False, timeout=3600)
    (vdir / "yt-dlp.log.txt").write_text(cp.stdout, encoding="utf-8")
    info_files = list(vdir.glob("*.info.json"))
    info = read_info(info_files[0]) if info_files else {}
    videos = [p for p in vdir.glob("video.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    if not videos:
        failures.append({"id": vid, "stage": "download", "log": cp.stdout[-2000:]})
        continue
    video = videos[0]
    probe = ffprobe(video)
    duration = float((probe.get("format") or {}).get("duration") or info.get("duration") or 0)
    subs = sorted(vdir.glob("*.vtt"))
    segments: list[dict[str, Any]] = []
    for s in subs:
        seg = parse_vtt(s)
        if len(seg) > len(segments):
            segments = seg
    with (vdir / "字幕区間.jsonl").open("w", encoding="utf-8") as f:
        for s in segments:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    (vdir / "字幕全文.txt").write_text("\n".join(s["text"] for s in segments), encoding="utf-8")

    hook_frames = sample_frames(video, vdir / "冒頭90秒フレーム", duration, hook=True)
    full_frames = sample_frames(video, vdir / "全編サンプルフレーム", duration, hook=False)
    make_contact_sheet(hook_frames, vdir / "冒頭90秒コンタクトシート.jpg", f"{item['channel']} / {item['title']} / 冒頭90秒")
    make_contact_sheet(full_frames, vdir / "全編コンタクトシート.jpg", f"{item['channel']} / {item['title']} / 全編")

    scenes = scene_changes(video)
    silences = silence_ranges(video)
    chapters = info.get("chapters") or []
    hook_blocks = []
    for start in range(0, min(90, int(math.ceil(duration))), 10):
        hook_blocks.append({"start": start, "end": min(start + 10, duration), "caption": captions_at(segments, start, min(start + 10, duration))})
    analysis = {
        "id": vid,
        "url": url,
        "genre": item["genre"],
        "channel_expected": item["channel"],
        "title_expected": item["title"],
        "title_actual": info.get("title"),
        "channel_actual": info.get("channel"),
        "upload_date": info.get("upload_date"),
        "duration": duration,
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "description": info.get("description"),
        "chapters": chapters,
        "subtitle_segments": len(segments),
        "scene_change_count": len(scenes),
        "scene_changes": scenes,
        "mean_seconds_per_scene_change": round(duration / len(scenes), 3) if scenes else None,
        "silence_count": len(silences),
        "silences": silences,
        "hook_10s_blocks": hook_blocks,
        "probe": probe,
    }
    (vdir / "直接視聴用データ.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    rows.append({
        "id": vid,
        "genre": item["genre"],
        "title": info.get("title") or item["title"],
        "channel": info.get("channel") or item["channel"],
        "duration": round(duration, 3),
        "view_count": info.get("view_count"),
        "subtitle_segments": len(segments),
        "scene_change_count": len(scenes),
        "mean_seconds_per_scene_change": round(duration / len(scenes), 3) if scenes else "",
        "silence_count": len(silences),
        "chapters": len(chapters),
        "url": url,
    })
    # Keep the low-resolution video so the artifact is auditable. Long files are acceptable for this research artifact.

fields = ["id","genre","title","channel","duration","view_count","subtitle_segments","scene_change_count","mean_seconds_per_scene_change","silence_count","chapters","url"]
with (OUT / "競合動画一覧.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(rows)
(OUT / "取得失敗.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "取得結果.json").write_text(json.dumps({"requested":len(VIDEOS),"downloaded":len(rows),"failures":len(failures),"rows":rows}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"downloaded":len(rows),"failures":len(failures)}, ensure_ascii=False))
