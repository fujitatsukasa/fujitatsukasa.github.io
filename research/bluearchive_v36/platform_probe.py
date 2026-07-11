#!/usr/bin/env python3
from __future__ import annotations
import json, re, time
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup
from curl_cffi import requests

OUT=Path('research/bluearchive_v36/probe_out'); OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session(impersonate='chrome')
s.headers.update({'User-Agent':'Mozilla/5.0 BlueArchiveResearchAudit/36','Accept-Language':'ja,en;q=0.8,ko;q=0.7,zh-CN;q=0.6'})

def get(name,url,as_json=False):
 r={'name':name,'url':url}
 try:
  x=s.get(url,timeout=45,allow_redirects=True)
  r.update(status=x.status_code,final_url=str(x.url),content_type=x.headers.get('content-type',''),bytes=len(x.content))
  if as_json:
   try:
    j=x.json(); r['json_type']=type(j).__name__; r['json_preview']=json.dumps(j,ensure_ascii=False)[:5000]
   except Exception as e: r['json_error']=repr(e); r['preview']=x.text[:2000]
  else:
   so=BeautifulSoup(x.text,'html.parser'); r['title']=so.title.get_text(' ',strip=True) if so.title else ''; r['preview']=re.sub(r'\s+',' ',so.get_text(' ',strip=True))[:3000]
 except Exception as e: r['error']=repr(e)
 print(name,r.get('status'),r.get('bytes'),r.get('error',''))
 return r

tests=[
 ('reddit_posts','https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=BlueArchive&query=Mika&over_18=false&limit=25',True),
 ('reddit_comments','https://arctic-shift.photon-reddit.com/api/comments/search?subreddit=BlueArchive&body=Mika&limit=25',True),
 ('bluesky','https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=Misono%20Mika%20Blue%20Archive&limit=25',True),
 ('bilibili','https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=%E5%9C%A3%E5%9B%AD%E6%9C%AA%E8%8A%B1%20%E7%A2%A7%E8%93%9D%E6%A1%A3%E6%A1%88&page=1&page_size=10',True),
 ('wikiru_comment','https://bluearchive.wikiru.jp/?'+quote('コメント/ミカ',safe='/'),False),
 ('yahoo_realtime','https://search.yahoo.co.jp/realtime/search?p='+quote('聖園ミカ ブルアカ')+'&ei=UTF-8',False),
 ('fivech_find','https://find.5ch.net/search?q='+quote('ミカ ブルアカ'),False),
 ('arca','https://arca.live/b/bluearchive?target=all&keyword='+quote('미소노 미카'),False),
 ('dcinside','https://gall.dcinside.com/mgallery/board/lists/?id=projectmx&s_type=search_subject_memo&s_keyword='+quote('미카'),False),
 ('tieba','https://tieba.baidu.com/f/search/res?ie=utf-8&kw='+quote('碧蓝档案')+'&qw='+quote('圣园未花'),False),
 ('ao3','https://archiveofourown.org/works/search?work_search%5Bquery%5D=Misono+Mika+Blue+Archive',False),
]
rows=[]
for a,b,c in tests:
 rows.append(get(a,b,c)); time.sleep(.6)
(OUT/'probe_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
