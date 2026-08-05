#!/usr/bin/env python3
from pathlib import Path
src=Path('research/bluearchive_v54/generate_audio_v54_clean.py').read_text(encoding='utf-8')
src=src.replace("'質問':('ja-JP-KeitaNeural','0%','+2Hz')","'質問':('ja-JP-KeitaNeural','+0%','+2Hz')")
exec(compile(src,'generate_audio_v54_clean.py','exec'),{'__name__':'__main__'})
