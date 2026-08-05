#!/usr/bin/env python3
import io,json
from pathlib import Path
from urllib.parse import quote,urlencode
import requests
from PIL import Image
out=Path('artifact_bluearchive_legacy_image_test');out.mkdir(exist_ok=True)
prompt='cinematic Japanese anime game event CG, Ryuuge Kisaki swimsuit from Blue Archive, exact dark indigo braided hair, half-lidded blue violet eyes, thin lavender sunglasses, petite body, black navy swimsuit with blue butterfly ornament and charcoal floral summer robe, no halo, no ring, no text, sitting at a summer beach rest hut table, right fingers stopping before a closed black notebook, tea cup and saucer, only one character, natural five-finger hands, 16:9'
url='https://image.pollinations.ai/prompt/'+quote(prompt,safe='')+'?'+urlencode({'model':'flux','width':1536,'height':1024,'seed':5441,'nologo':'true','enhance':'false'})
try:
 r=requests.get(url,timeout=600,headers={'User-Agent':'BlueArchiveV54/1.0'})
 rec={'status':r.status_code,'content_type':r.headers.get('content-type'),'bytes':len(r.content),'url':url}
 if r.status_code==200:
  im=Image.open(io.BytesIO(r.content));im.verify();(out/'legacy_scene01.jpg').write_bytes(r.content);rec['size']=list(im.size);rec['format']=im.format
 else:rec['text_head']=r.text[:1000]
except Exception as e:rec={'error':repr(e),'url':url}
(out/'result.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8');print(rec)
