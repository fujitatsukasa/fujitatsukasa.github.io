#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

OUT = Path("artifact_browser_watch_probe_v61")
OUT.mkdir(parents=True, exist_ok=True)
VIDEO_ID = "Ra9F56wUaCo"
INSTANCES = [
    "https://invidious.tiekoetter.com",
    "https://invidious.f5.si",
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yt.chocolatemoo53.com",
    "https://yewtu.be",
    "https://invidious.private.coffee",
    "https://inv.us.projectsegfau.lt",
    "https://invidious.flokinet.to",
    "https://invidious.osi.kr",
    "https://invidious.protokolla.fi",
    "https://invidious.adminforge.de",
    "https://invidious.fdn.fr",
]

async def main() -> None:
    records = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1365, "height": 768},
            locale="ja-JP",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36",
            ignore_https_errors=True,
        )
        for base in INSTANCES:
            host = re.sub(r"[^A-Za-z0-9._-]+", "_", urlparse(base).netloc)
            folder = OUT / host
            folder.mkdir(exist_ok=True)
            url = f"{base}/watch?v={VIDEO_ID}&local=true&quality=medium&autoplay=1"
            network = []
            page = await context.new_page()
            page.on("response", lambda r: network.append({"url": r.url, "status": r.status, "resource_type": r.request.resource_type, "content_type": r.headers.get("content-type")}))
            rec = {"base": base, "url": url}
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=50000)
                rec["page_status"] = resp.status if resp else None
                await page.wait_for_timeout(12000)
                rec["title"] = await page.title()
                rec["body_text_head"] = (await page.locator("body").inner_text())[:4000]
                await page.screenshot(path=str(folder / "page.jpg"), full_page=True, quality=82)
                videos = page.locator("video")
                rec["video_count"] = await videos.count()
                if rec["video_count"]:
                    video = videos.first
                    rec["video_state_before"] = await video.evaluate("""v => ({src:v.src,currentSrc:v.currentSrc,duration:v.duration,readyState:v.readyState,networkState:v.networkState,paused:v.paused,error:v.error?{code:v.error.code,message:v.error.message}:null,videoWidth:v.videoWidth,videoHeight:v.videoHeight,textTracks:Array.from(v.textTracks).map(t=>({kind:t.kind,label:t.label,language:t.language,mode:t.mode}))})""")
                    try:
                        await video.evaluate("v => { v.muted=true; return v.play(); }")
                    except Exception as e:
                        rec["play_error"] = repr(e)
                    await page.wait_for_timeout(8000)
                    rec["video_state_after_play"] = await video.evaluate("""v => ({currentTime:v.currentTime,duration:v.duration,readyState:v.readyState,paused:v.paused,error:v.error?{code:v.error.code,message:v.error.message}:null,videoWidth:v.videoWidth,videoHeight:v.videoHeight})""")
                    for t in [0, 5, 15, 30, 60]:
                        try:
                            await video.evaluate("(v,t) => { if (Number.isFinite(v.duration)) v.currentTime=Math.min(t, Math.max(0,v.duration-0.25)); }", t)
                            await page.wait_for_timeout(2500)
                            await video.screenshot(path=str(folder / f"video_{t:03d}s.jpg"), quality=90)
                        except Exception as e:
                            rec.setdefault("frame_errors", []).append({"time": t, "error": repr(e)})
                rec["html"] = str(folder / "page.html")
                (folder / "page.html").write_text(await page.content(), encoding="utf-8")
            except Exception as e:
                rec["error"] = repr(e)
                try:
                    await page.screenshot(path=str(folder / "error.jpg"), full_page=True, quality=80)
                except Exception:
                    pass
            finally:
                interesting = [x for x in network if any(k in x["url"] for k in ["videoplayback", "/api/v1/videos/", "/latest_version", "/videoplayback", "/captions", "googlevideo", "proxy"])]
                rec["network_interesting"] = interesting[:300]
                rec["network_count"] = len(network)
                (folder / "network.json").write_text(json.dumps(network, ensure_ascii=False, indent=2), encoding="utf-8")
                (folder / "result.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({"base": base, "status": rec.get("page_status"), "videos": rec.get("video_count"), "state": rec.get("video_state_after_play"), "error": rec.get("error")}, ensure_ascii=False), flush=True)
                records.append(rec)
                await page.close()
        await browser.close()
    (OUT / "summary.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

asyncio.run(main())
