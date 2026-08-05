#!/usr/bin/env python3
from __future__ import annotations
import asyncio, base64, csv, json, sys, zlib
from pathlib import Path
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.generators import Sine

VIDEO=sys.argv[1]
HERE=Path(__file__).parent
LINES=json.loads(zlib.decompress(base64.b64decode((HERE/f"{VIDEO}.b64").read_text().strip())).decode("utf-8"))
OUT=Path(f"artifact_v60_audio_{VIDEO}")
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"lines").mkdir(exist_ok=True)
VOICE_F="ja-JP-NanamiNeural"
VOICE_M="ja-JP-KeitaNeural"

def voice_for(item,idx):
    sp=str(item.get("speaker") or item.get("original_speaker") or "")
    style=item.get("style","")
    if VIDEO in ("reaction","concept"):
        if style in ("official","editor"):
            return VOICE_F,"-5%","+0Hz"
        return (VOICE_M,"+0%","-2Hz") if idx%2 else (VOICE_F,"+2%","+1Hz")
    if VIDEO=="explainer":
        return VOICE_F,"-5%","-1Hz"
    m={
      "先生":(VOICE_M,"-5%","-2Hz"),"アロナ":(VOICE_F,"+10%","+7Hz"),
      "ユウカ":(VOICE_F,"-3%","-1Hz"),"シロコ":(VOICE_F,"-8%","-4Hz"),
      "ホシノ":(VOICE_F,"-10%","-6Hz"),"ミカ":(VOICE_F,"+7%","+4Hz"),
      "ナギサ":(VOICE_F,"-3%","+0Hz"),"アル":(VOICE_F,"+4%","+2Hz"),
      "カヨコ":(VOICE_F,"-8%","-5Hz"),"ノア":(VOICE_F,"-2%","+1Hz"),
      "ヒナ":(VOICE_F,"-10%","-6Hz"),"地の文":(VOICE_F,"-8%","-2Hz"),
      "全員":(VOICE_F,"+0%","+0Hz")
    }
    return m.get(sp,(VOICE_F,"+0%","+0Hz"))

async def synth(text,path,voice,rate,pitch):
    last=None
    for attempt in range(6):
        try:
            await edge_tts.Communicate(text=text,voice=voice,rate=rate,pitch=pitch).save(str(path))
            if path.exists() and path.stat().st_size>500:return
        except Exception as e:last=e
        await asyncio.sleep(1.5*(attempt+1))
    raise RuntimeError(f"TTS failed: {text[:30]}: {last}")

def st(ms):
    h=ms//3600000;ms%=3600000;m=ms//60000;ms%=60000;s=ms//1000;z=ms%1000
    return f"{h:02d}:{m:02d}:{s:02d},{z:03d}"

async def main():
    combined=AudioSegment.silent(duration=350);timing=[];srt=[];prev=None
    for idx,item in enumerate(LINES,1):
        text=str(item.get("text","")).strip()
        speaker=str(item.get("speaker") or item.get("original_speaker") or "")
        section=str(item.get("section") or item.get("act") or "")
        if prev is not None and section!=prev:combined+=AudioSegment.silent(duration=550)
        start=len(combined)
        if speaker=="通知音" or text in ("ピン。","ピン、ピン。","ピピピピピピピピ。"):
            seg=Sine(880).to_audio_segment(duration=160).fade_out(80);voice="beep"
        else:
            p=OUT/"lines"/f"{idx:03d}.mp3";voice,rate,pitch=voice_for(item,idx)
            await synth(text,p,voice,rate,pitch);seg=normalize(AudioSegment.from_file(p)).apply_gain(-3.5)
        combined+=seg;end=len(combined)
        pause=(260 if VIDEO!="ss" else 220)+(80 if text.endswith(("。","！","？","…")) else 0)
        combined+=AudioSegment.silent(duration=pause)
        timing.append({"index":idx,"id":item.get("id") or item.get("line_id"),"speaker":speaker,"section":section,"text":text,"start_ms":start,"end_ms":end,"duration_ms":len(seg),"voice":voice})
        srt.append(f"{idx}\n{st(start)} --> {st(end)}\n{text}\n")
        prev=section
        if idx%20==0:print(VIDEO,idx,"/",len(LINES),flush=True)
    combined=combined.fade_in(100).fade_out(350)
    combined.export(OUT/f"{VIDEO}_narration.wav",format="wav")
    combined.export(OUT/f"{VIDEO}_narration.mp3",format="mp3",bitrate="192k")
    with (OUT/"timing.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=timing[0].keys());w.writeheader();w.writerows(timing)
    (OUT/f"{VIDEO}.srt").write_text("\n".join(srt),encoding="utf-8")
    (OUT/"script.json").write_text(json.dumps(LINES,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"summary.json").write_text(json.dumps({"video":VIDEO,"lines":len(LINES),"duration_ms":len(combined),"wav_bytes":(OUT/f"{VIDEO}_narration.wav").stat().st_size,"mp3_bytes":(OUT/f"{VIDEO}_narration.mp3").stat().st_size},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"video":VIDEO,"lines":len(LINES),"duration_ms":len(combined)},ensure_ascii=False))
asyncio.run(main())
