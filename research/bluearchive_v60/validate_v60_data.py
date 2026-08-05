#!/usr/bin/env python3
import base64, json, zlib
from pathlib import Path
out=Path('artifact_v60_data_validation');out.mkdir(exist_ok=True)
rows=[]
for name in ['reaction','concept','explainer','ss']:
 p=Path(__file__).parent/f'{name}.b64'
 rec={'name':name,'exists':p.exists()}
 try:
  s=p.read_text().strip();rec['chars']=len(s);rec['head']=s[:24];rec['tail']=s[-24:]
  raw=base64.b64decode(s,validate=True);rec['raw_bytes']=len(raw)
  data=json.loads(zlib.decompress(raw).decode('utf-8'));rec['records']=len(data);rec['status']='ok'
 except Exception as e:
  rec['status']='error';rec['error']=repr(e)
 rows.append(rec)
(out/'validation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
if any(r['status']!='ok' for r in rows):raise SystemExit(1)
