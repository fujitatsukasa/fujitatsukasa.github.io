#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from gradio_client import Client

OUT = Path("probe_output")
OUT.mkdir(parents=True, exist_ok=True)

client = Client("Aratako/Irodori-TTS-v4-Small-Demo", verbose=True)

result = {}
for return_format in ("dict", None):
    try:
        api = client.view_api(all_endpoints=True, print_info=False, return_format=return_format)
        result[f"view_api_{return_format or 'default'}"] = api
    except Exception as exc:
        result[f"view_api_{return_format or 'default'}_error"] = repr(exc)

# Save the client config as well, because Gradio versions expose slightly different details.
for attr in ("config", "endpoints", "api_info"):
    try:
        value = getattr(client, attr)
        if attr == "endpoints":
            value = {str(k): str(v) for k, v in value.items()}
        result[attr] = value
    except Exception as exc:
        result[f"{attr}_error"] = repr(exc)

(OUT / "api_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
