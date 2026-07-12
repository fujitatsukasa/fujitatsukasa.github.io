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

S = requests.Session(impersonate="chrome")
S.headers.update({
    "User-Agent": "Mozilla/5.0 BlueArchiveScriptResearch/37.2",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7,ko;q=0.6,zh-CN;q=0.5",
    "Referer": "https://www.google.com/",
})

# High-level fan-perception axes. These are discourse indicators, not claims about canon.
AXES = {
    "sexualized_gaze_safe": [r"色気", r"セクシ", r"sexy", r"水着", r"バニー", r"太もも", r"脚", r"スタイル", r"body"],
    "romance_sensei": [r"正妻", r"嫁", r"結婚", r"先生.{0,8}好き", r"先生.{0,8}愛", r"恋愛", r"デート", r"wife", r"marry", r"sensei.{0,12}love", r"girlfriend", r"romance"],
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

# Explicit sexual material is never retained as text. Only an aggregate exclusion count is kept.
EXPLICIT_RE = re.compile(
    r"(?i)(くぱ|まんこ|ちんこ|ちんぽ|性器|挿入|射精|中出し|フェラ|アナル|オナニ|自慰|性交|セックス|陵辱|輪姦|強姦|孕ま|搾精|porn|hentai|genitals?|penetrat|ejaculat|fellatio|anal sex|masturbat|rape|gangbang|creampie)"
)


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").casefold().replace(" ", "")


def clean_text(s: str, limit: int = 500) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"https?://\S+", "[URL]", s)
    s = re.sub(r"u/[A-Za-z0-9_-]+", "u/[user]", s)
    s = re.sub(r"@[A-Za-z0-9_]+", "@[user]", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def get_json(url: str, tries: int = 4):
    last = None
    for n in range(tries):
        try:
            r = S.get(url, timeout=45, allow_redirects=True)
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
            r = S.get(url, timeout=45, allow_redirects=True)
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
        if p.exists():
            j = json.loads(p.read_text(encoding="utf-8"))
            details[int(item["id"])] = j.get("data", j)
    grouped = defaultdict(list)
    for d in details.values():
        if d.get("is_npc") or not d.get("is_install"):
            continue
        jp = ((d.get("family_name_jp") or "") + (d.get("given_name_jp") or "")).strip()
        if jp:
            grouped[norm(jp)].append(d)
    chars = []
    for _, variants in grouped.items():
        base = sorted(variants, key=lambda x: (bool(x.get("skin") or x.get("skin_jp")), int(x.get("id", 0))))[0]
        jp = ((base.get("family_name_jp") or "") + (base.get("given_name_jp") or "")).strip()
        cn = ((base.get("family_name_cn") or base.get("family_name") or "") + (base.get("given_name_cn") or base.get("given_name") or "")).strip()
        en = " ".join(x for x in [base.get("family_name_en"), base.get("given_name_en")] if x).strip()
        aliases = [jp, base.get("given_name_jp") or "", cn, base.get("given_name_cn") or base.get("given_name") or "", en, base.get("given_name_en") or ""]
        aliases = [x for x in dict.fromkeys(aliases) if len(norm(x)) >= 2]
        chars.append({
            "base_character_jp": jp, "base_id": int(base["id"]), "name_en": en, "name_cn": cn,
            "given_jp": base.get("given_name_jp") or "", "given_en": base.get("given_name_en") or "",
            "aliases": aliases, "variant_ids": sorted(int(v["id"]) for v in variants),
        })
    return sorted(chars, key=lambda x: x["base_character_jp"])


def relevant(text: str, ch: dict) -> bool:
    t = norm(text)
    return any(norm(a) in t for a in ch["aliases"] if len(norm(a)) >= 2)


def safe_record(platform: str, raw_text: str, ch: dict, **meta):
    text = clean_text(raw_text)
    if not text or text in {"[deleted]", "[removed]"} or not relevant(text, ch):
        return None, 0
    if EXPLICIT_RE.search(text):
        return None, 1
    return {"platform": platform, "text": text, **meta}, 0


def reddit(ch):
    term = ch["given_en"] or ch["given_jp"] or ch["base_character_jp"]
    q = quote(term)
    base = "https://arctic-shift.photon-reddit.com/api"
    specs = [
        ("reddit_posts", f"{base}/posts/search?subreddit=BlueArchive&query={q}&over_18=false&limit=40&sort=desc"),
        ("reddit_comments", f"{base}/comments/search?subreddit=BlueArchive&body={q}&limit=60&sort=desc"),
    ]
    out, excluded, failures = [], 0, []
    for platform, url in specs:
        try:
            data, _ = get_json(url)
            items = data.get("data", data if isinstance(data, list) else []) or []
            for item in items:
                raw = ((item.get("title") or "") + "\n" + (item.get("selftext") or "")) if platform == "reddit_posts" else (item.get("body") or "")
                rec, ex = safe_record(platform, raw, ch, score=item.get("score"), created_utc=item.get("created_utc"), reference_id=item.get("id"), source_url=url)
                excluded += ex
                if rec: out.append(rec)
        except Exception as exc:
            failures.append({"platform": platform, "error": repr(exc)})
    return out, excluded, failures


def bluesky(ch):
    q = quote((ch["name_en"] or ch["base_character_jp"]) + " Blue Archive")
    url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={q}&limit=40"
    data, _ = get_json(url)
    out, excluded = [], 0
    for item in data.get("posts", []) or []:
        labels = [str(x.get("val") or "").lower() for x in (item.get("labels") or [])]
        raw = ((item.get("record") or {}).get("text") or "")
        if any(x in {"porn", "sexual", "nudity"} for x in labels):
            excluded += 1
            continue
        rec, ex = safe_record("bluesky", raw, ch, score=(item.get("likeCount") or 0) + (item.get("repostCount") or 0), created_utc=item.get("indexedAt"), reference_id=item.get("uri"), source_url="https://bsky.app/")
        excluded += ex
        if rec: out.append(rec)
    return out, excluded, []


def bilibili(ch):
    q = ch["name_cn"] or ch["base_character_jp"]
    url = "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=" + quote(q + " 碧蓝档案") + "&page=1&page_size=20"
    data, _ = get_json(url)
    out, excluded = [], 0
    for item in (((data or {}).get("data") or {}).get("result") or []):
        title = BeautifulSoup(item.get("title") or "", "html.parser").get_text(" ", strip=True)
        rec, ex = safe_record("bilibili", title + "\n" + (item.get("description") or ""), ch, score=item.get("play"), created_utc=item.get("pubdate"), reference_id=item.get("bvid"), source_url="https://www.bilibili.com/video/" + str(item.get("bvid") or ""))
        excluded += ex
        if rec: out.append(rec)
    return out, excluded, []


def wikiru_comment(ch):
    url = "https://bluearchive.wikiru.jp/?" + quote("コメント/" + ch["base_character_jp"], safe="/")
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    body = soup.select_one("div#body") or soup
    candidates = []
    for node in body.select("li, p, td"):
        t = clean_text(node.get_text(" ", strip=True), 400)
        if len(t) >= 8:
            candidates.append(t)
    out, excluded = [], 0
    for t in list(dict.fromkeys(candidates))[:60]:
        # Exact character comment page: relevance is established by page identity.
        if EXPLICIT_RE.search(t):
            excluded += 1
            continue
        out.append({"platform": "wikiru_comment", "text": t, "score": None, "created_utc": None, "reference_id": None, "source_url": str(r.url)})
    return out, excluded, []


def yahoo_realtime(ch):
    url = "https://search.yahoo.co.jp/realtime/search?p=" + quote(ch["base_character_jp"] + " ブルアカ") + "&ei=UTF-8"
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    out, excluded = [], 0
    for node in soup.select("article, li, p"):
        rec, ex = safe_record("yahoo_realtime", node.get_text(" ", strip=True), ch, score=None, created_utc=None, reference_id=None, source_url=str(r.url))
        excluded += ex
        if rec: out.append(rec)
    dedup = {x["text"]: x for x in out}
    return list(dedup.values())[:30], excluded, []


def fivech(ch):
    url = "https://find.5ch.net/search?q=" + quote(ch["given_jp"] + " ブルアカ")
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    out, excluded = [], 0
    for a in soup.find_all("a", href=True):
        rec, ex = safe_record("fivech_thread_title", a.get_text(" ", strip=True), ch, score=None, created_utc=None, reference_id=None, source_url=a.get("href") or str(r.url))
        excluded += ex
        if rec: out.append(rec)
    return out[:30], excluded, []


def ao3(ch):
    # AO3 is used only for safe aggregate relationship/trope metadata. Mature/Explicit works and explicit text are not retained.
    query = quote((ch["name_en"] or ch["base_character_jp"]) + " Blue Archive")
    url = "https://archiveofourown.org/works/search?work_search%5Bquery%5D=" + query
    text, r = get_html(url)
    soup = BeautifulSoup(text, "html.parser")
    out, excluded = [], 0
    for work in soup.select("li.work.blurb, li.blurb"): 
        rating = clean_text((work.select_one("span.rating") or work.select_one("span.text") or work).get_text(" ", strip=True), 60)
        block = clean_text(work.get_text(" ", strip=True), 600)
        if re.search(r"(?i)explicit|mature|not rated", rating) or EXPLICIT_RE.search(block):
            excluded += 1
            continue
        tags = [clean_text(a.get_text(" ", strip=True), 120) for a in work.select("ul.tags a.tag")]
        safe_tags = [t for t in tags if t and not EXPLICIT_RE.search(t)][:20]
        summary = "AO3 safe metadata; rating=" + rating + "; tags=" + " | ".join(safe_tags)
        rec, ex = safe_record("ao3_safe_metadata", summary + "; character=" + ch["base_character_jp"], ch, score=None, created_utc=None, reference_id=None, source_url=str(r.url))
        excluded += ex
        if rec: out.append(rec)
    return out[:20], excluded, []


def axis_counts(texts):
    joined = "\n".join(texts)
    return {axis: len(rx.findall(joined)) for axis, rx in AXIS_RE.items()}


def collect_one(ch):
    evidence, failures = [], []
    excluded_explicit = 0
    for fn in (reddit, bluesky, bilibili, wikiru_comment, yahoo_realtime, fivech, ao3):
        try:
            rows, ex, errs = fn(ch)
            evidence.extend(rows)
            excluded_explicit += ex
            failures.extend(errs)
        except Exception as exc:
            failures.append({"platform": fn.__name__, "error": repr(exc)})
        time.sleep(0.12)
    counts = Counter(x["platform"] for x in evidence)
    top = sorted(evidence, key=lambda x: (x.get("score") or 0, len(x.get("text") or "")), reverse=True)[:24]
    return {
        **ch,
        "evidence_count": len(evidence),
        "platform_counts": dict(counts),
        "axis_keyword_hits": axis_counts([x["text"] for x in evidence]),
        "explicit_sexual_material_excluded_count": excluded_explicit,
        "top_safe_evidence": top,
        "failures": failures,
        "method_note": "Only public, sanitized, character-relevant text is retained. Explicit sexual material is excluded and represented only by an aggregate count.",
    }, evidence


def main():
    chars = load_characters()
    selected = [c for i, c in enumerate(chars) if i % SHARDS == SHARD]
    summaries, all_evidence = [], []
    for n, ch in enumerate(selected, 1):
        print(f"[{n}/{len(selected)}] {ch['base_character_jp']}", flush=True)
        summary, evidence = collect_one(ch)
        summaries.append(summary)
        for e in evidence:
            all_evidence.append({"base_character_jp": ch["base_character_jp"], "base_id": ch["base_id"], **e})
    with (OUT / "character_social_summary.jsonl").open("w", encoding="utf-8") as f:
        for row in summaries: f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "social_evidence.jsonl").open("w", encoding="utf-8") as f:
        for row in all_evidence: f.write(json.dumps(row, ensure_ascii=False) + "\n")
    cols = ["base_character_jp", "base_id", "evidence_count", "platform_counts", "explicit_sexual_material_excluded_count", *AXES.keys(), "failure_count"]
    with (OUT / "social_axis_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for s in summaries:
            row = {"base_character_jp": s["base_character_jp"], "base_id": s["base_id"], "evidence_count": s["evidence_count"], "platform_counts": json.dumps(s["platform_counts"], ensure_ascii=False), "explicit_sexual_material_excluded_count": s["explicit_sexual_material_excluded_count"], "failure_count": len(s["failures"])}
            row.update(s["axis_keyword_hits"]); w.writerow(row)
    (OUT / "summary.json").write_text(json.dumps({"collector_version": "37.2", "shard": SHARD, "shards": SHARDS, "character_count": len(summaries), "evidence_count": len(all_evidence), "explicit_excluded_count": sum(x["explicit_sexual_material_excluded_count"] for x in summaries), "axis_names": list(AXES)}, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
