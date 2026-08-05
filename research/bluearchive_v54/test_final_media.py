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

prompt = """One cinematic 16:9 anime story still, not an infographic, not a report, not a collage. The only visible character is Ryuuge Kisaki (Swimsuit) from Blue Archive. Preserve the exact identity from the reference images: very petite, near-black dark indigo hair, long low braid over the front, half-lidded blue-violet eyes, thin pale lavender sunglasses, black/navy swimsuit, large blue-violet butterfly ornament, loose charcoal summer robe with blue-gray and gold floral hem. No halo, no ring, no magic circle, no emblem, no text, no logo, no subtitles, no background people. Scene: bright summer beach rest hut in the afternoon. She sits deeply in a chair at a small table. A closed black notebook lies face-down beside a white tea cup and saucer. She reaches her right index and middle finger toward the notebook corner but stops just before touching it. Left hand on the chair arm. Eyes on the notebook. Quiet restrained expression, dignified posture, soft natural light, accurate five-finger hands, polished Japanese game event-CG quality."""


def try_image(label: str, model: str, reference: bool) -> dict:
    params = {
        "model": model,
        "width": 1536,
        "height": 1024,
        "safe": "true",
        "seed": 5401,
    }
    if model.startswith("gpt"):
        params["quality"] = "high"
    if reference:
        params["image"] = f"{KISAKI_AVATAR}|{KISAKI_MEMORY}"
    url = f"https://gen.pollinations.ai/image/{quote(prompt, safe='')}?{urlencode(params)}"
    rec: dict = {"label": label, "model": model, "reference": reference, "url": url}
    try:
        r = requests.get(url, timeout=600, headers={"User-Agent": "BlueArchiveFinalMediaV54/1.0"})
        rec.update(status=r.status_code, content_type=r.headers.get("content-type"), bytes=len(r.content))
        if r.status_code != 200:
            rec["text_head"] = r.text[:1000]
            return rec
        im = Image.open(io.BytesIO(r.content))
        im.verify()
        ext = ".png" if im.format == "PNG" else ".jpg"
        (OUT / f"{label}{ext}").write_bytes(r.content)
        rec["image_format"] = im.format
        rec["image_size"] = list(im.size)
        rec["saved"] = f"{label}{ext}"
    except Exception as exc:
        rec["error"] = repr(exc)
    return rec


image_results = [
    try_image("01_zimage_text_only", "zimage", False),
    try_image("02_kontext_reference", "kontext", True),
]
(OUT / "image_responses.json").write_text(json.dumps(image_results, ensure_ascii=False, indent=2), encoding="utf-8")


async def make_audio() -> dict:
    rec: dict = {}
    try:
        text = "本日は休業じゃ。……そう言い切るだけで、これほど難しいとはの。"
        voice = "ja-JP-NanamiNeural"
        communicate = edge_tts.Communicate(text=text, voice=voice, rate="-5%", pitch="-2Hz")
        await communicate.save(str(OUT / "tts_test.mp3"))
        rec = {"saved": "tts_test.mp3", "bytes": (OUT / "tts_test.mp3").stat().st_size, "voice": voice}
    except Exception as exc:
        rec = {"error": repr(exc)}
    return rec


audio_result = asyncio.run(make_audio())
(OUT / "audio_response.json").write_text(json.dumps(audio_result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"images": image_results, "audio": audio_result}, ensure_ascii=False))
