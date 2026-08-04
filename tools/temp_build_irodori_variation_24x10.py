#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from huggingface_hub import HfApi, hf_hub_download
from scipy.signal import resample_poly

ROOT = Path.cwd()
WORK = ROOT / "temp_irodori_variation_work"
GENERATED = WORK / "generated"
TRANSFER = ROOT / "public_transfer"
for directory in (WORK, GENERATED, TRANSFER):
    directory.mkdir(parents=True, exist_ok=True)

CLONE_REPO = "SynDataLab-JA/irodori-clones-3m"
TARGET_SR = 48000

VOICES = [
    {"number": 1, "group": "低めの声", "label": "かなり低い・暗め・息混じり", "speaker_id": "speaker_03318"},
    {"number": 2, "group": "低めの声", "label": "かなり低い・硬め・明瞭", "speaker_id": "speaker_00374"},
    {"number": 3, "group": "低めの声", "label": "低い・太め・落ち着き", "speaker_id": "speaker_08346"},
    {"number": 4, "group": "低めの声", "label": "低い・フォーマル・はっきり", "speaker_id": "speaker_08935"},
    {"number": 5, "group": "低めの声", "label": "中低音・自然・笑い混じり", "speaker_id": "speaker_00063"},
    {"number": 6, "group": "低めの声", "label": "中低音・やわらかい・暗め", "speaker_id": "speaker_08524"},
    {"number": 7, "group": "低めの声", "label": "中低音・静か・深い", "speaker_id": "speaker_04916"},
    {"number": 8, "group": "低めの声", "label": "中低音・ドライ・明瞭", "speaker_id": "speaker_03049"},
    {"number": 9, "group": "中くらいの声", "label": "中音・穏やか・物語調", "speaker_id": "speaker_08458"},
    {"number": 10, "group": "中くらいの声", "label": "中音・冷静・少し硬め", "speaker_id": "speaker_03183"},
    {"number": 11, "group": "中くらいの声", "label": "中音・芯強め・クール", "speaker_id": "speaker_09784"},
    {"number": 12, "group": "中くらいの声", "label": "中高音・囁き・近距離", "speaker_id": "speaker_04428"},
    {"number": 13, "group": "中くらいの声", "label": "中高音・やさしい・透明", "speaker_id": "speaker_02022"},
    {"number": 14, "group": "中くらいの声", "label": "中高音・丁寧・明瞭", "speaker_id": "speaker_01635"},
    {"number": 15, "group": "中くらいの声", "label": "中高音・やわらかい・丸い", "speaker_id": "speaker_01639"},
    {"number": 16, "group": "中くらいの声", "label": "中高音・軽快・話しやすい", "speaker_id": "speaker_01281"},
    {"number": 17, "group": "高めの声", "label": "高い・小さめ・落ち着き", "speaker_id": "speaker_00526"},
    {"number": 18, "group": "高めの声", "label": "高い・親密・息少なめ", "speaker_id": "speaker_09925"},
    {"number": 19, "group": "高めの声", "label": "高い・軽い・自然会話", "speaker_id": "speaker_03333"},
    {"number": 20, "group": "高めの声", "label": "高い・明るい・息多め", "speaker_id": "speaker_00703"},
    {"number": 21, "group": "高めの声", "label": "かなり高い・元気・軽快", "speaker_id": "speaker_02196"},
    {"number": 22, "group": "高めの声", "label": "かなり高い・繊細・透明", "speaker_id": "speaker_02829"},
    {"number": 23, "group": "高めの声", "label": "かなり高い・はきはき・細め", "speaker_id": "speaker_00162"},
    {"number": 24, "group": "高めの声", "label": "非常に高い・鋭い・感情的", "speaker_id": "speaker_09137"},
]

UTTERANCE_GROUPS = [
    ("丁寧で落ち着いた話し方", [29, 30, 112]),
    ("自然な日常会話", [20, 21, 25]),
    ("明るくうれしい話し方", [73, 74, 81]),
    ("少し怒った話し方", [88, 91, 97]),
    ("悲しく弱った話し方", [119, 120, 128]),
    ("怖がって慌てた話し方", [47, 51, 68]),
    ("眠く力の抜けた話し方", [41, 44, 46]),
    ("やさしく心配する話し方", [101, 103, 111]),
    ("ゆったりした独り言", [132, 155, 176]),
    ("笑い混じりの話し方", [281, 24, 76]),
]


def safe_component(value: str, limit: int = 100) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or "名称なし")[:limit]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_audio_cell(value: Any, temp_dir: Path) -> tuple[np.ndarray, int]:
    if hasattr(value, "as_py"):
        value = value.as_py()
    payload: bytes | None = None
    if isinstance(value, dict) and value.get("bytes") is not None:
        payload = bytes(value["bytes"])
    elif isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
    if payload is None:
        raise RuntimeError("音声データがありません")
    try:
        audio, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
        return np.mean(audio, axis=1).astype(np.float32), int(sample_rate)
    except Exception:
        source = temp_dir / "decode_source.audio"
        destination = temp_dir / "decode_destination.wav"
        source.write_bytes(payload)
        process = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", str(TARGET_SR), "-c:a", "pcm_s16le", str(destination)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
        )
        source.unlink(missing_ok=True)
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg変換失敗: {process.stderr[-1000:]}")
        audio, sample_rate = sf.read(destination, dtype="float32", always_2d=True)
        destination.unlink(missing_ok=True)
        return np.mean(audio, axis=1).astype(np.float32), int(sample_rate)


def normalize_48k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if sample_rate != TARGET_SR:
        divisor = math.gcd(sample_rate, TARGET_SR)
        audio = resample_poly(audio, TARGET_SR // divisor, sample_rate // divisor).astype(np.float32)
    return np.clip(np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0), -1.0, 1.0).astype(np.float32)


def quality_metrics(audio48: np.ndarray) -> dict[str, Any]:
    if audio48.size == 0:
        return {"usable": False, "reasons": ["空音声"], "artifact_score": 999.0}
    peak = float(np.max(np.abs(audio48)))
    rms = float(np.sqrt(np.mean(audio48 * audio48) + 1e-12))
    peak_db = 20 * math.log10(max(peak, 1e-12))
    rms_db = 20 * math.log10(max(rms, 1e-12))
    duration = float(audio48.size / TARGET_SR)
    clip_ratio = float(np.mean(np.abs(audio48) >= 0.999))
    silence_threshold = max(10 ** (-46 / 20), peak * 0.012)
    silence_ratio = float(np.mean(np.abs(audio48) < silence_threshold))
    click_ratio = float(np.mean(np.abs(np.diff(audio48)) > 0.32)) if audio48.size > 1 else 1.0

    analysis = resample_poly(audio48, 1, 3).astype(np.float32)
    frame_length = 1024
    hop = 256
    if analysis.size < frame_length:
        analysis = np.pad(analysis, (0, frame_length - analysis.size))
    frames = np.lib.stride_tricks.sliding_window_view(analysis, frame_length)[::hop]
    window = np.hanning(frame_length).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1)) + 1e-9
    power = spectrum * spectrum
    frequencies = np.fft.rfftfreq(frame_length, d=1 / 16000)
    flatness = float(np.mean(np.exp(np.mean(np.log(power), axis=1)) / np.maximum(np.mean(power, axis=1), 1e-12)))
    high_frequency_ratio = float(np.mean(power[:, frequencies >= 5000].sum(axis=1) / np.maximum(power.sum(axis=1), 1e-12)))

    periodicities: list[float] = []
    for frame in frames[:: max(1, len(frames) // 80)]:
        frame = frame - float(np.mean(frame))
        energy = float(np.sqrt(np.mean(frame * frame) + 1e-12))
        if energy < 0.008:
            continue
        autocorrelation = np.correlate(frame, frame, mode="full")[frame_length - 1 :]
        lag_min = int(16000 / 500)
        lag_max = min(len(autocorrelation), int(16000 / 60))
        if lag_max <= lag_min or autocorrelation[0] <= 1e-12:
            continue
        periodicities.append(float(np.max(autocorrelation[lag_min:lag_max]) / autocorrelation[0]))
    periodicity = float(np.median(periodicities)) if periodicities else 0.0

    reasons: list[str] = []
    if not 1.0 <= duration <= 35.0:
        reasons.append("長さ異常")
    if rms_db < -45.0:
        reasons.append("音量不足")
    if rms_db > -2.0:
        reasons.append("音量過大")
    if clip_ratio > 0.0015:
        reasons.append("クリッピング")
    if silence_ratio > 0.90:
        reasons.append("無音過多")
    if flatness > 0.22:
        reasons.append("ざらつき過多")
    if high_frequency_ratio > 0.42:
        reasons.append("高域ノイズ過多")
    if click_ratio > 0.004:
        reasons.append("瞬間ノイズ過多")

    artifact_score = 2.8 * flatness + 1.8 * high_frequency_ratio + 1.2 * (1.0 - periodicity) + 18.0 * click_ratio + max(0.0, (-42.0 - rms_db) / 20.0) + max(0.0, (rms_db + 3.0) / 10.0)
    return {
        "usable": not reasons,
        "reasons": reasons,
        "artifact_score": float(artifact_score),
        "duration_sec": duration,
        "peak_dbfs": peak_db,
        "rms_dbfs": rms_db,
        "clip_ratio": clip_ratio,
        "silence_ratio": silence_ratio,
        "spectral_flatness": flatness,
        "high_frequency_ratio": high_frequency_ratio,
        "periodicity": periodicity,
        "click_ratio": click_ratio,
    }


def make_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(source.rglob("*.wav")):
            archive.write(path, path.relative_to(source).as_posix())
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP破損: {bad}")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    api = HfApi()
    dataset_info = api.dataset_info(CLONE_REPO, files_metadata=True)
    revision = str(dataset_info.sha)
    manifest: list[dict[str, Any]] = []

    for voice in VOICES:
        speaker_id = str(voice["speaker_id"])
        speaker_number = int(speaker_id.split("_")[-1])
        parquet_index = speaker_number - 1
        clone_filename = f"data/train-{parquet_index:05d}-of-10000.parquet"
        voice_work = WORK / f"voice_{int(voice['number']):02d}"
        voice_work.mkdir(parents=True, exist_ok=True)
        parquet_path = Path(hf_hub_download(repo_id=CLONE_REPO, repo_type="dataset", filename=clone_filename, revision=revision, local_dir=voice_work / "clone_repo"))
        rows = pq.read_table(parquet_path).to_pylist()
        if len(rows) < 299:
            raise RuntimeError(f"{speaker_id}: 299発話ありません")

        visible_folder = f"{int(voice['number']):02d}_{safe_component(str(voice['label']))}"
        wav_folder = GENERATED / voice["group"] / visible_folder
        wav_folder.mkdir(parents=True, exist_ok=True)

        for visible_index, (visible_label, candidate_indices) in enumerate(UTTERANCE_GROUPS, 1):
            candidates: list[dict[str, Any]] = []
            for source_index in candidate_indices:
                row = rows[source_index - 1]
                row_speaker = str(row.get("speaker_id") or speaker_id)
                if row_speaker != speaker_id:
                    raise RuntimeError(f"話者不一致: {speaker_id} != {row_speaker}")
                audio, sample_rate = decode_audio_cell(row.get("audio"), voice_work)
                audio48 = normalize_48k(audio, sample_rate)
                quality = quality_metrics(audio48)
                candidates.append({"source_index": source_index, "text": str(row.get("text") or ""), "audio": audio48, "quality": quality})
            usable = [candidate for candidate in candidates if bool(candidate["quality"]["usable"])]
            selected = min(usable or candidates, key=lambda item: float(item["quality"]["artifact_score"]))
            destination = wav_folder / f"{visible_index:02d}_{safe_component(visible_label)}.wav"
            sf.write(destination, selected["audio"], TARGET_SR, subtype="PCM_16")
            verified_audio, verified_rate = sf.read(destination, dtype="float32", always_2d=True)
            if verified_rate != TARGET_SR or verified_audio.shape[1] != 1 or verified_audio.shape[0] == 0:
                raise RuntimeError(f"WAV検証失敗: {destination}")
            manifest.append({
                "声番号": int(voice["number"]),
                "声域グループ": voice["group"],
                "表示声名": voice["label"],
                "内部話者ID": speaker_id,
                "発話番号": visible_index,
                "発話名": visible_label,
                "元発話番号": int(selected["source_index"]),
                "元テキスト": selected["text"],
                "出力ファイル": f"{voice['group']}/{visible_folder}/{destination.name}",
                "SHA256": sha256_file(destination),
                **{key: value for key, value in selected["quality"].items() if key != "reasons"},
                "検査理由": ",".join(selected["quality"]["reasons"]),
                "代替候補使用": int(selected["source_index"]) != int(candidate_indices[0]),
            })
        print(f"完成: {visible_folder}", flush=True)

    low_source = GENERATED / "低めの声"
    mid_source = GENERATED / "中くらいの声"
    high_source = GENERATED / "高めの声"
    for source, expected in ((low_source, 80), (mid_source, 80), (high_source, 80)):
        actual = len(list(source.rglob("*.wav")))
        if actual != expected:
            raise RuntimeError(f"{source.name}: {actual} != {expected}")

    archives = [
        (low_source, TRANSFER / "irodori_variation_low8_10each.zip"),
        (mid_source, TRANSFER / "irodori_variation_mid8_10each.zip"),
        (high_source, TRANSFER / "irodori_variation_high8_10each.zip"),
    ]
    for source, destination in archives:
        make_zip(source, destination)
        if destination.stat().st_size >= 99_000_000:
            raise RuntimeError(f"GitHub転送上限超過: {destination}")

    write_csv(TRANSFER / "validation_catalog.csv", manifest)
    total_duration = sum(float(row["duration_sec"]) for row in manifest)
    summary = {
        "声の種類": 24,
        "各声のWAV数": 10,
        "合計WAV数": 240,
        "低めの声": 8,
        "中くらいの声": 8,
        "高めの声": 8,
        "サンプルレート": 48000,
        "チャンネル": 1,
        "合計秒数": round(total_duration, 3),
        "ZIP_CRC": "PASS",
        "WAV全読込": "240/240 PASS",
        "利用者向けZIP内": "日本語名フォルダとWAVのみ",
        "元データリビジョン": revision,
    }
    (TRANSFER / "validation_result.txt").write_text("\n".join(f"{key}={value}" for key, value in summary.items()) + "\n", encoding="utf-8")
    (TRANSFER / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (TRANSFER / "file_sha256.txt").write_text("\n".join(f"{sha256_file(path)}  {path.name}" for _, path in archives) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
