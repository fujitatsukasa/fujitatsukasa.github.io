#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from rapidfuzz import fuzz

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import build_irodori_clear_voice as base  # noqa: E402
import irodori_clear_rebuild_spec as spec  # noqa: E402

VOICE = base.VOICE
TARGET_SR = base.TARGET_SR
NUM_STEPS = 48
MIN_CANDIDATES = 4
MAX_CANDIDATES = 8
MIN_ACCEPTED = 1


def asr_evaluation(target_text: str, transcript: str, mode: str) -> dict[str, Any]:
    target = base.to_hiragana(target_text)
    actual = base.to_hiragana(transcript)
    ratio = float(fuzz.ratio(target, actual) / 100.0)
    partial = float(fuzz.partial_ratio(target, actual) / 100.0) if actual else 0.0
    length_delta = len(actual) - len(target)
    if mode == "asmr":
        threshold = 0.90
    elif mode == "laugh":
        threshold = 0.90
    else:
        threshold = 0.93
    laugh_ok = mode != "laugh" or "ふふ" in actual
    # 末尾の余計な発話を最優先で拒否するため、正規化後に1文字でも長いものは不採用。
    accepted = (
        ratio >= threshold
        and partial >= 0.95
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
        "accepted": bool(accepted),
    }


def transcribe_and_align(path: Path, target_text: str, whisper: Any) -> tuple[Path, str, dict[str, Any]]:
    """ASRの単語時刻から、目標台詞に最も一致する終端で必ず切り、末尾の幻覚を除く。"""
    transcript, words = base.transcribe(path, whisper)
    original_eval = asr_evaluation(target_text, transcript, "neutral")
    if not words:
        return path, transcript, original_eval

    target = base.to_hiragana(target_text)
    cumulative = ""
    best_score = -1.0
    best_end = 0.0
    for word in words:
        cumulative += str(word["text"])
        normalized = base.to_hiragana(cumulative)
        ratio = float(fuzz.ratio(target, normalized) / 100.0)
        partial = float(fuzz.partial_ratio(target, normalized) / 100.0) if normalized else 0.0
        overshoot = max(0, len(normalized) - len(target))
        undershoot = max(0, len(target) - len(normalized))
        score = 0.72 * ratio + 0.28 * partial - 0.035 * overshoot - 0.006 * undershoot
        if score > best_score:
            best_score = score
            best_end = float(word["end"])

    if best_end <= 0.0 or best_score < 0.82:
        return path, transcript, original_eval

    signal, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(signal, axis=1).astype(np.float32)
    cut = min(mono.size, int((best_end + 0.12) * int(sample_rate)))
    if cut < int(0.7 * int(sample_rate)):
        return path, transcript, original_eval

    aligned_path = path.with_name(path.stem + "_台詞終端整列.wav")
    sf.write(aligned_path, mono[:cut], int(sample_rate), subtype="PCM_24")
    transcript2, _ = base.transcribe(aligned_path, whisper)
    eval2 = asr_evaluation(target_text, transcript2, "neutral")
    # 末尾余分が減り、類似度が大きく悪化しない場合だけ採用。
    if (
        eval2["length_delta"] <= original_eval["length_delta"]
        and eval2["asr_ratio"] >= original_eval["asr_ratio"] - 0.02
    ):
        return aligned_path, transcript2, eval2
    aligned_path.unlink(missing_ok=True)
    return path, transcript, original_eval


def quality_score(metrics: dict[str, float]) -> float:
    duration = float(metrics["duration_sec"])
    duration_score = 1.0 if 1.15 <= duration <= 8.5 else math.exp(-((duration - 4.0) / 3.0) ** 2)
    clip_score = max(0.0, 1.0 - float(metrics["clip_ratio"]) / 0.00015)
    flatness = float(metrics["spectral_flatness"])
    flat_score = math.exp(-((flatness - 0.025) / 0.065) ** 2)
    centroid = float(metrics["spectral_centroid_hz"])
    centroid_score = math.exp(-((centroid - 2600.0) / 1900.0) ** 2)
    high = float(metrics["high_frequency_ratio"])
    high_score = math.exp(-((high - 0.065) / 0.075) ** 2)
    return float(np.clip(
        0.15 * duration_score
        + 0.30 * clip_score
        + 0.15 * flat_score
        + 0.20 * centroid_score
        + 0.20 * high_score,
        0.0,
        1.0,
    ))


def synthesize_auto(
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
        base.SamplingRequest(
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
            max_seconds=10.0,
            max_ref_seconds=8.0,
            max_text_len=None,
            max_caption_len=None,
            num_steps=NUM_STEPS,
            cfg_scale_text=3.7,
            cfg_scale_caption=2.7,
            cfg_scale_speaker=4.7 if reference is not None else 0.0,
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
    base.save_wav(output_path, result.audios[0].float(), result.sample_rate)
    return {
        "seed": int(result.used_seed),
        "sample_rate": int(result.sample_rate),
        "stage_timings": result.stage_timings,
        "total_to_decode": float(result.total_to_decode),
        "messages": [*messages, *result.messages],
    }


def candidate_scales(base_scale: float) -> list[float]:
    multipliers = (0.90, 0.96, 1.00, 1.04, 1.09, 0.85, 1.14, 1.20)
    return [max(0.70, min(1.40, float(base_scale) * multiplier)) for multiplier in multipliers]


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

    for candidate_number, duration_scale in enumerate(candidate_scales(base_duration_scale), 1):
        raw_path = output_directory / f"候補_{candidate_number:02d}_生.wav"
        generation = synthesize_auto(
            runtime,
            text=target_text,
            caption=caption,
            reference=reference,
            seed=base_seed + candidate_number * 1009,
            duration_scale=duration_scale,
            output_path=raw_path,
        )
        aligned_path, first_transcript, _ = transcribe_and_align(raw_path, target_text, whisper)
        raw_signal, raw_sr = sf.read(aligned_path, dtype="float32", always_2d=True)
        processed = base.transparent_process(
            np.mean(raw_signal, axis=1).astype(np.float32),
            int(raw_sr),
            target_rms,
        )
        processed_path = output_directory / f"候補_{candidate_number:02d}_整音.wav"
        sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")

        # 整音後にも単語時刻で再整列する。ここで末尾音声を最終的に落とす。
        final_aligned_path, second_transcript, _ = transcribe_and_align(processed_path, target_text, whisper)
        if final_aligned_path != processed_path:
            aligned_signal, aligned_sr = sf.read(final_aligned_path, dtype="float32", always_2d=True)
            processed = base.transparent_process(
                np.mean(aligned_signal, axis=1).astype(np.float32),
                int(aligned_sr),
                target_rms,
            )
            sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")

        transcript, words = base.transcribe(processed_path, whisper)
        asr = asr_evaluation(target_text, transcript, mode)
        metrics = base.audio_metrics(processed, TARGET_SR)
        quality = quality_score(metrics)
        hard_quality_ok = (
            float(metrics["clip_ratio"]) <= 0.00005
            and float(metrics["spectral_flatness"]) <= 0.17
            and 800.0 <= float(metrics["spectral_centroid_hz"]) <= 6200.0
            and 0.006 <= float(metrics["high_frequency_ratio"]) <= 0.30
            and 1.0 <= float(metrics["duration_sec"]) <= 8.5
        )
        is_accepted = bool(asr["accepted"] and hard_quality_ok)
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
            "hard_quality_ok": hard_quality_ok,
            "accepted": is_accepted,
            "generation": generation,
        }
        records.append(record)
        base.log(
            f"{VOICE['folder']} / {label} / candidate={candidate_number} "
            f"asr={asr['asr_ratio']:.3f} partial={asr['asr_partial_ratio']:.3f} "
            f"delta={asr['length_delta']} quality={quality:.3f} accepted={is_accepted}"
        )
        if is_accepted:
            accepted.append((processed_path, record))
        if candidate_number >= MIN_CANDIDATES and len(accepted) >= MIN_ACCEPTED:
            break
        if candidate_number >= MAX_CANDIDATES:
            break

    if not accepted:
        records.sort(
            key=lambda item: (
                float(item["asr_ratio"]),
                float(item["asr_partial_ratio"]),
                float(item["quality_score"]),
            ),
            reverse=True,
        )
        best = records[0]
        raise RuntimeError(
            f"厳格条件を通る候補がありません: {VOICE['folder']} / {label}; "
            f"best_asr={best['asr_ratio']:.3f}, delta={best['length_delta']}, "
            f"transcript={best['transcript']!r}"
        )

    accepted.sort(
        key=lambda item: (
            float(item[1]["asr_ratio"]),
            float(item[1]["asr_partial_ratio"]),
            float(item[1]["quality_score"]),
        ),
        reverse=True,
    )
    return accepted[0][0], records


def main() -> None:
    base.log(f"明瞭再生成v2開始: {VOICE['folder']}")
    whisper = base.WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
        cpu_threads=max(2, os.cpu_count() or 2),
    )
    runtime = base.build_runtime()

    anchor_path, anchor_records = generate_candidates(
        runtime,
        whisper,
        label="基準声",
        target_text=spec.ANCHOR_TEXT,
        caption=f"{VOICE['caption']} {spec.ANCHOR_STYLE} {spec.QUALITY_STYLE}",
        reference=None,
        base_seed=int(VOICE["seed"]),
        base_duration_scale=float(spec.ANCHOR_DURATION_SCALE),
        target_rms=-19.5,
        mode="neutral",
        output_directory=base.ANCHOR_DIR,
    )
    anchor_signal, anchor_sr = sf.read(anchor_path, dtype="float32", always_2d=True)
    final_anchor = base.ANCHOR_DIR / "採用した基準声.wav"
    sf.write(
        final_anchor,
        np.mean(anchor_signal, axis=1).astype(np.float32),
        int(anchor_sr),
        subtype="PCM_24",
    )

    all_candidate_records: list[dict[str, Any]] = []
    final_records: list[dict[str, Any]] = []
    for style in spec.STYLES:
        style_number = int(style["number"])
        label = str(style["label"])
        caption = (
            "声質は参照音声と同じ人物として保つ。"
            f"{style['caption']} {spec.QUALITY_STYLE} "
            "発音を明瞭にし、指定された短い台詞だけを話す。"
            "台詞が終わったら完全に黙り、別の言葉、音節、うめき声、悲鳴、笑い声を追加しない。"
        )
        selected_path, records = generate_candidates(
            runtime,
            whisper,
            label=label,
            target_text=str(style["text"]),
            caption=caption,
            reference=str(final_anchor.resolve()),
            base_seed=int(VOICE["seed"]) + style_number * 100000,
            base_duration_scale=float(style["duration_scale"]),
            target_rms=float(style["target_rms"]),
            mode=str(style["mode"]),
            output_directory=base.CANDIDATE_DIR / f"{style_number:02d}_{base.safe_component(label)}",
        )
        all_candidate_records.extend(
            [
                {
                    "voice": VOICE["folder"],
                    "style_number": style_number,
                    "style_label": label,
                    **record,
                }
                for record in records
            ]
        )

        output_name = (
            f"{style_number:02d}_{base.safe_component(label)}_"
            f"{base.safe_component(style['short'])}.wav"
        )
        final_path = base.MONO_DIR / output_name
        signal, sample_rate = sf.read(selected_path, dtype="float32", always_2d=True)
        mono = np.mean(signal, axis=1).astype(np.float32)
        sf.write(final_path, mono, int(sample_rate), subtype="PCM_24")

        transcript, _ = base.transcribe(final_path, whisper)
        final_asr = asr_evaluation(str(style["text"]), transcript, str(style["mode"]))
        if not final_asr["accepted"]:
            raise RuntimeError(
                f"最終WAVのASR再検査に失敗: {output_name}: {transcript!r}"
            )
        metrics = base.audio_metrics(mono, int(sample_rate))
        final_records.append(
            {
                "voice_number": VOICE["number"],
                "voice_folder": VOICE["folder"],
                "style_number": style_number,
                "style_label": label,
                "target_text": style["text"],
                "file": str(final_path.relative_to(base.OUT)),
                "transcript": transcript,
                **final_asr,
                **metrics,
            }
        )
        if str(style["mode"]) == "asmr":
            sf.write(
                base.ASMR_DIR / output_name,
                base.make_ear_stereo(mono, int(VOICE["number"])),
                TARGET_SR,
                subtype="PCM_24",
            )

    base.write_csv(base.VALIDATION_DIR / "全候補検査.csv", all_candidate_records)
    base.write_csv(base.VALIDATION_DIR / "最終WAV検査.csv", final_records)
    base.write_csv(base.VALIDATION_DIR / "基準声候補検査.csv", anchor_records)
    summary = {
        "checkpoint": base.CHECKPOINT,
        "voice": VOICE,
        "num_steps": NUM_STEPS,
        "guidance": {
            "text": 3.7,
            "caption": 2.7,
            "speaker": 4.7,
            "mode": "independent",
        },
        "schedule": "linear",
        "emoji_in_input": False,
        "automatic_duration_predictor": True,
        "strict_asr_required": True,
        "positive_tail_length_allowed": 0,
        "final_mono_wavs": len(final_records),
        "asmr_stereo_wavs": len(list(base.ASMR_DIR.glob("*.wav"))),
        "human_listening": False,
    }
    (base.VALIDATION_DIR / "集計.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (base.VALIDATION_DIR / "生成条件.txt").write_text(
        "旧版の旧合成話者参照、20ステップ、Sway、高いcaption CFG、絵文字、長い台詞、"
        "話法に合わない後付け命名を廃止。\n"
        "600M-v3-VoiceDesignで基準声から作り直し、48ステップ・linear・v3自動時間予測・"
        "短いひらがな台詞・低いcaption CFGで再生成。\n"
        "ASR単語時刻で目標台詞の終端へ波形を切り、正規化後に1文字でも余計な末尾がある音声は不採用。\n"
        "ASR・帯域・クリップ条件を通らない場合は成果物を作らずジョブ失敗。\n",
        encoding="utf-8",
    )
    base.log(
        f"明瞭再生成v2完了: {VOICE['folder']} "
        f"mono={len(final_records)} asmr={len(list(base.ASMR_DIR.glob('*.wav')))}"
    )


if __name__ == "__main__":
    main()
