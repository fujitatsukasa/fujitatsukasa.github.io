#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright

OUT = Path("artifact_direct_visual_samples_v61")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://invidious.f5.si"
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

def font(size: int):
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc","/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc","/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def make_sheet(paths: list[Path], out: Path, title: str, cols: int = 5, cw: int = 360, ch: int = 235):
    if not paths:return
    rows=math.ceil(len(paths)/cols);top=65
    can=Image.new('RGB',(cols*cw,top+rows*ch),'white');d=ImageDraw.Draw(can);d.text((12,12),title,font=font(25),fill='black')
    for i,p in enumerate(paths):
        try: im=Image.open(p).convert('RGB')
        except Exception: continue
        im.thumbnail((cw-8,ch-30),Image.Resampling.LANCZOS)
        x=(i%cols)*cw+(cw-im.width)//2;y=top+(i//cols)*ch
        can.paste(im,(x,y));d.text(((i%cols)*cw+5,top+(i//cols)*ch+ch-24),p.stem.replace('frame_',''),font=font(14),fill='black')
    can.save(out,quality=88)

def dhash(path: Path) -> str:
    im=Image.open(path).convert('L').resize((9,8),Image.Resampling.LANCZOS)
    px=list(im.getdata());bits=[]
    for y in range(8):
        for x in range(8): bits.append(px[y*9+x] > px[y*9+x+1])
    n=0
    for b in bits:n=(n<<1)|int(b)
    return f'{n:016x}'

async def seek_capture(video, t: float, path: Path) -> dict:
    rec={'time':round(t,3)}
    try:
        await video.evaluate("(v,t)=>{v.pause(); if(Number.isFinite(v.duration)) v.currentTime=Math.min(Math.max(0,t),Math.max(0,v.duration-0.35));}",t)
        try:
            await video.evaluate("v => new Promise((resolve,reject)=>{let done=()=>{cleanup();resolve()};let err=()=>{cleanup();reject(new Error('seek error'))};let cleanup=()=>{v.removeEventListener('seeked',done);v.removeEventListener('error',err)};v.addEventListener('seeked',done,{once:true});v.addEventListener('error',err,{once:true});setTimeout(done,1800);})")
        except Exception: pass
        await video.screenshot(path=str(path),quality=88)
        rec.update(exists=path.exists(),bytes=path.stat().st_size if path.exists() else 0,dhash=dhash(path) if path.exists() else None)
    except Exception as e:rec['error']=repr(e)
    return rec

async def main():
    summary=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required','--no-sandbox'])
        context=await browser.new_context(viewport={'width':1280,'height':720},locale='ja-JP',ignore_https_errors=True,user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36')
        for vid,genre,title in VIDEOS:
            folder=OUT/vid;folder.mkdir(exist_ok=True);page=await context.new_page();network=[]
            page.on('response',lambda r: network.append({'url':r.url,'status':r.status,'type':r.request.resource_type,'content_type':r.headers.get('content-type')}))
            rec={'video_id':vid,'genre':genre,'expected_title':title,'url':f'{BASE}/watch?v={vid}&local=true&quality=medium&autoplay=1'}
            try:
                resp=await page.goto(rec['url'],wait_until='domcontentloaded',timeout=60000);rec['page_status']=resp.status if resp else None
                await page.wait_for_timeout(8000);rec['page_title']=await page.title();rec['body_head']=(await page.locator('body').inner_text())[:5000]
                await page.screenshot(path=str(folder/'page.jpg'),full_page=True,quality=80)
                video=page.locator('video').first
                if await page.locator('video').count()==0:raise RuntimeError('video element missing')
                state=await video.evaluate("v=>({duration:v.duration,readyState:v.readyState,error:v.error?{code:v.error.code,message:v.error.message}:null,currentSrc:v.currentSrc,videoWidth:v.videoWidth,videoHeight:v.videoHeight})")
                rec['video_state']=state;duration=float(state.get('duration') or 0);rec['duration']=duration
                if not duration or state.get('readyState',0)<2:raise RuntimeError(f'video not ready: {state}')
                hook_times=[float(x) for x in range(0,min(91,max(1,int(duration))),3)]
                full_count=72
                full_times=sorted(set(round(i*max(1,duration-1)/(full_count-1),2) for i in range(full_count)))
                hook=[];full=[]
                hdir=folder/'冒頭90秒';fdir=folder/'全編72点'
                hdir.mkdir(exist_ok=True);fdir.mkdir(exist_ok=True)
                for t in hook_times:
                    r=await seek_capture(video,t,hdir/f'frame_{t:07.2f}s.jpg');hook.append(r)
                for t in full_times:
                    r=await seek_capture(video,t,fdir/f'frame_{t:08.2f}s.jpg');full.append(r)
                hp=sorted(hdir.glob('*.jpg'));fp=sorted(fdir.glob('*.jpg'))
                make_sheet(hp,folder/'冒頭90秒コンタクトシート.jpg',f'{title} / 冒頭90秒',cols=5)
                make_sheet(fp,folder/'全編コンタクトシート_1.jpg',f'{title} / 全編 前半',cols=6)
                if len(fp)>36:
                    make_sheet(fp[:36],folder/'全編コンタクトシート_前半.jpg',f'{title} / 全編 前半',cols=6)
                    make_sheet(fp[36:],folder/'全編コンタクトシート_後半.jpg',f'{title} / 全編 後半',cols=6)
                rec['hook_frames']=hook;rec['full_frames']=full
                hashes=[x.get('dhash') for x in full if x.get('dhash')]
                rec['unique_dhash']=len(set(hashes));rec['full_frame_count']=len(hashes);rec['exact_duplicate_hashes']=len(hashes)-len(set(hashes))
                rec['success']=True
            except Exception as e:
                rec['success']=False;rec['error']=repr(e)
            rec['network_interesting']=[x for x in network if any(k in x['url'] for k in ['companion','videoplayback','googlevideo','caption','storyboard'])][:500]
            (folder/'network.json').write_text(json.dumps(network,ensure_ascii=False,indent=2),encoding='utf-8')
            (folder/'result.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'id':vid,'success':rec['success'],'duration':rec.get('duration'),'frames':rec.get('full_frame_count'),'error':rec.get('error')},ensure_ascii=False),flush=True)
            summary.append(rec);await page.close()
        await browser.close()
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'result_overview.json').write_text(json.dumps({'requested':len(VIDEOS),'success':sum(x.get('success') for x in summary),'failures':[x['video_id'] for x in summary if not x.get('success')]},ensure_ascii=False,indent=2),encoding='utf-8')
asyncio.run(main())
