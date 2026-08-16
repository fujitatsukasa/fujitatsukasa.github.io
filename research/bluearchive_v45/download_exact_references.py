#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, io, json, re, sys, time
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'StuArchive')
SHARD=int(sys.argv[2] if len(sys.argv)>2 else 0)
SHARDS=int(sys.argv[3] if len(sys.argv)>3 else 8)
OUT=Path(f'artifact_bluearchive_exact_refs_v45_{SHARD:02d}'); IMG=OUT/'images'; IMG.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'BlueArchiveAppearanceResearch/45','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'})

def safe(s):return re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',s or '')[:90]
def get(url,tries=5):
 last=None
 for i in range(tries):
  try:
   r=S.get(url,timeout=45);r.raise_for_status();im=Image.open(io.BytesIO(r.content));im.load();return r.content,im
  except Exception as e:last=repr(e);time.sleep(1.2*(i+1))
 raise RuntimeError(last)
def ext(im):return {'PNG':'.png','JPEG':'.jpg','WEBP':'.webp','GIF':'.gif'}.get((im.format or '').upper(),'.png')
def digest(b):return hashlib.sha256(b).hexdigest()

idx=json.loads((ROOT/'data/students/index.json').read_text(encoding='utf-8'));rows=[];fails=[]
for pos,it in enumerate(idx['items']):
 if pos%SHARDS!=SHARD:continue
 eid=int(it['id']);p=ROOT/f'data/students/{eid}.json';d=json.loads(p.read_text(encoding='utf-8')).get('data',{}) if p.exists() else {}
 name=(it.get('family_name_jp') or '')+(it.get('given_name_jp') or '')
 skin=it.get('skin_jp') or it.get('skin') or '通常';urls=[]
 for kind,key in [('公式アバター','avatar'),('SDモデル','sd_model_image'),('メモリアルロビー静止画','recollection_lobby_image')]:
  u=d.get(key) or (it.get(key) if key=='avatar' else None)
  if isinstance(u,str) and u.startswith('http'):urls.append((kind,u))
 seen=set()
 for kind,u in urls:
  if u in seen:continue
  seen.add(u);rec={'entry_id':eid,'name_jp':name,'skin_jp':skin,'kind':kind,'source_url':u}
  try:
   b,im=get(u);sh=digest(b);fn=f'{eid:04d}_{safe(name)}_{safe(skin)}_{safe(kind)}_{sh[:12]}{ext(im)}';dst=IMG/fn;dst.write_bytes(b)
   rec.update(local_path=str(dst.relative_to(OUT)),sha256=sh,width=im.width,height=im.height,format=im.format,mode=im.mode,bytes=len(b),verified=True)
  except Exception as e:rec.update(error=repr(e),verified=False);fails.append(rec.copy())
  rows.append(rec)
with (OUT/'manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
 fields=['entry_id','name_jp','skin_jp','kind','source_url','local_path','sha256','width','height','format','mode','bytes','verified','error'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'manifest.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
(OUT/'summary.json').write_text(json.dumps({'shard':SHARD,'rows':len(rows),'verified':sum(bool(r.get('verified')) for r in rows),'entries_with_avatar':len({r['entry_id'] for r in rows if r.get('verified') and r['kind']=='公式アバター'}),'failures':len(fails)},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(rows),'verified':sum(bool(r.get('verified')) for r in rows),'failures':len(fails)}))