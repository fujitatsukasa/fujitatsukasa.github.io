#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from pykakasi import kakasi
from rapidfuzz import fuzz
from scipy.signal import butter, resample_poly, sosfiltfilt

ROOT = Path(__file__).resolve().parents[1]
IRODORI_REPO = ROOT / "Irodori-TTS"
sys.path.insert(0, str(IRODORI_REPO))
sys.path.insert(0, str(ROOT / "tools"))

from irodori_tts.inference_runtime import (  # noqa: E402
    RuntimeKey,
    SamplingRequest,
    download_hf_checkpoint,
    get_cached_runtime,
    save_wav,
)
from irodori_final_delivery_spec import (  # noqa: E402
    ANCHOR_CAPTION,
    ANCHOR_TEXT,
    QUALITY_CAPTION,
    STYLES,
    VOICES,
)

VOICE_INDEX = int(os.environ.get("VOICE_INDEX", "0"))
VOICE = VOICES[VOICE_INDEX]
CHECKPOINT = "Aratako/Irodori-TTS-v4-Small"
CODEC = "Aratako/Semantic-DACVAE-Japanese-32dim"
TARGET_SR = 48_000
NUM_STEPS = 48
MIN_CANDIDATES = 4
MAX_CANDIDATES = 8
KAKASI = kakasi()

WORK = ROOT / "delivery_work" / f"voice_{VOICE_INDEX}"
OUT = ROOT / "delivery_output" / f"voice_{VOICE_INDEX}"
MONO_DIR = OUT / "モノラル" / str(VOICE["folder"])
STEREO_DIR = OUT / "耳元ステレオ" / str(VOICE["folder"])
VALIDATION_DIR = OUT / "検証"
CANDIDATE_DIR = WORK / "候補"
ANCHOR_DIR = WORK / "基準声"
for directory in (WORK, OUT, MONO_DIR, STEREO_DIR, VALIDATION_DIR, CANDIDATE_DIR, ANCHOR_DIR):
    directory.mkdir(parents=True, exist_ok=True)

REPLACEMENTS = {
    "辛い": "つらい",
    "良い": "いい",
    "大丈夫": "だいじょうぶ",
    "分かって": "わかって",
    "分かる": "わかる",
    "来て": "きて",
    "会えて": "あえて",
    "今日は": "きょうは",
    "今日": "きょう",
    "確認": "かくにん",
    "同じ": "おなじ",
    "無理": "むり",
    "聞こえる": "きこえる",
    "力": "ちから",
    "眠い": "ねむい",
    "何か": "なにか",
    "誰か": "だれか",
    "話さない": "はなさない",
    "話す": "はなす",
    "息": "いき",
}


def log(message: str) -> None:
    print(message, flush=True)
    with (VALIDATION_DIR / "実行ログ.txt").open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_component(value: str, limit: int = 120) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" ._")
    return (text or "名称なし")[:limit]


def to_hiragana(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    for source, replacement in REPLACEMENTS.items():
        text = text.replace(source, replacement)
    chunks: list[str] = []
    for item in KAKASI.convert(text):
        chunks.append(str(item.get("hira") or item.get("orig") or ""))
    return re.sub(r"[^0-9a-zぁ-んゔー]", "", "".join(chunks).lower())


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    if not fields:
        fields = ["empty"]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_whisper() -> WhisperModel:
    last_error: Exception | None = None
    for attempt in range(1, 9):
        try:
            log(f"faster-whisper small 読み込み attempt={attempt}/8")
            return WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
                cpu_threads=max(2, os.cpu_count() or 2),
            )
        except Exception as error:  # pragma: no cover - network recovery
            last_error = error
            wait = min(180, attempt * 20)
            log(f"Whisper読み込み失敗: {error!r}; {wait}秒後に再試行")
            time.sleep(wait)
    assert last_error is not None
    raise last_error


def transcribe(path: Path, model: WhisperModel) -> tuple[str, list[dict[str, Any]]]:
    segments, _ = model.transcribe(
        str(path),
        language="ja",
        beam_size=5,
        best_of=5,
        temperature=0.0,
        condition_on_previous_text=False,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 140},
    )
    text_parts: list[str] = []
    words: list[dict[str, Any]] = []
    for segment in segments:
        text_parts.append(str(segment.text))
        for word in segment.words or []:
            words.append(
                {
                    "text": str(word.word),
                    "start": float(word.start),
                    "end": float(word.end),
                }
            )
    return "".join(text_parts).strip(), words


def resample_mono(signal: np.ndarray, sample_rate: int) -> np.ndarray:
    x = np.asarray(signal, dtype=np.float32)
    if x.ndim > 1:
        x = np.mean(x, axis=1)
    if int(sample_rate) != TARGET_SR:
        divisor = math.gcd(int(sample_rate), TARGET_SR)
        x = resample_poly(x, TARGET_SR // divisor, int(sample_rate) // divisor).astype(np.float32)
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def trim_silence(signal: np.ndarray, before: float = 0.08, after: float = 0.14) -> np.ndarray:
    x = np.asarray(signal, dtype=np.float32)
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    threshold = max(10.0 ** (-55.0 / 20.0), peak * 0.006)
    active = np.flatnonzero(np.abs(x) >= threshold)
    if active.size == 0:
        return x
    start = max(0, int(active[0]) - int(before * TARGET_SR))
    end = min(x.size, int(active[-1]) + 1 + int(after * TARGET_SR))
    return x[start:end]


def rms_dbfs(signal: np.ndarray) -> float:
    x = np.asarray(signal, dtype=np.float32)
    return 20.0 * math.log10(max(float(np.sqrt(np.mean(np.square(x)) + 1e-12)), 1e-12))


def transparent_process(signal: np.ndarray, sample_rate: int, target_rms: float) -> np.ndarray:
    """Only mild cleanup: no denoiser, no bandwidth synthesis, no strong EQ."""
    x = resample_mono(signal, sample_rate)
    x -= float(np.mean(x))
    if x.size > 256:
        x = sosfiltfilt(
            butter(2, 48.0 / (TARGET_SR / 2.0), btype="highpass", output="sos"),
            x,
        ).astype(np.float32)
        spectrum = np.fft.rfft(x)
        frequencies = np.fft.rfftfreq(x.size, 1.0 / TARGET_SR)
        gain_db = np.zeros_like(frequencies, dtype=np.float64)
        # Very small boxiness cut and air shelf. Keep the generated timbre intact.
        gain_db -= 0.55 * np.exp(
            -0.5 * ((np.log2(np.maximum(frequencies, 1.0) / 310.0)) / 0.95) ** 2
        )
        gain_db += 0.55 / (1.0 + np.exp(-(frequencies - 6500.0) / 1700.0))
        gain_db[frequencies > 19_000.0] *= np.clip(
            (23_000.0 - frequencies[frequencies > 19_000.0]) / 4_000.0,
            0.0,
            1.0,
        )
        x = np.fft.irfft(spectrum * (10.0 ** (gain_db / 20.0)), n=x.size).astype(np.float32)
    x = trim_silence(x)
    if x.size == 0:
        return x
    current_rms = rms_dbfs(x)
    x *= 10.0 ** ((float(target_rms) - current_rms) / 20.0)
    peak = float(np.max(np.abs(x)))
    peak_limit = 10.0 ** (-1.0 / 20.0)
    if peak > peak_limit and peak > 0.0:
        x *= peak_limit / peak
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def align_to_target(path: Path, target_text: str, model: WhisperModel) -> tuple[Path, str, dict[str, Any]]:
    transcript, words = transcribe(path, model)
    target = to_hiragana(target_text)
    if not words:
        return path, transcript, {"alignment_score": 0.0, "word_start": 0, "word_end": 0}

    best_score = -1.0
    best_start = 0
    best_end = 0
    for start in range(len(words)):
        cumulative = ""
        for end in range(start, min(len(words), start + 24)):
            cumulative += str(words[end]["text"])
            normalized = to_hiragana(cumulative)
            ratio = float(fuzz.ratio(target, normalized) / 100.0)
            partial = float(fuzz.partial_ratio(target, normalized) / 100.0) if normalized else 0.0
            overshoot = max(0, len(normalized) - len(target))
            undershoot = max(0, len(target) - len(normalized))
            score = 0.74 * ratio + 0.26 * partial - 0.040 * overshoot - 0.004 * undershoot
            if score > best_score:
                best_score = score
                best_start = start
                best_end = end

    if best_score < 0.78:
        return path, transcript, {
            "alignment_score": best_score,
            "word_start": best_start,
            "word_end": best_end,
        }

    signal, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(signal, axis=1).astype(np.float32)
    start_seconds = max(0.0, float(words[best_start]["start"]) - 0.08)
    end_seconds = float(words[best_end]["end"]) + 0.14
    start_sample = max(0, int(start_seconds * int(sample_rate)))
    end_sample = min(mono.size, int(end_seconds * int(sample_rate)))
    if end_sample - start_sample < int(0.55 * int(sample_rate)):
        return path, transcript, {
            "alignment_score": best_score,
            "word_start": best_start,
            "word_end": best_end,
        }

    aligned = path.with_name(path.stem + "_台詞区間.wav")
    sf.write(aligned, mono[start_sample:end_sample], int(sample_rate), subtype="PCM_24")
    transcript2, _ = transcribe(aligned, model)
    if fuzz.ratio(target, to_hiragana(transcript2)) + 2 >= fuzz.ratio(target, to_hiragana(transcript)):
        return aligned, transcript2, {
            "alignment_score": best_score,
            "word_start": best_start,
            "word_end": best_end,
        }
    aligned.unlink(missing_ok=True)
    return path, transcript, {
        "alignment_score": best_score,
        "word_start": best_start,
        "word_end": best_end,
    }


def estimate_pitch(signal: np.ndarray, sample_rate: int) -> tuple[float, float]:
    x = np.asarray(signal, dtype=np.float32)
    if x.size < sample_rate // 2:
        return 0.0, 0.0
    if sample_rate != 16_000:
        divisor = math.gcd(int(sample_rate), 16_000)
        x = resample_poly(x, 16_000 // divisor, int(sample_rate) // divisor).astype(np.float32)
    frame_length = 1024
    hop = 320
    values: list[float] = []
    for start in range(0, max(1, x.size - frame_length), hop):
        frame = x[start : start + frame_length]
        if frame.size < frame_length:
            continue
        frame = frame - float(np.mean(frame))
        energy = float(np.sqrt(np.mean(frame * frame) + 1e-12))
        if energy < 0.008:
            continue
        autocorrelation = np.correlate(frame, frame, mode="full")[frame_length - 1 :]
        low = int(16_000 / 500)
        high = min(len(autocorrelation), int(16_000 / 65))
        if high <= low:
            continue
        lag = int(np.argmax(autocorrelation[low:high]) + low)
        if lag > 0 and autocorrelation[lag] > autocorrelation[0] * 0.24:
            values.append(16_000.0 / lag)
    if not values:
        return 0.0, 0.0
    array = np.asarray(values, dtype=np.float64)
    return float(np.median(array)), float(np.percentile(array, 75) - np.percentile(array, 25))


def audio_metrics(signal: np.ndarray, sample_rate: int) -> dict[str, float]:
    x = np.asarray(signal, dtype=np.float32)
    duration = float(x.size / int(sample_rate)) if sample_rate else 0.0
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12)) if x.size else 0.0
    clip_ratio = float(np.mean(np.abs(x) >= 0.999)) if x.size else 1.0
    if x.size < 2048:
        flatness, centroid, high_ratio = 1.0, 0.0, 1.0
    else:
        fft_size = 2048
        hop = 512
        count = 1 + max(0, (x.size - fft_size) // hop)
        indices = np.arange(fft_size)[None, :] + hop * np.arange(count)[:, None]
        frames = x[indices] * np.hanning(fft_size)[None, :]
        power = np.abs(np.fft.rfft(frames, axis=1)) ** 2 + 1e-12
        frequencies = np.fft.rfftfreq(fft_size, 1.0 / int(sample_rate))
        sums = np.maximum(np.sum(power, axis=1), 1e-12)
        centroid = float(np.mean(np.sum(power * frequencies[None, :], axis=1) / sums))
        flatness = float(
            np.mean(np.exp(np.mean(np.log(power), axis=1)) / np.maximum(np.mean(power, axis=1), 1e-12))
        )
        high_ratio = float(np.mean(np.sum(power[:, frequencies >= 7_000.0], axis=1) / sums))
    f0_median, f0_iqr = estimate_pitch(x, int(sample_rate))
    absolute = np.abs(x)
    dynamic_range = 0.0
    if absolute.size:
        upper = float(np.percentile(absolute, 95))
        lower = float(np.percentile(absolute, 35))
        dynamic_range = 20.0 * math.log10(max(upper, 1e-9) / max(lower, 1e-9))
    return {
        "duration_sec": duration,
        "peak_dbfs": 20.0 * math.log10(max(peak, 1e-12)),
        "rms_dbfs": 20.0 * math.log10(max(rms, 1e-12)),
        "clip_ratio": clip_ratio,
        "spectral_flatness": flatness,
        "spectral_centroid_hz": centroid,
        "high_frequency_ratio": high_ratio,
        "estimated_f0_median_hz": f0_median,
        "estimated_f0_iqr_hz": f0_iqr,
        "amplitude_dynamic_range_db": dynamic_range,
    }


def asr_evaluation(target_text: str, transcript: str, mode: str) -> dict[str, Any]:
    target = to_hiragana(target_text)
    actual = to_hiragana(transcript)
    ratio = float(fuzz.ratio(target, actual) / 100.0)
    partial = float(fuzz.partial_ratio(target, actual) / 100.0) if actual else 0.0
    length_delta = len(actual) - len(target)
    threshold = 0.88 if mode in {"asmr", "laugh"} else 0.91
    partial_threshold = 0.93 if mode in {"asmr", "laugh"} else 0.95
    laugh_ok = mode != "laugh" or "ふふ" in actual
    accepted = bool(
        ratio >= threshold
        and partial >= partial_threshold
        and -3 <= length_delta <= 0
        and laugh_ok
    )
    return {
        "target_hiragana": target,
        "actual_hiragana": actual,
        "asr_ratio": ratio,
        "asr_partial_ratio": partial,
        "length_delta": length_delta,
        "laugh_ok": laugh_ok,
        "asr_accepted": accepted,
    }


def integrity_ok(metrics: dict[str, float]) -> bool:
    return bool(
        0.60 <= float(metrics["duration_sec"]) <= 8.5
        and -32.0 <= float(metrics["rms_dbfs"]) <= -14.0
        and -14.0 <= float(metrics["peak_dbfs"]) <= -0.05
        and float(metrics["clip_ratio"]) <= 0.00010
        and 0.0 <= float(metrics["spectral_flatness"]) <= 0.40
        and 350.0 <= float(metrics["spectral_centroid_hz"]) <= 9_000.0
        and 0.0 <= float(metrics["high_frequency_ratio"]) <= 0.50
    )


def clarity_score(metrics: dict[str, float]) -> float:
    centroid = float(metrics["spectral_centroid_hz"])
    high = float(metrics["high_frequency_ratio"])
    flatness = float(metrics["spectral_flatness"])
    clip = float(metrics["clip_ratio"])
    presence = float(np.exp(-((centroid - 2_700.0) / 2_500.0) ** 2))
    air = float(np.exp(-((high - 0.070) / 0.100) ** 2))
    smoothness = float(np.exp(-((flatness - 0.025) / 0.13) ** 2))
    clean_peak = max(0.0, 1.0 - clip / 0.00010)
    return float(np.clip(0.36 * presence + 0.24 * air + 0.25 * smoothness + 0.15 * clean_peak, 0.0, 1.0))


def prosody_score(mode: str, metrics: dict[str, float], anchor_metrics: dict[str, float] | None) -> float:
    duration = float(metrics["duration_sec"])
    f0 = float(metrics["estimated_f0_median_hz"])
    f0_iqr = float(metrics["estimated_f0_iqr_hz"])
    dynamic = float(metrics["amplitude_dynamic_range_db"])
    anchor_f0 = float((anchor_metrics or {}).get("estimated_f0_median_hz", 0.0))
    if mode == "sleepy":
        return float(np.clip(0.55 * min(1.0, duration / 3.0) + 0.45 * np.exp(-(f0_iqr / 55.0) ** 2), 0, 1))
    if mode == "sad":
        return float(np.clip(0.60 * min(1.0, duration / 3.0) + 0.40 * np.exp(-(f0_iqr / 85.0) ** 2), 0, 1))
    if mode == "angry":
        return float(np.clip(0.55 * min(1.0, dynamic / 24.0) + 0.45 * np.exp(-((duration - 2.0) / 1.4) ** 2), 0, 1))
    if mode == "fear":
        relative = 0.5 if not anchor_f0 or not f0 else np.clip((f0 / anchor_f0 - 0.95) / 0.35, 0, 1)
        return float(np.clip(0.55 * relative + 0.45 * np.exp(-((duration - 2.2) / 1.5) ** 2), 0, 1))
    if mode == "happy":
        relative = 0.5 if not anchor_f0 or not f0 else np.clip((f0 / anchor_f0 - 0.95) / 0.30, 0, 1)
        return float(np.clip(0.55 * relative + 0.45 * min(1.0, dynamic / 22.0), 0, 1))
    if mode == "gentle":
        return float(np.clip(0.60 * min(1.0, duration / 2.5) + 0.40 * np.exp(-(f0_iqr / 80.0) ** 2), 0, 1))
    if mode == "asmr":
        flatness = float(metrics["spectral_flatness"])
        return float(np.clip(0.55 * np.exp(-((flatness - 0.06) / 0.12) ** 2) + 0.45 * min(1.0, duration / 3.2), 0, 1))
    if mode == "laugh":
        return float(np.clip(0.55 * min(1.0, dynamic / 22.0) + 0.45 * np.exp(-((duration - 2.5) / 1.5) ** 2), 0, 1))
    return float(np.clip(0.55 * np.exp(-((duration - 2.2) / 1.6) ** 2) + 0.45 * min(1.0, dynamic / 22.0), 0, 1))


def build_runtime() -> Any:
    checkpoint = download_hf_checkpoint(CHECKPOINT)
    runtime, _ = get_cached_runtime(
        RuntimeKey(
            checkpoint=str(checkpoint),
            model_device="cpu",
            codec_repo=CODEC,
            model_precision="fp32",
            codec_device="cpu",
            codec_precision="fp32",
            compile_model=False,
            compile_dynamic=False,
        )
    )
    return runtime


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
    messages: list[str] = []
    result = runtime.synthesize(
        SamplingRequest(
            text=text,
            caption=caption,
            ref_wav=reference,
            ref_wavs=None,
            ref_latent=None,
            ref_latents=None,
            ref_embed=None,
            no_ref=reference is None,
            ref_normalize_db=-18.0,
            ref_ensure_max=True,
            num_candidates=1,
            decode_mode="sequential",
            seconds=None,
            duration_scale=float(duration_scale),
            min_seconds=0.5,
            max_seconds=9.0,
            max_ref_seconds=10.0,
            max_text_len=None,
            max_caption_len=None,
            num_steps=NUM_STEPS,
            cfg_scale_text=3.65,
            cfg_scale_caption=2.70,
            cfg_scale_speaker=5.0 if reference is not None else 0.0,
            cfg_guidance_mode="independent",
            cfg_scale=None,
            cfg_min_t=0.5,
            cfg_max_t=1.0,
            truncation_factor=None,
            rescale_k=None,
            rescale_sigma=None,
            context_kv_cache=True,
            speaker_kv_scale=None,
            speaker_kv_min_t=None,
            speaker_kv_max_layers=None,
            speaker_uncond_mode="mask",
            seed=int(seed),
            t_schedule_mode="linear",
            sway_coeff=-1.0,
            trim_tail=True,
            lora_adapter=None,
        ),
        log_fn=messages.append,
    )
    save_wav(output_path, result.audios[0].float(), result.sample_rate)
    return {
        "used_seed": int(result.used_seed),
        "sample_rate": int(result.sample_rate),
        "stage_timings": result.stage_timings,
        "total_to_decode": float(result.total_to_decode),
        "messages": [*messages, *result.messages],
    }


def candidate_scales(base_scale: float) -> list[float]:
    multipliers = (0.94, 1.00, 1.06, 0.88, 1.12, 0.82, 1.18, 1.24)
    return [max(0.72, min(1.42, float(base_scale) * value)) for value in multipliers]


def generate_best(
    runtime: Any,
    whisper: WhisperModel,
    *,
    label: str,
    target_text: str,
    caption: str,
    reference: str | None,
    base_seed: int,
    base_duration_scale: float,
    target_rms: float,
    mode: str,
    output_directory: Path,
    anchor_metrics: dict[str, float] | None,
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    output_directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    accepted: list[tuple[Path, dict[str, Any]]] = []

    for candidate_number, duration_scale in enumerate(candidate_scales(base_duration_scale), 1):
        raw_path = output_directory / f"候補_{candidate_number:02d}_生.wav"
        generation = synthesize(
            runtime,
            text=target_text,
            caption=caption,
            reference=reference,
            seed=base_seed + candidate_number * 1009,
            duration_scale=duration_scale,
            output_path=raw_path,
        )
        aligned_path, transcript_before, alignment = align_to_target(raw_path, target_text, whisper)
        signal, sample_rate = sf.read(aligned_path, dtype="float32", always_2d=True)
        processed = transparent_process(np.mean(signal, axis=1), int(sample_rate), target_rms)
        processed_path = output_directory / f"候補_{candidate_number:02d}_整音.wav"
        sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")

        final_aligned_path, transcript_after_alignment, alignment2 = align_to_target(
            processed_path, target_text, whisper
        )
        if final_aligned_path != processed_path:
            signal2, sample_rate2 = sf.read(final_aligned_path, dtype="float32", always_2d=True)
            processed = transparent_process(np.mean(signal2, axis=1), int(sample_rate2), target_rms)
            sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")

        transcript, words = transcribe(processed_path, whisper)
        asr = asr_evaluation(target_text, transcript, mode)
        metrics = audio_metrics(processed, TARGET_SR)
        intact = integrity_ok(metrics)
        clarity = clarity_score(metrics)
        prosody = prosody_score(mode, metrics, anchor_metrics)
        accepted_flag = bool(asr["asr_accepted"] and intact)
        record: dict[str, Any] = {
            "voice": VOICE["folder"],
            "label": label,
            "candidate": candidate_number,
            "duration_scale": duration_scale,
            "target_text": target_text,
            "transcript_before": transcript_before,
            "transcript_after_alignment": transcript_after_alignment,
            "transcript_final": transcript,
            "word_count": len(words),
            **asr,
            **metrics,
            "alignment_score_first": alignment.get("alignment_score", 0.0),
            "alignment_score_second": alignment2.get("alignment_score", 0.0),
            "integrity_ok": intact,
            "clarity_score": clarity,
            "prosody_score": prosody,
            "accepted": accepted_flag,
            "raw_path": str(raw_path),
            "processed_path": str(processed_path),
            "generation": json.dumps(generation, ensure_ascii=False),
        }
        records.append(record)
        log(
            f"{VOICE['folder']} / {label} / candidate={candidate_number} "
            f"ASR={asr['asr_ratio']:.3f} partial={asr['asr_partial_ratio']:.3f} "
            f"delta={asr['length_delta']} clarity={clarity:.3f} prosody={prosody:.3f} "
            f"accepted={accepted_flag}"
        )
        if accepted_flag:
            accepted.append((processed_path, record))
        if candidate_number >= MIN_CANDIDATES and accepted:
            break
        if candidate_number >= MAX_CANDIDATES:
            break

    if not accepted:
        ranked = sorted(
            records,
            key=lambda item: (
                bool(item["integrity_ok"]),
                float(item["asr_ratio"]),
                float(item["asr_partial_ratio"]),
                -max(0, int(item["length_delta"])),
                float(item["clarity_score"]),
                float(item["prosody_score"]),
            ),
            reverse=True,
        )
        best = ranked[0]
        # One-character ASR disagreement is allowed only as an explicit fallback;
        # positive extra speech remains forbidden.
        fallback_ok = bool(
            best["integrity_ok"]
            and float(best["asr_ratio"]) >= 0.84
            and float(best["asr_partial_ratio"]) >= 0.90
            and -3 <= int(best["length_delta"]) <= 0
        )
        if not fallback_ok:
            raise RuntimeError(
                f"合格候補なし: {VOICE['folder']} / {label}; "
                f"ASR={best['asr_ratio']:.3f}, partial={best['asr_partial_ratio']:.3f}, "
                f"delta={best['length_delta']}, transcript={best['transcript_final']!r}"
            )
        best["accepted"] = True
        best["fallback_selected"] = True
        accepted = [(Path(str(best["processed_path"])), best)]
        log(f"一文字相当のASR差としてフォールバック採用: {VOICE['folder']} / {label}")

    accepted.sort(
        key=lambda item: (
            float(item[1]["asr_ratio"]),
            float(item[1]["asr_partial_ratio"]),
            -abs(int(item[1]["length_delta"])),
            float(item[1]["clarity_score"]),
            float(item[1]["prosody_score"]),
        ),
        reverse=True,
    )
    selected_path, selected_record = accepted[0]
    return selected_path, records, selected_record


def make_ear_stereo(signal: np.ndarray, voice_number: int) -> np.ndarray:
    """Near-ear stereo: small ITD, head-shadow low-pass and level difference."""
    x = np.asarray(signal, dtype=np.float32)
    side_left = voice_number % 2 == 1
    delay_samples = int(round(TARGET_SR * 0.00024))
    near = x.copy()
    far = np.pad(x, (delay_samples, 0))[: x.size]
    if far.size > 128:
        far = sosfiltfilt(
            butter(2, 6_200.0 / (TARGET_SR / 2.0), btype="lowpass", output="sos"),
            far,
        ).astype(np.float32)
    near *= 10.0 ** (0.45 / 20.0)
    far *= 10.0 ** (-1.55 / 20.0)
    stereo = np.column_stack((near, far)) if side_left else np.column_stack((far, near))
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    limit = 10.0 ** (-1.0 / 20.0)
    if peak > limit and peak > 0.0:
        stereo *= limit / peak
    return stereo.astype(np.float32)


def validate_wav(path: Path, channels: int) -> dict[str, Any]:
    info = sf.info(path)
    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    if int(info.samplerate) != TARGET_SR:
        raise RuntimeError(f"sample rate mismatch: {path} -> {info.samplerate}")
    if int(info.channels) != channels:
        raise RuntimeError(f"channel mismatch: {path} -> {info.channels}")
    if info.subtype != "PCM_24":
        raise RuntimeError(f"subtype mismatch: {path} -> {info.subtype}")
    if data.size == 0 or data.shape[0] / sample_rate < 0.5:
        raise RuntimeError(f"empty/short WAV: {path}")
    decode = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if decode.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed: {path}: {decode.stderr[-500:]!r}")
    return {
        "file": path.relative_to(OUT).as_posix(),
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "subtype": info.subtype,
        "duration_sec": round(float(data.shape[0] / sample_rate), 3),
        "sha256": sha256(path),
    }


def main() -> None:
    try:
        log(f"生成開始: {VOICE['folder']} / checkpoint={CHECKPOINT}")
        whisper = load_whisper()
        runtime = build_runtime()

        anchor_caption = f"{VOICE['caption']} {ANCHOR_CAPTION} {QUALITY_CAPTION}"
        anchor_path, anchor_candidates, anchor_selected = generate_best(
            runtime,
            whisper,
            label="基準声",
            target_text=ANCHOR_TEXT,
            caption=anchor_caption,
            reference=None,
            base_seed=int(VOICE["seed"]),
            base_duration_scale=1.0,
            target_rms=-20.0,
            mode="neutral",
            output_directory=ANCHOR_DIR,
            anchor_metrics=None,
        )
        anchor_signal, anchor_sample_rate = sf.read(anchor_path, dtype="float32", always_2d=True)
        final_anchor = ANCHOR_DIR / "採用した基準声.wav"
        anchor_mono = transparent_process(np.mean(anchor_signal, axis=1), int(anchor_sample_rate), -20.0)
        sf.write(final_anchor, anchor_mono, TARGET_SR, subtype="PCM_24")
        anchor_metrics = audio_metrics(anchor_mono, TARGET_SR)

        all_candidates = [*anchor_candidates]
        final_rows: list[dict[str, Any]] = []
        for style in STYLES:
            number = int(style["number"])
            label = str(style["label"])
            output_name = (
                f"{number:02d}_{safe_component(label)}_"
                f"{safe_component(str(style['short']))}.wav"
            )
            output_path = MONO_DIR / output_name
            caption = (
                "声質は参照音声と同じ人物として保つ。"
                f"{style['caption']} {QUALITY_CAPTION} "
                "指定された短い台詞だけを、最初から最後まで明瞭に話す。"
                "台詞が終わったら完全に黙り、別の言葉、音節、うめき声、悲鳴を追加しない。"
            )
            selected_path, candidates, selected = generate_best(
                runtime,
                whisper,
                label=label,
                target_text=str(style["text"]),
                caption=caption,
                reference=str(final_anchor.resolve()),
                base_seed=int(VOICE["seed"]) + number * 100_000,
                base_duration_scale=float(style["duration_scale"]),
                target_rms=float(style["target_rms"]),
                mode=str(style["mode"]),
                output_directory=CANDIDATE_DIR / f"{number:02d}_{safe_component(label)}",
                anchor_metrics=anchor_metrics,
            )
            selected_signal, selected_sr = sf.read(selected_path, dtype="float32", always_2d=True)
            final_signal = transparent_process(
                np.mean(selected_signal, axis=1), int(selected_sr), float(style["target_rms"])
            )
            sf.write(output_path, final_signal, TARGET_SR, subtype="PCM_24")
            final_transcript, _ = transcribe(output_path, whisper)
            final_asr = asr_evaluation(str(style["text"]), final_transcript, str(style["mode"]))
            final_metrics = audio_metrics(final_signal, TARGET_SR)
            if int(final_asr["length_delta"]) > 0:
                raise RuntimeError(f"最終WAVに余計な認識文字: {output_path} -> {final_transcript!r}")
            if not integrity_ok(final_metrics):
                raise RuntimeError(f"最終WAVの信号条件不合格: {output_path} -> {final_metrics}")

            final_row = {
                "voice": VOICE["folder"],
                "number": number,
                "label": label,
                "target_text": style["text"],
                "file": output_path.relative_to(OUT).as_posix(),
                "transcript": final_transcript,
                **final_asr,
                **final_metrics,
                "selected_candidate": selected.get("candidate"),
                "selected_asr_ratio": selected.get("asr_ratio"),
                "selected_clarity_score": selected.get("clarity_score"),
                "selected_prosody_score": selected.get("prosody_score"),
                "sha256": sha256(output_path),
            }
            final_rows.append(final_row)
            all_candidates.extend(candidates)

            if number == 9:
                stereo = make_ear_stereo(final_signal, int(VOICE["number"]))
                stereo_path = STEREO_DIR / output_name
                sf.write(stereo_path, stereo, TARGET_SR, subtype="PCM_24")

        write_csv(VALIDATION_DIR / "全候補検査.csv", all_candidates)
        write_csv(VALIDATION_DIR / "最終WAV検査.csv", final_rows)

        wav_checks: list[dict[str, Any]] = []
        mono_files = sorted(MONO_DIR.glob("*.wav"))
        stereo_files = sorted(STEREO_DIR.glob("*.wav"))
        if len(mono_files) != 10:
            raise RuntimeError(f"モノラルWAV数が10ではありません: {len(mono_files)}")
        if len(stereo_files) != 1:
            raise RuntimeError(f"耳元ステレオWAV数が1ではありません: {len(stereo_files)}")
        for path in mono_files:
            wav_checks.append(validate_wav(path, 1))
        for path in stereo_files:
            wav_checks.append(validate_wav(path, 2))
        write_csv(VALIDATION_DIR / "形式・全編デコード検証.csv", wav_checks)

        summary = {
            "voice_index": VOICE_INDEX,
            "voice": VOICE["folder"],
            "checkpoint": CHECKPOINT,
            "num_steps": NUM_STEPS,
            "mono_wav_count": len(mono_files),
            "stereo_wav_count": len(stereo_files),
            "anchor": {
                "text": ANCHOR_TEXT,
                "selected_candidate": anchor_selected.get("candidate"),
                "metrics": anchor_metrics,
            },
            "final_transcripts": [
                {
                    "label": row["label"],
                    "target": row["target_text"],
                    "transcript": row["transcript"],
                    "asr_ratio": row["asr_ratio"],
                    "length_delta": row["length_delta"],
                }
                for row in final_rows
            ],
        }
        (VALIDATION_DIR / "集計.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(f"生成完了: {VOICE['folder']} / 10 mono + 1 stereo")
    except Exception:
        error_text = traceback.format_exc()
        (VALIDATION_DIR / "致命的エラー.txt").write_text(error_text, encoding="utf-8")
        log(error_text)
        raise


if __name__ == "__main__":
    main()
