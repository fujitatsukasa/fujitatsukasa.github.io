#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from curl_cffi import requests

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "StuArchive")
SHARD = int(sys.argv[2] if len(sys.argv) > 2 else 0)
SHARDS = int(sys.argv[3] if len(sys.argv) > 3 else 1)
OUT = Path(f"artifact_social_v37_{SHARD:02d}")
OUT.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session(impersonate="chrome")
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 BlueArchiveScriptResearch/37",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7,ko;q=0.6,zh-CN;q=0.5",
})

AXES = {
    "sexualized_gaze": [r"えっち", r"エロ", r"色気", r"セクシ", r"sexy", r"hot\b", r"lewd", r"thicc", r"水着", r"バニー", r"胸", r"太もも", r"脚", r"body"],
    "romance_sensei": [r"正妻", r"嫁", r"結婚", r"先生.*好き", r"先生.*愛", r"恋愛", r"デート", r"wife", r"marry", r"sensei.*love", r"girlfriend", r"romance"],
    "humidity_obsession": [r"湿度", r"重い", r"依存", r"執着", r"独占", r"嫉妬", r"ヤンデレ", r"曇らせ", r"possessive", r"obsess", r"jealous", r"yandere", r"clingy"],
    "grit_effort": [r"泥臭", r"努力", r"頑張", r"成長", r"根性", r"不器用", r"苦労", r"奮闘", r"努力家", r"hard.?work", r"struggle", r"growth", r"determination"],
    "tragedy_salvation": [r"救済", r"救いたい", r"幸せに", r"過去", r"トラウマ", r"罪", r"贖罪", r"曇らせ", r"泣", r"trauma", r"save her", r"redemption", r"tragic", r"pain"],
    "cute_protect": [r"かわい", r"可愛", r"守りたい", r"娘", r"尊い", r"癒", r"cute", r"adorable", r"protect", r"daughter", r"precious"],
    "cool_strong": [r"かっこ", r"格好良", r"最強", r"強い", r"頼もし", r"イケメン", r"badass", r"strong", r"cool", r"powerful", r"goat"],
    "comedy_meme": [r"草", r"笑", r"ネタ", r"ミーム", r"ポンコツ", r"残念", r"芸人", r"おもしろ", r"lol", r"lmao", r"meme", r"funny", r"goofy", r"dork"],
    "gameplay_meta": [r"性能", r"人権", r"環境", r"編成", r"総力戦", r"大決戦", r"対抗戦", r"ガチャ", r"引くべき", r"強キャラ", r"meta", r"tier", r"pull", r"raid", r"build", r"damage", r"tank", r"healer"],
    "relationships_shipping": [r"カプ", r"百合", r"コンビ", r"関係性", r"幼馴染", r"相棒", r"姉妹", r"ship", r"pairing", r"yuri", r"duo", r"relationship"],
    "costume_design": [r"衣装", r"デザイン", r"服", r"ドレス", r"制服", r"水着", r"バニー", r"メイド", r"正月", r"体操服", r"costume", r"outfit", r"dress", r"uniform", r"swimsuit", r"maid"],
    "criticism_dispute": [r"嫌い", r"苦手", r"炎上", r"解釈違い", r"賛否", r"過大評価", r"弱い", r"不遇", r"hate", r"dislike", r"controvers", r"overrated", r"underwhelming", r"bad writing"],
}
AXIS_RE = {k: re.compile("|".join(v), re.I) for k, v in AXES.items()}


def clean_text(s: str, limit: int = 500) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"https?://\S+", "[URL]", s)
    s = re.sub(r"u/[A-Za-z0-9_-]+", "u/[user]", s)
    s = re.sub(r"@[A-Za-z0-9_]+", "@[user]", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def safe_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠々ー・＊*()（） _-]", "_", s)
    return s[:90] or "unknown"


def get_json(url: str, tries: int = 4):
    last = None
    for n in range(tries):
        try:
            r = SESSION.get(url, timeout=45, allow_redirects=True)
            if r.status_code == 200:
                return r.json(), r
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as exc:
            last = exc
        time.sleep(0.5 * (n + 1))
    raise RuntimeError(f"GET JSON failed: {url}: {last!r}")


def get_html(url: str, tries: int = 4):
    last = None
    for n in range(tries):
        try:
            r = SESSION.get(url, timeout=45, allow_redirects=True)
            if r.status_code == 200:
                return r.text, r
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as exc:
            last = exc
        time.sleep(0.5 * (n + 1))
    raise RuntimeError(f"GET HTML failed: {url}: {last!r}")


def load_characters():
    idx = json.loads((ROOT / "data/students/index.json").read_text(encoding="utf-8"))
    details = {}
    for item in idx["items"]:
        p = ROOT / f"data/students/{int(item['id'])}.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        details[int(item["id"])] = j.get("data", j)
    grouped = defaultdict(list)
    for d in details.values():
        if d.get("is_npc") or not d.get("is_install"):
            continue
        jp = ((d.get("family_name_jp") or "") + (d.get("given_name_jp") or "")).strip()
        if not jp:
            continue
        grouped[jp].append(d)
    chars = []
    for jp, variants in grouped.items():
        base = sorted(variants, key=lambda x: (bool(x.get("skin") or x.get("skin_jp")), int(x.get("id", 0))))[0]
        chars.append({
            "base_character_jp": jp,
            "base_id": int(base["id"]),
            "name_en": " ".join(x for x in [base.get("family_name_en"), base.get("given_name_en")] if x).strip(),
            "name_cn": ((base.get("family_name_cn") or base.get("family_name") or "") + (base.get("given_name_cn") or base.get("given_name") or "")).strip(),
            "given_jp": base.get("given_name_jp") or "",
            "given_en": base.get("given_name_en") or "",
            "variant_ids": sorted(int(v["id"]) for v in variants),
        })
    return sorted(chars, key=lambda x: x["base_character_jp"])


def axis_counts(texts):
    out = {}
    joined = "\n".join(texts)
    for axis, rx in AXIS_RE.items():
        out[axis] = len(rx.findall(joined))
    return out


def reddit(character):
    query = character["name_en"] or character["base_character_jp"]
    query = quote(query)
    base = "https://arctic-shift.photon-reddit.com/api"
    urls = {
        "reddit_posts": f"{base}/posts/search?subreddit=BlueArchive&query={query}&over_18=false&limit=40&sort=desc",
        "reddit_comments": f"{base}/comments/search?subreddit=BlueArchive&body={query}&limit=60&sort=desc",
    }
    records = []
    for platform, url in urls.items():
        data, _ = get_json(url)
        items = data.get("data", data if isinstance(data, list) else []) or []
        for item in items:
            if platform == "reddit_posts":
                text = clean_text((item.get("title") or "") + "\n" + (item.get("selftext") or ""))
                score = item.get("score")
                created = item.get("created_utc")
                ref = item.get("id")
            else:
                text = clean_text(item.get("body") or "")
                score = item.get("score")
                created = item.get("created_utc")
                ref = item.get("id")
            if not text or text in {"[deleted]", "[removed]"}:
                continue
            records.append({"platform": platform, "text": text, "score": score, "created_utc": created, "reference_id": ref, "source_url": url})
    return records


def bilibili(character):
    q = character["name_cn"] or character["base_character_jp"]
    url = "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=" + quote(q + " 碧蓝档案") + "&page=1&page_size=20"
    data, _ = get_json(url)
    items = (((data or {}).get("data") or {}).get("result") or [])
    records = []
    for item in items:
        title = BeautifulSoup(item.get("title") or "", "html.parser").get_text(" ", strip=True)
        text = clean_text(title + "\n" + (item.get("description") or ""))
        if text:
            records.append({
                "platform": "bilibili", "text": text, "score": item.get("play"),
                "created_utc": item.get("pubdate"), "reference_id": item.get("bvid"),
                "source_url": "https://www.bilibili.com/video/" + str(item.get("bvid") or ""),
            })
    return records


def wikiru_comment(character):
    page = "コメント/" + character["base_character_jp"]
    url = "https://bluearchive.wikiru.jp/?" + quote(page, safe="/")
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    body = soup.select_one("div#body") or soup
    lines = []
    for node in body.select("li, p, td"):
        t = clean_text(node.get_text(" ", strip=True), 350)
        if len(t) >= 8 and character["given_jp"] in t:
            lines.append(t)
    if not lines:
        raw = clean_text(body.get_text(" ", strip=True), 2500)
        lines = [raw] if raw else []
    return [{"platform": "wikiru_comment", "text": t, "score": None, "created_utc": None, "reference_id": None, "source_url": str(r.url)} for t in lines[:40]]


def yahoo_realtime(character):
    url = "https://search.yahoo.co.jp/realtime/search?p=" + quote(character["base_character_jp"] + " ブルアカ") + "&ei=UTF-8"
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    candidates = []
    for node in soup.select("article, li, p"):
        t = clean_text(node.get_text(" ", strip=True), 350)
        if character["given_jp"] and character["given_jp"] in t and len(t) >= 10:
            candidates.append(t)
    dedup = list(dict.fromkeys(candidates))[:30]
    return [{"platform": "yahoo_realtime", "text": t, "score": None, "created_utc": None, "reference_id": None, "source_url": str(r.url)} for t in dedup]


def fivech(character):
    url = "https://find.5ch.net/search?q=" + quote(character["given_jp"] + " ブルアカ")
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        t = clean_text(a.get_text(" ", strip=True), 300)
        if character["given_jp"] and character["given_jp"] in t:
            out.append({"platform": "fivech_thread_title", "text": t, "score": None, "created_utc": None, "reference_id": None, "source_url": a.get("href") or str(r.url)})
    return out[:30]


def collect_one(ch):
    evidence, failures = [], []
    for fn in (reddit, bilibili, wikiru_comment, yahoo_realtime, fivech):
        try:
            evidence.extend(fn(ch))
        except Exception as exc:
            failures.append({"platform": fn.__name__, "error": repr(exc)})
        time.sleep(0.15)
    counts = Counter(x["platform"] for x in evidence)
    axis = axis_counts([x["text"] for x in evidence])
    top = sorted(evidence, key=lambda x: (x.get("score") or 0, len(x.get("text") or "")), reverse=True)[:24]
    return {
        **ch,
        "evidence_count": len(evidence),
        "platform_counts": dict(counts),
        "axis_keyword_hits": axis,
        "top_evidence": top,
        "failures": failures,
    }, evidence


def main():
    chars = load_characters()
    selected = [c for i, c in enumerate(chars) if i % SHARDS == SHARD]
    summaries = []
    all_evidence = []
    for n, ch in enumerate(selected, 1):
        print(f"[{n}/{len(selected)}] {ch['base_character_jp']}", flush=True)
        summary, evidence = collect_one(ch)
        summaries.append(summary)
        for e in evidence:
            all_evidence.append({"base_character_jp": ch["base_character_jp"], "base_id": ch["base_id"], **e})
    with (OUT / "character_social_summary.jsonl").open("w", encoding="utf-8") as f:
        for row in summaries:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "social_evidence.jsonl").open("w", encoding="utf-8") as f:
        for row in all_evidence:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    cols = ["base_character_jp", "base_id", "evidence_count", "platform_counts", *AXES.keys(), "failure_count"]
    with (OUT / "social_axis_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for s in summaries:
            row = {"base_character_jp": s["base_character_jp"], "base_id": s["base_id"], "evidence_count": s["evidence_count"], "platform_counts": json.dumps(s["platform_counts"], ensure_ascii=False), "failure_count": len(s["failures"])}
            row.update(s["axis_keyword_hits"])
            w.writerow(row)
    (OUT / "summary.json").write_text(json.dumps({"shard": SHARD, "shards": SHARDS, "character_count": len(summaries), "evidence_count": len(all_evidence), "axis_names": list(AXES)}, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
