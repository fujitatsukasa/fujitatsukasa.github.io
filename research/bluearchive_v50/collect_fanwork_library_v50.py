#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,io,json,re,sys,time,unicodedata
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

OUT=Path(sys.argv[1] if len(sys.argv)>1 else 'artifact_bluearchive_fanwork_v50'); OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'BlueArchiveFanworkReferenceResearch/50','Accept':'application/json'})
BAD=re.compile(r'(nude|sex|nipples|areola|bondage|cum|guro|vore|explicit|panties|underwear|cameltoe|breast_focus|ass_focus)',re.I)
CATS=[
('パロディ全般','parody','構図・元ネタの置換'),('ミーム','meme','反応・字幕・オチ'),('描き直し','redraw','有名構図の再現'),('四コマ','4koma','起承転結'),('漫画風','manga','コマ割り・効果線'),('モノクロ漫画','monochrome','白黒・スクリーントーン'),('映画ポスター','movie_poster','主役配置・タイトル余白'),('アルバムジャケット','album_cover','正方形構図'),('雑誌表紙','magazine_cover','人物寄り・見出し'),('新聞','newspaper','紙面・見出し'),('指名手配','wanted_poster','正面像・罪状'),('警察写真','mugshot','正面・横・身長線'),('身分証','id_card','顔・所属・番号'),('カード','trading_card','枠・数値・能力'),('タロット','tarot','象徴物・上下対称'),('ゲーム画面','game_ui','UI・数値・選択肢'),('ビジュアルノベル','visual_novel','立ち絵・会話窓'),('偽画面','fake_screenshot','架空UI'),('SNS画面','social_media','投稿・返信'),('テレビ番組','television','テロップ・ワイプ'),('広告','advertisement','商品・短い訴求'),('監視カメラ','security_camera','固定画角・時刻'),('魚眼','fisheye','誇張遠近'),('斜め構図','dutch_angle','緊張・勢い'),('分割画面','split_screen','同時進行・対比'),('複数視点','multiple_views','正面・側面・背面'),('設定画','character_sheet','人物構造・衣装差分'),('図解','diagram','矢印・注釈'),('インフォグラフィック','infographic','比較・整理'),('ピクセルアート','pixel_art','ゲーム風'),('ちびキャラ','chibi','反応・頭身圧縮'),('デフォルメ','super_deformed','誇張表情'),('レトロ調','retro_artstyle','年代感・印刷色'),('浮世絵風','ukiyo-e','平面構図'),('ステンドグラス','stained_glass','分割面・発光色'),('影絵','silhouette','形で見せる'),('宣伝ポスター風','propaganda','見上げ・短文'),('防犯映像','cctv','低彩度・監視表示'),('ニュース','news','速報・下帯')]

def safe(s,n=90):
 s=unicodedata.normalize('NFKC',s or ''); s=re.sub(r'[\\/:*?"<>|\r\n]+','_',s); s=re.sub(r'\s+','_',s).strip('._ '); return s[:n] or 'untitled'
def getj(params,tries=5):
 e=None
 for i in range(tries):
  try:
   r=S.get('https://danbooru.donmai.us/posts.json',params=params,timeout=60)
   if r.status_code==200:return r.json(),str(r.url)
   e=RuntimeError(f'HTTP {r.status_code}: {r.text[:500]}')
  except Exception as x:e=x
  time.sleep(1.5*(i+1))
 raise RuntimeError(repr(e))
def getimg(url,tries=4):
 e=None
 for i in range(tries):
  try:
   r=S.get(url,timeout=90,allow_redirects=True)
   if r.status_code!=200:raise RuntimeError(f'HTTP {r.status_code}')
   b=r.content; im=Image.open(io.BytesIO(b)); im.verify(); im=Image.open(io.BytesIO(b)); return b,im.format or '',im.width,im.height
  except Exception as x:e=x; time.sleep(i+1)
 raise RuntimeError(repr(e))
def ext(fmt,url):
 return {'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','GIF':'.gif'}.get(fmt.upper(),Path(urlparse(url).path).suffix.lower() or '.img')

rows=[]; fails=[]; seen=set(); seen_id=set()
for label,tag,role in CATS:
 try:
  # Exactly two search tags; rating and sorting are handled locally to avoid anonymous tag-limit errors.
  arr,api=getj({'tags':f'blue_archive {tag}','limit':100,'only':'id,file_url,large_file_url,tag_string_general,tag_string_character,source,rating,score,created_at'})
  candidates=[]
  for p in arr if isinstance(arr,list) else []:
   pid=int(p.get('id') or 0); text=(p.get('tag_string_general') or '')+' '+(p.get('tag_string_character') or '')
   if not pid or pid in seen_id or p.get('rating')!='g' or BAD.search(text):continue
   u=p.get('large_file_url') or p.get('file_url')
   if not u or Path(urlparse(u).path).suffix.lower() in {'.webm','.mp4','.zip'}:continue
   candidates.append(p)
  candidates.sort(key=lambda p:int(p.get('score') or 0),reverse=True)
  got=0
  for p in candidates:
   if got>=6:break
   pid=int(p['id']); u=p.get('large_file_url') or p.get('file_url')
   try:
    b,fmt,w,h=getimg(u); sha=hashlib.sha256(b).hexdigest()
    if sha in seen:continue
    seen.add(sha); seen_id.add(pid); folder=OUT/safe(label); folder.mkdir(parents=True,exist_ok=True); fp=folder/f'{pid}_{tag}{ext(fmt,u)}'; fp.write_bytes(b)
    rows.append({'category':label,'reference_role':role,'post_id':pid,'score':p.get('score'),'characters':p.get('tag_string_character'),'general_tags':p.get('tag_string_general'),'source_page':f'https://danbooru.donmai.us/posts/{pid}','original_source':p.get('source'),'image_url':u,'api_url':api,'local_path':str(fp.relative_to(OUT)),'sha256':sha,'bytes':len(b),'width':w,'height':h,'format':fmt,'rating':'g','license_note':'公開二次創作の参照例。作者・出典はsource_pageとoriginal_sourceを確認。'}); got+=1
   except Exception as x:fails.append({'stage':'download','category':label,'post_id':pid,'error':repr(x)})
  time.sleep(.7)
 except Exception as x:fails.append({'stage':'query','category':label,'tag':tag,'error':repr(x)})

fields=sorted({k for r in rows for k in r})
with (OUT/'ブルアカ二次創作参考一覧.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
with (OUT/'ブルアカ二次創作参考一覧.jsonl').open('w',encoding='utf-8') as f:
 for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
(OUT/'取得失敗.json').write_text(json.dumps(fails,ensure_ascii=False,indent=2),encoding='utf-8')
summary={'records':len(rows),'categories_with_images':len({r['category'] for r in rows}),'unique_sha256':len(seen),'failures':len(fails)}
(OUT/'取得結果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False))
