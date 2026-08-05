#!/usr/bin/env python3
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
import edge_tts
from pydub import AudioSegment
from pydub.generators import Sine

IDX=int(sys.argv[1])
LINES={
94:("先生","ホシノの昼寝中なら静かだし。"),
95:("ホシノ","おじさんの昼寝を会議室にしないでよ～。"),
96:("ノア","先生は、予定を消す代わりに重ねようとしています。"),
97:("先生","予定は約束だから。"),
98:("ヒナ","約束したのは、休むこと。"),
99:("先生","……"),
100:("ヒナ","私の予約は、二十三時五十分から十分だけ。"),
101:("先生","何をする予定だったの？"),
102:("ヒナ","「お疲れ様」と言うだけ。返事もいらない。"),
103:("先生","それなら、残しても――"),
104:("ヒナ","最初に消す人が必要だから。"),
105:("通知音","ピン。"),
}
VOICE_F="ja-JP-NanamiNeural";VOICE_M="ja-JP-KeitaNeural"
VOICE={
"先生":(VOICE_M,"-5%","-2Hz"),
"ホシノ":(VOICE_F,"-10%","-6Hz"),
"ノア":(VOICE_F,"-2%","+1Hz"),
"ヒナ":(VOICE_F,"-10%","-6Hz"),
}
OUT=Path(f"artifact_v61_ss_line_{IDX}");OUT.mkdir(parents=True,exist_ok=True)
sp,text=LINES[IDX]
out=OUT/f"{IDX:03d}.mp3"
async def synth():
    if IDX==99:
        AudioSegment.silent(duration=900).export(out,format="mp3",bitrate="128k");return
    if IDX==105:
        Sine(880).to_audio_segment(duration=170).fade_out(100).export(out,format="mp3",bitrate="128k");return
    voice,rate,pitch=VOICE[sp]
    errors=[]
    variants=[text,text.replace("～","ー"),text.replace("――","、")]
    for attempt in range(12):
        try:
            t=variants[min(attempt//4,len(variants)-1)]
            await edge_tts.Communicate(text=t,voice=voice,rate=rate,pitch=pitch,connect_timeout=20,receive_timeout=60).save(str(out))
            if out.exists() and out.stat().st_size>500:return
        except Exception as e:
            errors.append(repr(e));await asyncio.sleep(2+attempt)
    # final fallback with neutral voice and simplified punctuation
    simple=text.replace("～","ー").replace("――","、").replace("「","").replace("」","")
    for attempt in range(6):
        try:
            await edge_tts.Communicate(text=simple,voice=VOICE_F,rate="+0%",pitch="+0Hz",connect_timeout=20,receive_timeout=60).save(str(out))
            if out.exists() and out.stat().st_size>500:return
        except Exception as e:
            errors.append(repr(e));await asyncio.sleep(3+attempt)
    raise RuntimeError(errors[-3:])
asyncio.run(synth())
(OUT/"record.json").write_text(json.dumps({"index":IDX,"speaker":sp,"text":text,"bytes":out.stat().st_size},ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"index":IDX,"bytes":out.stat().st_size},ensure_ascii=False))
