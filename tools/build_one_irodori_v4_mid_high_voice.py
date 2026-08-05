#!/usr/bin/env python3
from __future__ import annotations

import gc
import io
import json
import math
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from faster_whisper import WhisperModel
from huggingface_hub import hf_hub_download
from rapidfuzz import fuzz
from scipy.signal import resample_poly

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import build_irodori_v4_mid_high_emotion_asmr as spec  # noqa: E402

IRODORI_REPO = Path.cwd().resolve()
if not (IRODORI_REPO / "irodori_tts").is_dir():
    IRODORI_REPO = Path("Irodori-TTS").resolve()
sys.path.insert(0, str(IRODORI_REPO))

from irodori_tts.inference_runtime import (  # noqa: E402
    RuntimeKey,
    SamplingRequest,
    clear_cached_runtime,
    download_hf_checkpoint,
    get_cached_runtime,
    save_wav,
)

VOICE_INDEX = int(os.environ.get("VOICE_INDEX", "0"))
VOICE = spec.VOICES[VOICE_INDEX]
ROOT = Path.cwd()
WORK = ROOT / "final_voice_work" / f"voice_{VOICE_INDEX:02d}"
OUT = ROOT / "final_voice_output" / f"voice_{VOICE_INDEX:02d}"
MONO_DIR = OUT / "モノラル" / str(VOICE["folder"])
BINAURAL_DIR = OUT / "バイノーラル" / str(VOICE["folder"])
VALIDATION_DIR = OUT / "検証"
CANDIDATE_DIR = WORK / "候補"
REFERENCE_DIR = WORK / "参照"
for directory in (WORK, OUT, MONO_DIR, BINAURAL_DIR, VALIDATION_DIR, CANDIDATE_DIR, REFERENCE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

CLONE_REPO = "SynDataLab-JA/irodori-clones-3m"
CLONE_REVISION = "ce53b9287f04a2506c08f77b3b8b5287caed6bb4"
TARGET_SR = 48000
CHECKPOINT = "Aratako/Irodori-TTS-v4-Small"
NUM_STEPS = 20

ANCHOR_TEXT = (
    "おはよう。今日は空気が澄んでいて、とても気持ちのいい朝ですね。"
    "少しゆっくり話しながら、これからの予定を確認していきましょう。"
    "分からないことがあれば、遠慮なく聞いてください。"
)
ANCHOR_CAPTION = (
    "普段の自然な声で、力まず、穏やかに話す。声量は普通より少し小さく、"
    "一定の距離で、叫ばず、泣かず、笑い声や強い感情を入れない。"
)
QUALITY_CAPTION = (
    "静かな防音スタジオで、広帯域の高性能コンデンサーマイクを使った近接収録。"
    "透明で抜けがよく、こもりがなく、子音が自然に明瞭。"
    "部屋鳴り、ヒス、電話音、金属的な歪み、過度なノイズ抑制感はない。"
    "声を潰す強いコンプレッションは使わず、乾いた自然な音質。"
)


def log(message: str) -> None:
    print(message, flush=True)
    with (VALIDATION_DIR / "実行ログ.txt").open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def safe_component(value: str, limit: int = 110) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or "名称なし")[:limit]


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).lower()
    value = spec.EMOJI_PATTERN.sub("", value)
    value = re.sub(r"[\s、。,.!！?？…・『』「」()（）\-ー]", "", value)
    return value


def decode_audio_cell(value: Any) -> tuple[np.ndarray, int]:
    if hasattr(value, "as_py"):
        value = value.as_py()
    payload: bytes | None = None
    if isinstance(value, dict) and value.get("bytes") is not None:
        payload = bytes(value["bytes"])
    elif isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
    if payload is None:
        raise RuntimeError("音声データがありません")
    signal, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    return np.mean(signal, axis=1).astype(np.float32), int(sample_rate)


def resample_mono(signal: np.ndarray, sample_rate: int, target_rate: int = TARGET_SR) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32)
    if signal.ndim > 1:
        signal = np.mean(signal, axis=1)
    if sample_rate != target_rate:
        divisor = math.gcd(int(sample_rate), int(target_rate))
        signal = resample_poly(signal, target_rate // divisor, sample_rate // divisor).astype(np.float32)
    return np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def extract_old_references(rows: list[dict[str, Any]]) -> list[str]:
    reference_paths: list[str] = []
    for order, source_row in enumerate((20, 29, 112), 1):
        signal, sample_rate = decode_audio_cell(rows[source_row - 1].get("audio"))
        signal = resample_mono(signal, sample_rate)
        signal = spec.transparent_studio_process(signal, -20.0, str(VOICE["folder"]))
        path = REFERENCE_DIR / f"旧参照_{order:02d}.wav"
        sf.write(path, signal, TARGET_SR, subtype="PCM_24")
        reference_paths.append(str(path.resolve()))
    return reference_paths


def generate_one(
    runtime: Any,
    *,
    text: str,
    caption: str,
    references: list[str],
    seed: int,
    duration_scale: float,
    caption_cfg: float,
    output_path: Path,
) -> dict[str, Any]:
    messages: list[str] = []
    result = runtime.synthesize(
        SamplingRequest(
            text=text,
            caption=caption,
            ref_wav=None,
            ref_wavs=references,
            ref_latent=None,
            ref_latents=None,
            ref_embed=None,
            no_ref=False,
            ref_normalize_db=-16.0,
            ref_ensure_max=True,
            num_candidates=1,
            decode_mode="sequential",
            seconds=None,
            duration_scale=float(duration_scale),
            max_ref_seconds=30.0,
            max_text_len=None,
            max_caption_len=None,
            num_steps=NUM_STEPS,
            seed=int(seed),
            cfg_guidance_mode="alternating",
            cfg_scale_text=3.15,
            cfg_scale_caption=float(caption_cfg),
            cfg_scale_speaker=5.20,
            cfg_scale=None,
            cfg_min_t=0.5,
            cfg_max_t=1.0,
            truncation_factor=None,
            rescale_k=None,
            rescale_sigma=None,
            context_kv_cache=True,
            speaker_kv_scale=1.05,
            speaker_kv_min_t=None,
            speaker_kv_max_layers=None,
            t_schedule_mode="sway",
            sway_coeff=-1.0,
            trim_tail=True,
            lora_adapter=None,
        ),
        log_fn=messages.append,
    )
    save_wav(output_path, result.audios[0].float(), result.sample_rate)
    return {
        "seed": int(result.used_seed),
        "sample_rate": int(result.sample_rate),
        "stage_timings": result.stage_timings,
        "total_to_decode": float(result.total_to_decode),
        "messages": [*messages, *result.messages],
    }


def simple_quality(metrics: dict[str, float], target_rms: float) -> float:
    return spec.quality_score(metrics, target_rms)


def style_delivery_score(style: dict[str, Any], metrics: dict[str, float], transcript: str) -> float:
    rms = float(metrics["rms_dbfs"])
    duration = float(metrics["duration_sec"])
    f0 = float(metrics["f0_median_hz"])
    f0_std = float(metrics["f0_std_hz"])
    flatness = float(metrics["spectral_flatness"])
    label = str(style["label"])
    score = 0.5
    if "自然" in label:
        score = 0.45 * max(0.0, 1.0 - abs(rms + 20.0) / 12.0) + 0.35 * max(0.0, 1.0 - f0_std / 150.0) + 0.20 * max(0.0, 1.0 - max(0.0, f0 - 380.0) / 180.0)
    elif "丁寧" in label:
        score = 0.35 * max(0.0, 1.0 - abs(rms + 20.5) / 12.0) + 0.35 * max(0.0, 1.0 - f0_std / 125.0) + 0.30 * min(1.0, duration / 8.0)
    elif "眠く" in label:
        score = 0.30 * min(1.0, duration / 11.0) + 0.30 * max(0.0, min(1.0, (-rms - 16.0) / 10.0)) + 0.25 * max(0.0, 1.0 - f0_std / 115.0) + 0.15 * max(0.0, 1.0 - max(0.0, f0 - 330.0) / 160.0)
    elif "悲しく" in label:
        score = 0.35 * min(1.0, duration / 10.0) + 0.35 * max(0.0, min(1.0, (-rms - 16.0) / 10.0)) + 0.20 * max(0.0, 1.0 - max(0.0, f0 - 350.0) / 160.0) + 0.10 * min(1.0, f0_std / 90.0)
    elif "怒り" in label:
        score = 0.38 * max(0.0, min(1.0, (rms + 26.0) / 11.0)) + 0.35 * min(1.0, f0_std / 130.0) + 0.17 * min(1.0, f0 / 320.0) + 0.10 * max(0.0, 1.0 - duration / 18.0)
    elif "怖く" in label:
        score = 0.30 * min(1.0, f0 / 350.0) + 0.32 * min(1.0, f0_std / 135.0) + 0.23 * max(0.0, 1.0 - duration / 15.0) + 0.15 * max(0.0, min(1.0, (rms + 27.0) / 12.0))
    elif "うれしい" in label:
        score = 0.30 * min(1.0, f0 / 340.0) + 0.32 * min(1.0, f0_std / 125.0) + 0.23 * max(0.0, min(1.0, (rms + 27.0) / 12.0)) + 0.15 * max(0.0, 1.0 - duration / 17.0)
    elif "心配" in label:
        score = 0.32 * min(1.0, duration / 9.0) + 0.32 * max(0.0, min(1.0, (-rms - 16.0) / 10.0)) + 0.26 * max(0.0, 1.0 - f0_std / 120.0) + 0.10 * max(0.0, 1.0 - max(0.0, f0 - 350.0) / 160.0)
    elif "ASMR" in label:
        score = 0.28 * min(1.0, duration / 12.0) + 0.30 * max(0.0, min(1.0, (-rms - 18.0) / 11.0)) + 0.22 * max(0.0, min(1.0, (flatness - 0.012) / 0.16)) + 0.20 * max(0.0, 1.0 - f0_std / 115.0)
    elif "笑い" in label:
        laugh_text = 1.0 if re.search(r"ふふ|フフ|笑", transcript) else 0.25
        score = 0.35 * laugh_text + 0.30 * min(1.0, f0_std / 125.0) + 0.20 * max(0.0, min(1.0, (rms + 27.0) / 12.0)) + 0.15 * min(1.0, f0 / 340.0)
    return float(np.clip(score, 0.0, 1.0))


def select_best(paths: list[Path], target_text: str, style: dict[str, Any], whisper: WhisperModel) -> tuple[Path, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    for candidate_number, path in enumerate(paths, 1):
        signal, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        mono = np.mean(signal, axis=1).astype(np.float32)
        metrics = spec.audio_metrics(mono, int(sample_rate))
        transcript, asr_score = spec.transcribe_score(mono, int(sample_rate), target_text, whisper)
        quality = simple_quality(metrics, float(style["target_rms"]))
        delivery = style_delivery_score(style, metrics, transcript)
        final = 0.50 * asr_score + 0.27 * delivery + 0.23 * quality
        if asr_score < 0.45:
            final -= 0.22
        if "自然" in str(style["label"]) and (metrics["rms_dbfs"] > -14.0 or metrics["f0_std_hz"] > 180.0):
            final -= 0.18
        records.append({
            "candidate": candidate_number,
            "path": str(path),
            "transcript": transcript,
            "asr_score": asr_score,
            "delivery_score": delivery,
            "quality_score": quality,
            "final_score": final,
            **metrics,
        })
    records.sort(key=lambda item: float(item["final_score"]), reverse=True)
    return Path(records[0]["path"]), records


def split_anchor(anchor_path: Path) -> list[str]:
    signal, sample_rate = sf.read(anchor_path, dtype="float32", always_2d=True)
    mono = resample_mono(np.mean(signal, axis=1).astype(np.float32), int(sample_rate))
    length = mono.size
    split_points = [length // 3, length * 2 // 3]
    references: list[str] = []
    for order, segment in enumerate((mono[: split_points[0]], mono[split_points[0] : split_points[1]], mono[split_points[1] :]), 1):
        segment = spec.trim_silence(segment)
        if segment.size < TARGET_SR:
            segment = mono[max(0, (order - 1) * length // 3) : min(length, order * length // 3)]
        path = REFERENCE_DIR / f"v4参照_{order:02d}.wav"
        sf.write(path, segment, TARGET_SR, subtype="PCM_24")
        references.append(str(path.resolve()))
    return references


def kemar_binaural(signal: np.ndarray, angle: float) -> np.ndarray:
    try:
        import slab
        hrtf = slab.HRTF.kemar()
        try:
            hrtf = hrtf.diffuse_field_equalization()
        except Exception:
            pass
        hrtf_rate = int(hrtf.samplerate)
        mono = resample_mono(signal, TARGET_SR, hrtf_rate)
        desired_azimuth = (360.0 - angle) % 360.0 if angle >= 0 else abs(angle) % 360.0
        positions = np.asarray(hrtf.sources.vertical_polar)
        az_diff = np.abs((positions[:, 0] - desired_azimuth + 180.0) % 360.0 - 180.0)
        cost = az_diff + 2.0 * np.abs(positions[:, 1])
        source_index = int(np.argmin(cost))
        sound = slab.Sound(mono, samplerate=hrtf_rate)
        binaural = hrtf.apply(source_index, sound)
        itd = slab.Binaural.azimuth_to_itd(float(angle))
        binaural = binaural.itd(itd)
        stereo = np.asarray(binaural.data, dtype=np.float32)
        if hrtf_rate != TARGET_SR:
            divisor = math.gcd(hrtf_rate, TARGET_SR)
            stereo = resample_poly(stereo, TARGET_SR // divisor, hrtf_rate // divisor, axis=0).astype(np.float32)
    except Exception as exc:
        log(f"KEMAR HRTF failed, using ITD/ILD fallback: {exc!r}")
        stereo = spec.binaural_like(signal, float(angle), int(VOICE["number"]), 0)
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    limit = 10.0 ** (-1.0 / 20.0)
    if peak > limit:
        stereo *= limit / peak
    return stereo.astype(np.float32)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    spec.write_csv(path, rows)


def main() -> None:
    log(f"Start voice {VOICE_INDEX + 1}/8: {VOICE['folder']}")
    speaker_number = int(VOICE["speaker_number"])
    parquet_name = f"data/train-{speaker_number - 1:05d}-of-10000.parquet"
    parquet_path = Path(
        hf_hub_download(
            repo_id=CLONE_REPO,
            repo_type="dataset",
            filename=parquet_name,
            revision=CLONE_REVISION,
            local_dir=WORK / "clone_repo",
        )
    )
    rows = pq.read_table(parquet_path).to_pylist()
    old_refs = extract_old_references(rows)

    checkpoint_path = download_hf_checkpoint(CHECKPOINT)
    key = RuntimeKey(
        checkpoint=str(checkpoint_path),
        model_device="cpu",
        codec_repo="Aratako/Semantic-DACVAE-Japanese-32dim",
        model_precision="fp32",
        codec_device="cpu",
        codec_precision="fp32",
        compile_model=False,
        compile_dynamic=False,
    )
    runtime, _ = get_cached_runtime(key)
    whisper = WhisperModel("base", device="cpu", compute_type="int8")

    anchor_paths: list[Path] = []
    anchor_meta: list[dict[str, Any]] = []
    for candidate in range(1, 3):
        path = CANDIDATE_DIR / f"中立参照_候補_{candidate:02d}.wav"
        meta = generate_one(
            runtime,
            text=ANCHOR_TEXT,
            caption=f"声質は参照音声と同一人物として保つ。{VOICE['base_caption']}{ANCHOR_CAPTION}{QUALITY_CAPTION}",
            references=old_refs,
            seed=202608040000 + int(VOICE["number"]) * 100 + candidate,
            duration_scale=1.02,
            caption_cfg=4.5,
            output_path=path,
        )
        anchor_paths.append(path)
        anchor_meta.append(meta)
    anchor_style = {"label": "丁寧で穏やかな案内", "target_rms": -20.0}
    selected_anchor, anchor_records = select_best(anchor_paths, ANCHOR_TEXT, anchor_style, whisper)
    clean_refs = split_anchor(selected_anchor)
    log(f"Clean v4 reference selected: {selected_anchor.name}")

    generation_meta: dict[str, list[dict[str, Any]]] = {}
    style_candidates: dict[int, list[Path]] = {}
    for style in spec.STYLES:
        style_number = int(style["number"])
        paths: list[Path] = []
        metas: list[dict[str, Any]] = []
        for candidate in range(1, 4):
            candidate_folder = CANDIDATE_DIR / f"{style_number:02d}_{safe_component(style['label'])}"
            candidate_folder.mkdir(parents=True, exist_ok=True)
            path = candidate_folder / f"候補_{candidate:02d}.wav"
            caption = (
                f"声質は参照音声と同一人物として保つ。{VOICE['base_caption']}"
                f"{style['caption']}"
                "台詞の意味と感情を必ず一致させ、途中で普通声、無関係な叫び声、別の感情へ勝手に変えない。"
                f"{QUALITY_CAPTION}"
            )
            meta = generate_one(
                runtime,
                text=str(style["text"]),
                caption=caption,
                references=clean_refs,
                seed=202608040000 + int(VOICE["number"]) * 10000 + style_number * 100 + candidate * 17,
                duration_scale=float(style["duration_scale"]),
                caption_cfg=float(style["caption_cfg"]),
                output_path=path,
            )
            paths.append(path)
            metas.append(meta)
            log(f"Generated voice={VOICE['number']} style={style_number} candidate={candidate}")
        style_candidates[style_number] = paths
        generation_meta[str(style_number)] = metas

    try:
        clear_cached_runtime()
    except Exception:
        pass
    del runtime
    gc.collect()

    validation_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    angles = {1: 14.0, 2: 0.0, 3: 28.0, 4: -24.0, 5: 12.0, 6: -38.0, 7: 24.0, 8: -18.0, 9: 65.0, 10: 34.0}
    if int(VOICE["number"]) % 2 == 0:
        angles = {key: -value for key, value in angles.items()}

    for style in spec.STYLES:
        style_number = int(style["number"])
        selected_path, candidate_records = select_best(style_candidates[style_number], str(style["text"]), style, whisper)
        for record in candidate_records:
            validation_rows.append({
                "voice_number": VOICE["number"],
                "voice_folder": VOICE["folder"],
                "style_number": style_number,
                "style_label": style["label"],
                "target_text": style["text"],
                "selected": Path(record["path"]).resolve() == selected_path.resolve(),
                **record,
            })
        best = candidate_records[0]
        signal, sample_rate = sf.read(selected_path, dtype="float32", always_2d=True)
        mono = resample_mono(np.mean(signal, axis=1).astype(np.float32), int(sample_rate))
        processed = spec.transparent_studio_process(mono, float(style["target_rms"]), str(VOICE["folder"]))
        filename = f"{style_number:02d}_{safe_component(style['label'])}_{safe_component(style['short'])}.wav"
        mono_path = MONO_DIR / filename
        sf.write(mono_path, processed, TARGET_SR, subtype="PCM_24")
        stereo = kemar_binaural(processed, float(angles[style_number]))
        binaural_path = BINAURAL_DIR / filename
        sf.write(binaural_path, stereo, TARGET_SR, subtype="PCM_24")
        selected_rows.append({
            "voice_number": VOICE["number"],
            "voice_folder": VOICE["folder"],
            "style_number": style_number,
            "style_label": style["label"],
            "target_text": style["text"],
            "selected_candidate": best["candidate"],
            "asr_transcript": best["transcript"],
            "asr_score": best["asr_score"],
            "delivery_score": best["delivery_score"],
            "quality_score": best["quality_score"],
            "final_score": best["final_score"],
            "mono_file": str(mono_path.relative_to(OUT)),
            "binaural_file": str(binaural_path.relative_to(OUT)),
            "binaural_angle_degrees": angles[style_number],
        })
        log(f"Selected voice={VOICE['number']} style={style_number} candidate={best['candidate']} score={best['final_score']:.3f}")

    write_csv(VALIDATION_DIR / "候補30本_検証台帳.csv", validation_rows)
    write_csv(VALIDATION_DIR / "最終10本_選抜結果.csv", selected_rows)
    (VALIDATION_DIR / "生成設定.json").write_text(
        json.dumps({
            "checkpoint": CHECKPOINT,
            "checkpoint_path": str(checkpoint_path),
            "voice": VOICE,
            "styles": spec.STYLES,
            "num_steps": NUM_STEPS,
            "candidate_count_per_style": 3,
            "anchor_candidates": anchor_records,
            "generation_meta": generation_meta,
            "selection": "Japanese faster-whisper base ASR + objective quality + style-specific acoustic heuristics",
            "human_listening": False,
            "binaural": "KEMAR HRTF + ITD; generic dummy-head HRTF, not individualized",
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    mono_files = sorted(MONO_DIR.glob("*.wav"))
    binaural_files = sorted(BINAURAL_DIR.glob("*.wav"))
    if len(mono_files) != 10 or len(binaural_files) != 10:
        raise RuntimeError(f"final count mismatch: mono={len(mono_files)}, binaural={len(binaural_files)}")
    for path, expected_channels in [(p, 1) for p in mono_files] + [(p, 2) for p in binaural_files]:
        data, rate = sf.read(path, dtype="float32", always_2d=True)
        if int(rate) != TARGET_SR or data.shape[1] != expected_channels or data.size == 0:
            raise RuntimeError(f"invalid final WAV: {path}")
    summary = {
        "voice": VOICE,
        "mono_wavs": len(mono_files),
        "binaural_wavs": len(binaural_files),
        "sample_rate": TARGET_SR,
        "subtype": "PCM_24",
        "human_listening": False,
    }
    (VALIDATION_DIR / "最終検証結果.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
