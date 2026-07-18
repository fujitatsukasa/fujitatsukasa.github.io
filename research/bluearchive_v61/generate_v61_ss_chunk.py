#!/usr/bin/env python3
from __future__ import annotations
import asyncio,base64,csv,json,sys,zlib
from pathlib import Path
import edge_tts
from pydub.generators import Sine

CHUNK=int(sys.argv[1]);HERE=Path(__file__).parent
LINES=json.loads(zlib.decompress(base64.b64decode((HERE/'v61_ss.b64').read_text().strip())).decode('utf-8'))
N=4;start=(len(LINES)*CHUNK)//N;end=(len(LINES)*(CHUNK+1))//N
OUT=Path(f'artifact_v61_ss_chunk_{CHUNK}');OUT.mkdir(exist_ok=True);(OUT/'lines').mkdir(exist_ok=True)
F='ja-JP-NanamiNeural';M='ja-JP-KeitaNeural'
MAP={'先生':(M,'-4%','-3Hz'),'アロナ':(F,'+9%','+7Hz'),'ユウカ':(F,'-3%','-1Hz'),'シロコ':(F,'-8%','-5Hz'),'ノア':(F,'-1%','+2Hz'),'ホシノ':(F,'-10%','-6Hz'),'ミカ':(F,'+7%','+4Hz'),'ナギサ':(F,'-3%','+0Hz'),'アル':(F,'+4%','+2Hz'),'カヨコ':(F,'-8%','-5Hz'),'ヒナ':(F,'-10%','-6Hz'),'地の文':(F,'-7%','-2Hz'),'全員':(F,'+0%','+0Hz')}
async def synth(text,path,voice,rate,pitch):
 last=None
 for n in range(12):
  try:
   await edge_tts.Communicate(text=text,voice=voice,rate=rate,pitch=pitch).save(str(path))
   if path.exists() and path.stat().st_size>500:return
  except Exception as e:last=e
  await asyncio.sleep(2+n*1.1)
 raise RuntimeError(f'{text[:50]}: {last}')
async def main():
 rows=[]
 for global_idx in range(start,end):
  item=LINES[global_idx];text=str(item.get('text','')).strip();sp=str(item.get('speaker',''));p=OUT/'lines'/f'{global_idx+1:03d}.mp3'
  if sp=='通知音' or text in ('ピン。','ピン、ピン。','ピピピピピピピピ。'):
   Sine(880).to_audio_segment(duration=170).export(p,format='mp3',bitrate='128k');voice='beep'
  else:
   voice,rate,pitch=MAP.get(sp,(F,'+0%','+0Hz'));await synth(text,p,voice,rate,pitch)
  rows.append({'index':global_idx+1,'id':item.get('id'),'speaker':sp,'section':item.get('section'),'text':text,'file':str(p.relative_to(OUT)),'voice':voice})
  print(CHUNK,global_idx+1,'/',end,flush=True)
 with (OUT/'manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 (OUT/'summary.json').write_text(json.dumps({'chunk':CHUNK,'start_index':start+1,'end_index':end,'lines':len(rows)},ensure_ascii=False,indent=2),encoding='utf-8')
asyncio.run(main())
