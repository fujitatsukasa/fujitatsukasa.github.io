#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

import build_irodori_v4_mid_high_emotion_asmr as base


def choose_reference_rows_relaxed(rows: list[dict[str, Any]], reference_dir: Path) -> list[Path]:
    """Select three clean reference clips without assuming the 3M rows are emotionally neutral.

    The clone corpus contains long and stylized utterances, so a strict 3-12 second neutral
    gate can leave fewer than three rows. We score every technically usable row, penalize
    explicit emotional markers, and give the already verified rows 20/29/112 a small bonus.
    """
    reference_dir.mkdir(parents=True, exist_ok=True)
    forbidden = re.compile(r"[!！]{2,}|[?？]{2,}|笑|泣|怒|怖|叫|咳|あくび|眠|ため息|ふふ|あは", re.I)
    preferred = {20, 29, 112}
    candidates: list[tuple[float, int, str, Any, dict[str, float]]] = []
    for index, row in enumerate(rows, 1):
        text = str(row.get("text") or "")
        try:
            signal, sample_rate = base.decode_audio_cell(row.get("audio"))
            signal = base.resample_mono(signal, sample_rate, base.TARGET_SR)
            metrics = base.audio_metrics(signal, base.TARGET_SR)
        except Exception:
            continue
        if not 1.8 <= metrics["duration_sec"] <= 32.0:
            continue
        if metrics["clip_ratio"] > 0.003 or metrics["rms_dbfs"] < -44.0:
            continue
        score = base.quality_score(metrics, -19.0)
        score += 0.12 * max(0.0, 1.0 - abs(metrics["duration_sec"] - 9.0) / 18.0)
        score += 0.08 * max(0.0, 1.0 - metrics["silence_ratio"])
        if base.EMOJI_PATTERN.search(text):
            score -= 0.16
        if forbidden.search(text):
            score -= 0.12
        if index in preferred:
            score += 0.20
        candidates.append((score, index, text, signal, metrics))
    if len(candidates) < 3:
        raise RuntimeError(f"not enough technically usable reference rows: {len(candidates)}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[tuple[float, int, str, Any, dict[str, float]]] = []
    normalized_texts: list[str] = []
    for item in candidates:
        normalized = base.normalize_text(item[2])
        if normalized and any(fuzz.ratio(normalized, prior) > 78 for prior in normalized_texts):
            continue
        selected.append(item)
        normalized_texts.append(normalized)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        selected = candidates[:3]

    reference_paths: list[Path] = []
    for order, (_, source_index, text, signal, metrics) in enumerate(selected, 1):
        processed = base.transparent_studio_process(signal, target_rms=-20.0, style_label="参照")
        path = reference_dir / f"参照_{order:02d}.wav"
        base.sf.write(path, processed, base.TARGET_SR, subtype="PCM_24")
        reference_paths.append(path)
        (reference_dir / f"参照_{order:02d}.txt").write_text(
            json.dumps({"source_row": source_index, "text": text, "metrics": metrics}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return reference_paths


base.choose_reference_rows = choose_reference_rows_relaxed

if __name__ == "__main__":
    base.main()
