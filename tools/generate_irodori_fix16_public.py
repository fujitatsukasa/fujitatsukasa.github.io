#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from huggingface_hub import hf_hub_download
from resemblyzer import VoiceEncoder, preprocess_wav

ROOT = Path(__file__).resolve().parents[1]
IRODORI = ROOT / "Irodori-TTS"
sys.path.insert(0, str(IRODORI))
sys.path.insert(0, str(ROOT / "tools"))

import generate_irodori_final_delivery as base  # noqa: E402
from irodori_fix16_spec import COMMON_CAPTION, STYLES, VOICES  # noqa: E402
from irodori_tts.inference_runtime import SamplingRequest, save_wav  # noqa: E402

VOICE_INDEX = int(os.environ["VOICE_INDEX"])
VOICE = VOICES[VOICE_INDEX]
TARGET_SR = 48_000
REF_DATASET = "shoron08/irodori-refs-10k"
CHECKPOINT = "Aratako/Irodori-TTS-600M-v3-VoiceDesign"

WORK = ROOT / "fix16_public_work" / f"voice_{VOICE_INDEX:02d}"
OUT = ROOT / "fix16_public_output" / f"voice_{VOICE_INDEX:02d}"
WAV_DIR = OUT / "WAV" / str(VOICE["folder"])
VALIDATION_DIR = OUT / "検証"
CANDIDATE_DIR = WORK / "候補"
REF_DIR = WORK / "参照音声"
for directory in (WORK, OUT, WAV_DIR, VALIDATION_DIR, CANDIDATE_DIR, REF_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# Repoint all imported helper state to this exact fixed voice.
base.VOICE = VOICE
base.CHECKPOINT = CHECKPOINT
base.NUM_STEPS = 48
base.WORK = WORK
base.OUT = OUT
base.MONO_DIR = WAV_DIR
base.VALIDATION_DIR = VALIDATION_DIR
base.CANDIDATE_DIR = CANDIDATE_DIR


def log(message: str) -> None:
    print(message, flush=True)
    with (VALIDATION_DIR / "実行ログ.txt").open("a", encoding="utf-8") as file:
        file.write(message + "\n")


base.log = log


def decode_audio_cell(value: Any) -> tuple[np.ndarray, int]:
    if hasattr(value, "as_py"):
        value = value.as_py()
    payload: bytes | None = None
    if isinstance(value, dict) and value.get("bytes") is not None:
        payload = bytes(value["bytes"])
    elif isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
    if payload is None:
        raise RuntimeError("参照音声のParquetセルに音声バイトがありません")
    try:
        audio, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
        return np.mean(audio, axis=1).astype(np.float32), int(sample_rate)
    except Exception:
        source = REF_DIR / "reference.audio"
        destination = REF_DIR / "reference_decode.wav"
        source.write_bytes(payload)
        process = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source), "-vn", "-ac", "1", "-ar", str(TARGET_SR),
                "-c:a", "pcm_s24le", str(destination),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
        )
        if process.returncode != 0:
            raise RuntimeError(f"参照音声のデコード失敗: {process.stderr[-1000:]}")
        audio, sample_rate = sf.read(destination, dtype="float32", always_2d=True)
        return np.mean(audio, axis=1).astype(np.float32), int(sample_rate)


def fetch_exact_reference() -> tuple[Path, str]:
    speaker_id = str(VOICE["speaker_id"])
    speaker_number = int(speaker_id.split("_")[-1])
    global_row = speaker_number - 1
    shard = global_row // 1000
    row_in_shard = global_row % 1000
    filename = f"data/train-{shard:05d}-of-00010.parquet"
    parquet_path = Path(
        hf_hub_download(
            repo_id=REF_DATASET,
            repo_type="dataset",
            filename=filename,
            local_dir=WORK / "reference_repo",
        )
    )
    table = pq.read_table(parquet_path, columns=["audio", "text", "speaker_id"])
    row = table.slice(row_in_shard, 1).to_pylist()[0]
    actual_speaker = str(row.get("speaker_id") or "")
    if actual_speaker != speaker_id:
        raise RuntimeError(f"参照話者不一致: expected={speaker_id}, actual={actual_speaker}")
    audio, sample_rate = decode_audio_cell(row.get("audio"))
    reference = base.resample_mono(audio, sample_rate)
    reference = base.trim_silence(reference, before=0.08, after=0.12)
    path = REF_DIR / f"{speaker_id}_同一声参照.wav"
    sf.write(path, reference, TARGET_SR, subtype="PCM_24")
    return path, str(row.get("text") or "")


def preserve_audio(signal: np.ndarray, sample_rate: int, target_rms: float | None = None) -> np.ndarray:
    """Preserve timbre: no EQ, denoiser, de-esser, compressor, or loudness normalization."""
    x = base.resample_mono(signal, sample_rate)
    x = np.asarray(x, dtype=np.float32)
    x -= float(np.mean(x))
    x = base.trim_silence(x, before=0.07, after=0.11)
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    limit = 10.0 ** (-0.8 / 20.0)
    if peak > limit and peak > 0.0:
        x *= limit / peak
    return np.clip(x, -1.0, 1.0).astype(np.float32)


base.transparent_process = preserve_audio


def relative_acting_score(
    mode: str,
    metrics: dict[str, float],
    neutral: dict[str, float] | None,
) -> float:
    if not neutral or mode in {"neutral", "polite"}:
        duration = float(metrics["duration_sec"])
        return float(np.exp(-((duration - 2.7) / 2.2) ** 2))
    duration_ratio = float(metrics["duration_sec"]) / max(float(neutral["duration_sec"]), 0.1)
    rms_delta = float(metrics["rms_dbfs"]) - float(neutral["rms_dbfs"])
    f0_ratio = float(metrics["estimated_f0_median_hz"]) / max(float(neutral["estimated_f0_median_hz"]), 1.0)
    iqr_ratio = float(metrics["estimated_f0_iqr_hz"]) / max(float(neutral["estimated_f0_iqr_hz"]), 1.0)
    dynamic_ratio = float(metrics["amplitude_dynamic_range_db"]) / max(float(neutral["amplitude_dynamic_range_db"]), 1.0)
    if mode == "happy":
        return float(np.clip(0.42 * (f0_ratio - 0.88) / 0.28 + 0.38 * dynamic_ratio + 0.20 / max(duration_ratio, 0.6), 0, 1))
    if mode == "angry":
        return float(np.clip(0.45 * (rms_delta + 3.0) / 5.0 + 0.35 * dynamic_ratio + 0.20 / max(duration_ratio, 0.6), 0, 1))
    if mode == "sad":
        return float(np.clip(0.42 * duration_ratio + 0.34 * (-rms_delta + 2.0) / 5.0 + 0.24 / max(iqr_ratio, 0.5), 0, 1))
    if mode == "fear":
        return float(np.clip(0.42 * (f0_ratio - 0.82) / 0.38 + 0.38 * iqr_ratio + 0.20 / max(duration_ratio, 0.6), 0, 1))
    if mode == "sleepy":
        return float(np.clip(0.45 * duration_ratio + 0.35 * (-rms_delta + 2.0) / 5.0 + 0.20 / max(iqr_ratio, 0.5), 0, 1))
    if mode in {"gentle", "monologue"}:
        return float(np.clip(0.50 * duration_ratio + 0.30 * (-rms_delta + 2.0) / 5.0 + 0.20 / max(iqr_ratio, 0.5), 0, 1))
    if mode == "laugh":
        return float(np.clip(0.55 * dynamic_ratio + 0.25 * iqr_ratio + 0.20 * duration_ratio, 0, 1))
    return 0.5


base.prosody_score = relative_acting_score


def amplified_text(style: dict[str, Any], candidate_number: int) -> str:
    text = str(style["input_text"])
    if candidate_number <= int(style["candidate_count"]):
        return text
    emoji_map = {
        "happy": "😊😊",
        "angry": "😠😠",
        "sad": "😭😭",
        "fear": "😰😰",
        "sleepy": "😪😪😮‍💨",
        "gentle": "🫶🫶😟",
        "monologue": "🐢🐢📖",
        "laugh": "🤭🤭",
    }
    mode = str(style["mode"])
    if mode not in emoji_map:
        return text
    plain = re.sub(r"[👂😮‍💨⏸️🤭🥵📢😏🥺🌬️😮👅💋🫶😭😱😪😴⏩📞🐢🥤🤧😒😰😆💥😠😲🥱😖😟🫣🙄😊😎👌🙏🥴🎵🤐😌🤔💪👃📖]", "", text)
    return plain + emoji_map[mode]


def make_synthesize(style: dict[str, Any], candidate_number_box: dict[str, int]):
    def synthesize(
        runtime: Any,
        *,
        text: str,
        caption: str,
        reference: str | None,
        seed: int,
        duration_scale: float,
        output_path: Path,
    ) -> dict[str, Any]:
        candidate_number = int(candidate_number_box["value"])
        messages: list[str] = []
        result = runtime.synthesize(
            SamplingRequest(
                text=amplified_text(style, candidate_number),
                caption=caption,
                ref_wav=reference,
                ref_wavs=None,
                ref_latent=None,
                ref_latents=None,
                ref_embed=None,
                no_ref=False,
                ref_normalize_db=-18.0,
                ref_ensure_max=True,
                num_candidates=1,
                decode_mode="sequential",
                seconds=None,
                duration_scale=float(duration_scale),
                min_seconds=0.5,
                max_seconds=9.5,
                max_ref_seconds=8.0,
                max_text_len=None,
                max_caption_len=None,
                num_steps=48,
                cfg_scale_text=3.5,
                cfg_scale_caption=3.5 if str(style["mode"]) not in {"neutral", "polite"} else 2.8,
                cfg_scale_speaker=6.5,
                cfg_guidance_mode="independent",
                cfg_scale=None,
                cfg_min_t=0.45,
                cfg_max_t=1.0,
                truncation_factor=None,
                rescale_k=None,
                rescale_sigma=None,
                context_kv_cache=True,
                speaker_kv_scale=1.05,
                speaker_kv_min_t=0.35,
                speaker_kv_max_layers=None,
                speaker_uncond_mode="mask",
                seed=int(seed),
                t_schedule_mode="linear",
                sway_coeff=-1.0,
                trim_tail=True,
                tail_window_size=20,
                tail_std_threshold=0.05,
                tail_mean_threshold=0.1,
                lora_adapter=None,
            ),
            log_fn=messages.append,
        )
        save_wav(output_path, result.audios[0].float(), result.sample_rate)
        candidate_number_box["value"] = candidate_number + 1
        return {
            "used_seed": int(result.used_seed),
            "sample_rate": int(result.sample_rate),
            "stage_timings": result.stage_timings,
            "messages": [*messages, *result.messages],
        }

    return synthesize


def speaker_similarity(encoder: VoiceEncoder, reference_path: Path, candidate_path: Path) -> float:
    ref = encoder.embed_utterance(preprocess_wav(reference_path))
    cand = encoder.embed_utterance(preprocess_wav(candidate_path))
    return float(np.dot(ref, cand) / max(float(np.linalg.norm(ref) * np.linalg.norm(cand)), 1e-12))


def choose_candidate(
    records: list[dict[str, Any]],
    style: dict[str, Any],
    encoder: VoiceEncoder,
    reference_path: Path,
) -> tuple[Path, dict[str, Any]]:
    viable: list[tuple[Path, dict[str, Any]]] = []
    for record in records:
        path = Path(str(record["processed_path"]))
        similarity = speaker_similarity(encoder, reference_path, path)
        record["speaker_similarity"] = similarity
        acting_ok = float(record["prosody_score"]) >= float(style["acting_minimum"])
        record["acting_minimum"] = float(style["acting_minimum"])
        record["acting_ok"] = acting_ok
        if bool(record["accepted"]) and acting_ok and similarity >= 0.50:
            viable.append((path, record))
    if not viable:
        ranked = sorted(
            [(Path(str(record["processed_path"])), record) for record in records if bool(record["accepted"])],
            key=lambda item: (
                float(item[1].get("speaker_similarity", 0.0)),
                float(item[1]["prosody_score"]),
                float(item[1]["asr_ratio"]),
                float(item[1]["clarity_score"]),
            ),
            reverse=True,
        )
        if not ranked:
            raise RuntimeError(f"ASR・信号条件を満たす候補なし: {VOICE['folder']} / {style['label']}")
        path, record = ranked[0]
        # Never accept a different voice or a flat emotional take merely to finish the ZIP.
        if float(record.get("speaker_similarity", 0.0)) < 0.46:
            raise RuntimeError(f"話者同一性不足: {VOICE['folder']} / {style['label']} / {record.get('speaker_similarity')}")
        if float(record["prosody_score"]) < max(0.38, float(style["acting_minimum"]) - 0.12):
            raise RuntimeError(f"演技不足: {VOICE['folder']} / {style['label']} / {record['prosody_score']}")
        record["controlled_fallback"] = True
        return path, record
    viable.sort(
        key=lambda item: (
            float(item[1]["asr_ratio"]),
            float(item[1].get("speaker_similarity", 0.0)),
            float(item[1]["prosody_score"]),
            float(item[1]["clarity_score"]),
        ),
        reverse=True,
    )
    return viable[0]


def main() -> None:
    try:
        reference_path, reference_text = fetch_exact_reference()
        log(f"開始: {VOICE['folder']} / {VOICE['speaker_id']} / ref_text={reference_text!r}")
        whisper = base.load_whisper()
        runtime = base.build_runtime()
        encoder = VoiceEncoder(device="cpu")

        ordered = [next(style for style in STYLES if int(style["number"]) == 2)] + [
            style for style in STYLES if int(style["number"]) != 2
        ]
        neutral_metrics: dict[str, float] | None = None
        all_records: list[dict[str, Any]] = []
        final_rows: list[dict[str, Any]] = []

        for style in ordered:
            maximum = int(style["candidate_count"]) + (2 if str(style["mode"]) not in {"neutral", "polite"} else 1)
            base.MIN_CANDIDATES = maximum
            base.MAX_CANDIDATES = maximum
            candidate_number_box = {"value": 1}
            base.synthesize = make_synthesize(style, candidate_number_box)
            caption = (
                f"{style['caption']} {COMMON_CAPTION} "
                "参照音声と異なる性別、年齢、声域、話者へ変えない。"
            )
            _, records, _ = base.generate_best(
                runtime,
                whisper,
                label=str(style["label"]),
                target_text=str(style["input_text"]),
                caption=caption,
                reference=str(reference_path.resolve()),
                base_seed=int(VOICE["seed"]) + int(style["number"]) * 100_000,
                base_duration_scale=float(style["duration_scale"]),
                target_rms=-20.0,
                mode=str(style["mode"]),
                output_directory=CANDIDATE_DIR / f"{int(style['number']):02d}_{base.safe_component(str(style['label']))}",
                anchor_metrics=neutral_metrics,
            )
            selected_path, selected = choose_candidate(records, style, encoder, reference_path)
            all_records.extend(records)
            output_name = (
                f"{int(style['number']):02d}_{base.safe_component(str(style['label']))}_"
                f"{base.safe_component(str(style['short']))}.wav"
            )
            output_path = WAV_DIR / output_name
            signal, sample_rate = sf.read(selected_path, dtype="float32", always_2d=True)
            final_signal = preserve_audio(np.mean(signal, axis=1), int(sample_rate))
            sf.write(output_path, final_signal, TARGET_SR, subtype="PCM_24")
            transcript, _ = base.transcribe(output_path, whisper)
            final_asr = base.asr_evaluation(str(style["text"]), transcript, str(style["mode"]))
            final_metrics = base.audio_metrics(final_signal, TARGET_SR)
            if int(final_asr["length_delta"]) > 0:
                raise RuntimeError(f"最終WAVに余計な認識文字: {output_path} -> {transcript!r}")
            if not base.integrity_ok(final_metrics):
                raise RuntimeError(f"最終WAVの信号条件不合格: {output_path}")
            final_similarity = speaker_similarity(encoder, reference_path, output_path)
            if final_similarity < 0.46:
                raise RuntimeError(f"最終WAVの話者同一性不足: {output_path} -> {final_similarity}")
            row = {
                "voice": VOICE["folder"],
                "speaker_id": VOICE["speaker_id"],
                "style_number": style["number"],
                "style": style["label"],
                "target_text": style["text"],
                "transcript": transcript,
                "file": output_path.relative_to(OUT).as_posix(),
                **final_asr,
                **final_metrics,
                "speaker_similarity": final_similarity,
                "selected_candidate": selected.get("candidate"),
                "selected_acting_score": selected.get("prosody_score"),
                "selected_clarity_score": selected.get("clarity_score"),
                "sha256": base.sha256(output_path),
            }
            final_rows.append(row)
            if int(style["number"]) == 2:
                neutral_metrics = final_metrics

        final_rows.sort(key=lambda row: int(row["style_number"]))
        base.write_csv(VALIDATION_DIR / "全候補検査.csv", all_records)
        base.write_csv(VALIDATION_DIR / "最終WAV検査.csv", final_rows)
        wavs = sorted(WAV_DIR.glob("*.wav"))
        if len(wavs) != 10:
            raise RuntimeError(f"最終WAV数が10ではありません: {len(wavs)}")
        checks = [base.validate_wav(path, 1) for path in wavs]
        base.write_csv(VALIDATION_DIR / "形式・全編デコード検証.csv", checks)
        summary = {
            "voice_index": VOICE_INDEX,
            "voice": VOICE["folder"],
            "speaker_id": VOICE["speaker_id"],
            "reference_text": reference_text,
            "checkpoint": CHECKPOINT,
            "wav_count": len(wavs),
            "final": [
                {
                    "style": row["style"],
                    "target": row["target_text"],
                    "transcript": row["transcript"],
                    "asr_ratio": row["asr_ratio"],
                    "acting_score": row["selected_acting_score"],
                    "speaker_similarity": row["speaker_similarity"],
                }
                for row in final_rows
            ],
        }
        (VALIDATION_DIR / "集計.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"完了: {VOICE['folder']} / 10 WAV")
    except Exception:
        error = traceback.format_exc()
        (VALIDATION_DIR / "致命的エラー.txt").write_text(error, encoding="utf-8")
        log(error)
        raise


if __name__ == "__main__":
    main()
