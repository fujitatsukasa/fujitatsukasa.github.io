#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys, time, unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'StuArchive')
SHARD=int(sys.argv[2] if len(sys.argv)>2 else 0)
SHARDS=int(sys.argv[3] if len(sys.argv)>3 else 8)
OUT=Path(f'artifact_bluearchive_visual_tags_v45_{SHARD:02d}'); OUT.mkdir(parents=True,exist_ok=True)
UA='BlueArchiveAppearanceResearch/45 (public general-rated metadata only)'
VARIANT_MAP={'水着':['swimsuit'],'泳装':['swimsuit'],'正月':['new_year'],'ドレス':['dress'],'体操服':['gym','track'],'バニーガール':['bunny'],'メイド':['maid'],'パジャマ':['pajama'],'臨戦':['armed','battle'],'武装':['armed'],'制服':['school_uniform','uniform'],'私服':['casual'],'キャンプ':['camping'],'アイドル':['idol'],'ガイド':['guide'],'バンド':['band'],'応援団':['cheerleader'],'温泉':['hot_springs'],'幼女':['young'],'一年生':['first_year'],'チーパオ':['china_dress'],'クリスマス':['christmas'],'ライディング':['riding'],'サイクリング':['cycling']}
ALLOW_EXACT=set('''black_hair brown_hair blonde_hair orange_hair red_hair pink_hair purple_hair blue_hair green_hair white_hair grey_hair silver_hair multicolored_hair two-tone_hair gradient_hair streaked_hair black_eyes brown_eyes red_eyes pink_eyes purple_eyes blue_eyes green_eyes yellow_eyes grey_eyes orange_eyes heterochromia short_hair medium_hair long_hair very_long_hair bob_cut hair_over_one_eye hair_between_eyes swept_bangs blunt_bangs parted_bangs asymmetrical_bangs sidelocks ahoge ponytail high_ponytail low_ponytail side_ponytail twintails low_twintails braid braided_ponytail bun_hair double_bun hair_down hair_up hair_ribbon hairband hairclip hair_ornament hair_bow scrunchie hair_flower hairpin animal_ears cat_ears dog_ears wolf_ears fox_ears rabbit_ears horns wings tail glasses monocle eyepatch headphones headset hat cap beret school_uniform sailor_collar blazer jacket coat cardigan sweater vest shirt collared_shirt dress_shirt necktie bowtie ribbon neck_ribbon ascot skirt pleated_skirt pencil_skirt shorts pants dress sundress kimono yukata swimsuit one-piece_swimsuit bikini maid headdress apron bunny_suit track_suit gym_uniform long_sleeves short_sleeves sleeveless detached_sleeves gloves fingerless_gloves arm_warmers thighhighs kneehighs socks pantyhose leggings boots shoes loafers sneakers sandals belt harness holster pouch backpack shoulder_bag handbag briefcase armband badge name_tag epaulettes fur_trim cape cloak hood scarf petite tall short_person slim athletic muscular curvy broad_shoulders narrow_waist long_legs flat_chest small_bust medium_bust full_bust smile grin smirk serious expressionless frown sad angry surprised embarrassed blush closed_mouth open_mouth fang looking_at_viewer looking_away looking_back looking_down looking_up profile three-quarter_view front_view from_side from_behind standing sitting kneeling crouching running walking leaning crossed_arms arms_behind_back hands_on_hips hand_on_hip hand_to_face hand_in_pocket holding holding_weapon holding_book holding_phone pointing salute confident_pose relaxed_pose dynamic_pose fighting_stance contrapposto crossed_legs legs_together feet_apart solo multiple_girls indoors outdoors office classroom street rooftop cafe bedroom laboratory night sunset rain'''.split())
PREFIXES=('hair_','eye_','school_','sailor_','animal_','holding_','looking_','from_','hand_','arms_','legs_','feet_')
BLOCK=re.compile(r'(nude|sex|breast_focus|panties|underwear|cleavage|cameltoe|ass|nipples|areola|bondage|fetish|cum|vore|guro|pregnan|loli|shota)',re.I)

def get_json(base,params,tries=5):
 url=base+'?'+urlencode(params); last=None
 for i in range(tries):
  try:
   req=Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
   with urlopen(req,timeout=45) as r:return json.load(r),url
  except Exception as e:last=repr(e);time.sleep(1.2*(i+1))
 raise RuntimeError(f'{url}: {last}')

def norm(s):
 s=unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()
 return re.sub(r'[^a-z0-9]+','_',s).strip('_')

def load_entries():
 idx=json.loads((ROOT/'data/students/index.json').read_text(encoding='utf-8'));out=[]
 for it in idx['items']:
  p=ROOT/f"data/students/{int(it['id'])}.json";d=json.loads(p.read_text(encoding='utf-8')).get('data',{}) if p.exists() else {};out.append((it,d))
 return out

def candidate_score(name,it,d):
 n=name.lower()
 if 'blue_archive' not in n:return -999
 parts=set(re.findall(r'[a-z0-9]+',n.replace('blue_archive','')))
 given=norm(d.get('given_name_en') or it.get('given_name_jp') or it.get('given_name'))
 family=norm(d.get('family_name_en') or it.get('family_name_jp') or it.get('family_name'))
 given_parts=[p for p in given.split('_') if p];family_parts=[p for p in family.split('_') if p]
 # All given-name tokens must appear as complete components; substring matches such as aru -> koharu are rejected.
 if given_parts and not all(p in parts for p in given_parts):return -999
 score=9+3*len(given_parts)
 if family_parts and all(p in parts for p in family_parts):score+=7
 if family and given and (family+'_'+given) in n:score+=5
 skin=(it.get('skin_jp') or it.get('skin') or '');wanted=[]
 for k,v in VARIANT_MAP.items():
  if k in skin:wanted+=v
 if wanted:score+=max([5 if x in n else 0 for x in wanted] or [0])
 else:score-=sum(3 for x in sum(VARIANT_MAP.values(),[]) if x in n)
 score+=min(int(d.get('is_install',False)),1)
 return score

def choose_tag(it,d):
 given=norm(d.get('given_name_en') or it.get('given_name_jp') or it.get('given_name'));family=norm(d.get('family_name_en') or it.get('family_name_jp') or it.get('family_name'));queries=[]
 if given:queries.append(f'*{given}*blue_archive*')
 if family and given:queries.append(f'*{family}*{given}*blue_archive*')
 best=None
 for q in queries:
  try:arr,url=get_json('https://danbooru.donmai.us/tags.json',{'search[category]':4,'search[name_matches]':q,'search[order]':'count','limit':100})
  except Exception:continue
  for t in arr if isinstance(arr,list) else []:
   sc=candidate_score(t.get('name',''),it,d);key=(sc,int(t.get('post_count') or 0))
   if best is None or key>best[0]:best=(key,t,url)
  time.sleep(.25)
 if best and best[0][0]>=10:return best[1],best[2]
 return None,None

def wanted_tag(tag):return bool(tag and not BLOCK.search(tag) and (tag in ALLOW_EXACT or tag.startswith(PREFIXES)))
def fetch_common(tag):
 arr,url=get_json('https://danbooru.donmai.us/posts.json',{'tags':tag+' rating:general','limit':100,'only':'id,tag_string_general,tag_string_character,rating'});c=Counter();n=0
 for p in arr if isinstance(arr,list) else []:
  if p.get('rating')!='g':continue
  n+=1
  for t in (p.get('tag_string_general') or '').split():
   if wanted_tag(t):c[t]+=1
 return n,[{'tag':t,'count':v,'share':round(v/n,4) if n else 0} for t,v in c.most_common(120)],url

entries=load_entries();rows=[];failures=[]
for pos,(it,d) in enumerate(entries):
 if pos%SHARDS!=SHARD:continue
 rec={'entry_id':int(it['id']),'display_name':(it.get('family_name_jp') or '')+(it.get('given_name_jp') or ''),'skin_jp':it.get('skin_jp') or it.get('skin') or ''}
 try:
  tag,search_url=choose_tag(it,d);rec['danbooru_character_tag']=tag.get('name') if tag else None;rec['danbooru_post_count']=int(tag.get('post_count') or 0) if tag else 0;rec['tag_search_source']=search_url
  if tag:n,common,posts_url=fetch_common(tag['name']);rec['general_post_sample_size']=n;rec['visual_tags']=common;rec['posts_source']=posts_url
  else:rec['general_post_sample_size']=0;rec['visual_tags']=[];rec['posts_source']=None
 except Exception as e:rec['error']=repr(e);failures.append(rec.copy())
 rows.append(rec);time.sleep(.45)
with (OUT/'visual_tags.jsonl').open('w',encoding='utf-8') as f:
 for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
(OUT/'summary.json').write_text(json.dumps({'shard':SHARD,'shards':SHARDS,'rows':len(rows),'matched':sum(bool(r.get('danbooru_character_tag')) for r in rows),'failures':len(failures)},ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'rows':len(rows),'matched':sum(bool(r.get('danbooru_character_tag')) for r in rows),'failures':len(failures)}))