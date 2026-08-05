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

from irodori_fix16_spec import VOICES

ROOT = Path.cwd()
DOWNLOADED = ROOT / "downloaded_fix16"
WORK = ROOT / "fix16_package_work"
OUTPUT = ROOT / "fix16_package_output"
ALL_STAGE = WORK / "全16声"
MID_STAGE = WORK / "中くらい8声"
HIGH_STAGE = WORK / "高め8声"
VALIDATION_STAGE = WORK / "検証資料"
for directory in (ALL_STAGE, MID_STAGE, HIGH_STAGE, VALIDATION_STAGE, OUTPUT):
    directory.mkdir(parents=True, exist_ok=True)


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


def validate_wav(path: Path) -> dict[str, Any]:
    info = sf.info(path)
    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    if int(info.samplerate) != 48_000:
        raise RuntimeError(f"48kHzではありません: {path} -> {info.samplerate}")
    if int(info.channels) != 1:
        raise RuntimeError(f"モノラルではありません: {path} -> {info.channels}")
    if info.subtype != "PCM_24":
        raise RuntimeError(f"PCM 24-bitではありません: {path} -> {info.subtype}")
    duration = float(data.shape[0] / sample_rate)
    if duration < 0.5:
        raise RuntimeError(f"短すぎます: {path} -> {duration}")
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


def make_audio_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for wav in sorted(source.rglob("*.wav")):
            archive.write(wav, wav.relative_to(source).as_posix())
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC失敗: {destination} -> {bad}")
        files = [name for name in archive.namelist() if not name.endswith("/")]
        if any(not name.lower().endswith(".wav") for name in files):
            raise RuntimeError(f"音声ZIPにWAV以外が入っています: {destination}")


def make_general_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for file in sorted(source.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(source).as_posix())
    with zipfile.ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ZIP CRC失敗: {destination} -> {bad}")


def find_voice_root(voice_folder: str) -> Path:
    matches = [path for path in DOWNLOADED.rglob(voice_folder) if path.is_dir() and path.parent.name == "WAV"]
    if len(matches) != 1:
        raise RuntimeError(f"{voice_folder}: WAVフォルダが一意ではありません: {len(matches)}")
    return matches[0]


def copy_validation_for_voice(voice_folder: str, voice_root: Path) -> None:
    artifact_root = voice_root.parent.parent
    validation = artifact_root / "検証"
    if not validation.exists():
        raise RuntimeError(f"{voice_folder}: 検証フォルダがありません")
    destination = VALIDATION_STAGE / voice_folder
    destination.mkdir(parents=True, exist_ok=True)
    for file in validation.rglob("*"):
        if file.is_file():
            relative = file.relative_to(validation)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)


def main() -> None:
    if not DOWNLOADED.exists():
        raise RuntimeError("音声artifactがダウンロードされていません")

    validation_rows: list[dict[str, Any]] = []
    for voice in VOICES:
        folder = str(voice["folder"])
        source = find_voice_root(folder)
        wavs = sorted(source.glob("*.wav"))
        if len(wavs) != 10:
            raise RuntimeError(f"{folder}: WAV数 {len(wavs)} / 10")
        all_destination = ALL_STAGE / folder
        group_destination = (MID_STAGE if int(voice["number"]) <= 16 else HIGH_STAGE) / folder
        all_destination.mkdir(parents=True, exist_ok=True)
        group_destination.mkdir(parents=True, exist_ok=True)
        for wav in wavs:
            shutil.copy2(wav, all_destination / wav.name)
            shutil.copy2(wav, group_destination / wav.name)
            row = validate_wav(wav)
            row["voice"] = folder
            validation_rows.append(row)
        copy_validation_for_voice(folder, source)

    if len(list(ALL_STAGE.rglob("*.wav"))) != 160:
        raise RuntimeError("全16声のWAV数が160ではありません")
    if len(list(MID_STAGE.rglob("*.wav"))) != 80:
        raise RuntimeError("中くらい8声のWAV数が80ではありません")
    if len(list(HIGH_STAGE.rglob("*.wav"))) != 80:
        raise RuntimeError("高め8声のWAV数が80ではありません")

    write_csv(VALIDATION_STAGE / "全160WAV_形式・全編デコード検証.csv", validation_rows)

    all_zip = OUTPUT / "Irodori_同じ16声_セリフ・演技一致修正版_全160WAV.zip"
    mid_zip = OUTPUT / "Irodori_同じ中くらい8声_セリフ・演技一致修正版_80WAV.zip"
    high_zip = OUTPUT / "Irodori_同じ高め8声_セリフ・演技一致修正版_80WAV.zip"
    validation_zip = OUTPUT / "Irodori_同じ16声_生成・ASR・演技選抜検証資料.zip"
    make_audio_zip(ALL_STAGE, all_zip)
    make_audio_zip(MID_STAGE, mid_zip)
    make_audio_zip(HIGH_STAGE, high_zip)
    make_general_zip(VALIDATION_STAGE, validation_zip)

    expected = {all_zip: 160, mid_zip: 80, high_zip: 80}
    for package, count in expected.items():
        with zipfile.ZipFile(package) as archive:
            wav_count = len([name for name in archive.namelist() if name.lower().endswith(".wav")])
            if wav_count != count:
                raise RuntimeError(f"{package.name}: WAV数 {wav_count} / {count}")

    summary = {
        "voices": 16,
        "styles_per_voice": 10,
        "wav_count": 160,
        "sample_rate": 48_000,
        "channels": 1,
        "subtype": "PCM_24",
        "zip_crc": "PASS",
        "ffmpeg_full_decode": "160/160 PASS",
        "packages": {
            all_zip.name: sha256(all_zip),
            mid_zip.name: sha256(mid_zip),
            high_zip.name: sha256(high_zip),
            validation_zip.name: sha256(validation_zip),
        },
    }
    (OUTPUT / "最終集計.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "SHA256SUMS.txt").write_text(
        "\n".join(f"{digest}  {name}" for name, digest in summary["packages"].items()) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
