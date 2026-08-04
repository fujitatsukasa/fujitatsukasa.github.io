#!/usr/bin/env python3
from __future__ import annotations

import time
import unicodedata

import build_irodori_clear_voice_v4 as v4

v2 = v4.v2
v3 = v4.v3
base = v4.base
spec = v2.spec

# Japanese ASR often writes correct kanji whose generic dictionary reading is
# ambiguous (e.g. 辛い -> からい), even when the spoken reading is つらい.
# Normalize the exact vocabulary used by this fixed evaluation set before
# kana conversion so valid, intelligible speech is not rejected by the checker.
REPLACEMENTS = {
    "辛い": "つらい",
    "良い": "いい",
    "大丈夫": "だいじょうぶ",
    "分かって": "わかって",
    "分かる": "わかる",
    "来て": "きて",
    "今日は": "きょうは",
    "今日": "きょう",
    "確認": "かくにん",
    "同じ": "おなじ",
    "無理": "むり",
    "聞こえる": "きこえる",
    "力": "ちから",
    "眠い": "ねむい",
    "何か": "なにか",
}

ORIGINAL_TO_HIRAGANA = base.to_hiragana


def normalized_to_hiragana(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    for source, replacement in REPLACEMENTS.items():
        text = text.replace(source, replacement)
    return ORIGINAL_TO_HIRAGANA(text)


base.to_hiragana = normalized_to_hiragana

# A shorter neutral anchor prevents otherwise clean high voices from being
# discarded merely because ASR omitted the optional phrase "きょうも".
spec.ANCHOR_TEXT = "おはよう。ゆっくり、はじめようね。"

# Re-export the same strict no-positive-tail ASR policy after vocabulary
# normalization. Patch both modules because v2.main resolves the final check
# through v2, while v4 candidate selection resolves it through v3.
def asr_evaluation(target_text: str, transcript: str, mode: str):
    target = base.to_hiragana(target_text)
    actual = base.to_hiragana(transcript)
    from rapidfuzz import fuzz

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


v3.asr_evaluation = asr_evaluation
v2.asr_evaluation = asr_evaluation

# HF may temporarily rate-limit the shared Whisper model when recovery jobs
# start together. Retry instead of losing a clean multi-hour synthesis job.
OriginalWhisperModel = base.WhisperModel


class RetryingWhisperModel:
    def __new__(cls, *args, **kwargs):
        last_error: Exception | None = None
        for attempt in range(1, 9):
            try:
                return OriginalWhisperModel(*args, **kwargs)
            except Exception as error:
                last_error = error
                wait_seconds = min(180, 20 * attempt)
                base.log(
                    f"Whisperモデル取得失敗 attempt={attempt}/8: {error!r}; "
                    f"{wait_seconds}秒後に再試行"
                )
                time.sleep(wait_seconds)
        assert last_error is not None
        raise last_error


base.WhisperModel = RetryingWhisperModel


if __name__ == "__main__":
    v2.main()
