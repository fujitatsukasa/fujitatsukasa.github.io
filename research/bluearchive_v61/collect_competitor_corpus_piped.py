#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "artifact_bluearchive_competitor_v61_piped")
OUT.mkdir(parents=True, exist_ok=True)

VIDEOS = [
    ("Ra9F56wUaCo", "SS・数値ルール", "ブルアカ教室", "『1回 先生の椅子』全員の今日の回数が見えるようになった"),
    ("TANvlLrVFi8", "SS・秘密発覚", "ブルアカ教室", "先生が実は元軍人で銃の達人だった"),
    ("DVXk71WMCEY", "SS・秘密暴露", "ブルアカ教室", "先生AIが開発されて生徒の秘密が全部バレた"),
    ("GYgI1itvJH8", "長尺SS・後悔", "ブルアカ先生の反応集", "先生の疲労を見ないようにし続けて後悔するノア"),
    ("9_hdj8AlsHA", "反応集・ドッキリ", "ブルアカ先生の反応集", "先生が血を吐いて倒れるドッキリ"),
    ("xXaodZ_bZVo", "長尺SS集・秘密", "ブルアカ先生の反応集", "先生が義手義足だった場合の反応集"),
    ("-6rDxHu87GU", "あにまん概念スレ反応", "ななしさん", "ここだけミレニアムが存在しない世界線"),
    ("lZ7rtLvpavY", "解説・ミーム考察", "SIANちゃんねる", "おいしいマシンガンとは何なのか"),
    ("5MGcVpEEzp4", "解説・画風分析", "SIANちゃんねる", "絵をそれっぽくしてバズろう"),
]

INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.syncpundit.io",
    "https://pipedapi.aeong.one",
    "https://pipedapi.moomoo.me",
    "https://api-piped.mha.fi",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.tokhmi.xyz",
]

S = requests.Session()
S.headers.update({"User-Agent": "BlueArchiveCompetitorResearch/61", "Accept": "application/json,*/*"})


def run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def get_streams(video_id: str) -> tuple[dict[str, Any], str]:
    errors = []
    for base in INSTANCES:
        try:
            r = S.get(f"{base}/streams/{video_id}", timeout=75)
            if r.status_code == 200:
                j = r.json()
                if j.get("videoStreams") or j.get("hls"):
                    return j, base
            errors.append(f"{base}: HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            errors.append(f"{base}: {e!r}")
    raise RuntimeError(" | ".join(errors))


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with S.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)


def pick_streams(j: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    vids = j.get("videoStreams") or []
    auds = j.get("audioStreams") or []
    def qnum(v: dict[str, Any]) -> int:
        q = str(v.get("quality") or v.get("qualityLabel") or "")
        m = re.search(r"(\d+)", q)
        return int(m.group(1)) if m else 9999
    progressive = [v for v in vids if not v.get("videoOnly") and v.get("url") and qnum(v) <= 480]
    if progressive:
        progressive.sort(key=lambda v: (qnum(v), int(v.get("bitrate") or 0)), reverse=True)
        return progressive[0], None
    video_only = [v for v in vids if v.get("url") and qnum(v) <= 480]
    if not video_only:
        video_only = [v for v in vids if v.get("url")]
    video_only.sort(key=lambda v: (qnum(v), int(v.get("bitrate") or 0)), reverse=True)
    auds = [a for a in auds if a.get("url")]
    auds.sort(key=lambda a: int(a.get("bitrate") or 0), reverse=True)
    return (video_only[0] if video_only else None), (auds[0] if auds else None)


def make_video(j: dict[str, Any], vdir: Path) -> Path:
    v, a = pick_streams(j)
    if not v:
        raise RuntimeError("No video stream")
    rawv = vdir / "raw_video"
    download(v["url"], rawv)
    if a is None:
        out = vdir / "video.mp4"
        cp = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(rawv), "-c", "copy", "-y", str(out)], 600)
        if not out.exists():
            shutil.copy2(rawv, out)
    else:
        rawa = vdir / "raw_audio"
        download(a["url"], rawa)
        out = vdir / "video.mp4"
        cp = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(rawv), "-i", str(rawa), "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-shortest", "-y", str(out)], 1200)
        if not out.exists():
            raise RuntimeError(cp.stdout[-1000:])
        rawa.unlink(missing_ok=True)
    rawv.unlink(missing_ok=True)
    return out


def save_subtitles(j: dict[str, Any], vdir: Path) -> list[dict[str, Any]]:
    subs = j.get("subtitles") or []
    cand = []
    for s in subs:
        code = str(s.get("code") or "")
        name = str(s.get("name") or "")
        score = 3 if code.startswith("ja") else (2 if "Japanese" in name or "日本" in name else 0)
        if score and s.get("url"):
            cand.append((score, s))
    if not cand:
        return []
    cand.sort(key=lambda x: x[0], reverse=True)
    s = cand[0][1]
    r = S.get(s["url"], timeout=90)
    r.raise_for_status()
    text = r.text
    (vdir / "字幕原文.vtt").write_text(text, encoding="utf-8")
    return parse_vtt_text(text)


def ts(x: str) -> float:
    p = x.replace(",", ".").split(":")
    n = [float(i) for i in p]
    return n[-1] + (n[-2] * 60 if len(n) >= 2 else 0) + (n[-3] * 3600 if len(n) >= 3 else 0)


def parse_vtt_text(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(); out = []; i = 0
    pat = re.compile(r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})\s+-->\s+(\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})")
    while i < len(lines):
        m = pat.search(lines[i])
        if not m: i += 1; continue
        start, end = ts(m.group(1)), ts(m.group(2)); i += 1; buf = []
        while i < len(lines) and lines[i].strip():
            t = re.sub(r"<[^>]+>", "", lines[i]).strip()
            if t: buf.append(t)
            i += 1
        txt = " ".join(buf).strip()
        if txt:
            if out and out[-1]["text"] == txt and abs(out[-1]["end"] - start) < .3:
                out[-1]["end"] = round(end, 3)
            else:
                out.append({"start":round(start,3),"end":round(end,3),"text":txt})
        i += 1
    return out


def probe(video: Path) -> dict[str, Any]:
    cp = run(["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate", "-of", "json", str(video)], 180)
    try: return json.loads(cp.stdout)
    except Exception: return {"raw":cp.stdout}


def font(size: int):
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc","/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()


def frames(video: Path, folder: Path, duration: float, hook: bool) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    if hook: times = list(range(0, min(91, max(1,int(duration))), 3))
    else:
        step = max(5.0, duration / 72) if duration else 15
        times = [round(i*step,2) for i in range(min(72,max(1,math.ceil(duration/step))))]
    out=[]
    for t in times:
        p=folder/f"frame_{t:07.2f}s.jpg"
        run(["ffmpeg","-hide_banner","-loglevel","error","-ss",str(t),"-i",str(video),"-frames:v","1","-vf","scale=720:-2","-q:v","3","-y",str(p)],120)
        if p.exists() and p.stat().st_size>1000: out.append(p)
    return out


def sheet(paths: list[Path], out: Path, title: str, cols=6):
    if not paths: return
    cw,ch,top=360,225,62; rows=math.ceil(len(paths)/cols)
    can=Image.new("RGB",(cw*cols,top+ch*rows),"white"); d=ImageDraw.Draw(can); d.text((12,10),title,font=font(26),fill="black")
    for i,p in enumerate(paths):
        im=Image.open(p).convert("RGB"); im.thumbnail((cw-6,ch-26),Image.Resampling.LANCZOS)
        x=(i%cols)*cw+(cw-im.width)//2; y=top+(i//cols)*ch; can.paste(im,(x,y)); d.text(((i%cols)*cw+5,top+(i//cols)*ch+ch-22),p.stem.replace('frame_',''),font=font(14),fill="black")
    can.save(out,quality=88)


def scene_changes(video: Path):
    cp=run(["ffmpeg","-hide_banner","-i",str(video),"-filter:v","select='gt(scene,0.27)',showinfo","-f","null","-"],3600)
    return [round(float(x),3) for x in re.findall(r"pts_time:([0-9.]+)",cp.stdout)]


def silences(video: Path):
    cp=run(["ffmpeg","-hide_banner","-i",str(video),"-af","silencedetect=noise=-38dB:d=.5","-f","null","-"],3600)
    starts=[]; out=[]
    for line in cp.stdout.splitlines():
        m=re.search(r"silence_start: ([0-9.]+)",line)
        if m: starts.append(float(m.group(1)))
        m=re.search(r"silence_end: ([0-9.]+) \| silence_duration: ([0-9.]+)",line)
        if m:
            e,d=float(m.group(1)),float(m.group(2)); s=starts.pop(0) if starts else e-d; out.append({"start":round(s,3),"end":round(e,3),"duration":round(d,3)})
    return out


def caption_between(seg,start,end):
    vals=[]
    for s in seg:
        if s['end']>=start and s['start']<=end:
            t=re.sub(r"\s+"," ",s['text']).strip()
            if t and (not vals or vals[-1]!=t): vals.append(t)
    return " ".join(vals)

rows=[]; failures=[]
for vid,genre,channel,title in VIDEOS:
    vdir=OUT/'競合動画'/vid; vdir.mkdir(parents=True,exist_ok=True)
    try:
        j,instance=get_streams(vid)
        (vdir/'Piped応答.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
        video=make_video(j,vdir)
        pr=probe(video); duration=float((pr.get('format') or {}).get('duration') or j.get('duration') or 0)
        subs=save_subtitles(j,vdir)
        with (vdir/'字幕区間.jsonl').open('w',encoding='utf-8') as f:
            for s in subs:f.write(json.dumps(s,ensure_ascii=False)+'\n')
        (vdir/'字幕全文.txt').write_text('\n'.join(s['text'] for s in subs),encoding='utf-8')
        h=frames(video,vdir/'冒頭90秒フレーム',duration,True); a=frames(video,vdir/'全編サンプルフレーム',duration,False)
        sheet(h,vdir/'冒頭90秒コンタクトシート.jpg',f'{channel} / {title} / 冒頭90秒')
        sheet(a,vdir/'全編コンタクトシート.jpg',f'{channel} / {title} / 全編')
        sc=scene_changes(video); si=silences(video)
        blocks=[{'start':s,'end':min(s+10,duration),'caption':caption_between(subs,s,min(s+10,duration))} for s in range(0,min(90,int(math.ceil(duration))),10)]
        rec={'id':vid,'url':f'https://www.youtube.com/watch?v={vid}','genre':genre,'expected_channel':channel,'expected_title':title,'piped_instance':instance,'actual_title':j.get('title'),'actual_uploader':j.get('uploader'),'duration':duration,'views':j.get('views'),'likes':j.get('likes'),'description':j.get('description'),'chapters':j.get('chapters') or [],'subtitle_segments':len(subs),'scene_change_count':len(sc),'scene_changes':sc,'mean_seconds_per_scene_change':round(duration/len(sc),3) if sc else None,'silence_count':len(si),'silences':si,'hook_10s_blocks':blocks,'probe':pr}
        (vdir/'直接視聴用データ.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
        rows.append({'id':vid,'genre':genre,'title':j.get('title') or title,'channel':j.get('uploader') or channel,'duration':duration,'views':j.get('views'),'subtitle_segments':len(subs),'scene_change_count':len(sc),'mean_seconds_per_scene_change':rec['mean_seconds_per_scene_change'],'silence_count':len(si),'url':rec['url'],'piped_instance':instance})
        # Retain video for audit; low-resolution stream only.
    except Exception as e:
        failures.append({'id':vid,'stage':'piped','error':repr(e)})
        (vdir/'失敗.txt').write_text(repr(e),encoding='utf-8')

fields=['id','genre','title','channel','duration','views','subtitle_segments','scene_change_count','mean_seconds_per_scene_change','silence_count','url','piped_instance']
with (OUT/'競合動画一覧.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'取得失敗.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'取得結果.json').write_text(json.dumps({'requested':len(VIDEOS),'downloaded':len(rows),'failures':len(failures),'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'downloaded':len(rows),'failures':len(failures)},ensure_ascii=False))
