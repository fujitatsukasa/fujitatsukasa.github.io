from __future__ import annotations
import hashlib, html, json, re, shutil, subprocess, sys, time, urllib.parse, zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'research_output'; AS=OUT/'素材'; META=OUT/'metadata'; PARTS=ROOT/'parts'
for d in (OUT,AS,META,PARTS):
    if d.exists(): shutil.rmtree(d,ignore_errors=True)
    d.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','pip','install','--quiet','pillow','playwright','lxml'],check=False)
subprocess.run([sys.executable,'-m','playwright','install','chromium'],check=False)
import requests
from bs4 import BeautifulSoup
from PIL import Image,ImageFile
from playwright.sync_api import sync_playwright
ImageFile.LOAD_TRUNCATED_IMAGES=True
JST=timezone(timedelta(hours=9)); NOW=datetime.now(JST).replace(microsecond=0).isoformat()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36'
S=requests.Session(); S.headers.update({'User-Agent':UA,'Accept-Language':'ja,en;q=0.7'})
items=[]; errors=[]

def safe(s): return re.sub(r'[\\/:*?"<>|\r\n]+','_',s).strip(' .')[:180]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def image_ok(p):
    try:
        with Image.open(p) as im: im.load(); return im.width>=300 and im.height>=180,im.width,im.height
    except: return False,0,0
def probe(p):
    try:
        q=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height:format=duration','-of','json',str(p)],capture_output=True,text=True,timeout=60)
        j=json.loads(q.stdout or '{}'); st=(j.get('streams') or [{}])[0]; f=j.get('format') or {}
        return int(st.get('width') or 0),int(st.get('height') or 0),float(f.get('duration') or 0)
    except: return 0,0,0

def add(aid,p,name,source,page,direct,published,fmt,role,classification,strength,reason,video_origin=''):
    if not p.exists() or p.stat().st_size<8000:return False
    w=h=0;dur=0
    if p.suffix.lower() in ('.jpg','.jpeg','.png','.webp','.gif'):
        ok,w,h=image_ok(p)
        if not ok:p.unlink(missing_ok=True);return False
    elif p.suffix.lower() in ('.mp4','.mkv','.webm','.mov'):
        w,h,dur=probe(p)
        if w<300 or h<180 or dur<0.5:p.unlink(missing_ok=True);return False
    sh=digest(p)
    if any(x['sha256']==sh for x in items):p.unlink(missing_ok=True);return False
    dst=AS/safe(p.name);n=2
    while dst.exists():dst=AS/f'{dst.stem}_{n}{dst.suffix}';n+=1
    if p.resolve()!=dst.resolve():shutil.move(str(p),dst)
    items.append({'asset_id':aid,'filename':dst.name,'path':'素材/'+dst.name,'display_name':name,'source_name':source,'source_page_url':page,'direct_url':direct,'published_at':published,'acquired_at':NOW,'rights_status':'UNKNOWN','asset_format':fmt,'portfolio_role':role,'classification':classification,'evidence_strength':strength,'selection_reason':reason,'source_kind':'新規ウェブ取得','sha256':sh,'width':w,'height':h,'duration':round(dur,3),'video_origin_url':video_origin})
    return True

def get(url,timeout=80):
    e=None
    for n in range(4):
        try:
            r=S.get(url,timeout=timeout,allow_redirects=True);r.raise_for_status();return r
        except Exception as x:e=x;time.sleep(2**n)
    raise e

def save_url(aid,url,fn,**m):
    try:
        r=get(url);ct=(r.headers.get('content-type') or '').lower();ext='.png' if 'png' in ct else '.webp' if 'webp' in ct else '.jpg';p=OUT/safe(Path(fn).stem+ext);p.write_bytes(r.content)
        return add(aid,p,direct=r.url,**m)
    except Exception as e:errors.append({'asset_id':aid,'url':url,'error':repr(e)});return False

def capture_band(aid,url,fn,phrase,name,source,published,reason,height=760):
    p=OUT/safe(fn)
    try:
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True,args=['--no-sandbox']);pg=b.new_page(viewport={'width':1440,'height':1100},user_agent=UA,locale='ja-JP')
            pg.goto(url,wait_until='domcontentloaded',timeout=90000);pg.wait_for_timeout(2500)
            pg.add_style_tag(content='*{font-family:"Noto Sans CJK JP","Noto Sans JP",sans-serif!important;}')
            loc=pg.get_by_text(phrase,exact=False).first;loc.wait_for(state='visible',timeout=25000);box=loc.bounding_box()
            y=max(0,(box or {'y':0})['y']-150);fullh=pg.evaluate('document.documentElement.scrollHeight')
            h=min(height,max(300,fullh-y));pg.screenshot(path=str(p),clip={'x':0,'y':y,'width':1440,'height':h})
            final=pg.url;b.close()
        return add(aid,p,name,source,url,final,published,'UI_CROP','ORIGINAL_EVIDENCE','EVENT_ORIGINAL','原ページ該当箇所',reason)
    except Exception as e:errors.append({'asset_id':aid,'url':url,'error':repr(e)});p.unlink(missing_ok=True);return False

def page_images(url,prefix,fnpre,source,published,maxn,reason):
    try:r=get(url);txt=r.text;soup=BeautifulSoup(txt,'lxml')
    except Exception as e:errors.append({'asset_id':prefix,'url':url,'error':repr(e)});return
    cand=[]
    for m in soup.select('meta[property="og:image"],meta[name="twitter:image"]'):
        if m.get('content'):cand.append((m['content'],'OGP画像'))
    for im in soup.find_all('img'):
        alt=(im.get('alt') or '').strip()
        for a in ('src','data-src','data-original','data-lazy-src'):
            if im.get(a):cand.append((im[a],alt))
        for v in (im.get('srcset') or '').split(','):
            if v.strip():cand.append((v.strip().split()[0],alt))
    raw=html.unescape(txt).replace('\\/','/')
    for u in re.findall(r'https?://[^"\'<>\s]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<>\s]*)?',raw,re.I):cand.append((u,'本文埋込画像'))
    seen=set();saved=0
    for ru,alt in cand:
        u=urllib.parse.urljoin(r.url,ru)
        if u in seen:continue
        seen.add(u);low=u.lower()
        if any(x in low for x in ('logo','icon','avatar','sprite','pixel','banner','loading','favicon','adserver')):continue
        try:
            ir=get(u);ct=(ir.headers.get('content-type') or '').lower();ext='.png' if 'png' in ct else '.webp' if 'webp' in ct else '.jpg';p=OUT/safe(f'{fnpre}_{saved+1:02d}{ext}');p.write_bytes(ir.content)
            ok,w,h=image_ok(p)
            if not ok or p.stat().st_size<18000 or max(w/h,h/w)>4.5:p.unlink(missing_ok=True);continue
            if add(f'{prefix}_{saved+1:02d}',p,alt or f'{source}掲載写真',source,url,ir.url,published,'STILL_IMAGE','LIFE_OPERATION','EVENT_ORIGINAL','当事者・関係者公開写真',reason):saved+=1
            if saved>=maxn:break
        except Exception as e:errors.append({'asset_id':prefix,'url':u,'error':repr(e)})

def try_video(urls):
    for n,u in enumerate(urls,1):
        tmpl=str(OUT/f'50_公開報道動画_{n}.%(ext)s')
        try:
            q=subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--retries','3','--fragment-retries','3','--merge-output-format','mp4','-f','bv*[height<=720]+ba/b[height<=720]/b','-o',tmpl,u],capture_output=True,text=True,timeout=600)
            if q.returncode:errors.append({'asset_id':'news_video','url':u,'error':q.stderr[-1500:]})
        except Exception as e:errors.append({'asset_id':'news_video','url':u,'error':repr(e)})
        vids=[p for p in OUT.glob(f'50_公開報道動画_{n}.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mov')]
        if vids and add('news_video',max(vids,key=lambda p:p.stat().st_size),'今回の事件を扱う公開報道動画','報道機関',u,u,'2026-08-24','VIDEO_CLIP','EVENT_FOOTAGE','DIRECT_REPORTAGE','独立報道動画','不正手口と行政処分を動きで示す',u):return

press='https://www.metro.tokyo.lg.jp/information/press/2026/08/2026082406'
capture_band('official_amount_band',press,'02_東京都公式_取消額返還額.png','取消額及び返還請求額','取消額及び返還請求額','東京都保健医療局','2026-08-24','二つの金額を原発表の該当箇所で示す',800)
capture_band('official_reason_band',press,'03_東京都公式_取消理由.png','取消し等の理由','東京都が示した取消理由','東京都保健医療局','2026-08-24','行政が認定した不正理由の原文を示す',820)
capture_band('official_dates_band',press,'04_東京都公式_通知日.png','団体への交付決定取消等通知日','取消しと返還の通知日','東京都保健医療局','2026-08-24','処分日と公表時期を区別する',700)
capture_band('official_police_band',press,'05_東京都公式_警察連携.png','新宿警察署','新宿警察署への情報提供','東京都保健医療局','2026-08-24','警察連携の原発表を示す',650)
portal='https://www.npo-homepage.go.jp/npoportal/gyosei-print/013006834'
capture_band('npo_portal_readable',portal,'12_NPO法人ポータル_解散情報_日本語.png','解散年月日','法人の解散年月日と理由','内閣府NPO法人ポータルサイト','2025-10-29','解散日と破産手続開始決定を公示情報で示す',780)

page_images('https://www.mapion.co.jp/news/release/000000008.000104320-all/','mapion','20_第12回コンクール審査発表会','マピオンニュース／PR TIMES','2025-04-02',8,'再チャレンジ東京が中心となった審査発表会・連携活動を示す')
page_images('https://www.excite.co.jp/news/article/Prtimes_2025-04-01-104320-8/','excite','21_第12回コンクール審査発表会_エキサイト','エキサイトニュース／PR TIMES','2025-04-01',6,'再チャレンジ東京が中心となった審査発表会・連携活動を示す')
page_images('https://tie-up.promo/projects/94fd5cf2-aadc-4e7d-bcd6-b0c884a1ec4d','tieup_more','22_再チャレンジ東京_活動掲載','TIE UP PROMOTION','',8,'団体自身が掲載した活動場面を示す')
page_images('https://newsdig.tbs.co.jp/articles/-/2893309','tbs_correct','30_TBS報道_事件固有画像','TBS NEWS DIG','2026-08-24',2,'今回の処分を扱う事件固有報道画像')
capture_band('ann_article_crop','https://news.tv-asahi.co.jp/news_society/articles/000528420.html','31_ANN報道_記事該当箇所.png','領収書を偽造','ANN記事の不正手口説明','ANN NEWS','2026-08-24','偽造領収書、架空相談、授業の報道確認範囲を示す',850)

for u in ['https://production-tieup.s3.ap-northeast-1.amazonaws.com/thumbnails/large/mxORW4B4VTlGEzrLhqCoqr9arDndop9PvcpCqmm2.jpg','https://production-tieup.s3.ap-northeast-1.amazonaws.com/thumbnails/original/mxORW4B4VTlGEzrLhqCoqr9arDndop9PvcpCqmm2.jpg']:
    if save_url('tieup_logo_large',u,'23_再チャレンジ東京_団体ロゴ高解像度.jpg',name='再チャレンジ東京の掲載ロゴ',source='TIE UP PROMOTION',page='https://tie-up.promo/projects/94fd5cf2-aadc-4e7d-bcd6-b0c884a1ec4d',published='',fmt='STILL_IMAGE',role='LIFE_OPERATION',classification='EVENT_ORIGINAL',strength='団体掲載ページ',reason='今回の団体を視覚的に特定'):break

try_video(['https://newsdig.tbs.co.jp/articles/-/2893309','https://news.tv-asahi.co.jp/news_society/articles/000528420.html','https://www.asahi.co.jp/webnews/pages/ann_000528420.html','https://www.qab.co.jp/quebee/video/000528420/'])
summary={'saved_asset_count':len(items),'real_image_count':sum(x['filename'].lower().endswith(('.jpg','.jpeg','.png','.webp','.gif')) for x in items),'real_video_count':sum(x['filename'].lower().endswith(('.mp4','.mkv','.webm','.mov')) for x in items),'items':items,'errors':errors,'acquired_at':NOW}
(META/'collection_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(PARTS/'research_meme_part_01.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in AS.iterdir():
        if p.is_file():z.write(p,'素材/'+p.name)
    z.write(META/'collection_summary.json','collection_summary.json')
print(json.dumps({k:v for k,v in summary.items() if k not in ('items','errors')},ensure_ascii=False))
