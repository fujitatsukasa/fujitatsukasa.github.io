#!/usr/bin/env python3
from __future__ import annotations

import finish_irodori_final_pack as base

# The first completion run used an anchor sentence long enough to hit the
# runtime's 10-second maximum. The audio and ASR were both correct, but the
# generic <=9.5-second integrity gate rejected it. A shorter neutral sentence
# gives the same speaker reference purpose without forcing a clipped duration.
base.ANCHOR_TEXT = "おはよう。今日はゆっくり始めようね。"

if __name__ == "__main__":
    base.main()
