#!/usr/bin/env python3
from __future__ import annotations
import json,requests,time
from pathlib import Path

OUT=Path('artifact_youtube_player_api_probe_v61');OUT.mkdir(exist_ok=True)
VIDEO='Ra9F56wUaCo'
API_KEYS=['AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8','AIzaSyC9XL3ZjWDe-1_aD-4W56rvoGhQe9YckQk']
CLIENTS=[
 ('ANDROID','19.44.38',{'androidSdkVersion':30,'hl':'ja','gl':'JP'}),
 ('ANDROID_VR','1.60.19',{'androidSdkVersion':30,'hl':'ja','gl':'JP'}),
 ('IOS','19.45.4',{'deviceMake':'Apple','deviceModel':'iPhone16,2','osName':'iPhone','osVersion':'18.1.0.22B83','hl':'ja','gl':'JP'}),
 ('TVHTML5','7.20250205.16.00',{'hl':'ja','gl':'JP'}),
 ('TVHTML5_SIMPLY_EMBEDDED_PLAYER','2.0',{'hl':'ja','gl':'JP'}),
 ('WEB_EMBEDDED_PLAYER','1.20250205.01.00',{'hl':'ja','gl':'JP'}),
 ('MWEB','2.20250205.01.00',{'hl':'ja','gl':'JP'}),
 ('WEB_CREATOR','1.20250205.01.00',{'hl':'ja','gl':'JP'}),
]
S=requests.Session();S.headers.update({'User-Agent':'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/136 Mobile Safari/537.36','Origin':'https://www.youtube.com','Referer':f'https://www.youtube.com/watch?v={VIDEO}'})
rows=[]
for key in API_KEYS:
 for name,ver,extra in CLIENTS:
  client={'clientName':name,'clientVersion':ver}|extra
  payload={'context':{'client':client},'videoId':VIDEO,'contentCheckOk':True,'racyCheckOk':True}
  if 'EMBEDDED' in name:payload['context']['thirdParty']={'embedUrl':'https://www.youtube.com/'}
  rec={'key_suffix':key[-6:],'client':name,'version':ver}
  try:
   r=S.post(f'https://www.youtube.com/youtubei/v1/player?key={key}&prettyPrint=false',json=payload,timeout=60)
   rec['status']=r.status_code;rec['bytes']=len(r.content);rec['content_type']=r.headers.get('content-type')
   try:
    j=r.json();(OUT/f'{name}_{key[-6:]}.json').write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
    rec['playability']=(j.get('playabilityStatus') or {}).get('status');rec['reason']=(j.get('playabilityStatus') or {}).get('reason')
    rec['has_streaming']=bool(j.get('streamingData'));rec['has_storyboards']=bool(j.get('storyboards'));rec['has_captions']=bool(j.get('captions'))
    rec['title']=((j.get('videoDetails') or {}).get('title'))
    rec['storyboard_keys']=list((j.get('storyboards') or {}).keys())
   except Exception as e:
    rec['json_error']=repr(e);rec['text']=r.text[:1000]
  except Exception as e:rec['error']=repr(e)
  rows.append(rec);print(rec,flush=True);time.sleep(.5)
(OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
