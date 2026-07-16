#!/usr/bin/env python3
from __future__ import annotations
import csv,hashlib,io,json,re,sys,time,unicodedata
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'StuArchive')
OUT=Path(sys.argv[2] if len(sys.argv)>2 else 'artifact_bluearchive_reference_v50'); OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'BlueArchiveVisualReferenceResearch/50','Accept-Language':'ja,en;q=0.8'})
BAD=re.compile(r'(nude|sex|nipples|areola|bondage|cum|guro|vore|explicit|panties|underwear|cameltoe|breast_focus|ass_focus)',re.I)
CATS=[
('パロディ全般','parody','構図・元ネタの置換'),('ミーム','meme','反応・字幕・オチ'),('描き直し','redraw','有名構図の再現'),('四コマ','4koma','起承転結'),('漫画風','manga','コマ割り・効果線'),('モノクロ漫画','monochrome','白黒・スクリーントーン'),('映画ポスター','movie_poster','主役配置・タイトル余白'),('アルバムジャケット','album_cover','正方形構図'),('雑誌表紙','magazine_cover','人物寄り・見出し'),('新聞','newspaper','紙面・見出し'),('指名手配','wanted_poster','正面像・罪状'),('警察写真','mugshot','正面・横・身長線'),('身分証','id_card','顔・所属・番号'),('カード','trading_card','枠・数値・能力'),('タロット','tarot','象徴物・上下対称'),('ゲーム画面','game_ui','UI・数値・選択肢'),('ビジュアルノベル','visual_novel','立ち絵・会話窓'),('偽画面','fake_screenshot','架空UI'),('SNS画面','social_media','投稿・返信'),('テレビ番組','television','テロップ・ワイプ'),('広告','advertisement','商品・短い訴求'),('監視カメラ','security_camera','固定画角・時刻'),('魚眼','fisheye','誇張遠近'),('斜め構図','dutch_angle','緊張・勢い'),('分割画面','split_screen','同時進行・対比'),('複数視点','multiple_views','正面・側面・背面'),('設定画','character_sheet','人物構造・衣装差分'),('図解','diagram','矢印・注釈'),('インフォグラフィック','infographic','比較・整理'),('ピクセルアート','pixel_art','ゲーム風'),('ちびキャラ','chibi','反応・頭身圧縮'),('デフォルメ','super_deformed','誇張表情'),('レトロ調','retro_artstyle','年代感・印刷色'),('浮世絵風','ukiyo-e','平面構図'),('ステンドグラス','stained_glass','分割面・発光色'),('影絵','silhouette','形で見せる'),('宣伝ポスター風','propaganda','見上げ・短文'),('防犯映像','cctv','低彩度・監視表示'),('ニュース','news','速報・下帯')]
COMMONS=[('新聞一面','newspaper front page'),('雑誌表紙','magazine cover design'),('映画ポスター','public domain movie poster'),('指名手配','wanted poster'),('警察身長線','mugshot height chart'),('監視カメラ','CCTV security camera monitor'),('古い広告','vintage advertisement poster'),('プロパガンダ','public domain propaganda poster'),('設計図','blueprint technical drawing'),('証拠ボード','investigation evidence board'),('タロット','tarot card public domain'),('漫画コマ','comic strip public domain'),('ピクセルアート','pixel art public domain'),('浮世絵','ukiyo-e public domain'),('ステンドグラス','stained glass public domain'),('ニュース','television news studio'),('スポーツ中継','sports broadcast television'),('商品パッケージ','vintage product packaging'),('身分証','identification card sample'),('地図作戦図','military map briefing'),('フィルムノワール','film noir office public domain'),('VHS画面','VHS screen static'),('年鑑写真','school yearbook page')]

def safe(s,n=90):
 s=unicodedata.normalize('NFKC',s or ''); s=re.sub(r'[\\/:*?"<>|\r\n]+','_',s); s=re.sub(r'\s+','_',s).strip('._ '); return s[:n] or 'untitled'
def getj(url,params=None,tries=4):
 e=None
 for i in range(tries):
  try:
   r=S.get(url,params=params,timeout=60)
   if r.status_code==200:return r.json(),str(r.url)
   e=RuntimeError(f'HTTP {r.status_code}')
  except Exception as x:e=x
  time.sleep(i+1)
 raise RuntimeError(f'{url}: {e!r}')
def getimg(url,tries=4):
 e=None
 for i in range(tries):
  try:
   r=S.get(url,timeout=90,allow_redirects=True)
   if r.status_code!=200: raise RuntimeError(f'HTTP {r.status_code}')
   b=r.content; im=Image.open(io.BytesIO(b)); im.verify(); im=Image.open(io.BytesIO(b)); return b,im.format or '',im.width,im.height,r.headers.get('content-type','')
  except Exception as x:e=x; time.sleep(i+1)
 raise RuntimeError(f'{url}: {e!r}')
def ext(fmt,url):
 m={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','GIF':'.gif'}
 return m.get(fmt.upper(),Path(urlparse(url).path).suffix.lower() or '.img')
records=[]; fails=[]; seen_sha=set(); seen_post=set()
def save(b,fmt,w,h,folder,stem,rec):
 sha=hashlib.sha256(b).hexdigest()
 if sha in seen_sha:return False
 seen_sha.add(sha); folder.mkdir(parents=True,exist_ok=True); p=folder/(safe(stem)+ext(fmt,rec.get('image_url',''))); p.write_bytes(b)
 rec.update(local_path=str(p.relative_to(OUT)),sha256=sha,bytes=len(b),width=w,height=h,format=fmt); records.append(rec); return True

# Blue Archive public general-rated fan examples.
root=OUT/'01_ブルアカ二次創作パロディ実例'
for label,tag,role in CATS:
 try:
  arr,api=getj('https://danbooru.donmai.us/posts.json',{'tags':f'blue_archive {tag} rating:g order:score','limit':5,'only':'id,file_url,large_file_url,tag_string_general,tag_string_character,source,rating,score,created_at'})
  for p in arr if isinstance(arr,list) else []:
   pid=int(p.get('id') or 0); tags=(p.get('tag_string_general') or '')+' '+(p.get('tag_string_character') or '')
   if not pid or pid in seen_post or p.get('rating')!='g' or BAD.search(tags):continue
   u=p.get('large_file_url') or p.get('file_url')
   if not u or Path(urlparse(u).path).suffix.lower() in {'.webm','.mp4','.zip'}:continue
   try:
    b,fmt,w,h,ct=getimg(u); rec={'source_group':'ブルアカ二次創作','category':label,'reference_role':role,'title':f'Danbooru post {pid}','source_page':f'https://danbooru.donmai.us/posts/{pid}','image_url':u,'original_source':p.get('source'),'license_note':'公開二次創作の参照例。作者・出典はsource_pageとoriginal_sourceを確認。','rating':'g','score':p.get('score'),'created_at':p.get('created_at'),'characters':p.get('tag_string_character'),'general_tags':p.get('tag_string_general'),'api_url':api,'content_type':ct}
    if save(b,fmt,w,h,root/safe(label),f'{pid}_{tag}',rec):seen_post.add(pid)
   except Exception as x:fails.append({'stage':'danbooru_download','category':label,'post_id':pid,'error':repr(x)})
  time.sleep(.7)
 except Exception as x:fails.append({'stage':'danbooru_query','category':label,'tag':tag,'error':repr(x)})

# Official Blue Archive gallery images from StuArchive/Kivo public mirror.
off=OUT/'02_公式作品の場面と作風'; gdir=ROOT/'data/galleries'
if gdir.exists():
 for p in sorted(gdir.glob('*.json')):
  if p.name in {'index.json','lookup.json'}:continue
  try:
   d=json.loads(p.read_text(encoding='utf-8')).get('data',{}); gid=int(d.get('id') or p.stem); title=d.get('title') or f'gallery_{gid}'; n=0
   for cat in d.get('categorys') or d.get('categories') or []:
    for it in cat.get('images') or []:
     if n>=3:break
     u=it.get('image') or it.get('url')
     if not u:continue
     try:
      b,fmt,w,h,ct=getimg(u); rec={'source_group':'ブルアカ公式・準公式資料','category':title,'reference_role':'公式の画面密度・色・背景・人物配置','title':it.get('introduction') or Path(urlparse(u).path).name,'source_page':f'https://kivo.wiki/gallery/{gid}','image_url':u,'original_source':'Kivo public mirror of Blue Archive gallery metadata','license_note':'公式・準公式画像の参照。元権利表記は各公式媒体に従う。','gallery_id':gid,'gallery_category':cat.get('name') or 'Default','content_type':ct}
      if save(b,fmt,w,h,off/f'{gid:03d}_{safe(title)}',f'{n+1:02d}_{Path(urlparse(u).path).stem}',rec):n+=1
     except Exception as x:fails.append({'stage':'official_download','gallery':gid,'image_url':u,'error':repr(x)})
    if n>=3:break
  except Exception as x:fails.append({'stage':'official_parse','path':str(p),'error':repr(x)})

# Open general composition/style references from Wikimedia Commons.
com=OUT/'03_一般参考画像'
for label,q in COMMONS:
 try:
  j,api=getj('https://commons.wikimedia.org/w/api.php',{'action':'query','format':'json','generator':'search','gsrsearch':q,'gsrnamespace':6,'gsrlimit':3,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':1600}); got=0
  for page in ((j.get('query') or {}).get('pages') or {}).values():
   if got>=2:break
   info=(page.get('imageinfo') or [{}])[0]; u=info.get('thumburl') or info.get('url')
   if not u:continue
   try:
    b,fmt,w,h,ct=getimg(u); em=info.get('extmetadata') or {}; title=page.get('title') or label; rec={'source_group':'一般構図・作風資料','category':label,'reference_role':'構図・紙面・時代感・照明の参考','title':title,'source_page':info.get('descriptionurl'),'image_url':u,'original_source':info.get('url'),'license_note':(em.get('LicenseShortName') or {}).get('value'),'artist':(em.get('Artist') or {}).get('value'),'credit':(em.get('Credit') or {}).get('value'),'commons_query':q,'api_url':api,'content_type':ct}
    if save(b,fmt,w,h,com/safe(label),f'{got+1:02d}_{safe(title)}',rec):got+=1
   except Exception as x:fails.append({'stage':'commons_download','category':label,'image_url':u,'error':repr(x)})
  time.sleep(.3)
 except Exception as x:fails.append({'stage':'commons_query','category':label,'query':q,'error':repr(x)})

fields=sorted({k for r in records for k in r})
with (OUT/'全参考画像一覧.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(records)
with (OUT/'全参考画像一覧.jsonl').open('w',encoding='utf-8') as f:
 for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
(OUT/'取得失敗.json').write_text(json.dumps(fails,ensure_ascii=False,indent=2),encoding='utf-8')
summary={'records':len(records),'bluearchive_fanwork':sum(r.get('source_group')=='ブルアカ二次創作' for r in records),'official_gallery':sum(r.get('source_group')=='ブルアカ公式・準公式資料' for r in records),'general_reference':sum(r.get('source_group')=='一般構図・作風資料' for r in records),'failures':len(fails),'unique_sha256':len(seen_sha),'categories':sorted({r.get('category') for r in records})}
(OUT/'取得結果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False))
