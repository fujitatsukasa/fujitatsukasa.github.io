#!/usr/bin/env python3
from pathlib import Path
import json,requests,io
from PIL import Image
OUT=Path('artifact_storyboard_probe_v61');OUT.mkdir(exist_ok=True)
ids=['Ra9F56wUaCo','GYgI1itvJH8','9_hdj8AlsHA','xXaodZ_bZVo','lZ7rtLvpavY','5MGcVpEEzp4']
patterns=[
 'https://i.ytimg.com/sb/{id}/storyboard3_L0/M{n}.jpg',
 'https://i.ytimg.com/sb/{id}/storyboard3_L1/M{n}.jpg',
 'https://i.ytimg.com/sb/{id}/storyboard3_L2/M{n}.jpg',
 'https://i.ytimg.com/sb/{id}/storyboard3_L3/M{n}.jpg',
 'https://i.ytimg.com/sb/{id}/storyboard3_L0/default.jpg',
 'https://i.ytimg.com/sb/{id}/storyboard3_L1/default.jpg',
 'https://i.ytimg.com/sb/{id}/storyboard3_L2/default.jpg',
]
S=requests.Session();S.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.youtube.com/'})
rows=[]
for vid in ids:
 d=OUT/vid;d.mkdir(exist_ok=True)
 for pat in patterns:
  ns=range(0,15) if '{n}' in pat else [0]
  for n in ns:
   u=pat.format(id=vid,n=n)
   try:
    r=S.get(u,timeout=30);rec={'id':vid,'url':u,'status':r.status_code,'bytes':len(r.content),'content_type':r.headers.get('content-type')}
    if r.status_code==200 and r.content.startswith((b'\xff\xd8',b'\x89PNG')):
     im=Image.open(io.BytesIO(r.content));rec['size']=list(im.size);p=d/(u.split('/')[-2]+'_'+u.split('/')[-1]);p.write_bytes(r.content);rec['local']=str(p.relative_to(OUT))
    rows.append(rec);print(vid,r.status_code,len(r.content),u,flush=True)
   except Exception as e:rows.append({'id':vid,'url':u,'error':repr(e)})
   if rec.get('status')==404 and '{n}' in pat and n==0:break
(OUT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'summary.json').write_text(json.dumps({'files':sum('local' in r for r in rows),'success_urls':[r['url'] for r in rows if 'local' in r]},ensure_ascii=False,indent=2),encoding='utf-8')
