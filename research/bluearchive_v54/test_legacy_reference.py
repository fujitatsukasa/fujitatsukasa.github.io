#!/usr/bin/env python3
import io,json
from pathlib import Path
from urllib.parse import quote,urlencode
import requests
from PIL import Image
out=Path('artifact_bluearchive_legacy_reference_test');out.mkdir(exist_ok=True)
avatar='https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/Student_Portrait_CH0356_Collection.png'
memory='https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/CH0356_home_Idle_01_5.jpg'
prompt='Edit the reference character into one polished 2D Japanese anime game event CG. Preserve her exact face, hair, eyes, glasses, petite proportions, black swimsuit, butterfly ornament, and floral robe. Remove the halo completely. She sits at a beach rest hut table and pauses before touching a closed black notebook beside a tea cup. One character only, no text, no logo, natural hands, cinematic 16:9.'
results=[]
for model in ['kontext','flux','turbo']:
 params={'model':model,'width':1536,'height':1024,'seed':5442,'nologo':'true','enhance':'false','image':avatar+'|'+memory}
 url='https://image.pollinations.ai/prompt/'+quote(prompt,safe='')+'?'+urlencode(params)
 rec={'model':model,'url':url}
 try:
  r=requests.get(url,timeout=600,headers={'User-Agent':'BlueArchiveV54/1.0'});rec.update(status=r.status_code,content_type=r.headers.get('content-type'),bytes=len(r.content))
  if r.status_code==200:
   im=Image.open(io.BytesIO(r.content));im.verify();ext='.png' if im.format=='PNG' else '.jpg';(out/f'{model}{ext}').write_bytes(r.content);rec.update(size=list(im.size),format=im.format,saved=f'{model}{ext}')
  else:rec['text_head']=r.text[:1000]
 except Exception as e:rec['error']=repr(e)
 results.append(rec)
(out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(results)
