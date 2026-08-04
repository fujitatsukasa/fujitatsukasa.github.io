#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import struct
import zlib
from pathlib import Path
from typing import Iterable

import soundfile as sf

ROOT = Path.cwd()
SOURCE = ROOT / "downloaded_final_voices"
OUT = ROOT / "final_package_output"
PACKS = OUT / "packs"
VALIDATION = OUT / "validation"
for directory in (OUT, PACKS, VALIDATION):
    directory.mkdir(parents=True, exist_ok=True)

ALL_MONO = PACKS / "Irodori_v4_中高音8声_各10話法_台詞感情一致_透明スタジオ原音"
MID_MONO = PACKS / "Irodori_v4_中高音4声_各10話法_台詞感情一致_透明スタジオ原音"
HIGH_MONO = PACKS / "Irodori_v4_高音4声_各10話法_台詞感情一致_透明スタジオ原音"
ALL_BINAURAL = PACKS / "Irodori_v4_中高音8声_各10話法_KEMARバイノーラル版"
for directory in (ALL_MONO, MID_MONO, HIGH_MONO, ALL_BINAURAL):
    directory.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree_contents(source_root: Path, target_root: Path) -> int:
    count = 0
    for path in sorted(source_root.rglob("*.wav")):
        relative = path.relative_to(source_root)
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        count += 1
    return count


def find_voice_roots() -> list[Path]:
    roots: list[Path] = []
    for mono_dir in SOURCE.rglob("モノラル"):
        if mono_dir.is_dir() and len(list(mono_dir.rglob("*.wav"))) == 10:
            roots.append(mono_dir.parent)
    unique = sorted({root.resolve() for root in roots})
    if len(unique) != 8:
        raise RuntimeError(f"expected 8 voice artifacts, found {len(unique)}")
    return [Path(path) for path in unique]


def validate_directory(directory: Path, expected_files: int, channels: int) -> dict:
    wavs = sorted(directory.rglob("*.wav"))
    if len(wavs) != expected_files:
        raise RuntimeError(f"{directory.name}: WAV count {len(wavs)} != {expected_files}")
    total_duration = 0.0
    sha_values: set[str] = set()
    rows = []
    for path in wavs:
        data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        if int(sample_rate) != 48000 or data.shape[1] != channels or data.size == 0:
            raise RuntimeError(f"invalid WAV {path}: rate={sample_rate}, channels={data.shape[1]}")
        duration = data.shape[0] / sample_rate
        total_duration += duration
        digest = sha256_file(path)
        sha_values.add(digest)
        rows.append({
            "pack": directory.name,
            "file": path.relative_to(directory).as_posix(),
            "sample_rate": sample_rate,
            "channels": data.shape[1],
            "frames": data.shape[0],
            "duration_sec": duration,
            "sha256": digest,
        })
    if len(sha_values) != expected_files:
        raise RuntimeError(f"exact duplicate WAVs detected in {directory.name}")
    return {
        "directory": directory.name,
        "wav_count": expected_files,
        "sample_rate": 48000,
        "channels": channels,
        "total_duration_sec": round(total_duration, 3),
        "rows": rows,
    }


def dos_datetime(timestamp: float) -> tuple[int, int]:
    value = dt.datetime.fromtimestamp(timestamp)
    year = min(max(value.year, 1980), 2107)
    dos_date = ((year - 1980) << 9) | (value.month << 5) | value.day
    dos_time = (value.hour << 11) | (value.minute << 5) | (value.second // 2)
    return dos_time, dos_date


def unicode_path_extra(legacy_name: bytes, unicode_name: str) -> bytes:
    payload = b"\x01" + struct.pack("<I", zlib.crc32(legacy_name) & 0xFFFFFFFF) + unicode_name.encode("utf-8")
    return struct.pack("<HH", 0x7075, len(payload)) + payload


def make_windows_japanese_zip(source_dir: Path, destination: Path) -> None:
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    central_records: list[bytes] = []
    with destination.open("wb") as archive:
        for path in files:
            relative = path.relative_to(source_dir).as_posix()
            try:
                legacy_name = relative.encode("cp932")
            except UnicodeEncodeError:
                legacy_name = relative.encode("utf-8")
            extra = unicode_path_extra(legacy_name, relative)
            raw = path.read_bytes()
            crc = zlib.crc32(raw) & 0xFFFFFFFF
            compressor = zlib.compressobj(level=6, wbits=-15)
            compressed = compressor.compress(raw) + compressor.flush()
            dos_time, dos_date = dos_datetime(path.stat().st_mtime)
            offset = archive.tell()
            local_header = struct.pack(
                "<IHHHHHIIIHH",
                0x04034B50,
                20,
                0,
                8,
                dos_time,
                dos_date,
                crc,
                len(compressed),
                len(raw),
                len(legacy_name),
                len(extra),
            )
            archive.write(local_header)
            archive.write(legacy_name)
            archive.write(extra)
            archive.write(compressed)
            central_header = struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014B50,
                20,
                20,
                0,
                8,
                dos_time,
                dos_date,
                crc,
                len(compressed),
                len(raw),
                len(legacy_name),
                len(extra),
                0,
                0,
                0,
                0,
                offset,
            )
            central_records.append(central_header + legacy_name + extra)
        central_start = archive.tell()
        for record in central_records:
            archive.write(record)
        central_size = archive.tell() - central_start
        archive.write(
            struct.pack(
                "<IHHHHIIH",
                0x06054B50,
                0,
                0,
                len(central_records),
                len(central_records),
                central_size,
                central_start,
                0,
            )
        )


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    voice_roots = find_voice_roots()
    all_validation_rows: list[dict] = []
    voice_names: list[str] = []
    for root in voice_roots:
        mono_root = root / "モノラル"
        binaural_root = root / "バイノーラル"
        voice_folders = [path for path in mono_root.iterdir() if path.is_dir()]
        if len(voice_folders) != 1:
            raise RuntimeError(f"voice folder count mismatch under {root}")
        voice_folder = voice_folders[0]
        voice_name = voice_folder.name
        voice_names.append(voice_name)
        copy_tree_contents(mono_root, ALL_MONO)
        copy_tree_contents(binaural_root, ALL_BINAURAL)
        voice_number = int(voice_name.split("_", 1)[0])
        copy_tree_contents(mono_root, MID_MONO if voice_number <= 4 else HIGH_MONO)
        for csv_path in (root / "検証").glob("*.csv"):
            with csv_path.open(encoding="utf-8-sig", newline="") as file:
                for row in csv.DictReader(file):
                    all_validation_rows.append({"source_file": csv_path.name, **row})
        for path in (root / "検証").glob("*.json"):
            destination = VALIDATION / f"{voice_name}_{path.name}"
            shutil.copy2(path, destination)

    voice_names.sort()
    if len(voice_names) != 8 or len(set(voice_names)) != 8:
        raise RuntimeError(f"voice names invalid: {voice_names}")

    reports = [
        validate_directory(ALL_MONO, 80, 1),
        validate_directory(MID_MONO, 40, 1),
        validate_directory(HIGH_MONO, 40, 1),
        validate_directory(ALL_BINAURAL, 80, 2),
    ]
    write_csv(VALIDATION / "全候補・最終選抜統合台帳.csv", all_validation_rows)
    write_csv(VALIDATION / "最終WAV全160本検証台帳.csv", [row for report in reports for row in report.pop("rows")])
    summary = {
        "model": "Aratako/Irodori-TTS-v4-Small local official runtime",
        "voice_count": 8,
        "styles_per_voice": 10,
        "mono_wavs": 80,
        "binaural_wavs": 80,
        "voice_folders": voice_names,
        "human_listening": False,
        "generation": "3 candidates per voice/style; Japanese ASR + style-specific acoustic heuristics + objective quality selection",
        "binaural": "KEMAR HRTF, diffuse-field equalization when available, plus physical ITD; generic dummy-head HRTF, not individualized",
        "reports": reports,
    }
    (VALIDATION / "最終集計.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (VALIDATION / "最初に読んでください.txt").write_text(
        "以前の版は、既存の任意発話へ『眠い』『怒り』『笑い』などの名前を後付けしており、台詞・演技・ファイル名が一致していませんでした。\n"
        "本版は最新Irodori v4-Smallの公式ローカル実装で、各ファイル専用の台詞、感情キャプション、絵文字制御から新規生成しています。\n"
        "各話法につき3候補を作り、日本語ASR、音響品質、話法別の音響条件で1本を選びました。\n"
        "ただし全音声を人間が通し試聴して最終合格判定したものではありません。\n"
        "バイノーラル版はKEMARダミーヘッドHRTFを用いたヘッドホン向け処理で、利用者個人のHRTFではありません。\n",
        encoding="utf-8",
    )

    zip_targets = [
        (ALL_MONO, OUT / "Irodori_v4_中高音8声_各10話法_台詞感情一致_透明スタジオ原音_WAVのみ_日本語互換.zip"),
        (MID_MONO, OUT / "Irodori_v4_中高音4声_各10話法_台詞感情一致_透明スタジオ原音_WAVのみ_日本語互換.zip"),
        (HIGH_MONO, OUT / "Irodori_v4_高音4声_各10話法_台詞感情一致_透明スタジオ原音_WAVのみ_日本語互換.zip"),
        (ALL_BINAURAL, OUT / "Irodori_v4_中高音8声_各10話法_KEMARバイノーラル版_WAVのみ_日本語互換.zip"),
        (VALIDATION, OUT / "Irodori_v4_中高音8声_生成・選抜・音質検証資料.zip"),
    ]
    sha_lines = []
    for source, destination in zip_targets:
        make_windows_japanese_zip(source, destination)
        sha_lines.append(f"{sha256_file(destination)}  {destination.name}")
    (OUT / "SHA256SUMS.txt").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
