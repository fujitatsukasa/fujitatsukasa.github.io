#!/usr/bin/env python3
from __future__ import annotations

import package_irodori_v4_fresh as base

EASY_LINES = {
    1: "ねえ、今日、カフェに行かない？",
    2: "こちらを、見てください。",
    3: "ごめん、まだ、眠いの。",
    4: "今日は、少し、つらいの。",
    5: "もう、その話は、やめて。",
    6: "待って。そこに、誰かいる。",
    7: "来てくれたんだ。うれしい。",
    8: "無理しなくて、いいよ。",
    9: "聞こえる？ ゆっくり、力を抜いて。",
    10: "ふふっ。ちゃんと、分かってるよ。",
}
for number, text in EASY_LINES.items():
    base.STYLES[number]["text"] = text

if __name__ == "__main__":
    base.main()
