#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from rapidfuzz import fuzz

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import build_irodori_clear_voice_v2 as v2  # noqa: E402


def asr_evaluation(target_text: str, transcript: str, mode: str) -> dict[str, Any]:
    target = v2.base.to_hiragana(target_text)
    actual = v2.base.to_hiragana(transcript)
    ratio = float(fuzz.ratio(target, actual) / 100.0)
    partial = float(fuzz.partial_ratio(target, actual) / 100.0) if actual else 0.0
    length_delta = len(actual) - len(target)
    threshold = 0.88 if mode in {"asmr", "laugh"} else 0.90
    laugh_ok = mode != "laugh" or "ふふ" in actual
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
    """単語時刻の全連続区間を探索し、先頭のフィラーと末尾の幻覚を両方切る。"""
    transcript, words = v2.base.transcribe(path, whisper)
    original_eval = asr_evaluation(target_text, transcript, "neutral")
    if not words:
        return path, transcript, original_eval

    target = v2.base.to_hiragana(target_text)
    best_score = -1.0
    best_start = 0.0
    best_end = 0.0
    best_normalized = ""
    word_count = len(words)
    for start_index in range(word_count):
        cumulative = ""
        for end_index in range(start_index, word_count):
            cumulative += str(words[end_index]["text"])
            normalized = v2.base.to_hiragana(cumulative)
            if not normalized:
                continue
            ratio = float(fuzz.ratio(target, normalized) / 100.0)
            partial = float(fuzz.partial_ratio(target, normalized) / 100.0)
            overshoot = max(0, len(normalized) - len(target))
            undershoot = max(0, len(target) - len(normalized))
            score = (
                0.73 * ratio
                + 0.27 * partial
                - 0.050 * overshoot
                - 0.006 * undershoot
            )
            # 同点なら、目標長に近く、より後ろまで到達した区間を選ぶ。
            if score > best_score + 1e-9 or (
                abs(score - best_score) <= 1e-9
                and abs(len(normalized) - len(target)) < abs(len(best_normalized) - len(target))
            ):
                best_score = score
                best_start = float(words[start_index]["start"])
                best_end = float(words[end_index]["end"])
                best_normalized = normalized

    if best_end <= best_start or best_score < 0.78:
        return path, transcript, original_eval

    signal, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(signal, axis=1).astype(np.float32)
    start_sample = max(0, int((best_start - 0.07) * int(sample_rate)))
    end_sample = min(mono.size, int((best_end + 0.12) * int(sample_rate)))
    if end_sample - start_sample < int(0.65 * int(sample_rate)):
        return path, transcript, original_eval

    aligned_path = path.with_name(path.stem + "_台詞区間整列.wav")
    sf.write(aligned_path, mono[start_sample:end_sample], int(sample_rate), subtype="PCM_24")
    transcript2, _ = v2.base.transcribe(aligned_path, whisper)
    eval2 = asr_evaluation(target_text, transcript2, "neutral")

    original_distance = abs(int(original_eval["length_delta"]))
    aligned_distance = abs(int(eval2["length_delta"]))
    if (
        eval2["asr_ratio"] >= original_eval["asr_ratio"] - 0.025
        and aligned_distance <= original_distance
        and eval2["length_delta"] <= original_eval["length_delta"]
    ):
        return aligned_path, transcript2, eval2
    aligned_path.unlink(missing_ok=True)
    return path, transcript, original_eval


# v2モジュール内のgenerate_candidates/mainが参照する関数を差し替える。
v2.asr_evaluation = asr_evaluation
v2.transcribe_and_align = transcribe_and_align


if __name__ == "__main__":
    v2.main()
