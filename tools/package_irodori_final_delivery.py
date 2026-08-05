#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import soundfile as sf

ROOT = Path.cwd()
DOWNLOADED = ROOT / "downloaded_delivery_voices"
WORK = ROOT / "delivery_package_work"
OUTPUT = ROOT / "delivery_package_output"
MONO_STAGE = WORK / "01_透明モノラル80WAV"
STEREO_STAGE = WORK / "02_ASMR耳元ステレオ8WAV"
VALIDATION_STAGE = WORK / "検証資料"
for directory in (MONO_STAGE, STEREO_STAGE, VALIDATION_STAGE, OUTPUT):
    directory.mkdir(parents=True, exist_ok=True)

EXPECTED_VOICE_FOLDERS = [
    "01_中高音・やわらかい・透明",
    "02_中高音・上品・明瞭",
    "03_中高音・丸い・親しみやすい",
    "04_中高音・細め・クール",
    "05_高音・澄んだ・近距離",
    "06_高音・明るい・自然",
    "07_高音・繊細・息少なめ",
    "08_かなり高い・透明・安定",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields or ["empty"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_wav(path: Path, channels: int) -> dict[str, Any]:
    info = sf.info(path)
    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    if int(info.samplerate) != 48_000:
        raise RuntimeError(f"48kHzではありません: {path} -> {info.samplerate}")
    if int(info.channels) != channels:
        raise RuntimeError(f"チャンネル数が不正です: {path} -> {info.channels}")
    if info.subtype != "PCM_24":
        raise RuntimeError(f"PCM 24-bitではありません: {path} -> {info.subtype}")
    duration = float(data.shape[0] / sample_rate)
    if duration < 0.5:
        raise RuntimeError(f"短すぎるWAVです: {path} -> {duration}")
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if decoded.returncode != 0:
        raise RuntimeError(f"全編デコード失敗: {path}: {decoded.stderr[-500:]!r}")
    return {
        "file": path.as_posix(),
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "subtype": info.subtype,
        "duration_sec": round(duration, 3),
        "sha256": sha256(path),
    }


def make_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for file in sorted(source.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(source).as_posix())
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC失敗: {destination} -> {bad}")


def copy_voice_data() -> None:
    artifact_dirs = [path for path in DOWNLOADED.iterdir() if path.is_dir()]
    for voice_folder in EXPECTED_VOICE_FOLDERS:
        mono_matches = [
            path
            for path in DOWNLOADED.rglob("*.wav")
            if "モノラル" in path.parts and voice_folder in path.parts
        ]
        stereo_matches = [
            path
            for path in DOWNLOADED.rglob("*.wav")
            if "耳元ステレオ" in path.parts and voice_folder in path.parts
        ]
        if len(mono_matches) != 10:
            raise RuntimeError(f"{voice_folder}: モノラルWAV {len(mono_matches)} / 10")
        if len(stereo_matches) != 1:
            raise RuntimeError(f"{voice_folder}: 耳元ステレオWAV {len(stereo_matches)} / 1")

        mono_destination = MONO_STAGE / voice_folder
        stereo_destination = STEREO_STAGE / voice_folder
        mono_destination.mkdir(parents=True, exist_ok=True)
        stereo_destination.mkdir(parents=True, exist_ok=True)
        for source in sorted(mono_matches):
            shutil.copy2(source, mono_destination / source.name)
        for source in sorted(stereo_matches):
            shutil.copy2(source, stereo_destination / source.name)

        # Copy validation files from the artifact directory that contains this voice.
        for artifact_dir in artifact_dirs:
            if not any(voice_folder in candidate.parts for candidate in artifact_dir.rglob("*.wav")):
                continue
            for validation_file in artifact_dir.rglob("検証/*"):
                if validation_file.is_file():
                    target = VALIDATION_STAGE / voice_folder / validation_file.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(validation_file, target)


def main() -> None:
    if not DOWNLOADED.exists():
        raise RuntimeError("ダウンロード済み音声artifactがありません")
    copy_voice_data()

    mono_files = sorted(MONO_STAGE.rglob("*.wav"))
    stereo_files = sorted(STEREO_STAGE.rglob("*.wav"))
    if len(mono_files) != 80:
        raise RuntimeError(f"最終モノラルWAV数 {len(mono_files)} / 80")
    if len(stereo_files) != 8:
        raise RuntimeError(f"最終ステレオWAV数 {len(stereo_files)} / 8")

    validation_rows: list[dict[str, Any]] = []
    for file in mono_files:
        row = validate_wav(file, 1)
        row["package"] = "透明モノラル"
        validation_rows.append(row)
    for file in stereo_files:
        row = validate_wav(file, 2)
        row["package"] = "ASMR耳元ステレオ"
        validation_rows.append(row)
    write_csv(VALIDATION_STAGE / "全88WAV_形式・全編デコード検証.csv", validation_rows)

    mono_zip = OUTPUT / "Irodori_中高音8声_明瞭再生成_完成版_モノラル80WAV.zip"
    stereo_zip = OUTPUT / "Irodori_中高音8声_ASMR耳元ステレオ_8WAV.zip"
    combined_zip = OUTPUT / "Irodori_中高音8声_明瞭再生成_完成版_全88WAV.zip"
    validation_zip = OUTPUT / "Irodori_中高音8声_明瞭再生成_検証資料.zip"

    make_zip(MONO_STAGE, mono_zip)
    make_zip(STEREO_STAGE, stereo_zip)
    make_zip(WORK, combined_zip)
    make_zip(VALIDATION_STAGE, validation_zip)

    with zipfile.ZipFile(mono_zip) as archive:
        if len([name for name in archive.namelist() if name.lower().endswith(".wav")]) != 80:
            raise RuntimeError("モノラルZIPのWAV数が80ではありません")
        if any(not name.lower().endswith(".wav") for name in archive.namelist() if not name.endswith("/")):
            raise RuntimeError("モノラルZIPにWAV以外が入っています")
    with zipfile.ZipFile(stereo_zip) as archive:
        if len([name for name in archive.namelist() if name.lower().endswith(".wav")]) != 8:
            raise RuntimeError("ステレオZIPのWAV数が8ではありません")
        if any(not name.lower().endswith(".wav") for name in archive.namelist() if not name.endswith("/")):
            raise RuntimeError("ステレオZIPにWAV以外が入っています")

    summary = {
        "mono_wav_count": 80,
        "stereo_wav_count": 8,
        "sample_rate": 48_000,
        "mono_channels": 1,
        "stereo_channels": 2,
        "subtype": "PCM_24",
        "zip_crc": "PASS",
        "ffmpeg_full_decode": "88/88 PASS",
        "packages": {
            mono_zip.name: sha256(mono_zip),
            stereo_zip.name: sha256(stereo_zip),
            combined_zip.name: sha256(combined_zip),
            validation_zip.name: sha256(validation_zip),
        },
    }
    (OUTPUT / "最終集計.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT / "SHA256SUMS.txt").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in summary["packages"].items()) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
