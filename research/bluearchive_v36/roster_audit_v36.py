#!/usr/bin/env python3
from __future__ import annotations
import csv, json, re, time, unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse
from bs4 import BeautifulSoup
from curl_cffi import requests

BASE='https://bluearchive.wikiru.jp/'
GENERIC=re.compile(r'^(?:トップ|編集|一覧|検索|ヘルプ|生徒一覧|NPC一覧|フィルタテーブル版|ステータス一覧|攻撃属性別|学校別|銃種別|声優別|絵師別|HALO一覧|プロフィール一覧|キャラ呼称表|実装履歴|募集|イベント|ロビー)$')
CODELIKE=re.compile(r'(?i)^(?:Automata|Citizen|Enemy|NPC|Mob|Raid|Boss|ID)[_\d-]')

def norm(s:str)->str:
    s=unicodedata.normalize('NFKC',s or '')
    s=s.replace('(', '（').replace(')', '）').replace('*','＊')
    s=re.sub(r'\s+','',s)
    return s.strip()

def display(d):
    fam=(d.get('family_name_jp') or '').strip(); giv=(d.get('given_name_jp') or d.get('given_name') or '').strip()
    base=fam+giv if fam else giv
    if not base: base=str(d.get('code') or d.get('name') or f"ID{d.get('id')}")
    skin=(d.get('skin_jp') or '').strip()
    if not skin:
        raw=(d.get('skin') or '').strip()
        if raw.lower() not in {'','original','default','初始','默认'}: skin=raw
    entry=f'{base}（{skin}）' if skin else base
    page=f'{giv}（{skin}）' if skin else giv
    return base,giv,skin,entry,page

def load(root:Path):
    idx=json.loads((root/'data/students/index.json').read_text(encoding='utf-8'))
    rows=[]
    for it in idx.get('items',[]):
        p=root/f"data/students/{int(it['id'])}.json"
        if not p.exists(): continue
        d=json.loads(p.read_text(encoding='utf-8')).get('data',{})
        base,giv,skin,entry,page=display(d)
        installed=bool(d.get('is_install_jp',d.get('is_install',False))); npc=bool(d.get('is_npc'))
        status='JP実装済み生徒・衣装' if installed and not npc else ('NPC・敵・市民' if npc else '未実装・その他・コラボ差分')
        aliases={page,entry,giv,base}
        if page=='シロコ（テラー）': aliases.add('シロコ＊テラー')
        if page=='ホシノ（1年生）': aliases.add('ホシノ（臨戦）')
        aliases={norm(x) for x in aliases if x}
        rows.append({'student_id':int(d.get('id') or it['id']),'character_entry':entry,'base_character':base,'given_name_jp':giv,'variant_jp':skin,'status':status,'is_npc':npc,'jp_implemented':installed and not npc,'release_date_jp':d.get('release_date') or '', 'expected_wikiru_page':page,'aliases':aliases})
    return idx,sorted(rows,key=lambda x:x['student_id'])

def get(session,url):
    last=None
    for i in range(5):
        try:
            r=session.get(url,timeout=60,allow_redirects=True)
            if r.status_code==200:return r
            last=RuntimeError(f'HTTP {r.status_code}')
        except Exception as e:last=e
        time.sleep(1+i)
    raise RuntimeError(f'{url}: {last!r}')

def extract_page_names(html_text,final_url):
    soup=BeautifulSoup(html_text,'html.parser')
    body=soup.select_one('div#body') or soup.select_one('main') or soup
    out=set(); links=[]
    for a in body.find_all('a',href=True):
        text=a.get_text(' ',strip=True)
        href=urljoin(final_url,a['href'])
        if text and not GENERIC.match(text): out.add(norm(text))
        q=urlparse(href).query
        if q and not q.startswith(('cmd=','plugin=')):
            page=unquote(q.split('&',1)[0]).rstrip('=')
            if page and not GENERIC.match(page): out.add(norm(page))
        links.append({'text':text,'href':href})
    return out,links,soup.title.get_text(' ',strip=True) if soup.title else ''

def main():
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='StuArchive'); ap.add_argument('--out',default='research/bluearchive_v36/roster_out')
    args=ap.parse_args(); root=Path(args.root); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    idx,rows=load(root)
    s=requests.Session(impersonate='chrome'); s.headers.update({'User-Agent':'Mozilla/5.0 BlueArchiveRosterAudit/36','Accept-Language':'ja-JP,ja;q=0.9'})
    char=get(s,BASE+'?'+quote('キャラクター一覧')); npc=get(s,BASE+'?'+quote('NPC一覧'))
    char_names,char_links,char_title=extract_page_names(char.text,str(char.url)); npc_names,npc_links,npc_title=extract_page_names(npc.text,str(npc.url))
    audit=[]
    for r in rows:
        exact=norm(r['expected_wikiru_page'])
        cm=exact in char_names; nm=exact in npc_names
        alias_c=sorted(a for a in r['aliases'] if a in char_names); alias_n=sorted(a for a in r['aliases'] if a in npc_names)
        any_c=cm or bool(alias_c); any_n=nm or bool(alias_n)
        generic=bool(CODELIKE.match(r['base_character'])) or len(r['given_name_jp'])<2
        if r['jp_implemented']:
            coverage='confirmed_cross_source' if any_c else 'metadata_only_needs_manual_check'
        elif r['is_npc']:
            coverage='confirmed_cross_source' if any_n else ('generic_asset_entity_not_expected_in_wikiru' if generic else 'metadata_only_needs_manual_check')
        else:
            coverage='wikiru_or_metadata_confirmed' if (any_c or any_n) else 'metadata_only_unimplemented_or_other'
        audit.append({k:v for k,v in r.items() if k!='aliases'} | {
            'wikiru_student_exact_match':cm,'wikiru_student_alias_matches':' | '.join(alias_c),'wikiru_npc_exact_match':nm,'wikiru_npc_alias_matches':' | '.join(alias_n),'cross_source_coverage':coverage,'generic_or_code_entity':generic,
        })
    fields=list(audit[0])
    with (out/'全481エントリ_母集団網羅性監査_v36.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(audit)
    missing=[r for r in audit if r['cross_source_coverage']=='metadata_only_needs_manual_check']
    with (out/'要手動確認エントリ_v36.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(missing)
    summary={
      'generated_at_source':idx.get('generated_at'), 'metadata_total':len(rows),
      'status_counts':dict(Counter(r['status'] for r in rows)),
      'implemented_student_outfit_total':sum(r['jp_implemented'] for r in rows),
      'npc_total':sum(r['is_npc'] for r in rows),
      'unimplemented_other_total':sum(not r['jp_implemented'] and not r['is_npc'] for r in rows),
      'wikiru_character_anchor_names':len(char_names),'wikiru_npc_anchor_names':len(npc_names),
      'implemented_cross_source_confirmed':sum(r['jp_implemented'] and r['cross_source_coverage']=='confirmed_cross_source' for r in audit),
      'implemented_manual_check':sum(r['jp_implemented'] and r['cross_source_coverage']=='metadata_only_needs_manual_check' for r in audit),
      'named_npc_cross_source_confirmed':sum(r['is_npc'] and r['cross_source_coverage']=='confirmed_cross_source' for r in audit),
      'manual_check_total':len(missing),'wikiru_character_page_title':char_title,'wikiru_npc_page_title':npc_title,
      'definition_note':'481 entries are database records, not 481 distinct human students. Outfit forms are separate entries; NPC/enemy/citizen and unimplemented/collaboration/other records are included.',
    }
    (out/'summary_roster_v36.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
