#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

OUT = Path("artifact_bluearchive_competitor_transcripts_storyboards_v61")
OUT.mkdir(parents=True, exist_ok=True)

VIDEOS = [
    {"id":"Ra9F56wUaCo","genre":"SS","label":"頭上に先生の椅子回数が見える"},
    {"id":"TANvlLrVFi8","genre":"SS","label":"先生が元軍人で銃の達人"},
    {"id":"DVXk71WMCEY","genre":"SS","label":"先生AIが生徒の秘密を暴く"},
    {"id":"GYgI1itvJH8","genre":"SS","label":"ノアが先生の疲労を見落として後悔"},
    {"id":"9_hdj8AlsHA","genre":"SS・反応","label":"先生が血を吐いて倒れるドッキリ"},
    {"id":"xXaodZ_bZVo","genre":"長尺SS","label":"先生が義手義足だった場合"},
    {"id":"-6rDxHu87GU","genre":"あにまん反応","label":"ここだけ生徒に対して甘える先生"},
    {"id":"lZ7rtLvpavY","genre":"解説","label":"ブルアカのキャラクター名の由来解説"},
    {"id":"5MGcVpEEzp4","genre":"解説","label":"ブルアカ主要キャラ設定解説"},
]

S = requests.Session()
S.headers.update({
    "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/136 Safari/537.36",
    "Accept-Language":"ja,en-US;q=0.8,en;q=0.6",
})

PROVIDERS = [
    {
        "name":"outlyo",
        "method":"POST",
        "url":"https://www.outlyo.com/api/tools/youtube-transcript-generator",
        "referer":"https://www.outlyo.com/tools/youtube-transcript-generator",
    },
    {
        "name":"transcriptgrab",
        "method":"POST",
        "url":"https://transcriptgrab.com/api/transcript",
        "referer":"https://transcriptgrab.com/",
    },
    {
        "name":"yttt",
        "method":"GET",
        "url":"https://youtubetotranscriptai.com/api/transcript",
        "referer":"https://youtubetotranscriptai.com/",
    },
]


def fetch_provider(provider: dict, video_url: str) -> tuple[int, str, dict | list | None]:
    headers={"Accept":"application/json","Referer":provider["referer"],"Origin":provider["referer"].rstrip('/')}
    if provider["method"] == "POST":
        r=S.post(provider["url"],json={"url":video_url},headers=headers,timeout=180)
    else:
        r=S.get(provider["url"],params={"url":video_url,"lang":"ja"},headers=headers,timeout=180)
    text=r.text
    try: body=r.json()
    except Exception: body=None
    return r.status_code,text,body


def flatten_transcript(obj):
    title=channel=language=None; segments=[]; full_text=""
    if isinstance(obj,dict):
        title=obj.get("title") or obj.get("videoTitle") or obj.get("name")
        channel=obj.get("channel") or obj.get("channelTitle") or obj.get("author")
        language=obj.get("language") or obj.get("lang")
        candidates=[]
        for key in ["segments","transcript","captions","items","result","data"]:
            if key in obj: candidates.append(obj[key])
        for cand in candidates:
            if isinstance(cand,str) and len(cand)>len(full_text): full_text=cand
            elif isinstance(cand,list):
                for x in cand:
                    if isinstance(x,str): segments.append({"text":x})
                    elif isinstance(x,dict):
                        txt=x.get("text") or x.get("content") or x.get("caption") or x.get("sentence")
                        if txt:
                            segments.append({
                                "start":x.get("start") or x.get("startTime") or x.get("offset") or x.get("timestamp"),
                                "duration":x.get("duration") or x.get("dur"),
                                "text":txt,
                            })
            elif isinstance(cand,dict):
                t,c,l,s,f=flatten_transcript(cand)
                title=title or t; channel=channel or c; language=language or l
                if len(s)>len(segments): segments=s
                if len(f)>len(full_text): full_text=f
        if not full_text:
            for key in ["text","transcriptText","fullText","content"]:
                v=obj.get(key)
                if isinstance(v,str) and len(v)>len(full_text):full_text=v
    elif isinstance(obj,list):
        for x in obj:
            if isinstance(x,dict):
                txt=x.get("text") or x.get("content") or x.get("caption")
                if txt: segments.append({"start":x.get("start") or x.get("startTime"),"duration":x.get("duration"),"text":txt})
    if segments and not full_text: full_text="\n".join(str(x.get("text","")) for x in segments)
    return title,channel,language,segments,full_text


def storyboard_candidates(video_id):
    for level in [3,2,1,0]:
        for page in range(0,80):
            yield level,page,f"https://i.ytimg.com/sb/{video_id}/storyboard3_L{level}/M{page}.jpg"


def split_storyboard(im: Image.Image):
    # Common YouTube storyboard tiles are 160x90; fallback searches 16:9 grids.
    candidates=[]
    for tw in [160,120,100,80,240,320]:
        th=round(tw*9/16)
        if im.width%tw==0 and im.height%th==0:
            cols=im.width//tw; rows=im.height//th
            if 1<=cols<=20 and 1<=rows<=20: candidates.append((cols*rows,tw,th,cols,rows))
    if not candidates:
        return [im.copy()]
    _,tw,th,cols,rows=max(candidates)
    return [im.crop((c*tw,r*th,(c+1)*tw,(r+1)*th)) for r in range(rows) for c in range(cols)]


def contact_sheet(frames, labels, out_path, cols=5, cell=(320,180)):
    if not frames:return
    rows=(len(frames)+cols-1)//cols
    canvas=Image.new("RGB",(cols*cell[0],rows*(cell[1]+28)),"#111111")
    d=ImageDraw.Draw(canvas)
    for i,im in enumerate(frames):
        thumb=im.convert("RGB").resize(cell,Image.Resampling.LANCZOS)
        x=(i%cols)*cell[0];y=(i//cols)*(cell[1]+28)
        canvas.paste(thumb,(x,y)); d.text((x+6,y+cell[1]+5),labels[i],fill="white")
    canvas.save(out_path,quality=90)


rows=[]; failures=[]
for vi,v in enumerate(VIDEOS,1):
    vid=v["id"]; video_url=f"https://www.youtube.com/watch?v={vid}"
    d=OUT/"競合動画"/vid;d.mkdir(parents=True,exist_ok=True)
    rec={**v,"url":video_url,"providers":[],"transcript_provider":None,"transcript_segments":0,"transcript_chars":0,"storyboard_level":None,"storyboard_pages":0,"storyboard_frames":0}
    best=None
    for provider in PROVIDERS:
        try:
            status,text,body=fetch_provider(provider,video_url)
            (d/f"provider_{provider['name']}.txt").write_text(text,encoding="utf-8",errors="ignore")
            pr={"name":provider["name"],"status":status,"bytes":len(text),"json":isinstance(body,(dict,list))}
            if isinstance(body,(dict,list)):
                (d/f"provider_{provider['name']}.json").write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding="utf-8")
                title,channel,language,segments,full_text=flatten_transcript(body)
                pr.update({"title":title,"channel":channel,"language":language,"segments":len(segments),"chars":len(full_text)})
                if len(full_text)>200 and (best is None or len(full_text)>len(best[5])):
                    best=(provider['name'],title,channel,language,segments,full_text)
            rec["providers"].append(pr)
        except Exception as exc:
            rec["providers"].append({"name":provider["name"],"error":repr(exc)})
        time.sleep(1.5)
    if best:
        name,title,channel,language,segments,full_text=best
        rec.update({"transcript_provider":name,"title":title or v["label"],"channel":channel,"language":language,"transcript_segments":len(segments),"transcript_chars":len(full_text)})
        (d/"transcript.txt").write_text(full_text,encoding="utf-8")
        (d/"transcript_segments.json").write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding="utf-8")
    else:
        failures.append({"id":vid,"stage":"transcript","providers":rec["providers"]})
    # Download YouTube thumbnail and storyboard sprites.
    for name in ["maxresdefault","sddefault","hqdefault"]:
        try:
            r=S.get(f"https://i.ytimg.com/vi/{vid}/{name}.jpg",timeout=60)
            if r.status_code==200 and len(r.content)>1000:
                Image.open(io.BytesIO(r.content)).verify();(d/f"thumbnail_{name}.jpg").write_bytes(r.content);break
        except Exception: pass
    best_level=None; sheets=[]; frames=[]
    for level in [3,2,1,0]:
        level_sheets=[];level_frames=[]
        for page in range(80):
            url=f"https://i.ytimg.com/sb/{vid}/storyboard3_L{level}/M{page}.jpg"
            try:
                r=S.get(url,timeout=60)
                if r.status_code!=200 or len(r.content)<1000:break
                im=Image.open(io.BytesIO(r.content)).convert("RGB")
                # YouTube sometimes returns a tiny error image; require useful dimensions.
                if im.width<300 or im.height<150:break
                p=d/f"storyboard_L{level}_M{page:02d}.jpg";p.write_bytes(r.content)
                level_sheets.append(p);level_frames.extend(split_storyboard(im))
            except Exception:break
        if level_sheets:
            best_level=level;sheets=level_sheets;frames=level_frames;break
    if frames:
        # Remove trailing fully blank/repeated tiles conservatively by perceptual mean.
        filtered=[];labels=[]
        last_sig=None
        for i,im in enumerate(frames):
            small=im.resize((8,8)).convert('L');sig=tuple(small.getdata())
            if i>0 and len(set(sig))<=2 and sum(sig)/len(sig)<5:continue
            filtered.append(im);labels.append(f"frame {i+1}")
        frames=filtered
        rec.update({"storyboard_level":best_level,"storyboard_pages":len(sheets),"storyboard_frames":len(frames)})
        # Full audit sheets, 50 frames per page.
        for start in range(0,len(frames),50):
            contact_sheet(frames[start:start+50],labels[start:start+50],d/f"storyboard_contact_{start//50+1:02d}.jpg",cols=5)
        # Hook sheet from first 30 frames.
        contact_sheet(frames[:30],labels[:30],d/"storyboard_hook.jpg",cols=5)
    else:
        failures.append({"id":vid,"stage":"storyboard"})
    (d/"record.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8")
    rows.append(rec);print(vid,rec["transcript_provider"],rec["transcript_chars"],rec["storyboard_frames"],flush=True)

# Compact CSV.
fields=["id","genre","label","title","channel","transcript_provider","transcript_segments","transcript_chars","storyboard_level","storyboard_pages","storyboard_frames","url"]
with (OUT/"競合動画一覧.csv").open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:r.get(k) for k in fields} for r in rows])
(OUT/"取得失敗.json").write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/"取得結果.json").write_text(json.dumps({"requested":len(VIDEOS),"transcripts":sum(bool(r.get('transcript_provider')) for r in rows),"storyboards":sum(bool(r.get('storyboard_frames')) for r in rows),"failures":len(failures)},ensure_ascii=False,indent=2),encoding='utf-8')
