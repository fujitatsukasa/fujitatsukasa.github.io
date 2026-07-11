#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from curl_cffi import requests
from PIL import Image

URL_RE = re.compile(r'https?://[^\s<>"\')\]]+?(?:\.png|\.jpe?g|\.webp|\.gif|\.bmp)(?:\?[^\s<>"\')\]]*)?', re.I)
LOCAL_IMAGE_RE = re.compile(r'(?:\(|\s|^)(images/students/[^\s)]+?\.(?:png|jpe?g|webp|gif))', re.I)
IMG_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}


def clean(s: str, limit: int = 80) -> str:
    s = unicodedata.normalize('NFKC', s or '')
    s = s.replace('/', '／').replace('\\', '＼')
    s = re.sub(r'[<>:"|?*\r\n\t]', '_', s)
    s = re.sub(r'\s+', ' ', s).strip(' .') or '_'
    if len(s) > limit:
        s = s[:limit-9] + '_' + hashlib.sha1(s.encode()).hexdigest()[:8]
    return s


def display(d: dict) -> tuple[str, str]:
    fam = str(d.get('family_name_jp') or '').strip()
    giv = str(d.get('given_name_jp') or d.get('given_name') or f"ID{d.get('id')}").strip()
    skin = str(d.get('skin_jp') or '').strip()
    if not skin:
        raw = str(d.get('skin') or '').strip()
        if raw.lower() not in {'', 'original', 'default', '初始', '默认'}:
            skin = raw
    name = (fam + giv) if fam else giv
    return (f'{name}（{skin}）' if skin else name), skin


def walk_urls(value, path='data'):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk_urls(v, f'{path}.{k}')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk_urls(v, f'{path}[{i}]')
    elif isinstance(value, str):
        for u in URL_RE.findall(value):
            yield path, u.rstrip('.,;')
        # Local gallery markdown paths can be served from static.kivo.wiki.
        for m in LOCAL_IMAGE_RE.finditer(value):
            local_path = m.group(1)
            # Avoid treating a suffix already captured inside an absolute URL as local.
            prefix = value[max(0, m.start(1)-12):m.start(1)].lower()
            if 'http://' in prefix or 'https://' in prefix:
                continue
            yield path, 'https://static.kivo.wiki/' + local_path


def category(key: str, url: str) -> str:
    t = (key + ' ' + url).lower()
    if 'recollection_lobby' in t or '_home_' in t or 'memorial' in t:
        return 'メモリアルロビー'
    if 'sd_model' in t or 'enemyinfo_' in t or '/sd' in t:
        return 'SD・スプライト'
    if 'avatar' in t or 'portrait' in t or 'collection' in t:
        return 'アバター・立ち絵'
    if 'banner' in t:
        return '募集・バナー'
    if 'intro' in t or '紹介' in t:
        return '公式紹介画像'
    if 'gallery' in t or '图集' in t or '設定' in t:
        return '公式図集・設定資料'
    return 'その他キャラクター画像'


def inspect(data: bytes):
    with Image.open(io.BytesIO(data)) as im:
        fmt = im.format or ''
        w, h = im.size
        mode = im.mode
        frames = getattr(im, 'n_frames', 1)
        im.verify()
    return fmt, w, h, mode, frames


def get(session, url: str, retries=4):
    last = None
    for i in range(retries):
        try:
            r = session.get(url, timeout=60, allow_redirects=True)
            if r.status_code == 200:
                return r
            last = RuntimeError(f'HTTP {r.status_code}')
        except Exception as e:
            last = e
        time.sleep(0.8 * (i + 1))
    raise RuntimeError(f'{url}: {last!r}')


def main():
    root = Path('StuArchive')
    ids = json.loads(Path('research/bluearchive_v36/kivo_missing/missing_ids.json').read_text())
    out = Path('research/bluearchive_v36/kivo_missing_out')
    imgroot = out / 'images'
    imgroot.mkdir(parents=True, exist_ok=True)
    s = requests.Session(impersonate='chrome')
    s.headers.update({'User-Agent':'Mozilla/5.0 BlueArchiveKivoCoverage/36','Accept-Language':'ja,en;q=0.8','Referer':'https://kivo.wiki/'})
    rows=[]; failures=[]; seen_sha={}; total_bytes=0; max_bytes=155*1024*1024
    per_id_counts={}
    for n, sid in enumerate(ids, 1):
        p = root / f'data/students/{sid}.json'
        d = json.loads(p.read_text(encoding='utf-8')).get('data', {})
        char, variant = display(d)
        candidates = {}
        for key, url in walk_urls(d):
            if url not in candidates:
                candidates[url] = key
        ordered = sorted(candidates.items(), key=lambda kv: (
            0 if 'recollection_lobby' in kv[1] else 1 if 'avatar' in kv[1] else 2 if 'sd_model' in kv[1] else 3,
            kv[1], kv[0]
        ))
        saved=0
        for url,key in ordered:
            if total_bytes >= max_bytes:
                break
            try:
                r=get(s,url)
                data=bytes(r.content)
                fmt,w,h,mode,frames=inspect(data)
                if w<80 or h<80:
                    continue
                sha=hashlib.sha256(data).hexdigest()
                dup=sha in seen_sha
                if not dup:
                    ext='.'+fmt.lower().replace('jpeg','jpg') if fmt else Path(urlparse(r.url).path).suffix.lower()
                    if ext not in IMG_EXTS: ext='.png'
                    cat=category(key,url)
                    original_name=clean(Path(urlparse(r.url).path).name,70)
                    dest=imgroot/clean(cat,40)/clean(char,60)/f'{sha[:12]}_{original_name}'
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    if not dest.suffix: dest=dest.with_suffix(ext)
                    dest.write_bytes(data)
                    seen_sha[sha]=dest.relative_to(out).as_posix()
                    total_bytes += len(data)
                    saved += 1
                rows.append({
                    'student_id':sid,'character':char,'variant_jp':variant,'category':category(key,url),
                    'json_key_path':key,'source_url':url,'final_url':str(r.url),
                    'local_path':seen_sha[sha],'duplicate_by_sha256':dup,'sha256':sha,'bytes':len(data),
                    'width':w,'height':h,'format':fmt,'mode':mode,'frames':frames,
                })
            except Exception as e:
                failures.append({'student_id':sid,'character':char,'json_key_path':key,'url':url,'error':repr(e)})
        per_id_counts[str(sid)]={'character':char,'candidate_urls':len(ordered),'saved_unique':saved}
        print(n, sid, char, len(ordered), saved, total_bytes, flush=True)
    fields=list(rows[0]) if rows else []
    with (out/'manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    with (out/'failures.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields2=['student_id','character','json_key_path','url','error']; w=csv.DictWriter(f,fieldnames=fields2);w.writeheader();w.writerows(failures)
    summary={
        'requested_entry_count':len(ids),'entries_with_at_least_one_unique_image':sum(v['saved_unique']>0 for v in per_id_counts.values()),
        'valid_image_occurrences':len(rows),'unique_local_image_bodies':len(seen_sha),'sha_duplicate_occurrences':sum(bool(r['duplicate_by_sha256']) for r in rows),
        'local_bytes':total_bytes,'failure_count':len(failures),'per_entry':per_id_counts,
    }
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='per_entry'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
