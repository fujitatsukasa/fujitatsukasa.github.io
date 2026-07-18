#!/usr/bin/env python3
from __future__ import annotations
import asyncio,base64,csv,json,sys,zlib
from pathlib import Path
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.generators import Sine

VIDEO=sys.argv[1]
HERE=Path(__file__).parent
LINES=json.loads(zlib.decompress(base64.b64decode((HERE/f'v61_{VIDEO}.b64').read_text().strip())).decode('utf-8'))
OUT=Path(f'artifact_v61_audio_{VIDEO}');OUT.mkdir(parents=True,exist_ok=True);(OUT/'lines').mkdir(exist_ok=True)
F='ja-JP-NanamiNeural';M='ja-JP-KeitaNeural'

def voice_for(item,idx):
 sp=str(item.get('speaker') or '')
 style=str(item.get('style') or '')
 if VIDEO=='reaction':
  if sp in ('ナレーション','公式確認','固定コメント'):return F,'-4%','-1Hz'
  if 'コメント' in sp or sp.startswith('@'):return (F,'+4%','+2Hz') if idx%3 else (M,'+3%','-1Hz')
  if sp in ('まとめ見出し','記事コメント'):return M,'+2%','-2Hz'
  if sp in ('↳ 返信','↳ 引用'):return F,'+6%','+4Hz'
  return (M,'+2%','-2Hz') if idx%2 else (F,'+4%','+1Hz')
 if VIDEO=='explainer':
  if sp=='反論':return M,'-2%','-3Hz'
  if sp in ('引用要約','公式確認'):return F,'+0%','+1Hz'
  return F,'-5%','-2Hz'
 mapping={
  '先生':(M,'-4%','-3Hz'),'アロナ':(F,'+9%','+7Hz'),'ユウカ':(F,'-3%','-1Hz'),
  'シロコ':(F,'-8%','-5Hz'),'ノア':(F,'-1%','+2Hz'),'ホシノ':(F,'-10%','-6Hz'),
  'ミカ':(F,'+7%','+4Hz'),'ナギサ':(F,'-3%','+0Hz'),'アル':(F,'+4%','+2Hz'),
  'カヨコ':(F,'-8%','-5Hz'),'ヒナ':(F,'-10%','-6Hz'),'地の文':(F,'-7%','-2Hz'),
  '全員':(F,'+0%','+0Hz')}
 return mapping.get(sp,(F,'+0%','+0Hz'))

async def synth(text,path,voice,rate,pitch):
 last=None
 for n in range(7):
  try:
   await edge_tts.Communicate(text=text,voice=voice,rate=rate,pitch=pitch).save(str(path))
   if path.exists() and path.stat().st_size>500:return
  except Exception as e:last=e
  await asyncio.sleep(1.4*(n+1))
 raise RuntimeError(f'TTS failed {text[:40]}: {last}')

def stamp(ms):
 h=ms//3600000;ms%=3600000;m=ms//60000;ms%=60000;s=ms//1000;z=ms%1000
 return f'{h:02d}:{m:02d}:{s:02d},{z:03d}'

async def main():
 combined=AudioSegment.silent(duration=400);timing=[];srt=[];prev=''
 for idx,item in enumerate(LINES,1):
  text=str(item.get('text','')).strip();speaker=str(item.get('speaker',''));section=str(item.get('section',''))
  if section!=prev and prev:combined+=AudioSegment.silent(duration=700)
  start=len(combined)
  if speaker=='通知音' or text in ('ピン。','ピン、ピン。','ピピピピピピピピ。'):
   seg=Sine(880).to_audio_segment(duration=170).fade_in(10).fade_out(90);voice='beep'
  else:
   p=OUT/'lines'/f'{idx:03d}.mp3';voice,rate,pitch=voice_for(item,idx)
   await synth(text,p,voice,rate,pitch);seg=normalize(AudioSegment.from_file(p)).apply_gain(-4.0)
  combined+=seg;end=len(combined)
  pause=300 if VIDEO!='ss' else 240
  if text.endswith(('。','！','？','…')):pause+=90
  combined+=AudioSegment.silent(duration=pause)
  timing.append({'index':idx,'id':item.get('id'),'speaker':speaker,'section':section,'text':text,'start_ms':start,'end_ms':end,'duration_ms':len(seg),'voice':voice})
  srt.append(f'{idx}\n{stamp(start)} --> {stamp(end)}\n{text}\n')
  prev=section
  if idx%20==0:print(VIDEO,idx,'/',len(LINES),flush=True)
 combined=combined.fade_in(100).fade_out(350)
 combined.export(OUT/f'{VIDEO}_narration.wav',format='wav')
 combined.export(OUT/f'{VIDEO}_narration.mp3',format='mp3',bitrate='192k')
 with (OUT/'timing.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=timing[0].keys());w.writeheader();w.writerows(timing)
 (OUT/f'{VIDEO}.srt').write_text('\n'.join(srt),encoding='utf-8')
 (OUT/'script.json').write_text(json.dumps(LINES,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'summary.json').write_text(json.dumps({'video':VIDEO,'lines':len(LINES),'duration_ms':len(combined),'wav_bytes':(OUT/f'{VIDEO}_narration.wav').stat().st_size,'mp3_bytes':(OUT/f'{VIDEO}_narration.mp3').stat().st_size},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'video':VIDEO,'lines':len(LINES),'duration_ms':len(combined)},ensure_ascii=False))
asyncio.run(main())
