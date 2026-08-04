#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import wave
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path.cwd()
SOURCE = ROOT / "downloaded_clear_voices"
OUT = ROOT / "clear_package_output"
STAGE_ALL = ROOT / "clear_stage_all"
STAGE_MID = ROOT / "clear_stage_mid"
STAGE_HIGH = ROOT / "clear_stage_high"
STAGE_ASMR = ROOT / "clear_stage_asmr"
STAGE_VALIDATION = ROOT / "clear_stage_validation"
for directory in (OUT, STAGE_ALL, STAGE_MID, STAGE_HIGH, STAGE_ASMR, STAGE_VALIDATION):
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_wav(path: Path, channels: int) -> dict[str, object]:
    with wave.open(str(path), "rb") as wav:
        actual_channels = wav.getnchannels()
        rate = wav.getframerate()
        width = wav.getsampwidth()
        frames = wav.getnframes()
        wav.readframes(frames)
    if actual_channels != channels:
        raise RuntimeError(f"チャンネル数不一致: {path}: {actual_channels} != {channels}")
    if rate != 48000:
        raise RuntimeError(f"サンプルレート不一致: {path}: {rate}")
    if width != 3:
        raise RuntimeError(f"PCM 24-bitではありません: {path}: width={width}")
    if frames <= 0:
        raise RuntimeError(f"空のWAVです: {path}")
    return {
        "file": str(path),
        "channels": actual_channels,
        "sample_rate": rate,
        "sample_width": width,
        "frames": frames,
        "duration_sec": frames / rate,
        "sha256": sha256(path),
    }


def make_zip(stage: Path, output: Path) -> None:
    output.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(stage).as_posix())
    with zipfile.ZipFile(output, "r") as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC失敗: {output}: {bad}")
        names = archive.namelist()
        if any("#U" in name for name in names):
            raise RuntimeError(f"文字化け名を検出: {output}")


def copy_wavs(paths: Iterable[Path], stage: Path, source_marker: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(paths):
        marker_index = path.parts.index(source_marker)
        relative_parts = path.parts[marker_index + 1 :]
        destination = stage.joinpath(*relative_parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        rows.append(validate_wav(destination, 1 if source_marker == "モノラル" else 2))
    return rows


def main() -> None:
    mono_paths = sorted(SOURCE.rglob("モノラル/*/*.wav"))
    asmr_paths = sorted(SOURCE.rglob("耳元ステレオ/*/*.wav"))
    if len(mono_paths) != 80:
        raise RuntimeError(f"モノラルWAVが80本ではありません: {len(mono_paths)}")
    if len(asmr_paths) != 8:
        raise RuntimeError(f"耳元ステレオWAVが8本ではありません: {len(asmr_paths)}")

    all_rows = copy_wavs(mono_paths, STAGE_ALL, "モノラル")
    mid_paths = [path for path in mono_paths if any(part.startswith(("01_", "02_", "03_", "04_")) for part in path.parts)]
    high_paths = [path for path in mono_paths if any(part.startswith(("05_", "06_", "07_", "08_")) for part in path.parts)]
    mid_rows = copy_wavs(mid_paths, STAGE_MID, "モノラル")
    high_rows = copy_wavs(high_paths, STAGE_HIGH, "モノラル")
    asmr_rows = copy_wavs(asmr_paths, STAGE_ASMR, "耳元ステレオ")
    if len(mid_rows) != 40 or len(high_rows) != 40:
        raise RuntimeError(f"分割件数不一致: mid={len(mid_rows)} high={len(high_rows)}")

    validation_files = sorted(SOURCE.rglob("検証/*"))
    for path in validation_files:
        if not path.is_file():
            continue
        voice_dir = next((part for part in path.parts if part.startswith("voice_")), "voice_unknown")
        destination = STAGE_VALIDATION / voice_dir / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    output_all = OUT / "Irodori_明瞭再生成版_中高音8声_各10話法_モノラル80WAV_日本語.zip"
    output_mid = OUT / "Irodori_明瞭再生成版_中高音4声_各10話法_モノラル40WAV_日本語.zip"
    output_high = OUT / "Irodori_明瞭再生成版_高音4声_各10話法_モノラル40WAV_日本語.zip"
    output_asmr = OUT / "Irodori_明瞭再生成版_ASMR耳元ステレオ_8声8WAV_日本語.zip"
    output_validation = OUT / "Irodori_明瞭再生成版_厳格ASR・生成検証資料.zip"
    make_zip(STAGE_ALL, output_all)
    make_zip(STAGE_MID, output_mid)
    make_zip(STAGE_HIGH, output_high)
    make_zip(STAGE_ASMR, output_asmr)
    make_zip(STAGE_VALIDATION, output_validation)

    report_rows = []
    for category, rows in (("全8声", all_rows), ("中高音4声", mid_rows), ("高音4声", high_rows), ("ASMR耳元", asmr_rows)):
        report_rows.append({
            "category": category,
            "wav_count": len(rows),
            "total_duration_sec": round(sum(float(row["duration_sec"]) for row in rows), 3),
            "sample_rates": sorted({int(row["sample_rate"]) for row in rows}),
            "channels": sorted({int(row["channels"]) for row in rows}),
            "sample_widths": sorted({int(row["sample_width"]) for row in rows}),
            "exact_sha_duplicates": len(rows) - len({str(row["sha256"]) for row in rows}),
        })
    summary = {
        "model": "Aratako/Irodori-TTS-600M-v3-VoiceDesign",
        "mono_wavs": len(all_rows),
        "asmr_stereo_wavs": len(asmr_rows),
        "format": "48000Hz PCM 24-bit",
        "strict_asr_gate": True,
        "emoji_input": False,
        "fixed_seconds": True,
        "num_steps": 40,
        "human_listening": False,
        "reports": report_rows,
    }
    (OUT / "最終集計.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    checksums = []
    for path in (output_all, output_mid, output_high, output_asmr, output_validation):
        checksums.append(f"{sha256(path)}  {path.name}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
