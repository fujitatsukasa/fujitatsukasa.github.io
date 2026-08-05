#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import tempfile
import zlib
from pathlib import Path

import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize

OUT = Path("artifact_bluearchive_audio_v54")
OUT.mkdir(parents=True, exist_ok=True)

DATA_B64 = "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"

SCRIPTS = json.loads(zlib.decompress(base64.b64decode(DATA_B64)).decode("utf-8"))

VOICE_MAP = {
    "編集部": ("ja-JP-NanamiNeural", "-4%", "-1Hz"),
    "解説": ("ja-JP-NanamiNeural", "-6%", "-1Hz"),
    "地の文": ("ja-JP-NanamiNeural", "-8%", "-2Hz"),
    "キサキ": ("ja-JP-NanamiNeural", "-13%", "-5Hz"),
    "シュン": ("ja-JP-NanamiNeural", "-5%", "+3Hz"),
    "係の生徒": ("ja-JP-NanamiNeural", "+3%", "+4Hz"),
    "コメント": ("ja-JP-KeitaNeural", "+2%", "+1Hz"),
    "返信": ("ja-JP-KeitaNeural", "+5%", "+2Hz"),
    "別の返信": ("ja-JP-KeitaNeural", "+1%", "-1Hz"),
    "新任": ("ja-JP-KeitaNeural", "+3%", "+3Hz"),
    "質問": ("ja-JP-KeitaNeural", "0%", "+2Hz"),
}


def srt_time(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


async def synth_line(text: str, path: Path, voice: str, rate: str, pitch: str) -> None:
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch).save(str(path))
            if path.exists() and path.stat().st_size > 500:
                return
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5 * (attempt + 1))


async def build_script(name: str, rows: list[dict]) -> dict:
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    combined = AudioSegment.silent(duration=450)
    srt_entries: list[tuple[int, int, str, str]] = []
    meta: list[dict] = []
    for idx, row in enumerate(rows, 1):
        speaker = row["speaker"]
        text = row["text"]
        voice, rate, pitch = VOICE_MAP.get(speaker, ("ja-JP-NanamiNeural", "0%", "0Hz"))
        mp3 = work / f"{idx:03d}_{speaker}.mp3"
        await synth_line(text, mp3, voice, rate, pitch)
        seg = AudioSegment.from_file(mp3)
        start = len(combined)
        combined += seg
        end = len(combined)
        pause = 420 if speaker in {"編集部", "解説", "地の文"} else 300
        combined += AudioSegment.silent(duration=pause)
        srt_entries.append((start, end, speaker, text))
        meta.append({"index": idx, "speaker": speaker, "text": text, "start_ms": start, "end_ms": end, "duration_ms": len(seg), "voice": voice, "rate": rate, "pitch": pitch, "segment": mp3.name})
    combined += AudioSegment.silent(duration=700)
    out_mp3 = OUT / f"{name}_ナレーション.mp3"
    combined.export(out_mp3, format="mp3", bitrate="192k")
    out_wav = OUT / f"{name}_ナレーション.wav"
    combined.export(out_wav, format="wav")
    srt = OUT / f"{name}_字幕.srt"
    with srt.open("w", encoding="utf-8") as f:
        for i, (start, end, speaker, text) in enumerate(srt_entries, 1):
            f.write(f"{i}\n{srt_time(start)} --> {srt_time(end)}\n{speaker}：{text}\n\n")
    csv_path = OUT / f"{name}_音声区間.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0].keys()))
        w.writeheader(); w.writerows(meta)
    return {"name": name, "lines": len(rows), "duration_ms": len(combined), "mp3": out_mp3.name, "wav": out_wav.name, "srt": srt.name, "csv": csv_path.name}


async def main() -> None:
    results = []
    for key in ("reaction", "explanation", "ss"):
        results.append(await build_script(key, SCRIPTS[key]))
    (OUT / "audio_summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


asyncio.run(main())
