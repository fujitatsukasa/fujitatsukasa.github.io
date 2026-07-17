#!/usr/bin/env python3
import csv
import runpy
runpy.run_path('research/bluearchive_v54/generate_audio_v54.py', run_name='__main__', init_globals={'csv': csv})
