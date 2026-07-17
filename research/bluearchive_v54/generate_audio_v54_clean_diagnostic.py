#!/usr/bin/env python3
import runpy,traceback
from pathlib import Path
out=Path('artifact_bluearchive_audio_v54_clean');out.mkdir(parents=True,exist_ok=True)
try:
 runpy.run_path('research/bluearchive_v54/generate_audio_v54_clean.py',run_name='__main__')
except Exception:
 text=traceback.format_exc();(out/'diagnostic_error.txt').write_text(text,encoding='utf-8');print(text)
