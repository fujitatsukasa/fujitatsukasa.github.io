#!/usr/bin/env python3
from __future__ import annotations
import io,json,re,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from PIL import Image
import onnxruntime as ort
from huggingface_hub import hf_hub_download

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'StuArchive')
OUT=Path(sys.argv[2] if len(sys.argv)>2 else 'artifact_bluearchive_wdtagger_v45'); OUT.mkdir(parents=True,exist_ok=True)
MODEL_REPO='SmilingWolf/wd-swinv2-tagger-v3'
UA='BlueArchiveAppearanceResearch/45'

# Only visual construction tags are retained. Explicit content tags are discarded.
KEEP_HINTS=(
 'hair','bangs','ponytail','twintails','braid','bun','sidelocks','ahoge','eyes','heterochromia','eyebrows','eyelashes','fang','mole','freckles',
 'glasses','eyepatch','headphones','headset','ear','horn','wing','tail','hat','cap','beret','hairband','hairclip','hair_ornament','ribbon','flower',
 'uniform','sailor','blazer','jacket','coat','cardigan','sweater','vest','shirt','collar','necktie','bowtie','ascot','skirt','shorts','pants','dress','kimono','yukata','swimsuit','maid','apron','bunny','track','gym',
 'sleeve','glove','arm_warmer','thighhigh','kneehigh','sock','pantyhose','legging','boot','shoe','loafer','sneaker','sandal','belt','harness','holster','pouch','bag','backpack','armband','badge','epaulette','fur_trim','cape','cloak','hood','scarf',
 'smile','grin','smirk','serious','expressionless','frown','sad','angry','surprised','embarrassed','blush','closed_mouth','open_mouth',
 'looking','profile','front_view','from_side','from_behind','standing','sitting','kneeling','crouching','running','walking','leaning','crossed_arms','arms_behind_back','hands_on_hips','hand_on_hip','hand_to_face','hand_in_pocket','holding','pointing','salute','crossed_legs','legs_together','feet_apart',
 'petite','tall','short_person','slim','athletic','muscular','broad_shoulders','narrow_waist','long_legs'
)
BLOCK=re.compile(r'(nude|sex|panties|underwear|cleavage|cameltoe|nipples|areola|bondage|fetish|cum|vore|guro|pregnan|loli|shota|breast_focus|ass_focus)',re.I)
TORSO_MAP={'flat_chest':'very_small','small_breasts':'small','medium_breasts':'medium','large_breasts':'full','huge_breasts':'very_full'}

def visual_tag(name:str)->bool:
 if BLOCK.search(name): return False
 return any(h in name for h in KEEP_HINTS) or name in TORSO_MAP

def preprocess(im:Image.Image,w:int,h:int):
 im=im.convert('RGB'); size=max(im.size)
 canvas=Image.new('RGB',(size,size),'white'); canvas.paste(im,((size-im.width)//2,(size-im.height)//2))
 canvas=canvas.resize((w,h),Image.Resampling.BICUBIC)
 arr=np.asarray(canvas,dtype=np.float32)[:,:,::-1]
 return np.expand_dims(arr,0)

def download_image(url,tries=4):
 last=None
 for i in range(tries):
  try:
   r=requests.get(url,timeout=40,headers={'User-Agent':UA}); r.raise_for_status(); return Image.open(io.BytesIO(r.content)),len(r.content)
  except Exception as e:
   last=repr(e); time.sleep(i+1)
 raise RuntimeError(last)

model_path=hf_hub_download(MODEL_REPO,'model.onnx')
tags_path=hf_hub_download(MODEL_REPO,'selected_tags.csv')
tags=pd.read_csv(tags_path)
sess=ort.InferenceSession(model_path,providers=['CPUExecutionProvider'])
inp=sess.get_inputs()[0]; shape=inp.shape
height=int(shape[1] if isinstance(shape[1],int) else 448); width=int(shape[2] if isinstance(shape[2],int) else 448)
idx=json.loads((ROOT/'data/students/index.json').read_text(encoding='utf-8'))
rows=[]; failures=[]
for n,it in enumerate(idx['items'],1):
 rec={'entry_id':int(it['id']),'name_jp':(it.get('family_name_jp') or '')+(it.get('given_name_jp') or ''),'skin_jp':it.get('skin_jp') or it.get('skin') or '', 'avatar_url':it.get('avatar')}
 try:
  im,byte_count=download_image(it['avatar']); rec['image_bytes']=byte_count; rec['image_size']=list(im.size)
  pred=sess.run(None,{inp.name:preprocess(im,width,height)})[0][0]
  out=[]; torso=[]
  for i,p in enumerate(pred):
   name=str(tags.iloc[i]['name']); cat=int(tags.iloc[i]['category'])
   if cat!=0: continue
   prob=float(p)
   if name in TORSO_MAP and prob>=0.18: torso.append({'label':TORSO_MAP[name],'probability':round(prob,4),'source_model_tag':name})
   if prob>=0.18 and visual_tag(name) and name not in TORSO_MAP: out.append({'tag':name,'probability':round(prob,4)})
  out.sort(key=lambda x:x['probability'],reverse=True); torso.sort(key=lambda x:x['probability'],reverse=True)
  rec['visual_tags']=out[:160]; rec['upper_torso_silhouette_candidates']=torso[:3]
 except Exception as e:
  rec['error']=repr(e); failures.append(rec.copy())
 rows.append(rec)
 if n%25==0: print(n,'/',len(idx['items']))
with (OUT/'wdtagger_visual_features.jsonl').open('w',encoding='utf-8') as f:
 for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
(OUT/'summary.json').write_text(json.dumps({'rows':len(rows),'success':sum('error' not in r for r in rows),'failures':len(failures),'model':MODEL_REPO,'threshold':0.18},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')