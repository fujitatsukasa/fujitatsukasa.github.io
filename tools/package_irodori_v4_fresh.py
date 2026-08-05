#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import whisper
from pykakasi import kakasi
from rapidfuzz import fuzz

ROOT = Path.cwd()
SOURCE = ROOT / "downloaded_fresh"
STAGE = ROOT / "irodori_v4_fresh_stage"
MONO_STAGE = STAGE / "モノラル"
STEREO_STAGE = STAGE / "ASMR耳元ステレオ"
VALIDATION = STAGE / "検証"
OUT = ROOT / "irodori_v4_fresh_output"
for d in (MONO_STAGE, STEREO_STAGE, VALIDATION, OUT):
    d.mkdir(parents=True, exist_ok=True)

VOICE_FOLDERS = [
    "01_中高音・ささやき向き・やわらかい",
    "02_中高音・やさしい・透明",
    "03_中高音・上品・明瞭",
    "04_中高音・丸い・親しみやすい",
    "05_高音・小さめ・落ち着き",
    "06_高音・親密・澄んだ声",
    "07_高音・軽やか・自然会話",
    "08_かなり高い・繊細・透明",
]

STYLES = {
    1: {"label":"自然な近距離会話","text":"ねえ、今日、カフェ寄らない？","mode":"neutral"},
    2: {"label":"丁寧で穏やかな案内","text":"こちらを確認してください。","mode":"polite"},
    3: {"label":"眠く力の抜けた話し方","text":"ごめん、まだ眠いの。","mode":"sleepy"},
    4: {"label":"悲しく弱った話し方","text":"今日は少しつらいの。","mode":"sad"},
    5: {"label":"怒りを抑えた話し方","text":"もう、同じことはしないで。","mode":"angry"},
    6: {"label":"怖く慌てた話し方","text":"待って。そこに何かいる。","mode":"fear"},
    7: {"label":"明るくうれしい話し方","text":"来てくれたんだ。うれしい。","mode":"happy"},
    8: {"label":"やさしく心配する話し方","text":"無理しなくていいよ。","mode":"gentle"},
    9: {"label":"ASMR耳元ささやき","text":"聞こえる？ 力を抜いて。","mode":"asmr"},
    10:{"label":"笑い混じりの話し方","text":"ふふっ。ちゃんと分かってるよ。","mode":"laugh"},
}

REPLACEMENTS = {
    "辛い":"つらい","良い":"いい","大丈夫":"だいじょうぶ","分かって":"わかって","分かる":"わかる",
    "来て":"きて","今日は":"きょうは","今日":"きょう","確認":"かくにん","同じ":"おなじ",
    "無理":"むり","聞こえる":"きこえる","力":"ちから","眠い":"ねむい","何か":"なにか",
}
KAKASI = kakasi()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_hiragana(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    for src, dst in REPLACEMENTS.items():
        text = text.replace(src, dst)
    chunks: list[str] = []
    for item in KAKASI.convert(text):
        chunks.append(str(item.get("hira") or item.get("orig") or ""))
    return re.sub(r"[^0-9a-zぁ-んゔー]", "", "".join(chunks).lower())


def transcribe(path: Path, model: Any) -> str:
    result = model.transcribe(
        str(path),
        language="ja",
        fp16=False,
        temperature=0.0,
        beam_size=5,
        best_of=5,
        condition_on_previous_text=False,
        word_timestamps=False,
        verbose=False,
    )
    return str(result.get("text") or "").strip()


def audio_metrics(signal: np.ndarray, sr: int) -> dict[str, float]:
    x = np.asarray(signal, dtype=np.float32)
    if x.ndim > 1:
        mono = np.mean(x, axis=1)
    else:
        mono = x
    duration = float(mono.size / sr)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(mono)) + 1e-12)) if mono.size else 0.0
    clip = float(np.mean(np.abs(mono) >= 0.999)) if mono.size else 1.0
    return {
        "duration_sec": duration,
        "peak_dbfs": 20 * math.log10(max(peak, 1e-12)),
        "rms_dbfs": 20 * math.log10(max(rms, 1e-12)),
        "clip_ratio": clip,
    }


def find_voice_dir(root_name: str, voice_folder: str) -> Path:
    matches = [p for p in SOURCE.rglob(voice_folder) if p.is_dir() and root_name in p.parts]
    if len(matches) != 1:
        raise RuntimeError(f"{root_name}/{voice_folder} の候補数が1ではありません: {matches}")
    return matches[0]


def make_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        for path in sorted(source.rglob("*.wav")):
            zf.write(path, path.relative_to(source).as_posix())
    with zipfile.ZipFile(destination, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC異常: {bad}")


def main() -> None:
    # Merge the eight independent v4-Small generation jobs.
    for voice_folder in VOICE_FOLDERS:
        mono_source = find_voice_dir("最終モノラル", voice_folder)
        stereo_source = find_voice_dir("ASMR耳元ステレオ", voice_folder)
        mono_files = sorted(mono_source.glob("*.wav"))
        stereo_files = sorted(stereo_source.glob("*.wav"))
        if len(mono_files) != 10:
            raise RuntimeError(f"{voice_folder}: モノラルが10本ではありません: {len(mono_files)}")
        if len(stereo_files) != 1:
            raise RuntimeError(f"{voice_folder}: ASMRステレオが1本ではありません: {len(stereo_files)}")
        mono_dest = MONO_STAGE / voice_folder
        stereo_dest = STEREO_STAGE / voice_folder
        mono_dest.mkdir(parents=True, exist_ok=True)
        stereo_dest.mkdir(parents=True, exist_ok=True)
        for p in mono_files:
            shutil.copy2(p, mono_dest / p.name)
        for p in stereo_files:
            shutil.copy2(p, stereo_dest / p.name)

    model = whisper.load_model("base", device="cpu")
    rows: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for voice_folder in VOICE_FOLDERS:
        files = sorted((MONO_STAGE / voice_folder).glob("*.wav"))
        for style_number, style in STYLES.items():
            candidates = [p for p in files if p.name.startswith(f"{style_number:02d}_")]
            if len(candidates) != 1:
                raise RuntimeError(f"{voice_folder} style {style_number}: ファイルが1本ではありません")
            path = candidates[0]
            info = sf.info(path)
            signal, sr = sf.read(path, dtype="float32", always_2d=True)
            if int(sr) != 48000 or signal.shape[1] != 1 or info.subtype != "PCM_24":
                raise RuntimeError(f"WAV形式異常: {path}: sr={sr}, ch={signal.shape[1]}, subtype={info.subtype}")
            if not np.all(np.isfinite(signal)):
                raise RuntimeError(f"NaN/Infを含むWAV: {path}")
            transcript = transcribe(path, model)
            target_hira = to_hiragana(str(style["text"]))
            actual_hira = to_hiragana(transcript)
            ratio = float(fuzz.ratio(target_hira, actual_hira) / 100.0)
            partial = float(fuzz.partial_ratio(target_hira, actual_hira) / 100.0) if actual_hira else 0.0
            delta = len(actual_hira) - len(target_hira)
            threshold = 0.74 if style["mode"] in {"asmr", "laugh"} else 0.78
            if ratio < threshold or partial < 0.90 or delta > 2:
                raise RuntimeError(
                    f"最終ASR不合格: {path}: target={style['text']!r}, transcript={transcript!r}, "
                    f"ratio={ratio:.3f}, partial={partial:.3f}, delta={delta}"
                )
            metrics = audio_metrics(signal, int(sr))
            if not (0.55 <= metrics["duration_sec"] <= 9.5):
                raise RuntimeError(f"再生時間異常: {path}: {metrics['duration_sec']}")
            if metrics["clip_ratio"] > 0.0001:
                raise RuntimeError(f"クリッピング異常: {path}: {metrics['clip_ratio']}")
            digest = sha256(path)
            if digest in seen_hashes:
                raise RuntimeError(f"完全一致重複: {path}")
            seen_hashes.add(digest)
            rows.append({
                "file": str(path.relative_to(MONO_STAGE)),
                "voice": voice_folder,
                "style_number": style_number,
                "style": style["label"],
                "target_text": style["text"],
                "transcript": transcript,
                "asr_ratio": ratio,
                "asr_partial": partial,
                "length_delta": delta,
                "sample_rate": int(sr),
                "channels": int(signal.shape[1]),
                "subtype": info.subtype,
                "sha256": digest,
                **metrics,
            })

    stereo_rows: list[dict[str, Any]] = []
    for voice_folder in VOICE_FOLDERS:
        files = sorted((STEREO_STAGE / voice_folder).glob("*.wav"))
        if len(files) != 1:
            raise RuntimeError(f"ステレオASMR数異常: {voice_folder}")
        path = files[0]
        info = sf.info(path)
        signal, sr = sf.read(path, dtype="float32", always_2d=True)
        if int(sr) != 48000 or signal.shape[1] != 2 or info.subtype != "PCM_24":
            raise RuntimeError(f"ステレオ形式異常: {path}")
        stereo_rows.append({
            "file": str(path.relative_to(STEREO_STAGE)),
            "sample_rate": int(sr),
            "channels": int(signal.shape[1]),
            "subtype": info.subtype,
            "sha256": sha256(path),
            **audio_metrics(signal, int(sr)),
        })

    with (VALIDATION / "最終80WAV検査.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (VALIDATION / "ASMRステレオ8WAV検査.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(stereo_rows[0].keys()))
        writer.writeheader()
        writer.writerows(stereo_rows)

    mono_zip = OUT / "Irodori_v4_中高音8声_各10話法_明瞭再生成版_80WAV_日本語.zip"
    stereo_zip = OUT / "Irodori_v4_ASMR耳元ステレオ_8声8WAV_日本語.zip"
    validation_zip = OUT / "Irodori_v4_明瞭再生成版_検証資料.zip"
    make_zip(MONO_STAGE, mono_zip)
    make_zip(STEREO_STAGE, stereo_zip)
    validation_zip.unlink(missing_ok=True)
    with zipfile.ZipFile(validation_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(VALIDATION.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(VALIDATION).as_posix())
    summary = {
        "checkpoint": "Aratako/Irodori-TTS-v4-Small",
        "mono_wav_count": len(rows),
        "stereo_wav_count": len(stereo_rows),
        "sample_rate": 48000,
        "subtype": "PCM_24",
        "minimum_asr_ratio": min(float(r["asr_ratio"]) for r in rows),
        "maximum_positive_length_delta": max(int(r["length_delta"]) for r in rows),
        "mono_zip_sha256": sha256(mono_zip),
        "stereo_zip_sha256": sha256(stereo_zip),
        "validation_zip_sha256": sha256(validation_zip),
    }
    (OUT / "最終集計.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(p)}  {p.name}" for p in (mono_zip, stereo_zip, validation_zip)) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
