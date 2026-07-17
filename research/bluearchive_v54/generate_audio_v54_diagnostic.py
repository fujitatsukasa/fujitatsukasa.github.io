#!/usr/bin/env python3
import csv
import runpy
import traceback
from pathlib import Path

out = Path('artifact_bluearchive_audio_v54')
out.mkdir(parents=True, exist_ok=True)
try:
    runpy.run_path('research/bluearchive_v54/generate_audio_v54.py', run_name='__main__', init_globals={'csv': csv})
except Exception:
    text = traceback.format_exc()
    (out / 'diagnostic_error.txt').write_text(text, encoding='utf-8')
    print(text)
