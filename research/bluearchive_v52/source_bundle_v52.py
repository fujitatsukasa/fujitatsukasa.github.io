#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests
from PIL import Image

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "artifact_bluearchive_sources_v52")
OUT.mkdir(parents=True, exist_ok=True)

S = requests.Session(impersonate="chrome")
S.headers.update({
    "User-Agent": "Mozilla/5.0 BlueArchiveSourceResearch/52",
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.7",
})

SOURCES = [
    {"id":"OFFICIAL_001","kind":"公式","role":"発表の一次情報","date":"2026-06-14","url":"https://bluearchive.jp/news/newsJump/667"},
    {"id":"OFFICIAL_002","kind":"公式","role":"イベント・募集・日程の一次情報","date":"2026-06-23","url":"https://bluearchive.jp/news/newsJump/670"},
    {"id":"OFFICIAL_003","kind":"公式動画","role":"発表映像・画像の一次情報","date":"2026-06-20","url":"https://www.youtube.com/watch?v=N-WHdoxBDdU"},
    {"id":"MEDIA_001","kind":"報道・まとめ","role":"発表内容の時系列整理と画像","date":"2026-06-20","url":"https://dengekionline.com/article/202606/78992"},
    {"id":"MEDIA_002","kind":"攻略メディア","role":"性能・日程・攻略視点の整理","date":"2026-06-20","url":"https://game8.jp/blue-archive/637876"},
    {"id":"MEDIA_003","kind":"報道","role":"イベント内容の事実確認","date":"2026-06-20","url":"https://www.4gamer.net/games/519/G051983/20260620003/"},
    {"id":"MEDIA_004","kind":"報道","role":"水着キサキ発表時の媒体 framing と画像","date":"2026-06-20","url":"https://game.watch.impress.co.jp/docs/news/2118784.html"},
    {"id":"MEDIA_005","kind":"報道","role":"水着シュン発表時の媒体 framing と画像","date":"2026-06-20","url":"https://game.watch.impress.co.jp/docs/news/2118785.html"},
    {"id":"MEDIA_006","kind":"報道","role":"実装開始後のイベント事実確認","date":"2026-06-24","url":"https://www.gamer.ne.jp/news/202606240079/"},
    {"id":"REACTION_001","kind":"掲示板まとめ","role":"発表当日の匿名掲示板由来の反応傾向","date":"2026-06-20","url":"https://buruaka-matome.doorblog.jp/archives/30181857.html"},
    {"id":"REACTION_002","kind":"個人まとめ","role":"発表当日のネット反応の要約例","date":"2026-06-20","url":"https://ameblo.jp/soarer3840/entry-12970282017.html"},
    {"id":"REACTION_003","kind":"個人レビュー","role":"実装後の性能評価と運用上の論点","date":"2026-06-29","url":"https://ippandouga.hatenablog.com/entry/2026/06/29/014147"},
    {"id":"REACTION_004","kind":"個人プレイ記録","role":"イベント・ガチャ体験後の感想","date":"2026-06-27","url":"https://ameblo.jp/neko-teki-inu/entry-12970909903.html"},
    {"id":"REACTION_005","kind":"リアルタイム検索","role":"当日ハッシュタグ検索の入口","date":"2026-06-20","url":"https://search.yahoo.co.jp/realtime/search?p=%23%E3%83%96%E3%83%AB%E3%82%A2%E3%82%AB%E3%82%89%E3%81%84%E3%81%B6%E3%81%99%E3%81%9F%E3%81%95%E3%81%BESP&ei=UTF-8"},
    {"id":"SS_001","kind":"小説投稿サイト検索","role":"ブルアカ二次創作の母集団・タグ・形式確認","date":"2026-07-16","url":"https://syosetu.org/search/?filter=unread&mode=search&rensai3=1&tag3=1&tag4=1&tag6=1&type=18&word=%E5%8E%9F%E4%BD%9C%EF%BC%9A%E3%83%96%E3%83%AB%E3%83%BC%E3%82%A2%E3%83%BC%E3%82%AB%E3%82%A4%E3%83%96"},
    {"id":"SS_002","kind":"小説投稿サイト推薦掲示板","role":"読者が面白いと評価する作品・形式の確認","date":"2026-05-09","url":"https://syosetu.org/?mode=seek_view&thread_id=70311"},
    {"id":"SS_003","kind":"小説投稿サイト推薦掲示板","role":"感動・曇らせ・救済系の需要確認","date":"2025-11-27","url":"https://syosetu.org/?mode=seek_view&thread_id=65574"},
    {"id":"SS_004","kind":"小説投稿作品","role":"掲示板形式SSの構成研究","date":"2023-08-18","url":"https://syosetu.org/novel/323622/"},
    {"id":"SS_005","kind":"小説投稿作品","role":"長編・クロスオーバー・原作改変の構造研究","date":"2024-07-02","url":"https://syosetu.org/novel/348128/"},
    {"id":"SS_006","kind":"小説投稿作品","role":"掲示板回を含む長編作品の構成研究","date":"2024-12-08","url":"https://syosetu.org/novel/361152/"},
]

BAD_IMAGE = re.compile(r"(logo|icon|avatar|emoji|sprite|pixel|tracking|1x1|banner_ad|ads?)", re.I)


def safe_name(s: str, max_len: int = 90) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", s)
    s = re.sub(r"\s+", "_", s).strip("._ ")
    return s[:max_len] or "untitled"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, tries: int = 4):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=60, allow_redirects=True)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as exc:
            last = exc
        time.sleep(0.8 * (i + 1))
    raise RuntimeError(f"fetch failed: {url}: {last!r}")


def meta_value(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if node and node.get("content"):
            return str(node.get("content")).strip()
    return ""


def visible_summary(soup: BeautifulSoup, limit: int = 900) -> str:
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    # Only a short discovery excerpt is retained; the full article/novel is not copied.
    return text[:limit]


def image_candidates(soup: BeautifulSoup, page_url: str) -> list[str]:
    out: list[str] = []
    for key in ("og:image", "twitter:image", "twitter:image:src"):
        v = meta_value(soup, key)
        if v:
            out.append(urljoin(page_url, v))
    for img in soup.find_all("img"):
        for attr in ("data-src", "data-original", "data-lazy-src", "src"):
            v = img.get(attr)
            if v and not str(v).startswith("data:"):
                out.append(urljoin(page_url, str(v)))
                break
        srcset = img.get("srcset")
        if srcset:
            parts = [p.strip().split(" ")[0] for p in str(srcset).split(",") if p.strip()]
            if parts:
                out.append(urljoin(page_url, parts[-1]))
    # YouTube page: add maxres thumbnail explicitly.
    if "youtube.com/watch" in page_url:
        m = re.search(r"[?&]v=([A-Za-z0-9_-]+)", page_url)
        if m:
            out.insert(0, f"https://i.ytimg.com/vi/{m.group(1)}/maxresdefault.jpg")
    uniq = []
    seen = set()
    for u in out:
        if not u or u in seen or BAD_IMAGE.search(urlparse(u).path):
            continue
        seen.add(u)
        uniq.append(u)
    return uniq


def download_image(url: str):
    r = fetch(url, tries=3)
    data = bytes(r.content)
    if len(data) < 12_000:
        raise ValueError("too small")
    im = Image.open(io.BytesIO(data))
    im.verify()
    im2 = Image.open(io.BytesIO(data))
    if im2.width < 320 or im2.height < 180:
        raise ValueError("dimensions too small")
    fmt = im2.format or ""
    ext = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}.get(fmt.upper(), Path(urlparse(url).path).suffix or ".img")
    return data, fmt, im2.width, im2.height, ext


source_rows = []
image_rows = []
failures = []
seen_image_sha: set[str] = set()

for src in SOURCES:
    sid = src["id"]
    folder = OUT / "sources" / sid
    folder.mkdir(parents=True, exist_ok=True)
    row = dict(src)
    row.update({"status": "", "final_url": "", "title": "", "description": "", "published": "", "page_sha256": "", "image_count": 0})
    try:
        r = fetch(src["url"])
        row["status"] = str(r.status_code)
        row["final_url"] = str(r.url)
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        row["title"] = meta_value(soup, "og:title", "twitter:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
        row["description"] = meta_value(soup, "og:description", "description", "twitter:description")
        row["published"] = meta_value(soup, "article:published_time", "date", "datePublished") or src.get("date", "")
        row["page_sha256"] = sha256(bytes(r.content))
        (folder / "ページ情報.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        (folder / "短い確認用抜粋.txt").write_text(visible_summary(soup), encoding="utf-8")
        candidates = image_candidates(soup, str(r.url))
        saved = 0
        for idx, u in enumerate(candidates, 1):
            if saved >= 10:
                break
            try:
                data, fmt, w, h, ext = download_image(u)
                digest = sha256(data)
                if digest in seen_image_sha:
                    continue
                seen_image_sha.add(digest)
                name = f"{saved+1:02d}_{safe_name(Path(urlparse(u).path).stem)}{ext}"
                p = folder / "images" / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                image_rows.append({
                    "source_id": sid, "source_kind": src["kind"], "source_role": src["role"],
                    "page_url": src["url"], "image_url": u, "local_path": str(p.relative_to(OUT)),
                    "sha256": digest, "bytes": len(data), "width": w, "height": h, "format": fmt,
                })
                saved += 1
            except Exception as exc:
                failures.append({"source_id": sid, "stage": "image", "url": u, "error": repr(exc)})
        row["image_count"] = saved
    except Exception as exc:
        row["status"] = "error"
        failures.append({"source_id": sid, "stage": "page", "url": src["url"], "error": repr(exc)})
    source_rows.append(row)

source_fields = list(source_rows[0].keys())
with (OUT / "URL出典一覧.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=source_fields)
    w.writeheader(); w.writerows(source_rows)

img_fields = list(image_rows[0].keys()) if image_rows else ["source_id"]
with (OUT / "取得画像一覧.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=img_fields)
    w.writeheader(); w.writerows(image_rows)

(OUT / "取得失敗.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
summary = {
    "source_count": len(source_rows),
    "source_success": sum(r.get("status") not in {"", "error"} for r in source_rows),
    "image_count": len(image_rows),
    "unique_image_sha256": len(seen_image_sha),
    "failure_count": len(failures),
    "source_kinds": sorted({r["kind"] for r in source_rows}),
}
(OUT / "取得結果.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
