from __future__ import annotations
import json, re, shutil, subprocess, sys, time, urllib.parse, zipfile, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'research_output'; AS=OUT/'素材'; META=OUT/'metadata'; PARTS=ROOT/'parts'
for d in (OUT,AS,META,PARTS):
    if d.exists(): shutil.rmtree(d,ignore_errors=True)
    d.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','pip','install','--quiet','pillow','pymupdf','playwright','lxml'],check=False)
subprocess.run([sys.executable,'-m','playwright','install','chromium'],check=False)
import requests, fitz
from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import sync_playwright
JST=timezone(timedelta(hours=9)); NOW=datetime.now(JST).replace(microsecond=0).isoformat()
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36'
S=requests.Session(); S.headers.update({'User-Agent':UA,'Accept-Language':'ja,en;q=0.7'})
items=[]; errors=[]

def safe(s): return re.sub(r'[\\/:*?"<>|\r\n]+','_',s).strip(' .')[:180]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def valid_image(p):
    try:
        with Image.open(p) as im: im.load(); return im.width>=220 and im.height>=120,im.width,im.height
    except: return False,0,0
def probe(p):
    try:
        q=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height:format=duration','-of','json',str(p)],capture_output=True,text=True,timeout=60)
        j=json.loads(q.stdout or '{}'); st=(j.get('streams') or [{}])[0]; f=j.get('format') or {}
        return int(st.get('width') or 0),int(st.get('height') or 0),float(f.get('duration') or 0)
    except: return 0,0,0

def add(aid,p,name,source,page,direct,published,rights,fmt,role,classification,strength,reason,video_origin=''):
    if not p.exists() or p.stat().st_size<500:return False
    ext=p.suffix.lower(); w=h=0; dur=0
    if ext in ('.jpg','.jpeg','.png','.webp','.gif'):
        ok,w,h=valid_image(p)
        if not ok:p.unlink(missing_ok=True);return False
    elif ext in ('.mp4','.mkv','.webm','.mov'):
        w,h,dur=probe(p)
        if w<220 or h<120 or dur<0.2:p.unlink(missing_ok=True);return False
    elif ext=='.pdf':
        try:
            d=fitz.open(p); w=int(d[0].rect.width); h=int(d[0].rect.height); d.close()
        except: p.unlink(missing_ok=True);return False
    digest=sha(p)
    if any(x['sha256']==digest for x in items):p.unlink(missing_ok=True);return False
    dest=AS/safe(p.name); n=2
    while dest.exists():dest=AS/f'{dest.stem}_{n}{dest.suffix}';n+=1
    if p.resolve()!=dest.resolve():shutil.move(str(p),dest)
    items.append({'asset_id':aid,'filename':dest.name,'path':'素材/'+dest.name,'display_name':name,'source_name':source,'source_page_url':page,'direct_url':direct,'published_at':published,'acquired_at':NOW,'rights_status':rights,'asset_format':fmt,'portfolio_role':role,'classification':classification,'evidence_strength':strength,'selection_reason':reason,'source_kind':'新規ウェブ取得','sha256':digest,'width':w,'height':h,'duration':round(dur,3),'video_origin_url':video_origin})
    return True

def get(url,timeout=75):
    e=None
    for n in range(4):
        try:
            r=S.get(url,timeout=timeout,allow_redirects=True);r.raise_for_status();return r
        except Exception as x:e=x;time.sleep(2**n)
    raise e

def dl(aid,urls,fn,**m):
    for u in urls:
        try:
            r=get(u); p=OUT/safe(fn);p.write_bytes(r.content)
            if add(aid,p,direct=r.url,**m):return True
        except Exception as e:errors.append({'asset_id':aid,'url':u,'error':repr(e)})
    return False

def shot(aid,url,fn,phrase,**m):
    pth=OUT/safe(fn)
    try:
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True,args=['--no-sandbox']);pg=b.new_page(viewport={'width':1440,'height':1700},user_agent=UA,locale='ja-JP')
            pg.goto(url,wait_until='domcontentloaded',timeout=90000);pg.wait_for_timeout(2500)
            loc=pg.get_by_text(phrase,exact=False).first
            try:loc.wait_for(state='visible',timeout=20000); box=loc.locator('xpath=../..').bounding_box()
            except:box=None
            if box:
                x=max(0,box['x']-50);y=max(0,box['y']-70);w=min(1380-x,max(900,box['width']+100));h=min(1450,max(500,box['height']+140))
                pg.screenshot(path=str(pth),clip={'x':x,'y':y,'width':w,'height':h})
            else:pg.screenshot(path=str(pth),full_page=False)
            final=pg.url;b.close()
        return add(aid,pth,direct=final,**m)
    except Exception as e:errors.append({'asset_id':aid,'url':url,'error':repr(e)});pth.unlink(missing_ok=True);return False

def render(pdf_aid,newid,fn,patterns,name,role='ORIGINAL_EVIDENCE'):
    x=next((i for i in items if i['asset_id']==pdf_aid),None)
    if not x:return False
    d=fitz.open(AS/x['filename']);best=(0,0)
    for i in range(d.page_count):
        t=d[i].get_text('text');s=sum(p in t for p in patterns)
        if s>best[0]:best=(s,i)
    i=best[1]; pix=d[i].get_pixmap(matrix=fitz.Matrix(2.3,2.3),alpha=False);p=OUT/safe(fn);pix.save(p);d.close()
    return add(newid,p,name,x['source_name'],x['source_page_url'],x['direct_url']+f'#page={i+1}',x['published_at'],x['rights_status'],'DOCUMENT_CROP',role,'EVENT_ORIGINAL' if role=='ORIGINAL_EVIDENCE' else 'INSTITUTIONAL_CONTEXT','一次資料',name)

def pageimgs(url,prefix,fnpre,source,published,patterns,maxn,role,classification,strength,reason):
    saved=[]
    try:r=get(url);s=BeautifulSoup(r.text,'lxml')
    except Exception as e:errors.append({'asset_id':prefix,'url':url,'error':repr(e)});return saved
    arr=[]
    for m in s.select('meta[property="og:image"],meta[name="twitter:image"]'):
        if m.get('content'):arr.append((m['content'],'OGP'))
    for im in s.find_all('img'):
        alt=(im.get('alt') or '').strip()
        for a in ('src','data-src','data-original','data-lazy-src'):
            if im.get(a):arr.append((im[a],alt))
        for q in (im.get('srcset') or '').split(','):
            if q.strip():arr.append((q.strip().split()[0],alt))
    seen=set()
    for raw,alt in arr:
        u=urllib.parse.urljoin(r.url,raw)
        if u in seen or (patterns and not any(re.search(p,u,re.I) for p in patterns)):continue
        seen.add(u)
        if re.search(r'(logo|icon|avatar|sprite|pixel|loading|adserver)',u,re.I) and not re.search(r'(release_image|challenge|jigyo)',u,re.I):continue
        try:
            ir=get(u);ct=(ir.headers.get('content-type') or '').lower();ext='.png' if 'png' in ct else '.webp' if 'webp' in ct else '.jpg';p=OUT/safe(f'{fnpre}_{len(saved)+1:02d}{ext}');p.write_bytes(ir.content)
            ok,w,h=valid_image(p)
            if not ok or p.stat().st_size<8000:p.unlink(missing_ok=True);continue
            aid=f'{prefix}_{len(saved)+1:02d}'
            if add(aid,p,alt or f'{source}掲載画像',source,url,ir.url,published,'UNKNOWN','STILL_IMAGE',role,classification,strength,reason):saved.append(aid)
            if len(saved)>=maxn:break
        except Exception as e:errors.append({'asset_id':prefix,'url':u,'error':repr(e)})
    return saved

press='https://www.metro.tokyo.lg.jp/information/press/2026/08/2026082406'; attach='https://www.metro.tokyo.lg.jp/documents/d/tosei/20260824_07_01'; portal='https://www.npo-homepage.go.jp/npoportal/gyosei-print/013006834'
base=dict(source='東京都保健医療局',page=press,published='2026-08-24',rights='UNKNOWN（公的機関公開資料）',fmt='UI_CROP',role='ORIGINAL_EVIDENCE',classification='EVENT_ORIGINAL',strength='行政処分一次資料')
shot('official_press',press,'01_東京都公式_処分発表.png','再チャレンジ東京',name='東京都公式の交付取消し・返還命令発表',reason='団体名と処分内容を原発表で示す',**base)
shot('official_amount',press,'02_東京都公式_取消額返還額.png','取消額及び返還請求額',name='取消額及び返還請求額',reason='二つの金額を原発表で示す',**base)
shot('official_reason',press,'03_東京都公式_取消理由.png','偽りその他不正の手段',name='東京都が示した取消理由',reason='行政が認定した不正理由の原文',**base)
shot('official_dates',press,'04_東京都公式_通知日.png','団体への交付決定取消等通知日',name='取消しと返還の通知日',reason='処分日と公表時期を区別する',**base)
shot('official_police',press,'05_東京都公式_警察連携.png','新宿警察署',name='新宿警察署への情報提供',reason='警察連携の原発表',**base)
dl('amount_pdf',[attach,attach+'?download=1'],'06_東京都公式_年度別内訳.pdf',name='年度別取消額・返還請求額内訳',source='東京都保健医療局',page=press,published='2026-08-24',rights='UNKNOWN（公的機関公開資料）',fmt='DOCUMENT_CROP',role='ORIGINAL_EVIDENCE',classification='EVENT_ORIGINAL',strength='行政処分一次資料',reason='七年度と二補助枠の内訳')
render('amount_pdf','amount_page','07_東京都公式_年度別内訳頁.png',['48,939,000','37,793,000','令和6年度'],'年度別取消額・返還請求額内訳')

gurls=['https://www.hokeniryo.metro.tokyo.lg.jp/documents/d/hokeniryo/r7youkou_chiiki','https://www.hokeniryo.metro.tokyo.lg.jp/documents/d/hokeniryo/r6youkou_chiiki','https://www.hokeniryo.metro.tokyo.lg.jp/documents/d/hokeniryo/r5youkou_chiiki']
dl('guideline_pdf',gurls+[u+'?download=1' for u in gurls],'08_東京都公式_自殺対策補助金交付要綱.pdf',name='東京都地域自殺対策強化補助事業補助金交付要綱',source='東京都保健医療局',page='https://www.hokeniryo.metro.tokyo.lg.jp/kenkou/tokyokaigi/minkandantai',published='2025-07-07',rights='UNKNOWN（公的機関公開資料）',fmt='DOCUMENT_CROP',role='MECHANISM_COMPARISON',classification='INSTITUTIONAL_CONTEXT',strength='制度一次資料',reason='審査、現地調査、実績報告、立入検査の根拠')
render('guideline_pdf','guideline_field','09_交付要綱_現地調査頁.png',['現地調査','交付申請','審査'],'申請審査と現地調査','MECHANISM_COMPARISON')
render('guideline_pdf','guideline_inspect','10_交付要綱_立入検査頁.png',['立ち入り','関係者に質問','帳簿','検査'],'立入検査と関係者質問','MECHANISM_COMPARISON')
render('guideline_pdf','guideline_payment','11_交付要綱_実績報告支払頁.png',['実績報告書','精算払','概算払','五年間'],'実績報告と支払・保存規定','MECHANISM_COMPARISON')
shot('npo_portal',portal,'12_NPO法人ポータル_解散情報.png','解散年月日',name='法人の解散年月日と理由',source='内閣府NPO法人ポータルサイト',page=portal,published='2025-10-29',rights='UNKNOWN（公的情報）',fmt='UI_CROP',role='ORIGINAL_EVIDENCE',classification='EVENT_ORIGINAL',strength='法人公示情報',reason='解散日と破産手続開始決定を示す')

dl('tieup_logo',['https://production-tieup.s3.ap-northeast-1.amazonaws.com/thumbnails/small/mxORW4B4VTlGEzrLhqCoqr9arDndop9PvcpCqmm2.jpg'],'13_再チャレンジ東京_団体ロゴ.jpg',name='再チャレンジ東京の掲載ロゴ',source='TIE UP PROMOTION',page='https://tie-up.promo/projects/94fd5cf2-aadc-4e7d-bcd6-b0c884a1ec4d',published='',rights='UNKNOWN',fmt='STILL_IMAGE',role='LIFE_OPERATION',classification='EVENT_ORIGINAL',strength='団体掲載ページ',reason='今回の団体を視覚的に特定')
dl('tieup_activity',['https://production-tieup.s3.ap-northeast-1.amazonaws.com/thumbnails/large/0xCDRvrmayaPQaGfk7Vb3kHMhYeTYfIi41eQX8du.jpg'],'14_再チャレンジ東京_活動写真.jpg',name='いじめ・自殺防止活動の掲載写真',source='TIE UP PROMOTION',page='https://tie-up.promo/projects/94fd5cf2-aadc-4e7d-bcd6-b0c884a1ec4d',published='',rights='UNKNOWN',fmt='STILL_IMAGE',role='LIFE_OPERATION',classification='EVENT_ORIGINAL',strength='団体掲載ページ',reason='団体が掲げた学校・啓発活動を示す')
pageimgs('https://prtimes.jp/main/html/rd/p/000000008.000104320.html','pr','15_再チャレンジ東京_コンクール','PR TIMES','2025-04-01',[r'release_image',r'prcdn'],6,'LIFE_OPERATION','EVENT_ORIGINAL','当事者側公開資料','コンクール・講演の実在場面')
pageimgs('https://compe.japandesign.ne.jp/jigyo-saisei-hyogo-2023/','contest','21_いじめ自殺防止コンクール募集','登竜門','2023',[r'jigyo',r'hyogo',r'uploads'],3,'LIFE_OPERATION','INSTITUTIONAL_CONTEXT','独立募集情報','作文・標語・ポスター募集の外部掲載')
pageimgs('https://www.komei.or.jp/km/oka-akihiko/%E5%B2%A1%E6%98%8E%E5%BD%A6%E3%81%AE%E3%81%97%E3%81%94%E3%81%A8-2/%EF%BC%91%E6%9E%9A%E3%81%AE%E3%83%9D%E3%82%B9%E3%82%BF%E3%83%BC%E3%81%8B%E3%82%89%E3%80%81%EF%BC%91%E4%BA%BA%E3%81%A7%E3%82%82%E6%95%91%E3%81%84%E3%81%9F%E3%81%84%E3%80%81%E6%95%91%E3%81%88%E3%82%8B/','komei','24_学校寄贈ポスター','岡明彦愛知県議会議員公式サイト','',[r'wp-content/uploads'],4,'LIFE_OPERATION','EVENT_ORIGINAL','公人公式活動記録','受賞ポスターの学校掲示・寄贈場面')
pageimgs('https://www.kknews.co.jp/news/20210914yt02','kknews','28_コンクール受賞活動','教育家庭新聞','2021-09-14',[r'wp-content/uploads',r'kknews'],3,'LIFE_OPERATION','DIRECT_REPORTAGE','独立報道','コンクール受賞を起点とした学校活動')

dl('ann_still',['https://news.tv-asahi.co.jp/articles_img/000528420_1200.jpg'],'31_ANN報道_事件固有画像.jpg',name='自殺対策NPO補助金問題のANN報道画像',source='ANN NEWS',page='https://news.tv-asahi.co.jp/news_society/articles/000528420.html',published='2026-08-24 21:14',rights='UNKNOWN',fmt='STILL_IMAGE',role='EVENT_FOOTAGE',classification='DIRECT_REPORTAGE',strength='独立報道写真',reason='今回の処分を扱う事件固有の報道画像')
for pref,fn,u,src in [('tbs','32_TBS報道','https://newsdig.tbs.co.jp/articles/-/2890931?display=1','TBS NEWS DIG'),('fnn','33_FNN報道','https://www.fnn.jp/articles/-/1100503','FNNプライムオンライン'),('abc','34_ABC報道','https://www.asahi.co.jp/webnews/pages/ann_000528420.html','ABCニュース'),('ncc','35_NCC報道','https://www.ncctv.co.jp/news/article/16831490','NCC長崎文化放送')]:
    pageimgs(u,pref,fn,src,'2026-08-24',[r'image',r'img',r'news',r'article',r'thumb',r'ogp'],1,'EVENT_FOOTAGE','DIRECT_REPORTAGE','独立報道写真','今回の処分を扱う事件固有画像')

for n,u in enumerate(['https://news.tv-asahi.co.jp/news_society/articles/000528420.html','https://www.asahi.co.jp/webnews/pages/ann_000528420.html','https://www.qab.co.jp/quebee/video/000528420/','https://www.ncctv.co.jp/news/article/16831490'],1):
    tmpl=str(OUT/f'36_報道動画_{n}.%(ext)s')
    try:subprocess.run([sys.executable,'-m','yt_dlp','--no-playlist','--retries','3','--fragment-retries','3','--merge-output-format','mp4','-f','bv*[height<=720]+ba/b[height<=720]/b','-o',tmpl,u],capture_output=True,text=True,timeout=420)
    except Exception as e:errors.append({'asset_id':'news_video','url':u,'error':repr(e)});continue
    vids=[p for p in OUT.glob(f'36_報道動画_{n}.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mov')]
    if vids and add('news_video',max(vids,key=lambda p:p.stat().st_size),'今回の事件を扱う公開報道動画','ANN系列報道',u,u,'2026-08-24','UNKNOWN','VIDEO_CLIP','EVENT_FOOTAGE','DIRECT_REPORTAGE','独立報道動画','不正手口と行政処分の報道場面',u):break

summary={'saved_asset_count':len(items),'real_image_count':sum(x['filename'].lower().endswith(('.jpg','.jpeg','.png','.webp','.gif')) for x in items),'real_video_count':sum(x['filename'].lower().endswith(('.mp4','.mkv','.webm','.mov')) for x in items),'real_pdf_count':sum(x['filename'].lower().endswith('.pdf') for x in items),'items':items,'errors':errors,'acquired_at':NOW}
(META/'collection_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(PARTS/'research_meme_part_01.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in AS.iterdir():
        if p.is_file():z.write(p,'素材/'+p.name)
    z.write(META/'collection_summary.json','collection_summary.json')
print(json.dumps({k:v for k,v in summary.items() if k not in ('items','errors')},ensure_ascii=False))
