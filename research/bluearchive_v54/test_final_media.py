#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from urllib.parse import quote, urlencode

import edge_tts
import requests
from PIL import Image

OUT = Path("artifact_bluearchive_final_media_v54_test")
OUT.mkdir(parents=True, exist_ok=True)

KISAKI_AVATAR = "https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/Student_Portrait_CH0356_Collection.png"
KISAKI_MEMORY = "https://static.kivo.wiki/images/students/%E9%BE%99%E5%8D%8E%20%E5%A6%83%E5%92%B2/%E6%B3%B3%E8%A3%85/CH0356_home_Idle_01_5.jpg"

prompt = """Create one cinematic 16:9 anime story still, not an infographic, not a report, not a collage. The only visible character is Ryuuge Kisaki (Swimsuit) from Blue Archive. Preserve the exact identity from both reference images: very petite 17-year-old student, near-black dark indigo hair, long low braid over the front, half-lidded blue-violet eyes, thin pale lavender sunglasses, black/navy swimsuit, large blue-violet butterfly ornament at the chest, loose charcoal summer robe with blue-gray and gold floral hem. Do not draw a halo, ring, magic circle, emblem, text, logo, subtitle, or any background people. Scene: a bright summer beach rest hut in the afternoon, seated deeply in a chair at a small table. A closed black notebook lies face-down on the table beside a white tea cup and saucer. She reaches her right index and middle finger toward the corner of the notebook but stops just before touching it; her left hand rests on the chair arm. Her eyes look at the notebook corner. Quiet restrained expression, dignified posture, soft natural summer light, accurate five-finger hands, natural wrists/elbows/shoulders, no object intersections, polished Japanese game event-CG quality."""

params = {
    "model": "kontext",
    "width": 1536,
    "height": 1024,
    "quality": "high",
    "safe": "true",
    "seed": 5401,
    "image": f"{KISAKI_AVATAR}|{KISAKI_MEMORY}",
}
url = f"https://gen.pollinations.ai/image/{quote(prompt, safe='')}?{urlencode(params)}"
r = requests.get(url, timeout=600, headers={"User-Agent": "BlueArchiveFinalMediaV54/1.0"})
(OUT / "image_response.json").write_text(
    json.dumps({"status": r.status_code, "content_type": r.headers.get("content-type"), "url": url, "text_head": r.text[:500] if "text" in r.headers.get("content-type", "") else ""}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
r.raise_for_status()
img_bytes = r.content
im = Image.open(io.BytesIO(img_bytes))
im.verify()
(OUT / "scene01_kisaki_notebook.png").write_bytes(img_bytes)

async def make_audio() -> None:
    text = "本日は休業じゃ。……そう言い切るだけで、これほど難しいとはの。"
    voice = "ja-JP-NanamiNeural"
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="-5%", pitch="-2Hz")
    await communicate.save(str(OUT / "tts_test.mp3"))

asyncio.run(make_audio())
print(json.dumps({"image_bytes": len(img_bytes), "image_size": im.size, "audio_bytes": (OUT / "tts_test.mp3").stat().st_size}, ensure_ascii=False))
