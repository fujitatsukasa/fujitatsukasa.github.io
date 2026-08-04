#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import build_irodori_clear_voice_v3 as v3  # noqa: E402

v2 = v3.v2
base = v2.base
VOICE = v2.VOICE
TARGET_SR = v2.TARGET_SR
MIN_CANDIDATES = 3
MAX_CANDIDATES = 6


def broad_integrity_gate(metrics: dict[str, float]) -> bool:
    """Reject only actual corruption, clipping, silence, or implausible bandwidth.

    Spectral descriptors vary greatly for high-pitched, whispered, sleepy and sad speech.
    They are used for ranking, not as narrow absolute rejection bands.
    """
    duration = float(metrics["duration_sec"])
    peak_dbfs = float(metrics["peak_dbfs"])
    rms_dbfs = float(metrics["rms_dbfs"])
    clip_ratio = float(metrics["clip_ratio"])
    flatness = float(metrics["spectral_flatness"])
    centroid = float(metrics["spectral_centroid_hz"])
    high_ratio = float(metrics["high_frequency_ratio"])
    return bool(
        0.65 <= duration <= 9.5
        and -45.0 <= rms_dbfs <= -8.0
        and -12.0 <= peak_dbfs <= -0.05
        and clip_ratio <= 0.00010
        and 0.0 <= flatness <= 0.40
        and 250.0 <= centroid <= 8500.0
        and 0.0 <= high_ratio <= 0.45
    )


def clarity_rank(metrics: dict[str, float]) -> float:
    """Soft ranking for audible clarity without falsely rejecting quiet/whisper styles."""
    centroid = float(metrics["spectral_centroid_hz"])
    high = float(metrics["high_frequency_ratio"])
    flatness = float(metrics["spectral_flatness"])
    clip = float(metrics["clip_ratio"])
    # Broad optima: presence around 2.8 kHz, some high-band energy, low noise-like flatness.
    presence = float(np.exp(-((centroid - 2800.0) / 2300.0) ** 2))
    air = float(np.exp(-((high - 0.070) / 0.090) ** 2))
    smoothness = float(np.exp(-((flatness - 0.025) / 0.11) ** 2))
    clean_peak = max(0.0, 1.0 - clip / 0.00010)
    return float(np.clip(0.36 * presence + 0.24 * air + 0.25 * smoothness + 0.15 * clean_peak, 0.0, 1.0))


def generate_candidates(
    runtime: Any,
    whisper: Any,
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
) -> tuple[Path, list[dict[str, Any]]]:
    output_directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    accepted: list[tuple[Path, dict[str, Any]]] = []

    scales = v2.candidate_scales(base_duration_scale)[:MAX_CANDIDATES]
    for candidate_number, duration_scale in enumerate(scales, 1):
        raw_path = output_directory / f"候補_{candidate_number:02d}_生.wav"
        generation = v2.synthesize_auto(
            runtime,
            text=target_text,
            caption=caption,
            reference=reference,
            seed=base_seed + candidate_number * 1009,
            duration_scale=duration_scale,
            output_path=raw_path,
        )

        # Search all word spans, cutting both leading filler and trailing hallucination.
        aligned_path, first_transcript, _ = v3.transcribe_and_align(raw_path, target_text, whisper)
        raw_signal, raw_sr = sf.read(aligned_path, dtype="float32", always_2d=True)
        processed = base.transparent_process(
            np.mean(raw_signal, axis=1).astype(np.float32),
            int(raw_sr),
            target_rms,
        )
        processed_path = output_directory / f"候補_{candidate_number:02d}_整音.wav"
        sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")

        # Align again after processing so the delivered file contains only the requested line.
        final_aligned_path, second_transcript, _ = v3.transcribe_and_align(
            processed_path, target_text, whisper
        )
        if final_aligned_path != processed_path:
            aligned_signal, aligned_sr = sf.read(
                final_aligned_path, dtype="float32", always_2d=True
            )
            processed = base.transparent_process(
                np.mean(aligned_signal, axis=1).astype(np.float32),
                int(aligned_sr),
                target_rms,
            )
            sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")

        transcript, words = base.transcribe(processed_path, whisper)
        asr = v3.asr_evaluation(target_text, transcript, mode)
        metrics = base.audio_metrics(processed, TARGET_SR)
        quality = v2.quality_score(metrics)
        clarity = clarity_rank(metrics)
        integrity_ok = broad_integrity_gate(metrics)
        is_accepted = bool(asr["accepted"] and integrity_ok)
        record = {
            "label": label,
            "candidate": candidate_number,
            "duration_scale": duration_scale,
            "raw_path": str(raw_path),
            "processed_path": str(processed_path),
            "first_transcript": first_transcript,
            "second_transcript": second_transcript,
            "transcript": transcript,
            "word_count": len(words),
            **asr,
            **metrics,
            "quality_score": quality,
            "clarity_rank": clarity,
            "integrity_ok": integrity_ok,
            "accepted": is_accepted,
            "generation": generation,
        }
        records.append(record)
        base.log(
            f"{VOICE['folder']} / {label} / candidate={candidate_number} "
            f"asr={asr['asr_ratio']:.3f} partial={asr['asr_partial_ratio']:.3f} "
            f"delta={asr['length_delta']} clarity={clarity:.3f} accepted={is_accepted}"
        )
        if is_accepted:
            accepted.append((processed_path, record))
        if candidate_number >= MIN_CANDIDATES and accepted:
            break

    if not accepted:
        records.sort(
            key=lambda item: (
                float(item["asr_ratio"]),
                float(item["asr_partial_ratio"]),
                float(item["clarity_rank"]),
            ),
            reverse=True,
        )
        best = records[0]
        raise RuntimeError(
            f"ASRと信号健全性を同時に満たす候補がありません: "
            f"{VOICE['folder']} / {label}; best_asr={best['asr_ratio']:.3f}, "
            f"delta={best['length_delta']}, transcript={best['transcript']!r}, "
            f"metrics={{'rms': {best['rms_dbfs']}, 'centroid': {best['spectral_centroid_hz']}, "
            f"'flatness': {best['spectral_flatness']}, 'high': {best['high_frequency_ratio']}}}"
        )

    # Exact reading first; then prefer the clearest intact candidate.
    accepted.sort(
        key=lambda item: (
            float(item[1]["asr_ratio"]),
            float(item[1]["asr_partial_ratio"]),
            -abs(int(item[1]["length_delta"])),
            float(item[1]["clarity_rank"]),
            float(item[1]["quality_score"]),
        ),
        reverse=True,
    )
    return accepted[0][0], records


# v2.main resolves this global in the v2 module.
v2.generate_candidates = generate_candidates


if __name__ == "__main__":
    v2.main()
