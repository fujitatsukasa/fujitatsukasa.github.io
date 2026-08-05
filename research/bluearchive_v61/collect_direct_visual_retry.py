#!/usr/bin/env python3
from __future__ import annotations
import asyncio,json,math,re
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from playwright.async_api import async_playwright
OUT=Path('artifact_direct_visual_retry_v61');OUT.mkdir(parents=True,exist_ok=True)
VIDEOS=[
('Ra9F56wUaCo','SS・数値ルール','先生の持ち物を盗んだ回数'),
('GYgI1itvJH8','長尺SS・後悔','ノアが先生の疲労を見ないふり'),
('9_hdj8AlsHA','反応集・ドッキリ','先生が血を吐いて倒れるドッキリ'),
('xXaodZ_bZVo','長尺SS集・秘密','先生が義手義足だった場合'),
('lZ7rtLvpavY','解説・ミーム考察','おいしいマシンガンとは何なのか'),
('5MGcVpEEzp4','解説・画風分析','絵をそれっぽくしてバズろう'),
]
INSTANCES=['https://invidious.tiekoetter.com','https://invidious.f5.si','https://invidious.private.coffee','https://yewtu.be','https://inv.nadeko.net']
MODES=['local=true&quality=medium&autoplay=1','local=false&quality=medium&autoplay=1','quality=dash&autoplay=1']
def font(s):
 for p in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
  if Path(p).exists():return ImageFont.truetype(p,s)
 return ImageFont.load_default()
def sheet(paths,out,title,cols=4):
 if not paths:return
 cw,ch,top=480,300,65;rows=math.ceil(len(paths)/cols);can=Image.new('RGB',(cw*cols,top+ch*rows),'white');d=ImageDraw.Draw(can);d.text((14,12),title,font=font(26),fill='black')
 for i,p in enumerate(paths):
  try:im=Image.open(p).convert('RGB')
  except:continue
  im.thumbnail((cw-8,ch-30),Image.Resampling.LANCZOS);x=(i%cols)*cw+(cw-im.width)//2;y=top+(i//cols)*ch;can.paste(im,(x,y));d.text(((i%cols)*cw+5,top+(i//cols)*ch+ch-23),p.stem.replace('frame_',''),font=font(15),fill='black')
 can.save(out,quality=90)
async def try_one(context,vid,folder):
 attempts=[]
 for base in INSTANCES:
  for mode in MODES:
   page=await context.new_page();url=f'{base}/watch?v={vid}&{mode}';rec={'base':base,'mode':mode,'url':url};net=[];page.on('response',lambda r:net.append({'url':r.url,'status':r.status,'type':r.request.resource_type,'ct':r.headers.get('content-type')}))
   try:
    resp=await page.goto(url,wait_until='domcontentloaded',timeout=55000);rec['status']=resp.status if resp else None;await page.wait_for_timeout(8000)
    cnt=await page.locator('video').count();rec['video_count']=cnt
    if cnt:
     v=page.locator('video').first
     for _ in range(3):
      try:await v.evaluate("v=>{v.muted=true;return v.play()}")
      except:pass
      await page.wait_for_timeout(5000)
      st=await v.evaluate("v=>({duration:v.duration,currentTime:v.currentTime,readyState:v.readyState,paused:v.paused,error:v.error?{code:v.error.code,message:v.error.message}:null,src:v.currentSrc,videoWidth:v.videoWidth,videoHeight:v.videoHeight})")
      rec['state']=st
      if st.get('readyState',0)>=2 and st.get('videoWidth',0)>0 and isinstance(st.get('duration'),(int,float)) and st['duration']>0:break
      await page.reload(wait_until='domcontentloaded',timeout=55000);await page.wait_for_timeout(6000);v=page.locator('video').first
     st=rec.get('state') or {}
     if st.get('readyState',0)>=2 and st.get('videoWidth',0)>0 and st.get('duration',0)>0:
      duration=float(st['duration']);rec['success']=True;rec['duration']=duration
      times=sorted(set([0,3,8,15,30,60,90,round(duration*.25,2),round(duration*.5,2),round(duration*.75,2),max(0,round(duration-5,2))]))
      frame_dir=folder/'frames';frame_dir.mkdir(exist_ok=True);frames=[]
      for t in times:
       try:
        await v.evaluate("(v,t)=>{v.pause();v.currentTime=Math.min(Math.max(0,t),v.duration-.4)}",t);await page.wait_for_timeout(2200);p=frame_dir/f'frame_{t:08.2f}s.jpg';await v.screenshot(path=str(p),quality=90);frames.append(p)
       except Exception as e:rec.setdefault('frame_errors',[]).append({'time':t,'error':repr(e)})
      await page.screenshot(path=str(folder/'page.jpg'),full_page=True,quality=80);sheet(frames,folder/'直接視聴コンタクトシート.jpg',f'{vid} / {duration:.1f}秒')
      rec['network_interesting']=[x for x in net if any(k in x['url'] for k in ['videoplayback','companion','googlevideo','caption'])][:200];await page.close();return rec
   except Exception as e:rec['error']=repr(e)
   attempts.append(rec);await page.close();await asyncio.sleep(1)
 return {'success':False,'attempts':attempts}
async def main():
 summary=[]
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required','--no-sandbox']);context=await browser.new_context(viewport={'width':1365,'height':768},locale='ja-JP',ignore_https_errors=True,user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36')
  for vid,genre,title in VIDEOS:
   folder=OUT/vid;folder.mkdir(exist_ok=True);rec=await try_one(context,vid,folder);rec.update(video_id=vid,genre=genre,title=title);(folder/'result.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8');summary.append(rec);print(json.dumps({'id':vid,'success':rec.get('success'),'base':rec.get('base'),'duration':rec.get('duration')},ensure_ascii=False),flush=True)
  await browser.close()
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'overview.json').write_text(json.dumps({'requested':len(VIDEOS),'success':sum(x.get('success') for x in summary),'failed':[x['video_id'] for x in summary if not x.get('success')]},ensure_ascii=False,indent=2),encoding='utf-8')
asyncio.run(main())
