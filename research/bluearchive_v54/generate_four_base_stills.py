#!/usr/bin/env python3
from __future__ import annotations
import io,json
from pathlib import Path
from urllib.parse import quote,urlencode
import requests
from PIL import Image
out=Path('artifact_bluearchive_four_base_stills_v54');out.mkdir(exist_ok=True)
scenes={
'01_notebook': 'polished 2D Japanese anime game event CG, cinematic 16:9, a very petite dignified dark indigo haired young woman with a long low front braid and thin lavender sunglasses, black navy swimsuit with blue butterfly ornament and charcoal floral summer robe, sitting deeply in a chair at a bright summer beach rest hut table, closed black notebook beside a white tea cup and saucer, her right index and middle fingers stop just before touching the notebook corner, left hand on chair arm, restrained expression, only one character, no halo, no ring, no magic circle, no text, no logo, natural five-finger hands, cel shaded, clean line art',
'02_conversation': 'polished 2D Japanese anime game event CG, cinematic 16:9, quiet summer beach rest hut, two women having a calm private conversation across a small wooden table, left is a very petite dark indigo haired young woman with long front braid, thin lavender sunglasses, black navy swimsuit and charcoal floral robe, seated with closed black notebook and tea cup, right is a tall mature dark-haired woman with black cat ears, bright green eyes, navy floral bikini and loose white summer cover-up, standing and leaning slightly toward the table, natural eye contact, only these two characters, no halo, no ring, no text, natural hands, cel shaded',
'03_invoice': 'polished 2D Japanese anime game event CG, cinematic 16:9, summer beach rest hut reception area, a nervous young clerk shown from behind holds a delivery invoice with both hands, facing a very petite dark indigo haired woman with front braid and lavender sunglasses seated on the right, and a tall black-haired cat-eared woman with bright green eyes standing on the left, the invoice is the visual focus, exactly three people, no extra faces, no halo, no ring, no text, natural hands, cel shaded, clean game story illustration',
'04_saucer': 'polished 2D Japanese anime game event CG, cinematic 16:9 macro close-up of a wooden table in a summer rest hut, a white long-sleeved right hand gently places a white saucer on top of a closed black notebook, fresh tea cup on the saucer, another small hand withdraws from the notebook on the right edge, only hands and forearms visible, no faces, no people in background, no halo, no ring, no text, anatomically natural five-finger hands, soft afternoon light, cel shaded game event illustration'
}
results=[]
for idx,(name,prompt) in enumerate(scenes.items(),1):
 for variant,seed in [('a',5500+idx*10),('b',5501+idx*10)]:
  params={'model':'flux','width':1536,'height':1024,'seed':seed,'nologo':'true','enhance':'false'}
  url='https://image.pollinations.ai/prompt/'+quote(prompt,safe='')+'?'+urlencode(params)
  rec={'scene':name,'variant':variant,'seed':seed,'url':url}
  try:
   r=requests.get(url,timeout=600,headers={'User-Agent':'BlueArchiveV54/1.0'});rec.update(status=r.status_code,content_type=r.headers.get('content-type'),bytes=len(r.content))
   if r.status_code==200:
    im=Image.open(io.BytesIO(r.content));im.verify();fn=f'{name}_{variant}.jpg';(out/fn).write_bytes(r.content);rec.update(saved=fn,size=list(im.size),format=im.format)
   else:rec['text_head']=r.text[:500]
  except Exception as e:rec['error']=repr(e)
  results.append(rec)
(out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(results)
