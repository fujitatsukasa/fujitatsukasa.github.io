#!/usr/bin/env python3
from __future__ import annotations
import json,re,requests,urllib.parse
from pathlib import Path
SITES=[
 'https://quicktranscript.ai/',
 'https://www.outlyo.com/tools/youtube-transcript-generator',
 'https://transcriptgrab.com/',
 'https://yttools.co/',
 'https://voxtly.com/',
 'https://transcriptifyyt.com/',
 'https://www.scriptbase.app/en/youtube-transcript',
 'https://transcript.you/',
 'https://www.ytranscript.net/',
 'https://youtubetotranscriptai.com/',
]
OUT=Path('artifact_transcript_site_probe');OUT.mkdir(exist_ok=True)
S=requests.Session();S.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36','Accept-Language':'en-US,en;q=.8'})
records=[]
for site in SITES:
 rec={'site':site,'scripts':[],'matches':[]}
 try:
  r=S.get(site,timeout=60);rec['status']=r.status_code;rec['html_bytes']=len(r.content);html=r.text
  host=urllib.parse.urlparse(site).netloc.replace(':','_');d=OUT/host;d.mkdir(exist_ok=True)
  (d/'index.html').write_text(html,encoding='utf-8',errors='ignore')
  srcs=re.findall(r'<script[^>]+src=["\']([^"\']+)',html,re.I)
  for idx,src in enumerate(srcs[:100]):
   u=urllib.parse.urljoin(site,src)
   try:
    rr=S.get(u,timeout=60);txt=rr.text;name=f'{idx:03d}_'+re.sub(r'[^A-Za-z0-9._-]+','_',urllib.parse.urlparse(u).path.split('/')[-1] or 'script.js')
    if len(txt)<8_000_000:(d/name).write_text(txt,encoding='utf-8',errors='ignore')
    pats=[]
    patterns=[r'https?://[^"\'\s`]+',r'/api/[A-Za-z0-9_?&=./${}-]+',r'fetch\((.{0,500})',r'axios\.(?:get|post)\((.{0,500})',r'transcript.{0,400}',r'youtube.{0,400}']
    for pat in patterns:
     for m in re.finditer(pat,txt,re.I|re.S):
      val=m.group(0).replace('\n',' ')[:800]
      if any(k in val.lower() for k in ['transcript','youtube','caption','subtitle','/api/']):pats.append(val)
      if len(pats)>=200:break
     if len(pats)>=200:break
    rec['scripts'].append({'url':u,'status':rr.status_code,'bytes':len(rr.content),'matches':pats[:200]})
   except Exception as e:rec['scripts'].append({'url':u,'error':repr(e)})
  for pat in [r'/api/[A-Za-z0-9_?&=./${}-]+',r'fetch\((.{0,500})',r'transcript.{0,400}',r'youtube.{0,400}']:
   for m in re.finditer(pat,html,re.I|re.S):
    v=m.group(0).replace('\n',' ')[:800]
    if any(k in v.lower() for k in ['transcript','youtube','caption','subtitle','/api/']):rec['matches'].append(v)
    if len(rec['matches'])>=200:break
  rec['matches']=rec['matches'][:200]
 except Exception as e:rec['error']=repr(e)
 records.append(rec);print(site,rec.get('status'),sum(len(x.get('matches',[])) for x in rec.get('scripts',[])),flush=True)
(OUT/'probe.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sites':len(records),'ok':sum(r.get('status')==200 for r in records)},ensure_ascii=False))
