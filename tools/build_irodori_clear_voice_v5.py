#!/usr/bin/env python3
from __future__ import annotations

import time

import build_irodori_clear_voice_v4 as v4


OriginalWhisperModel = v4.base.WhisperModel


class RetryingWhisperModel:
    def __new__(cls, *args, **kwargs):
        last_error: Exception | None = None
        for attempt in range(1, 9):
            try:
                return OriginalWhisperModel(*args, **kwargs)
            except Exception as error:
                last_error = error
                wait_seconds = min(180, 20 * attempt)
                v4.base.log(
                    f"Whisperモデル取得失敗 attempt={attempt}/8: {error!r}; "
                    f"{wait_seconds}秒後に再試行"
                )
                time.sleep(wait_seconds)
        assert last_error is not None
        raise last_error


# v2.main() resolves WhisperModel through the base module.
v4.base.WhisperModel = RetryingWhisperModel


if __name__ == "__main__":
    v4.v2.main()
