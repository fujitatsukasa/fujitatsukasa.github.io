#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, io, json, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image

OUT=Path('artifact_bluearchive_v62_assets');OUT.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers.update({'User-Agent':'BlueArchiveV62FinalAssets/1.0','Accept-Language':'ja,en;q=.8'})
MANIFEST={
'アロナ':{'公式アバター':'https://static.kivo.wiki/images/students/%E9%98%BF%E7%BD%97%E5%A8%9C/avatar.png'},
'聖園ミカ':{'公式アバター':'https://static.kivo.wiki/images/students/%E5%9C%A3%E5%9B%AD%E6%9C%AA%E8%8A%B1/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E5%9C%A3%E5%9B%AD%E6%9C%AA%E8%8A%B1/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E5%9C%A3%E5%9B%AD%20%E6%9C%AA%E8%8A%B1/original/134A90D9A9CDC033F4B848DF776F8357.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E3839FE382AB_E3839FE382AB5FE7AB8BE381A1E7B5B5312E706E67.png'},
'桐藤ナギサ':{'公式アバター':'https://static.kivo.wiki/images/students/%E6%A1%90%E8%97%A4%20%E6%B8%9A/avatar.png','メモリアル':'https://static.kivo.wiki/images/students/%E6%A1%90%E8%97%A4%20%E6%B8%9A/original/Nagisa_home_Idle_01_4.350499999999995.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E3838AE382AEE382B5_E3838AE382AEE382B55F322E706E67.png'},
'生塩ノア':{'公式アバター':'https://static.kivo.wiki/images/students/%E7%94%9F%E7%9B%90%20%E8%AF%BA%E4%BA%9A/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E7%94%9F%E7%9B%90%20%E8%AF%BA%E4%BA%9A/original/EnemyInfo_CH0095.png','メモリアル':'https://static.kivo.wiki/images/students/%E7%94%9F%E7%9B%90%20%E8%AF%BA%E4%BA%9A/recollection_lobby_image.png'},
'早瀬ユウカ':{'公式アバター':'https://static.kivo.wiki/images/students/%E6%97%A9%E7%80%AC%20%E4%BC%98%E9%A6%99/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E6%97%A9%E7%80%AC%20%E4%BC%98%E9%A6%99/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E6%97%A9%E6%BF%91%20%E4%BC%98%E9%A6%99/original/Yuuka_home_Idle_01_0.9582000000000003.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E383A6E382A6E382AB_E383A6E382A6E382AB28E5B08F292E706E67.png'},
'空崎ヒナ':{'公式アバター':'https://static.kivo.wiki/images/students/%E7%A9%BA%E5%B4%8E%20%E6%97%A5%E5%A5%88/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E7%A9%BA%E5%B4%8E%20%E6%97%A5%E5%A5%88/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E7%A9%BA%E5%B4%8E%20%E6%97%A5%E5%A5%88/original/Hina_home_Idle_01_1.1921000000000022.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E38392E3838A_E38392E3838AE68BA1E5A4A75F322E706E67.png'},
'小鳥遊ホシノ':{'公式アバター':'https://static.kivo.wiki/images/students/%E5%B0%8F%E9%B8%9F%E6%B8%B8%20%E6%98%9F%E9%87%8E/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E5%B0%8F%E9%B8%9F%E6%B8%B8%20%E6%98%9F%E9%87%8E/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E5%B0%8F%E9%B8%9F%E6%B8%B8%20%E6%98%9F%E9%87%8E/original/1.png','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E3839BE382B7E3838E_E3839BE382B7E3838E5F302E706E67.png'},
'砂狼シロコ':{'公式アバター':'https://static.kivo.wiki/images/students/%E7%A0%82%E7%8B%BC%20%E7%99%BD%E5%AD%90/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E7%A0%82%E7%8B%BC%20%E7%99%BD%E5%AD%90/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E7%A0%82%E7%8B%BC%20%E7%99%BD%E5%AD%90/original/Shiroko_home_Idle_01_0.6751000000000005.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382B7E383ADE382B3_E382B7E383ADE382B328E5B08F292E706E67.png'},
'春原シュン':{'公式アバター':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/original/Shun_home_Idle_01_1.2534999999999996.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382B7E383A5E383B3_E382B7E383A5E383B35F302E706E67.png'},
'春原シュン（幼女）':{'公式アバター':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/%E5%B9%BC%E5%A5%B3/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/%E5%B9%BC%E5%A5%B3/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/%E5%B9%BC%E5%A5%B3/CH0066_home_Idle_01_0.7789999999999998.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382B7E383A5E383B3EFBC88E5B9BCE5A5B3EFBC89_E382B7E383A5E383B3EFBC88E5B9BCE5A5B3EFBC892E706E67.png'},
'陸八魔アル':{'公式アバター':'https://static.kivo.wiki/images/students/%E9%99%86%E5%85%AB%E9%AD%94%20%E9%98%BF%E9%9C%B2/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E9%99%86%E5%85%AB%E9%AD%94%20%E9%98%BF%E9%9C%B2/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E9%99%86%E5%85%AB%E9%AD%94%20%E9%98%BF%E9%9C%B2/original/Aru_home_Idle_01_0.7497000000000007.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382A2E383AB_E382A2E383AB5F302E706E67.png'},
'鬼方カヨコ':{'公式アバター':'https://static.kivo.wiki/images/students/%E9%AC%BC%E6%96%B9%20%E4%BD%B3%E4%BB%A3%E5%AD%90/avatar.png','SDモデル':'https://static.kivo.wiki/images/students/%E9%AC%BC%E6%96%B9%20%E4%BD%B3%E4%BB%A3%E5%AD%90/sd_model.png','メモリアル':'https://static.kivo.wiki/images/students/%E9%AC%BC%E6%96%B9%20%E4%BD%B3%E4%BB%A3%E5%AD%90/original/Kayoko_home_Idle_01_2.0334.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382ABE383A8E382B3_E382ABE383A8E382B328E5B08F292E706E67.png'},
'春原シュン（水着）':{'公式アバター':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/%E6%B3%B3%E8%A3%85%20/Student_Portrait_CH0355_Collection.png','SDモデル':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/%E6%B3%B3%E8%A3%85%20/EnemyInfo_CH0355_01.png','メモリアル':'https://static.kivo.wiki/images/students/%E6%98%A5%E5%8E%9F%20%E7%9E%AC/%E6%B3%B3%E8%A3%85%20/CH0355_home_Idle_01_1.403.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382B7E383A5E383B3EFBC88E6B0B4E79D80EFBC89_E382B7E383A5E383B3EFBC88E6B0B4E79D80EFBC892E706E67.png'},
'竜華キサキ（水着）':{'公式アバター':'https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/Student_Portrait_CH0356_Collection.png','SDモデル':'https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/EnemyInfo_CH0356.png','メモリアル':'https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/CH0356_home_Idle_01_5.jpg','全身立ち絵':'https://bluearchive.wikiru.jp/attach2/E382ADE382B5E382ADEFBC88E6B0B4E79D80EFBC89_E382ADE382B5E382ADEFBC88E6B0B4E79D80EFBC892E706E67.png'},
'シュエリン（水着）':{'公式アバター':'https://static.kivo.wiki/images/students/%20%E9%9B%AA%E7%8E%B2/%E6%B3%B3%E8%A3%85/Student_Portrait_CH0355_01_Collection.png','SDモデル':'https://static.kivo.wiki/images/students/%20%E9%9B%AA%E7%8E%B2/%E6%B3%B3%E8%A3%85/EnemyInfo_CH0355_02.png','メモリアル':'https://static.kivo.wiki/images/students/%20%E9%9B%AA%E7%8E%B2/%E6%B3%B3%E8%A3%85/CH0355_home_Start_Idle_01.webm_20260624_234349.575.jpg'}
}

def safe(s):return re.sub(r'[\\/:*?"<>|]+','_',s)
rows=[];fails=[]
for name,items in MANIFEST.items():
    d=OUT/safe(name);d.mkdir(parents=True,exist_ok=True)
    for kind,url in items.items():
        ok=False;err=None
        for attempt in range(5):
            try:
                r=S.get(url,timeout=90,allow_redirects=True);r.raise_for_status();data=r.content
                im=Image.open(io.BytesIO(data));im.verify();im=Image.open(io.BytesIO(data))
                ext={"JPEG":"jpg","PNG":"png","WEBP":"webp"}.get((im.format or '').upper(),Path(urlparse(url).path).suffix.lstrip('.') or 'img')
                p=d/f'{safe(kind)}.{ext}';p.write_bytes(data)
                rows.append({'name':name,'kind':kind,'url':url,'local_path':str(p.relative_to(OUT)),'width':im.width,'height':im.height,'format':im.format,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()});ok=True;break
            except Exception as e:err=repr(e);time.sleep(1+attempt)
        if not ok:fails.append({'name':name,'kind':kind,'url':url,'error':err})
fields=['name','kind','url','local_path','width','height','format','bytes','sha256']
with (OUT/'画像台帳.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'取得結果.json').write_text(json.dumps({'downloaded':len(rows),'failed':len(fails),'failures':fails},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'downloaded':len(rows),'failed':len(fails)},ensure_ascii=False))
