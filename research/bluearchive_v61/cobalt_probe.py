#!/usr/bin/env python3
from __future__ import annotations
import json,requests
from pathlib import Path
OUT=Path('artifact_cobalt_probe_v61');OUT.mkdir(exist_ok=True)
url='https://www.youtube.com/watch?v=Ra9F56wUaCo'
instances=['https://api.cobalt.tools/','https://cobalt-api.meowing.de/','https://cobalt-api.hyper.lol/','https://cobalt-api.kwiatekmiki.com/']
rows=[]
for inst in instances:
 rec={'instance':inst}
 try:
  r=requests.post(inst,json={'url':url,'videoQuality':'360','downloadMode':'auto','filenameStyle':'basic'},headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'Mozilla/5.0'},timeout=120)
  rec|={'status':r.status_code,'bytes':len(r.content),'content_type':r.headers.get('content-type'),'text':r.text[:2000]}
  try:
   j=r.json();rec['json']=j
   if isinstance(j,dict):
    media=j.get('url') or j.get('downloadUrl')
    if media:
     rr=requests.get(media,stream=True,timeout=300,headers={'User-Agent':'Mozilla/5.0'})
     rec['media_status']=rr.status_code;rec['media_type']=rr.headers.get('content-type');rec['media_length']=rr.headers.get('content-length')
     if rr.status_code==200:
      p=OUT/'sample_media.bin'
      with p.open('wb') as f:
       n=0
       for chunk in rr.iter_content(1024*1024):
        if not chunk:continue
        f.write(chunk);n+=len(chunk)
        if n>150*1024*1024:break
      rec['saved_bytes']=p.stat().st_size
  except Exception as e:rec['json_error']=repr(e)
 except Exception as e:rec['error']=repr(e)
 rows.append(rec);print(rec,flush=True)
(OUT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
