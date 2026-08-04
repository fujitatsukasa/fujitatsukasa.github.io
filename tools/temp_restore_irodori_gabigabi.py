#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from deepfilternet_rs import DeepFilterNetRealtime
from huggingface_hub import HfApi, hf_hub_download
from scipy.signal import butter, resample_poly, sosfiltfilt

ROOT = Path.cwd()
WORK = ROOT / "irodori_restore_work"
OUT = ROOT / "irodori_restore_output"
WAV_ROOT = OUT / "WAV"
for directory in (WORK, OUT, WAV_ROOT):
    directory.mkdir(parents=True, exist_ok=True)

CLONE_REPO = "SynDataLab-JA/irodori-clones-3m"
REVISION = "ce53b9287f04a2506c08f77b3b8b5287caed6bb4"
TARGET_SR = 48000
VOICES = json.loads('[{"voice_no":1,"voice_label":"かなり低い・暗め・息混じり","speaker_id":"speaker_03318","source_rows":[112,25,81,88,128,47,46,101,132,24]},{"voice_no":2,"voice_label":"かなり低い・硬め・明瞭","speaker_id":"speaker_00374","source_rows":[29,20,81,91,120,68,46,111,176,76]},{"voice_no":3,"voice_label":"低い・太め・落ち着き","speaker_id":"speaker_08346","source_rows":[112,21,74,88,119,51,44,111,176,24]},{"voice_no":4,"voice_label":"低い・フォーマル・はっきり","speaker_id":"speaker_08935","source_rows":[29,25,81,88,120,68,41,101,176,76]},{"voice_no":5,"voice_label":"中低音・自然・笑い混じり","speaker_id":"speaker_00063","source_rows":[112,21,73,88,120,68,46,103,155,281]},{"voice_no":6,"voice_label":"中低音・やわらかい・暗め","speaker_id":"speaker_08524","source_rows":[30,25,81,97,120,68,46,101,155,76]},{"voice_no":7,"voice_label":"中低音・静か・深い","speaker_id":"speaker_04916","source_rows":[112,20,81,91,120,68,44,101,132,281]},{"voice_no":8,"voice_label":"中低音・ドライ・明瞭","speaker_id":"speaker_03049","source_rows":[29,21,73,91,128,51,41,103,132,24]},{"voice_no":9,"voice_label":"中音・穏やか・物語調","speaker_id":"speaker_08458","source_rows":[112,21,73,88,120,51,41,111,132,281]},{"voice_no":10,"voice_label":"中音・冷静・少し硬め","speaker_id":"speaker_03183","source_rows":[30,20,74,91,119,68,46,101,132,281]},{"voice_no":11,"voice_label":"中音・芯強め・クール","speaker_id":"speaker_09784","source_rows":[112,20,73,88,120,68,46,101,155,281]},{"voice_no":12,"voice_label":"中高音・囁き・近距離","speaker_id":"speaker_04428","source_rows":[30,25,81,91,120,47,46,111,132,24]},{"voice_no":13,"voice_label":"中高音・やさしい・透明","speaker_id":"speaker_02022","source_rows":[30,20,74,97,120,47,46,103,155,76]},{"voice_no":14,"voice_label":"中高音・丁寧・明瞭","speaker_id":"speaker_01635","source_rows":[29,20,74,91,119,68,46,103,176,281]},{"voice_no":15,"voice_label":"中高音・やわらかい・丸い","speaker_id":"speaker_01639","source_rows":[30,21,81,91,119,51,41,101,155,76]},{"voice_no":16,"voice_label":"中高音・軽快・話しやすい","speaker_id":"speaker_01281","source_rows":[112,20,73,97,120,47,41,101,132,24]},{"voice_no":17,"voice_label":"高い・小さめ・落ち着き","speaker_id":"speaker_00526","source_rows":[29,20,81,91,128,68,44,111,176,281]},{"voice_no":18,"voice_label":"高い・親密・息少なめ","speaker_id":"speaker_09925","source_rows":[29,25,74,97,128,68,44,103,176,24]},{"voice_no":19,"voice_label":"高い・軽い・自然会話","speaker_id":"speaker_03333","source_rows":[30,20,81,91,120,68,44,111,176,281]},{"voice_no":20,"voice_label":"高い・明るい・息多め","speaker_id":"speaker_00703","source_rows":[29,25,81,88,119,47,44,111,176,76]},{"voice_no":21,"voice_label":"かなり高い・元気・軽快","speaker_id":"speaker_02196","source_rows":[30,21,81,91,119,47,44,101,155,24]},{"voice_no":22,"voice_label":"かなり高い・繊細・透明","speaker_id":"speaker_02829","source_rows":[30,20,73,97,120,47,41,111,132,76]},{"voice_no":23,"voice_label":"かなり高い・はきはき・細め","speaker_id":"speaker_00162","source_rows":[112,21,73,91,128,51,41,101,176,24]},{"voice_no":24,"voice_label":"非常に高い・鋭い・感情的","speaker_id":"speaker_09137","source_rows":[29,20,74,88,128,51,41,101,132,76]}]')
UTTERANCE_LABELS = json.loads('["丁寧で落ち着いた話し方","自然な日常会話","明るくうれしい話し方","少し怒った話し方","悲しく弱った話し方","怖がって慌てた話し方","眠く力の抜けた話し方","やさしく心配する話し方","ゆったりした独り言","笑い混じりの話し方"]')

def safe_component(value: str, limit: int = 120) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or "名称なし")[:limit]

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def decode_audio_cell(value: Any) -> tuple[np.ndarray, int]:
    if hasattr(value, "as_py"):
        value = value.as_py()
    payload = None
    if isinstance(value, dict):
        raw = value.get("bytes")
        if raw is not None:
            payload = bytes(raw)
    elif isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
    if payload is None:
        raise RuntimeError("Parquet audio cell has no embedded bytes")
    audio, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    return np.mean(audio, axis=1).astype(np.float32), int(sample_rate)

def normalize_48k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    signal = np.asarray(audio, dtype=np.float32)
    if sample_rate != TARGET_SR:
        divisor = math.gcd(sample_rate, TARGET_SR)
        signal = resample_poly(signal, TARGET_SR // divisor, sample_rate // divisor).astype(np.float32)
    signal = np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(signal, -1.0, 1.0).astype(np.float32)

def analyze_roughness(signal: np.ndarray) -> dict[str, float]:
    if signal.size == 0:
        return {"flatness": 1.0, "hf_ratio": 1.0, "click_ratio": 1.0, "roughness": 999.0}
    click_ratio = float(np.mean(np.abs(np.diff(signal)) > 0.32)) if signal.size > 1 else 1.0
    analysis = resample_poly(signal, 1, 3).astype(np.float32)
    frame_length = 1024
    hop = 256
    if analysis.size < frame_length:
        analysis = np.pad(analysis, (0, frame_length - analysis.size))
    frames = np.lib.stride_tricks.sliding_window_view(analysis, frame_length)[::hop]
    window = np.hanning(frame_length).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1)) + 1e-9
    power = spectrum * spectrum
    frequencies = np.fft.rfftfreq(frame_length, 1 / 16000)
    flatness = float(np.mean(np.exp(np.mean(np.log(power), axis=1)) / np.maximum(np.mean(power, axis=1), 1e-12)))
    hf_ratio = float(np.mean(power[:, frequencies >= 5000].sum(axis=1) / np.maximum(power.sum(axis=1), 1e-12)))
    roughness = 3.0 * flatness + 2.0 * hf_ratio + 20.0 * click_ratio
    return {"flatness": flatness, "hf_ratio": hf_ratio, "click_ratio": click_ratio, "roughness": roughness}

def active_rms(signal: np.ndarray) -> float:
    if signal.size == 0:
        return 0.0
    peak = float(np.max(np.abs(signal)))
    active = np.abs(signal) >= max(0.0015, peak * 0.01)
    selected = signal[active] if np.any(active) else signal
    return float(np.sqrt(np.mean(selected * selected) + 1e-12))

def align_length(processed: np.ndarray, original: np.ndarray) -> np.ndarray:
    if processed.size > original.size:
        return processed[: original.size]
    if processed.size < original.size:
        if processed.size == 0:
            return original.copy()
        return np.pad(processed, (0, original.size - processed.size), mode="edge")
    return processed

def de_click(signal: np.ndarray, threshold: float = 0.36) -> tuple[np.ndarray, int]:
    if signal.size < 5:
        return signal, 0
    output = signal.copy()
    jumps = np.flatnonzero(np.abs(np.diff(output)) > threshold) + 1
    count = 0
    for index in jumps:
        if 2 <= index < output.size - 2:
            local = np.concatenate([output[index - 2:index], output[index + 1:index + 3]])
            output[index] = float(np.median(local))
            count += 1
    return output, count

def enhance_adaptive(original: np.ndarray, before: dict[str, float]) -> tuple[np.ndarray, dict[str, Any]]:
    score = float(before["roughness"])
    if score < 0.105:
        return original.copy(), {"mode": "無補正", "mix": 0.0, "cutoff": 0, "declicked": 0}
    if score < 0.145:
        mix, cutoff, high_blend = 0.20, 18500, 0.06
    elif score < 0.190:
        mix, cutoff, high_blend = 0.32, 17500, 0.10
    elif score < 0.235:
        mix, cutoff, high_blend = 0.44, 16500, 0.16
    else:
        mix, cutoff, high_blend = 0.56, 15500, 0.23
    processor = DeepFilterNetRealtime(model_path=None, atten_lim=18.0, log_level="error", compensate_delay=True, post_filter_beta=0.0)
    try:
        enhanced = np.asarray(processor.process_chunk(original.astype(np.float32)), dtype=np.float32)
        tail = np.asarray(processor.finalize(), dtype=np.float32)
        if tail.size:
            enhanced = np.concatenate([enhanced, tail])
    finally:
        try:
            processor.close()
        except Exception:
            pass
    enhanced = align_length(enhanced, original)
    original_rms = active_rms(original)
    enhanced_rms = active_rms(enhanced)
    if original_rms > 1e-8 and enhanced_rms > 1e-8:
        enhanced *= float(np.clip(original_rms / enhanced_rms, 0.70, 1.35))
    output = (1.0 - mix) * original + mix * enhanced
    lowpass = butter(4, cutoff / (TARGET_SR / 2), btype="lowpass", output="sos")
    try:
        low = sosfiltfilt(lowpass, output).astype(np.float32)
        output = (1.0 - high_blend) * output + high_blend * low
    except ValueError:
        pass
    output, replaced = de_click(output)
    peak = float(np.max(np.abs(output))) if output.size else 0.0
    if peak > 0.97:
        output *= 0.97 / peak
    return np.clip(output, -0.98, 0.98).astype(np.float32), {"mode": "軽減補正", "mix": mix, "cutoff": cutoff, "declicked": replaced}

def write_zip(source: Path, destination: Path, folders: set[str] | None = None) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(source.rglob("*.wav")):
            relative = path.relative_to(source).as_posix()
            top = relative.split("/", 1)[0]
            if folders is None or top in folders:
                archive.write(path, relative)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"ZIP CRC failed: {destination}")
        expected = 240 if folders is None else len(folders) * 10
        actual = len([name for name in archive.namelist() if name.lower().endswith(".wav")])
        if actual != expected:
            raise RuntimeError(f"ZIP count mismatch: {destination}: {actual} != {expected}")

def main() -> None:
    dataset = HfApi().dataset_info(CLONE_REPO, revision=REVISION, files_metadata=True)
    if str(dataset.sha) != REVISION:
        raise RuntimeError(f"dataset revision mismatch: {dataset.sha}")
    validation_rows: list[dict[str, Any]] = []
    for current, voice in enumerate(VOICES, 1):
        speaker_id = str(voice["speaker_id"])
        number = int(speaker_id.split("_")[-1])
        parquet_name = f"data/train-{number - 1:05d}-of-10000.parquet"
        parquet_path = Path(hf_hub_download(repo_id=CLONE_REPO, repo_type="dataset", filename=parquet_name, revision=REVISION, local_dir=WORK / "clone_repo"))
        rows = pq.read_table(parquet_path).to_pylist()
        voice_folder = f"{int(voice['voice_no']):02d}_{safe_component(voice['voice_label'])}"
        for utterance_number, (utterance_label, source_row) in enumerate(zip(UTTERANCE_LABELS, voice["source_rows"]), 1):
            source = rows[int(source_row) - 1]
            source_speaker = str(source.get("speaker_id") or "")
            if source_speaker and source_speaker != speaker_id:
                raise RuntimeError(f"speaker mismatch: {source_speaker} != {speaker_id}")
            original, sample_rate = decode_audio_cell(source.get("audio"))
            original = normalize_48k(original, sample_rate)
            before = analyze_roughness(original)
            corrected, treatment = enhance_adaptive(original, before)
            after = analyze_roughness(corrected)
            file_name = f"{utterance_number:02d}_{safe_component(utterance_label)}.wav"
            output_path = WAV_ROOT / voice_folder / file_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, corrected, TARGET_SR, subtype="PCM_16")
            verify, verify_rate = sf.read(output_path, dtype="float32", always_2d=True)
            if verify_rate != TARGET_SR or verify.shape[1] != 1 or verify.shape[0] == 0:
                raise RuntimeError(f"WAV verification failed: {output_path}")
            validation_rows.append({"声番号": int(voice["voice_no"]), "声名": voice["voice_label"], "発話番号": utterance_number, "発話名": utterance_label, "内部話者ID": speaker_id, "元発話番号": int(source_row), "処理": treatment["mode"], "DeepFilterNet混合率": treatment["mix"], "高域平滑化カットオフ": treatment["cutoff"], "クリック補間数": treatment["declicked"], "補正前ざらつき指数": before["roughness"], "補正後ざらつき指数": after["roughness"], "補正前スペクトル平坦度": before["flatness"], "補正後スペクトル平坦度": after["flatness"], "補正前高域比率": before["hf_ratio"], "補正後高域比率": after["hf_ratio"], "WAV": f"{voice_folder}/{file_name}", "SHA256": sha256_file(output_path)})
        print(f"voice {current}/24 complete: {voice_folder}", flush=True)
    if len(validation_rows) != 240:
        raise RuntimeError(f"expected 240 WAVs, got {len(validation_rows)}")
    with (OUT / "補正検証台帳.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(validation_rows[0].keys()))
        writer.writeheader()
        writer.writerows(validation_rows)
    folder_names = sorted(path.name for path in WAV_ROOT.iterdir() if path.is_dir())
    outputs = [("Irodori_声バリエーション24種_各10本_ガビガビ軽減補正版_WAVのみ.zip", None), ("Irodori_低めの声8種_各10本_ガビガビ軽減補正版_WAVのみ.zip", set(folder_names[:8])), ("Irodori_中くらいの声8種_各10本_ガビガビ軽減補正版_WAVのみ.zip", set(folder_names[8:16])), ("Irodori_高めの声8種_各10本_ガビガビ軽減補正版_WAVのみ.zip", set(folder_names[16:24]))]
    for name, selection in outputs:
        write_zip(WAV_ROOT, OUT / name, selection)
    summary = {"声の種類": 24, "各声のWAV数": 10, "合計WAV数": 240, "補正実施": sum(1 for row in validation_rows if row["処理"] == "軽減補正"), "無補正コピー": sum(1 for row in validation_rows if row["処理"] == "無補正"), "サンプルレート": TARGET_SR, "チャンネル": 1, "形式": "PCM_16", "平均ざらつき指数_補正前": float(np.mean([float(row["補正前ざらつき指数"]) for row in validation_rows])), "平均ざらつき指数_補正後": float(np.mean([float(row["補正後ざらつき指数"]) for row in validation_rows])), "ZIP_CRC": "4/4 PASS", "WAV全読込": "240/240 PASS", "注意": "人間の全件試聴合格ではなく、DeepFilterNetと音響指標による保守的な軽減補正。"}
    (OUT / "補正集計.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    checksum_lines = []
    for name, _ in outputs:
        path = OUT / name
        checksum_lines.append(f"{sha256_file(path)}  {name}")
    (OUT / "SHA256.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
