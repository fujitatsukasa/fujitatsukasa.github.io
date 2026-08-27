from __future__ import annotations
import hashlib,json,re,shutil,subprocess,sys,time,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'research_output';AS=OUT/'素材';META=OUT/'metadata';PARTS=ROOT/'parts'
for d in (OUT,AS,META,PARTS):
    if d.exists():shutil.rmtree(d,ignore_errors=True)
    d.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-m','pip','install','--quiet','pillow','playwright'],check=False)
subprocess.run([sys.executable,'-m','playwright','install','chromium'],check=False)
from PIL import Image
from playwright.sync_api import sync_playwright
NOW=datetime.now(timezone(timedelta(hours=9))).replace(microsecond=0).isoformat();UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36'
items=[];errors=[]
def safe(s):return re.sub(r'[\\/:*?"<>|\r\n]+','_',s)[:180]
def add(aid,p,name,source,page,published,reason):
    try:
        with Image.open(p) as im:im.load();w,h=im.size
    except Exception:return False
    if w<600 or h<400:return False
    sh=hashlib.sha256(p.read_bytes()).hexdigest()
    if any(x['sha256']==sh for x in items):return False
    dst=AS/p.name;shutil.move(str(p),dst)
    items.append({'asset_id':aid,'filename':dst.name,'path':'素材/'+dst.name,'display_name':name,'source_name':source,'source_page_url':page,'direct_url':page,'published_at':published,'acquired_at':NOW,'rights_status':'UNKNOWN','asset_format':'UI_CROP','portfolio_role':'ORIGINAL_EVIDENCE','classification':'EVENT_ORIGINAL','evidence_strength':'原ページ該当箇所','selection_reason':reason,'source_kind':'新規ウェブ取得','sha256':sh,'width':w,'height':h,'duration':0,'video_origin_url':''});return True

def viewport(aid,url,fn,phrases,name,source,published,reason):
    p=OUT/safe(fn)
    try:
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True,args=['--no-sandbox']);pg=b.new_page(viewport={'width':1440,'height':1000},user_agent=UA,locale='ja-JP')
            pg.goto(url,wait_until='domcontentloaded',timeout=90000);pg.wait_for_timeout(2500);pg.add_style_tag(content='*{font-family:"Noto Sans CJK JP","Noto Sans JP",sans-serif!important;}')
            loc=None
            for ph in phrases:
                q=pg.get_by_text(ph,exact=False).first
                try:q.wait_for(state='attached',timeout=12000);loc=q;break
                except:pass
            if loc is None:raise RuntimeError('phrase not found '+repr(phrases))
            loc.evaluate('(e)=>e.scrollIntoView({block:"center",inline:"nearest"})');pg.wait_for_timeout(900);pg.screenshot(path=str(p),full_page=False)
            b.close()
        add(aid,p,name,source,url,published,reason)
    except Exception as e:errors.append({'asset_id':aid,'url':url,'error':repr(e)});p.unlink(missing_ok=True)

def full(aid,url,fn,name,source,published,reason):
    p=OUT/safe(fn)
    try:
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True,args=['--no-sandbox']);pg=b.new_page(viewport={'width':1440,'height':1000},user_agent=UA,locale='ja-JP')
            pg.goto(url,wait_until='domcontentloaded',timeout=90000);pg.wait_for_timeout(2500);pg.add_style_tag(content='*{font-family:"Noto Sans CJK JP","Noto Sans JP",sans-serif!important;}');pg.screenshot(path=str(p),full_page=True);b.close()
        add(aid,p,name,source,url,published,reason)
    except Exception as e:errors.append({'asset_id':aid,'url':url,'error':repr(e)});p.unlink(missing_ok=True)
press='https://www.metro.tokyo.lg.jp/information/press/2026/08/2026082406'
viewport('official_reason_view',press,'03_東京都公式_取消理由_該当画面.png',['偽りその他不正の手段','交付決定に付した条件に違反'],'東京都が示した取消理由','東京都保健医療局','2026-08-24','行政が認定した二つの取消理由を原文で示す')
viewport('official_dates_view',press,'04_東京都公式_通知日_該当画面.png',['令和7年8月28日','令和7年6月6日'],'取消しと返還の通知日','東京都保健医療局','2026-08-24','取消しと返還請求の通知日を原文で示す')
viewport('official_police_view',press,'05_東京都公式_警察連携_該当画面.png',['新宿警察署に対して','新宿警察署'],'新宿警察署への情報提供','東京都保健医療局','2026-08-24','警察への情報提供を原文で示す')
viewport('ann_report_view','https://news.tv-asahi.co.jp/news_society/articles/000528420.html','31_ANN報道_不正手口該当画面.png',['領収書を偽造','架空請求'],'ANN報道の不正手口説明','ANN NEWS','2026-08-24','領収書偽造、架空相談、架空授業の報道確認範囲を示す')
full('npo_portal_full','https://www.npo-homepage.go.jp/npoportal/gyosei-print/013006834','12_NPO法人ポータル_法人情報_日本語.png','法人の解散情報','内閣府NPO法人ポータルサイト','2025-10-29','法人公示ページを無改変で示す')
summary={'saved_asset_count':len(items),'real_image_count':len(items),'real_video_count':0,'items':items,'errors':errors,'acquired_at':NOW}
(META/'collection_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(PARTS/'research_meme_part_01.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in AS.iterdir():z.write(p,'素材/'+p.name)
    z.write(META/'collection_summary.json','collection_summary.json')
print(json.dumps({k:v for k,v in summary.items() if k not in ('items','errors')},ensure_ascii=False))
