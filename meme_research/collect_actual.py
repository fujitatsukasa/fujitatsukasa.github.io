#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json, re, shutil, threading, urllib.parse, warnings, zipfile
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter('ignore', InsecureRequestWarning)
BASE = Path(__file__).parent
OUT = BASE / 'coverage_output'
MEDIA = OUT / 'media'
PAGES = OUT / 'pages'
META = OUT / 'metadata'
PARTS = BASE / 'coverage_parts'
for d in (OUT, PARTS):
    if d.exists():
        shutil.rmtree(d)
for d in (MEDIA, PAGES, META, PARTS):
    d.mkdir(parents=True, exist_ok=True)

SRC = json.loads((BASE / 'sources.json').read_text(encoding='utf-8'))
UA = {'User-Agent': 'Mozilla/5.0 Chrome/131 ActualMemeCoverageAudit/3.0', 'Accept': '*/*'}
MEDIA_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.svg', '.mp4', '.webm'}
CT_EXT = {
    'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
    'image/webp': '.webp', 'image/avif': '.avif', 'image/svg+xml': '.svg',
    'video/mp4': '.mp4', 'video/webm': '.webm'
}
CHROME_WORDS = ('favicon', 'logo', 'avatar', 'profile_images', 'emoji', 'pixel', 'tracking', 'sprite', 'loading', 'blank.gif', 'icon-')
lock = threading.Lock()
seen_sha: dict[str, str] = {}
records: list[dict] = []
failures: list[dict] = []
duplicates: list[dict] = []
source_specs = {s['id']: s for s in SRC.get('page_sources', [])}
source_specs.update({s['id']: s for s in SRC.get('direct_sources', [])})


def safe(s: object, n: int = 120) -> str:
    s = urllib.parse.unquote(str(s))
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', s)
    s = re.sub(r'\s+', ' ', s).strip(' ._')
    return (s or 'media')[:n]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm(s: object) -> str:
    s = urllib.parse.unquote(str(s)).lower()
    return re.sub(r'[\s\u3000\-_/|・…!?！？♡♥☆★「」『』（）()\[\]【】.,:;]+', '', s)


def get(url: str, referer: str = '') -> requests.Response:
    headers = dict(UA)
    if referer:
        headers['Referer'] = referer
    return requests.get(url, headers=headers, timeout=(10, 35), allow_redirects=True, verify=False)


def absu(base: str, value: str) -> str:
    return urllib.parse.urljoin(base, value)


def page_title_and_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))[:12000]
    return title, text


def media_candidates(base: str, text: str, page_title: str = '') -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(text, 'html.parser')
    arr: list[tuple[str, str, str]] = []
    for m in soup.select('meta[property="og:image"],meta[name="twitter:image"],meta[property="twitter:image"]'):
        if m.get('content'):
            arr.append((absu(base, m['content']), 'meta_image', page_title))
    for tag in soup.find_all(['img', 'source', 'video']):
        context_parts = [tag.get('alt', ''), tag.get('title', '')]
        parent = tag.parent.get_text(' ', strip=True)[:300] if tag.parent else ''
        context_parts.append(parent)
        context = re.sub(r'\s+', ' ', ' '.join(x for x in context_parts if x)).strip()
        for key in ('src', 'data-src', 'data-original', 'data-lazy-src', 'poster'):
            value = tag.get(key)
            if value and not value.startswith('data:'):
                arr.append((absu(base, value), 'html_media', context or page_title))
        if tag.get('srcset'):
            for item in tag['srcset'].split(','):
                value = item.strip().split()[0]
                if value:
                    arr.append((absu(base, value), 'srcset', context or page_title))
    for match in re.finditer(r'https?://[^"\'< >\s\\]+?\.(?:jpe?g|png|gif|webp|avif|svg|mp4|webm)(?:\?[^"\'< >\s\\]*)?', text, re.I):
        u = match.group(0).replace('\\/', '/')
        left = max(0, match.start() - 140); right = min(len(text), match.end() + 140)
        arr.append((u, 'embedded_absolute', re.sub(r'\s+', ' ', text[left:right])))
    for match in re.finditer(r'["\']((?:/|\.\.?/)[^"\']+?\.(?:jpe?g|png|gif|webp|avif|svg|mp4|webm)(?:\?[^"\']*)?)["\']', text, re.I):
        u = absu(base, match.group(1).replace('\\/', '/'))
        left = max(0, match.start() - 140); right = min(len(text), match.end() + 140)
        arr.append((u, 'embedded_relative', re.sub(r'\s+', ' ', text[left:right])))
    out = []
    seen = set()
    for u, kind, context in arr:
        u = u.replace('&amp;', '&')
        if u not in seen:
            seen.add(u); out.append((u, kind, context[:500]))
    return out


def dimensions(path: Path, mime: str) -> tuple[int, int, int]:
    if mime == 'image/svg+xml' or path.suffix.lower() == '.svg':
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')[:4000]
            vb = re.search(r'viewBox=["\']\s*[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)', text)
            if vb:
                return int(float(vb.group(1))), int(float(vb.group(2))), 1
            w = re.search(r'width=["\']([\d.]+)', text); h = re.search(r'height=["\']([\d.]+)', text)
            if w and h:
                return int(float(w.group(1))), int(float(h.group(1))), 1
        except Exception:
            pass
        return 0, 0, 1
    if mime.startswith('image/'):
        try:
            with Image.open(path) as im:
                return int(im.width), int(im.height), int(getattr(im, 'n_frames', 1))
        except Exception:
            return 0, 0, 0
    return 0, 0, 0


def quality_state(source_category: str, url: str, context: str, mime: str, width: int, height: int, frames: int, direct: bool) -> str:
    hay = (url + ' ' + context).lower()
    if source_category == 'trend_evidence':
        return 'TREND_EVIDENCE_NOT_MEME_MEDIA'
    if any(w in hay for w in CHROME_WORDS):
        return 'PAGE_CHROME_OR_LOW_VALUE'
    if mime.startswith('video/') or frames > 1:
        return 'ACTUAL_ANIMATED_MEME_OR_REFERENCE'
    if direct:
        return 'DIRECT_ACTUAL_MEME_MEDIA'
    if width and height and (width < 140 or height < 100):
        return 'SMALL_THUMBNAIL_REVIEW'
    if source_category in {'meme_archive', 'gif_archive', 'meme_gallery', 'specific_meme_page', 'meme_article'}:
        return 'LIKELY_ACTUAL_MEME_MEDIA'
    return 'UNVERIFIED_PAGE_MEDIA'


def matched_terms(spec: dict, url: str, context: str, page_text: str = '') -> str:
    hay = norm(url + ' ' + context + ' ' + page_text[:3000])
    found = []
    for term in spec.get('expected_terms', []):
        nt = norm(term)
        if nt and nt in hay:
            found.append(term)
    return ' | '.join(found)


def download(task: tuple) -> None:
    sid, parent_id, label, url, folder, referer, source_type, source_category, context, page_text, direct = task
    try:
        r = get(url, referer)
        if r.status_code != 200:
            raise RuntimeError(f'HTTP {r.status_code}')
        b = r.content
        if not b or len(b) > 80 * 1024 * 1024:
            raise RuntimeError('empty or too large')
        ct = r.headers.get('content-type', '').split(';')[0].lower()
        head = b[:256].lstrip().lower()
        if ct.startswith('text/html') or head.startswith(b'<!doctype html') or head.startswith(b'<html'):
            raise RuntimeError('HTML instead of media')
        dg = sha256(b)
        with lock:
            if dg in seen_sha:
                duplicates.append({'source_id': sid, 'url': url, 'duplicate_of': seen_sha[dg], 'sha256': dg})
                return
            ext = CT_EXT.get(ct)
            if not ext:
                ext = Path(urllib.parse.urlparse(r.url).path).suffix.lower()
                ext = '.jpg' if ext == '.jpeg' else (ext if ext in MEDIA_EXT else '.bin')
            od = MEDIA / safe(folder); od.mkdir(parents=True, exist_ok=True)
            p = od / f'{safe(sid)}__{safe(Path(urllib.parse.urlparse(r.url).path).stem or sid)}{ext}'
            n = 2
            while p.exists():
                p = od / f'{safe(sid)}_{n}{ext}'; n += 1
            p.write_bytes(b)
            width, height, frames = dimensions(p, ct)
            q = quality_state(source_category, r.url, context, ct, width, height, frames, direct)
            spec = source_specs.get(parent_id, {})
            seen_sha[dg] = p.relative_to(OUT).as_posix()
            records.append({
                'source_id': sid, 'parent_source_id': parent_id, 'label': label,
                'kind': 'actual_media', 'source_category': source_category,
                'original_url': url, 'final_url': r.url, 'referer': referer,
                'source_type': source_type, 'context': context,
                'matched_terms': matched_terms(spec, r.url, context, page_text),
                'local_path': p.relative_to(OUT).as_posix(), 'mime': ct,
                'bytes': len(b), 'sha256': dg, 'width': width, 'height': height,
                'frames': frames, 'quality_state': q
            })
    except Exception as e:
        with lock:
            failures.append({'source_id': sid, 'parent_source_id': parent_id, 'url': url, 'referer': referer, 'error': repr(e), 'label': label})


def page_urls(spec: dict) -> list[str]:
    url = spec['url']
    pages = int(spec.get('pages', 1) or 1)
    if pages <= 1:
        return [url]
    sep = '&' if '?' in url else '?'
    return [url] + [f'{url}{sep}page={n}' for n in range(2, pages + 1)]


tasks = []
fetched_pages = set()
for s in SRC.get('direct_sources', []):
    tasks.append((s['id'], s['id'], s['label'], s['url'], 'direct_reference', '', 'direct', s.get('source_category', 'direct_meme_media'), s['label'], '', True))

for s in SRC.get('page_sources', []):
    category = s.get('source_category', 'unclassified')
    max_pages = int(s.get('max_pages', 200) or 200)
    queue = deque(page_urls(s))
    page_number = 0
    host = urllib.parse.urlparse(s['url']).netloc
    while queue and page_number < max_pages:
        url = queue.popleft()
        if url in fetched_pages:
            continue
        fetched_pages.add(url); page_number += 1
        try:
            r = get(url)
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}')
            html = r.text
            title, visible_text = page_title_and_text(html)
            p = PAGES / safe(s['id']) / f'{page_number:04d}.html'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(html, encoding='utf-8', errors='replace')
            records.append({
                'source_id': s['id'], 'parent_source_id': s['id'], 'label': s['label'],
                'kind': 'page_snapshot', 'source_category': category,
                'original_url': url, 'final_url': r.url, 'referer': '', 'source_type': 'html',
                'context': title, 'matched_terms': matched_terms(s, r.url, title, visible_text),
                'local_path': p.relative_to(OUT).as_posix(), 'mime': 'text/html',
                'bytes': len(html.encode()), 'sha256': sha256(html.encode()),
                'width': 0, 'height': 0, 'frames': 0, 'quality_state': 'PAGE_SNAPSHOT'
            })
            folder = f'{safe(category)}/{safe(s["id"])}'
            for i, (mu, kind, context) in enumerate(media_candidates(r.url, html, title), 1):
                if any(w in mu.lower() for w in ('favicon', 'pixel', 'tracking')):
                    continue
                tasks.append((f'{s["id"]}_{page_number:04d}_{i:05d}', s['id'], s['label'], mu, folder, r.url, kind, category, context, visible_text, False))
            if s.get('kind') == 'crawl_site':
                soup = BeautifulSoup(html, 'html.parser')
                for a in soup.find_all('a', href=True):
                    nu = absu(r.url, a['href'])
                    pu = urllib.parse.urlparse(nu)
                    ext = Path(pu.path).suffix.lower()
                    if pu.netloc == host and ext not in MEDIA_EXT and nu not in fetched_pages and len(queue) < max_pages * 3:
                        queue.append(nu)
                for tag in soup.find_all(['script', 'link']):
                    value = tag.get('src') or tag.get('href')
                    if not value:
                        continue
                    nu = absu(r.url, value); pu = urllib.parse.urlparse(nu)
                    ext = Path(pu.path).suffix.lower()
                    if pu.netloc == host and ext in {'.js', '.json', '.xml', '.txt'} and nu not in fetched_pages and len(queue) < max_pages * 3:
                        queue.append(nu)
        except Exception as e:
            failures.append({'source_id': s['id'], 'parent_source_id': s['id'], 'url': url, 'referer': '', 'error': repr(e), 'label': s['label']})

# Deduplicate URLs before download.
unique_tasks = {}
for t in tasks:
    unique_tasks.setdefault(t[3], t)
tasks = list(unique_tasks.values())
with ThreadPoolExecutor(max_workers=28) as executor:
    futures = [executor.submit(download, t) for t in tasks]
    for f in as_completed(futures):
        f.result()

fields = sorted({k for r in records for k in r})
with (META / 'media_manifest.csv').open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(records)
for name, data, cols in [
    ('failures.csv', failures, ['source_id', 'parent_source_id', 'url', 'referer', 'error', 'label']),
    ('duplicates.csv', duplicates, ['source_id', 'url', 'duplicate_of', 'sha256'])
]:
    with (META / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(data)

quality_counts = Counter(r.get('quality_state', '') for r in records if r.get('kind') == 'actual_media')
mime_counts = Counter(r.get('mime', '') for r in records if r.get('kind') == 'actual_media')
source_rows = []
for sid, spec in source_specs.items():
    own = [r for r in records if r.get('parent_source_id') == sid]
    actual = [r for r in own if r.get('kind') == 'actual_media']
    likely = [r for r in actual if r.get('quality_state') in {'DIRECT_ACTUAL_MEME_MEDIA', 'LIKELY_ACTUAL_MEME_MEDIA', 'ACTUAL_ANIMATED_MEME_OR_REFERENCE'}]
    source_rows.append({
        'source_id': sid, 'label': spec.get('label', ''),
        'source_category': spec.get('source_category', ''),
        'page_snapshots': sum(r.get('kind') == 'page_snapshot' for r in own),
        'actual_media_files': len(actual), 'likely_meme_media_files': len(likely),
        'matched_terms': ' | '.join(sorted({x for r in own for x in str(r.get('matched_terms', '')).split(' | ') if x})),
        'expected_terms': ' | '.join(spec.get('expected_terms', [])),
        'coverage_state': 'COVERED' if likely else ('EVIDENCE_CAPTURED' if own and spec.get('source_category') == 'trend_evidence' else 'UNRESOLVED')
    })
with (META / 'source_coverage.csv').open('w', encoding='utf-8-sig', newline='') as f:
    cols = list(source_rows[0]) if source_rows else []
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(source_rows)

likely_count = sum(v for k, v in quality_counts.items() if k in {'DIRECT_ACTUAL_MEME_MEDIA', 'LIKELY_ACTUAL_MEME_MEDIA', 'ACTUAL_ANIMATED_MEME_OR_REFERENCE'})
summary = {
    'scope': 'listed source universe; not all memes on the internet',
    'source_definitions': len(source_specs),
    'candidate_media_urls': len(tasks),
    'downloaded_actual_media_files': sum(r.get('kind') == 'actual_media' for r in records),
    'likely_actual_meme_media_files': likely_count,
    'page_snapshots': sum(r.get('kind') == 'page_snapshot' for r in records),
    'failures': len(failures), 'duplicates': len(duplicates),
    'generated_or_self_made_replacement_media': 0,
    'actual_media_bytes': sum(int(r.get('bytes', 0)) for r in records if r.get('kind') == 'actual_media'),
    'quality_state_counts': dict(quality_counts), 'mime_counts': dict(mime_counts),
    'source_coverage': dict(Counter(r['coverage_state'] for r in source_rows)),
    'unresolved_source_ids': [r['source_id'] for r in source_rows if r['coverage_state'] == 'UNRESOLVED']
}
(META / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'README_研究用実物ミーム収集.txt').write_text(
    '実際にウェブ上で公開・流通している画像・GIF・動画・掲載ページを研究用に収集したものです。\n'
    '流行語ランキング画像は鮮度の証拠であり、元ミーム媒体には数えません。\n'
    'モデル生成・自作代替画像・自作GIF・自作MP4は0件です。\n'
    '877件などのファイル数を、独立ミーム数や全網羅と同一視しません。\n'
    '出典URL、文脈、寸法、フレーム数、SHA-256、失敗、重複はmetadataへ記録しています。\n',
    encoding='utf-8'
)

# Independent ZIP parts under GitHub's 100 MB single-file limit.
all_files = sorted(p for p in OUT.rglob('*') if p.is_file())
max_uncompressed = 78 * 1024 * 1024
part_no = 1; part_size = 0; zf = None; part_rows = []
for p in all_files:
    size = p.stat().st_size
    if zf is None or (part_size and part_size + size > max_uncompressed):
        if zf is not None:
            zf.close()
        part_path = PARTS / f'research_meme_verified_part_{part_no:02d}.zip'
        zf = zipfile.ZipFile(part_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=3)
        part_rows.append({'part': part_path.name, 'first_file': p.relative_to(OUT).as_posix(), 'uncompressed_bytes': 0})
        part_no += 1; part_size = 0
    zf.write(p, p.relative_to(OUT.parent))
    part_size += size; part_rows[-1]['uncompressed_bytes'] += size
if zf is not None:
    zf.close()
for row in part_rows:
    pp = PARTS / row['part']; row['zip_bytes'] = pp.stat().st_size; row['sha256'] = sha256(pp.read_bytes())
(PARTS / 'parts_manifest.json').write_text(json.dumps({'parts': part_rows, 'summary': summary}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
