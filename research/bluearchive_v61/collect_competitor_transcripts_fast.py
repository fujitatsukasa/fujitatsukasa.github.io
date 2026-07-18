#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures as cf
import json,re,time
from pathlib import Path
from typing import Any
import requests
OUT=Path('artifact_competitor_transcripts_v61_fast');OUT.mkdir(parents=True,exist_ok=True)
VIDEOS=[
('Ra9F56wUaCo','SS・数値ルール','「1回 先生の椅子」全員の今日の回数が見えるようになった'),
('TANvlLrVFi8','SS・秘密発覚','先生が実は元軍人で銃の達人だった'),
('DVXk71WMCEY','SS・秘密暴露','先生AIが開発されて生徒の秘密が全部バレた'),
('GYgI1itvJH8','長尺SS・後悔','先生の疲労を見ないようにし続けて後悔するノア'),
('9_hdj8AlsHA','反応集・ドッキリ','先生が血を吐いて倒れるドッキリ'),
('xXaodZ_bZVo','長尺SS集・秘密','先生が義手義足だった場合の反応集'),
('-6rDxHu87GU','あにまん概念スレ反応','ここだけミレニアムが存在しない世界線'),
('lZ7rtLvpavY','解説・ミーム考察','おいしいマシンガンとは何なのか'),
('5MGcVpEEzp4','解説・画風分析','絵をそれっぽくしてバズろう'),
]
EPS=[
('Outlyo','POST','https://www.outlyo.com/api/tools/youtube-transcript-generator','https://www.outlyo.com/tools/youtube-transcript-generator'),
('TranscriptGrab','POST','https://transcriptgrab.com/api/transcript','https://transcriptgrab.com/'),
('YTTools','GET','https://yttools.co/api/transcript','https://yttools.co/'),
('YouTubeToTranscriptAI','GET','https://youtubetotranscriptai.com/api/transcript','https://youtubetotranscriptai.com/'),
]
HEAD={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36','Accept':'application/json,text/plain,*/*','Accept-Language':'ja,en-US;q=.8,en;q=.7'}

def ptime(v):
 if v is None:return None
 if isinstance(v,(int,float)):
  n=float(v);return n/1000 if n>100000 else n
 s=str(v).strip().replace(',','.')
 if not s:return None
 if re.fullmatch(r'\d+(?:\.\d+)?',s):return float(s)
 try:n=[float(x) for x in s.split(':')]
 except:return None
 return n[-1]+(n[-2]*60 if len(n)>=2 else 0)+(n[-3]*3600 if len(n)>=3 else 0)

def walk(o,path='root',depth=0):
 yield path,o
 if depth>=6:return
 if isinstance(o,dict):
  for k,v in o.items():yield from walk(v,f'{path}.{k}',depth+1)
 elif isinstance(o,list):
  for i,v in enumerate(o[:20]):yield from walk(v,f'{path}[{i}]',depth+1)

def normalize(o):
 best=[];bp=None;longstr=None
 for path,v in walk(o):
  if isinstance(v,list) and v:
   rows=[]
   for it in v:
    if not isinstance(it,dict):rows=[];break
    text=next((it.get(k) for k in ['text','content','caption','sentence','transcript','utf8'] if isinstance(it.get(k),str) and it.get(k).strip()),None)
    if not text:rows=[];break
    st=next((ptime(it.get(k)) for k in ['start','offset','time','timestamp','startTime'] if it.get(k) is not None),None)
    en=next((ptime(it.get(k)) for k in ['end','endTime'] if it.get(k) is not None),None)
    du=next((ptime(it.get(k)) for k in ['duration','dur'] if it.get(k) is not None),None)
    if en is None and st is not None and du is not None:en=st+du
    rows.append({'start':st,'end':en,'duration':du,'text':re.sub(r'\s+',' ',text).strip()})
   if len(rows)>len(best):best,bp=rows,path
  elif isinstance(v,str) and len(v)>1000 and any(x in path.lower() for x in ['transcript','content','text']):
   if longstr is None or len(v)>len(longstr[1]):longstr=(path,v)
 if best:return best,{'path':bp}
 if longstr:return [{'start':None,'end':None,'duration':None,'text':re.sub(r'\s+',' ',longstr[1]).strip()}],{'path':longstr[0]}
 return [],{}

def fetch(task):
 vid,genre,title,service,method,url,referer=task;yu=f'https://www.youtube.com/watch?v={vid}'
 s=requests.Session();h=dict(HEAD);h.update({'Referer':referer,'Origin':referer.rstrip('/')})
 rec={'video_id':vid,'genre':genre,'title':title,'service':service,'endpoint':url}
 try:
  if method=='POST':r=s.post(url,json={'url':yu},headers=h,timeout=(20,65))
  else:r=s.get(url,params={'url':yu},headers=h,timeout=(20,65))
  rec.update(status=r.status_code,content_type=r.headers.get('content-type'),bytes=len(r.content),head=r.text[:1000])
  try:o=r.json();rec['json']=o;rows,meta=normalize(o);rec['rows']=rows;rec['meta']=meta;rec['chars']=sum(len(x['text']) for x in rows)
  except Exception as e:rec['json_error']=repr(e);rec['text']=r.text
 except Exception as e:rec['error']=repr(e)
 return rec

tasks=[(v,g,t,s,m,u,r) for v,g,t in VIDEOS for s,m,u,r in EPS]
results=[]
with cf.ThreadPoolExecutor(max_workers=16) as ex:
 for rec in cf.as_completed([ex.submit(fetch,t) for t in tasks]):
  x=rec.result();results.append(x);print(x['video_id'],x['service'],x.get('status'),len(x.get('rows',[])),x.get('error'),flush=True)
by={v:[] for v,_,_ in VIDEOS}
for r in results:by[r['video_id']].append(r)
summary=[]
for vid,genre,title in VIDEOS:
 d=OUT/vid;d.mkdir(exist_ok=True);attempts=[];best=None
 for r in sorted(by[vid],key=lambda x:x['service']):
  rr={k:v for k,v in r.items() if k not in ['json','rows','text']};attempts.append(rr)
  service=r['service']
  if 'json' in r:(d/f'raw_{service}.json').write_text(json.dumps(r['json'],ensure_ascii=False,indent=2),encoding='utf-8')
  elif 'text' in r:(d/f'raw_{service}.txt').write_text(r['text'],encoding='utf-8',errors='ignore')
  if r.get('rows'):
   with (d/f'normalized_{service}.jsonl').open('w',encoding='utf-8') as f:
    for row in r['rows']:f.write(json.dumps(row,ensure_ascii=False)+'\n')
   (d/f'normalized_{service}.txt').write_text('\n'.join(x['text'] for x in r['rows']),encoding='utf-8')
   if best is None or r.get('chars',0)>best.get('chars',0):best=r
 out={'video_id':vid,'genre':genre,'title':title,'youtube_url':f'https://www.youtube.com/watch?v={vid}','success':bool(best),'attempts':attempts}
 if best:
  out.update(chosen_service=best['service'],rows=len(best['rows']),chars=best['chars'],meta=best.get('meta'))
  with (d/'transcript.jsonl').open('w',encoding='utf-8') as f:
   for row in best['rows']:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  (d/'transcript.txt').write_text('\n'.join(x['text'] for x in best['rows']),encoding='utf-8')
 (d/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');summary.append(out)
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'videos':len(summary),'success':sum(x['success'] for x in summary),'chosen':{s:sum(x.get('chosen_service')==s for x in summary) for s,_,_,_ in EPS}},ensure_ascii=False))
