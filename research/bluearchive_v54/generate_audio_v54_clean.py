#!/usr/bin/env python3
from __future__ import annotations
import asyncio, base64, csv, json, zlib
from pathlib import Path
import edge_tts
from pydub import AudioSegment

OUT=Path('artifact_bluearchive_audio_v54_clean'); OUT.mkdir(parents=True,exist_ok=True)
CHUNKS=[
"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"
]
SCRIPTS=json.loads(zlib.decompress(base64.b64decode(''.join(CHUNKS))).decode('utf-8'))
VOICE={
'編集部':('ja-JP-NanamiNeural','-4%','-1Hz'),'解説':('ja-JP-NanamiNeural','-6%','-1Hz'),'地の文':('ja-JP-NanamiNeural','-8%','-2Hz'),
'キサキ':('ja-JP-NanamiNeural','-13%','-5Hz'),'シュン':('ja-JP-NanamiNeural','-5%','+3Hz'),'係の生徒':('ja-JP-NanamiNeural','+3%','+4Hz'),
'コメント':('ja-JP-KeitaNeural','+2%','+1Hz'),'返信':('ja-JP-KeitaNeural','+5%','+2Hz'),'別の返信':('ja-JP-KeitaNeural','+1%','-1Hz'),
'新任':('ja-JP-KeitaNeural','+3%','+3Hz'),'質問':('ja-JP-KeitaNeural','0%','+2Hz')}

def ts(ms):
 h,r=divmod(ms,3600000); m,r=divmod(r,60000); s,x=divmod(r,1000); return f'{h:02d}:{m:02d}:{s:02d},{x:03d}'
async def say(text,path,voice,rate,pitch):
 for i in range(4):
  try:
   await edge_tts.Communicate(text=text,voice=voice,rate=rate,pitch=pitch).save(str(path))
   if path.exists() and path.stat().st_size>500:return
  except Exception:
   if i==3:raise
   await asyncio.sleep(1+i)
async def build(name,rows):
 work=OUT/name; work.mkdir(exist_ok=True)
 mix=AudioSegment.silent(450); meta=[]; subs=[]
 for i,row in enumerate(rows,1):
  sp=row['speaker']; text=row['text']; voice,rate,pitch=VOICE.get(sp,('ja-JP-NanamiNeural','0%','0Hz'))
  p=work/f'{i:03d}.mp3'; await say(text,p,voice,rate,pitch); seg=AudioSegment.from_file(p)
  a=len(mix); mix+=seg; b=len(mix); mix+=AudioSegment.silent(420 if sp in {'編集部','解説','地の文'} else 300)
  meta.append({'index':i,'speaker':sp,'text':text,'start_ms':a,'end_ms':b,'duration_ms':len(seg),'voice':voice,'rate':rate,'pitch':pitch})
  subs.append((a,b,sp,text))
 mix+=AudioSegment.silent(700)
 mix.export(OUT/f'{name}_ナレーション.mp3',format='mp3',bitrate='192k'); mix.export(OUT/f'{name}_ナレーション.wav',format='wav')
 with (OUT/f'{name}_字幕.srt').open('w',encoding='utf-8') as f:
  for i,(a,b,sp,text) in enumerate(subs,1):f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{sp}：{text}\n\n')
 with (OUT/f'{name}_音声区間.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(meta[0]));w.writeheader();w.writerows(meta)
 return {'name':name,'lines':len(rows),'duration_ms':len(mix)}
async def main():
 result=[]
 for name in ('reaction','explanation','ss'):result.append(await build(name,SCRIPTS[name]))
 (OUT/'audio_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(result)
asyncio.run(main())
