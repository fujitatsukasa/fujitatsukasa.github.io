#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re, threading, urllib.parse, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE=Path(__file__).parent
OUT=BASE/'output'; MEDIA=OUT/'media'; PAGES=OUT/'pages'; META=OUT/'metadata'
for d in (MEDIA,PAGES,META): d.mkdir(parents=True,exist_ok=True)
SRC=json.loads((BASE/'sources.json').read_text(encoding='utf-8'))
UA={'User-Agent':'Mozilla/5.0 Chrome/131 ActualMemeResearch/1.0','Accept':'*/*'}
MEDIA_EXT={'.jpg','.jpeg','.png','.gif','.webp','.avif','.svg','.mp4','.webm'}
CT_EXT={'image/jpeg':'.jpg','image/png':'.png','image/gif':'.gif','image/webp':'.webp','image/avif':'.avif','image/svg+xml':'.svg','video/mp4':'.mp4','video/webm':'.webm'}
lock=threading.Lock(); seen={}; records=[]; failures=[]; duplicates=[]

def safe(s,n=110):
 s=urllib.parse.unquote(str(s));s=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',s);s=re.sub(r'\s+',' ',s).strip(' ._');return (s or 'media')[:n]
def sha(b):return hashlib.sha256(b).hexdigest()
def get(url,referer=''):
 h=dict(UA)
 if referer:h['Referer']=referer
 return requests.get(url,headers=h,timeout=(8,20),allow_redirects=True)
def absu(base,v):return urllib.parse.urljoin(base,v)
def candidates(base,html):
 soup=BeautifulSoup(html,'html.parser');arr=[]
 for m in soup.select('meta[property="og:image"],meta[name="twitter:image"],meta[property="twitter:image"]'):
  if m.get('content'):arr.append((absu(base,m['content']),'meta_image'))
 for tag in soup.find_all(['img','source','video']):
  for key in ('src','data-src','data-original','data-lazy-src','poster'):
   v=tag.get(key)
   if v and not v.startswith('data:'):arr.append((absu(base,v),'html_media'))
  if tag.get('srcset'):
   for x in tag['srcset'].split(','):
    v=x.strip().split()[0]
    if v:arr.append((absu(base,v),'srcset'))
 for m in re.findall(r'https?://[^"\'< >\s\\]+?\.(?:jpe?g|png|gif|webp|avif|mp4|webm)(?:\?[^"\'< >\s\\]*)?',html,re.I):arr.append((m.replace('\\/','/'),'embedded'))
 out=[];ss=set()
 for u,k in arr:
  u=u.replace('&amp;','&')
  if u not in ss:ss.add(u);out.append((u,k))
 return out
def download(t):
 sid,label,url,folder,referer,source_type=t
 try:
  r=get(url,referer)
  if r.status_code!=200:raise RuntimeError(f'HTTP {r.status_code}')
  b=r.content
  if not b or len(b)>80*1024*1024:raise RuntimeError('empty or too large')
  ct=r.headers.get('content-type','').split(';')[0].lower();head=b[:256].lstrip().lower()
  if ct.startswith('text/html') or head.startswith(b'<!doctype html') or head.startswith(b'<html'):raise RuntimeError('HTML instead of media')
  dg=sha(b)
  with lock:
   if dg in seen:duplicates.append({'source_id':sid,'url':url,'duplicate_of':seen[dg],'sha256':dg});return
   ext=CT_EXT.get(ct)
   if not ext:
    ext=Path(urllib.parse.urlparse(r.url).path).suffix.lower()
    ext='.jpg' if ext=='.jpeg' else (ext if ext in MEDIA_EXT else '.bin')
   od=MEDIA/safe(folder);od.mkdir(parents=True,exist_ok=True);p=od/f'{safe(sid)}__{safe(Path(urllib.parse.urlparse(r.url).path).stem or sid)}{ext}';n=2
   while p.exists():p=od/f'{safe(sid)}_{n}{ext}';n+=1
   p.write_bytes(b);seen[dg]=p.as_posix()
   records.append({'source_id':sid,'label':label,'kind':'actual_media','original_url':url,'final_url':r.url,'referer':referer,'source_type':source_type,'local_path':p.relative_to(OUT).as_posix(),'mime':ct,'bytes':len(b),'sha256':dg})
 except Exception as e:
  with lock:failures.append({'source_id':sid,'url':url,'referer':referer,'error':repr(e),'label':label})

tasks=[]
for s in SRC['direct_sources']:tasks.append((s['id'],s['label'],s['url'],'direct_reference','',s.get('source_type','direct')))
for s in SRC['page_sources']:
 try:
  r=get(s['url'])
  if r.status_code!=200:raise RuntimeError(f'HTTP {r.status_code}')
  html=r.text;p=PAGES/f"{safe(s['id'])}.html";p.write_text(html,encoding='utf-8',errors='replace')
  records.append({'source_id':s['id'],'label':s['label'],'kind':'page_snapshot','original_url':s['url'],'final_url':r.url,'referer':'','source_type':'html','local_path':p.relative_to(OUT).as_posix(),'mime':'text/html','bytes':len(html.encode()),'sha256':sha(html.encode())})
  folder='netmeme_forest' if s['kind']=='crawl_site' else f"page_sources/{s['id']}"
  for i,(u,k) in enumerate(candidates(r.url,html),1):
   if any(x in u.lower() for x in ['favicon','logo.svg','icon-','avatar','emoji','pixel']):continue
   tasks.append((f"{s['id']}_{i:05d}",s['label'],u,folder,r.url,k))
 except Exception as e:failures.append({'source_id':s['id'],'url':s['url'],'referer':'','error':repr(e),'label':s['label']})
uniq={}
for t in tasks:uniq.setdefault(t[2],t)
tasks=list(uniq.values())
with ThreadPoolExecutor(max_workers=24) as ex:
 for f in as_completed([ex.submit(download,t) for t in tasks]):f.result()
fields=sorted({k for r in records for k in r})
with (META/'media_manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
for name,data,fields2 in [('failures.csv',failures,['source_id','url','referer','error','label']),('duplicates.csv',duplicates,['source_id','url','duplicate_of','sha256'])]:
 with (META/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields2);w.writeheader();w.writerows(data)
summary={'candidate_urls':len(tasks),'actual_media_files':sum(r.get('kind')=='actual_media' for r in records),'page_snapshots':sum(r.get('kind')=='page_snapshot' for r in records),'failures':len(failures),'duplicates':len(duplicates),'generated_replacement_media':0,'actual_media_bytes':sum(int(r.get('bytes',0)) for r in records if r.get('kind')=='actual_media')}
(META/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'README_研究用実物ミーム収集.txt').write_text('実際にウェブ上で公開・流通している画像・GIF・掲載ページの研究用収集。モデル生成・自作代替媒体は0件。出典URL、失敗、SHA-256はmetadataへ記録。\n',encoding='utf-8')
zip_path=BASE/'research_meme_actual.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
 for p in sorted(OUT.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(BASE))
print(json.dumps(summary,ensure_ascii=False))
