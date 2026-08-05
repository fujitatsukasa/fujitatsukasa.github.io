#!/usr/bin/env python3
from __future__ import annotations
import asyncio,base64,csv,json,sys,zlib
from pathlib import Path
import edge_tts
from pydub.generators import Sine

PART=int(sys.argv[1]);HERE=Path(__file__).parent
LINES=json.loads(zlib.decompress(base64.b64decode((HERE/'v61_ss.b64').read_text().strip())).decode('utf-8'))
# Missing chunk is global lines 94..140 inclusive, split into four parts.
bounds=[(93,105),(105,117),(117,129),(129,140)]
start,end=bounds[PART]
OUT=Path(f'artifact_v61_ss_chunk2_part_{PART}');OUT.mkdir(exist_ok=True);(OUT/'lines').mkdir(exist_ok=True)
F='ja-JP-NanamiNeural';M='ja-JP-KeitaNeural'
MAP={'先生':(M,'-4%','-3Hz'),'アロナ':(F,'+9%','+7Hz'),'ユウカ':(F,'-3%','-1Hz'),'シロコ':(F,'-8%','-5Hz'),'ノア':(F,'-1%','+2Hz'),'ホシノ':(F,'-10%','-6Hz'),'ミカ':(F,'+7%','+4Hz'),'ナギサ':(F,'-3%','+0Hz'),'アル':(F,'+4%','+2Hz'),'カヨコ':(F,'-8%','-5Hz'),'ヒナ':(F,'-10%','-6Hz'),'地の文':(F,'-7%','-2Hz'),'全員':(F,'+0%','+0Hz')}
async def synth(text,path,voice,rate,pitch):
 errors=[]
 attempts=[(voice,rate,pitch),(F,'+0%','+0Hz'),(M,'+0%','+0Hz')]
 for v,r,p in attempts:
  for n in range(8):
   try:
    await edge_tts.Communicate(text=text,voice=v,rate=r,pitch=p).save(str(path))
    if path.exists() and path.stat().st_size>500:return v
   except Exception as e:errors.append(repr(e))
   await asyncio.sleep(1.5+n*.8)
 raise RuntimeError(f'TTS failed {text[:60]}: {errors[-3:]}')
async def main():
 rows=[]
 for gi in range(start,end):
  item=LINES[gi];text=str(item.get('text','')).strip();sp=str(item.get('speaker',''));p=OUT/'lines'/f'{gi+1:03d}.mp3'
  if sp=='通知音' or text in ('ピン。','ピン、ピン。','ピピピピピピピピ。'):
   Sine(880).to_audio_segment(duration=170).export(p,format='mp3',bitrate='128k');used='beep'
  else:
   voice,rate,pitch=MAP.get(sp,(F,'+0%','+0Hz'));used=await synth(text,p,voice,rate,pitch)
  rows.append({'index':gi+1,'id':item.get('id'),'speaker':sp,'section':item.get('section'),'text':text,'file':str(p.relative_to(OUT)),'voice':used})
  print(PART,gi+1,'/',end,flush=True)
 with (OUT/'manifest.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 (OUT/'summary.json').write_text(json.dumps({'part':PART,'start_index':start+1,'end_index':end,'lines':len(rows)},ensure_ascii=False,indent=2),encoding='utf-8')
asyncio.run(main())
