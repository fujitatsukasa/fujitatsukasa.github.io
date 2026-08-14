#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

import generate_irodori_final_delivery as base

# Generate enough alternatives to select acting, not merely the first readable take.
base.MIN_CANDIDATES = 6
base.MAX_CANDIDATES = 6

# The original delivery run proved pronunciation, but several takes were too neutral.
# Add Irodori's supported emoji cues and stronger, explicit acting constraints.
for style in base.STYLES:
    mode = str(style["mode"])
    if mode == "sleepy":
        style["text"] = "ん……ごめん、まだ、ねむいの。🥱"
        style["duration_scale"] = 1.24
        style["caption"] += " 声の立ち上がりを弱くし、息を少し含ませ、眠気が誰にでも分かるほど明確にする。"
    elif mode == "sad":
        style["text"] = "きょうは……すこし、つらいの。😢"
        style["duration_scale"] = 1.16
        style["caption"] += " 涙をこらえて声が弱く震えるが、子音と母音は崩さない。"
    elif mode == "angry":
        style["text"] = "もう！ おなじことは、しないで。😠"
        style["duration_scale"] = 0.94
        style["caption"] += " 冒頭の『もう』と『しないで』へ明確な怒気を置き、普通の会話には戻さない。"
    elif mode == "fear":
        style["text"] = "まって……そこに、だれか、いる！😰"
        style["duration_scale"] = 0.91
        style["caption"] += " 恐怖で息が浅く、声の高さと揺れが明確に上がる。平静な読み上げにしない。"
    elif mode == "happy":
        style["text"] = "あえて、うれしい！😊"
        style["duration_scale"] = 0.91
        style["caption"] += " 喜びで声が自然に弾み、明るい笑顔がはっきり聞こえる。"
    elif mode == "gentle":
        style["caption"] += " 相手を安心させる温かさを語尾まで保ち、無感情に読まない。"
    elif mode == "asmr":
        style["text"] = "きこえる？ ゆっくり、いきをして。👂😮‍💨"
        style["duration_scale"] = 1.25
        style["caption"] += " 通常発声ではなく、耳元の小さなささやきとして一貫させる。"
    elif mode == "laugh":
        style["text"] = "ふふふっ。ちゃんと、わかってるよ。🤭"
        style["duration_scale"] = 1.08
        style["caption"] += " 冒頭に聞き間違えない短い笑い声を実際に入れ、微笑みを保って台詞へつなぐ。"

_original_generate_best = base.generate_best
_original_clarity_score = base.clarity_score

# Among takes that are all readable and technically healthy, prioritize acting.
# Integrity and ASR are still hard gates in the base generator.
def acting_selection_clarity(metrics: dict[str, float]) -> float:
    return 1.0 if base.integrity_ok(metrics) else _original_clarity_score(metrics)


base.clarity_score = acting_selection_clarity

PROSODY_MINIMUMS = {
    "sleepy": 0.62,
    "sad": 0.58,
    "angry": 0.52,
    "fear": 0.38,
    "happy": 0.48,
    "gentle": 0.58,
    "asmr": 0.65,
    "laugh": 0.45,
}


def generate_best_with_acting_retry(
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
    anchor_metrics: dict[str, float] | None,
):
    attempts: list[tuple[Path, list[dict[str, Any]], dict[str, Any]]] = []
    rounds = 1 if mode in {"neutral", "polite"} or reference is None else 2
    for round_number in range(1, rounds + 1):
        stronger_caption = caption
        if round_number == 2:
            stronger_caption += (
                " 発音の明瞭さを維持したまま、指定された感情と話し方を一段強く、"
                "冒頭から語尾まで一貫して表現する。"
            )
        result = _original_generate_best(
            runtime,
            whisper,
            label=label,
            target_text=target_text,
            caption=stronger_caption,
            reference=reference,
            base_seed=base_seed + (round_number - 1) * 9_000_001,
            base_duration_scale=base_duration_scale,
            target_rms=target_rms,
            mode=mode,
            output_directory=output_directory / f"演技試行_{round_number}",
            anchor_metrics=anchor_metrics,
        )
        attempts.append(result)
        selected = result[2]
        minimum = PROSODY_MINIMUMS.get(mode, 0.0)
        laugh_ok = mode != "laugh" or bool(selected.get("laugh_ok"))
        if float(selected.get("prosody_score") or 0.0) >= minimum and laugh_ok:
            break

    # Prefer an actually accepted reading, then the strongest acting score.
    viable = [
        item for item in attempts
        if bool(item[2].get("integrity_ok"))
        and int(item[2].get("length_delta") or 0) <= 0
        and (mode != "laugh" or bool(item[2].get("laugh_ok")))
    ]
    if not viable:
        viable = attempts
    viable.sort(
        key=lambda item: (
            bool(item[2].get("asr_accepted")),
            float(item[2].get("prosody_score") or 0.0),
            float(item[2].get("asr_ratio") or 0.0),
            float(item[2].get("asr_partial_ratio") or 0.0),
        ),
        reverse=True,
    )
    selected_result = viable[0]
    selected = selected_result[2]
    minimum = PROSODY_MINIMUMS.get(mode, 0.0)
    if mode not in {"neutral", "polite"} and reference is not None:
        if float(selected.get("prosody_score") or 0.0) < minimum:
            raise RuntimeError(
                f"演技条件を満たす候補なし: {base.VOICE['folder']} / {label}; "
                f"prosody={selected.get('prosody_score')}, minimum={minimum}"
            )
        if mode == "laugh" and not bool(selected.get("laugh_ok")):
            raise RuntimeError(f"明確な笑い声を含む候補なし: {base.VOICE['folder']} / {label}")

    combined_records: list[dict[str, Any]] = []
    for item in attempts:
        combined_records.extend(item[1])
    return selected_result[0], combined_records, selected


base.generate_best = generate_best_with_acting_retry

if __name__ == "__main__":
    base.main()
