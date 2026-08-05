#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pyarrow.parquet as pq
import soundfile as sf
from gradio_client import Client, handle_file
from huggingface_hub import hf_hub_download

OUT = Path("generation_test_output")
REF = OUT / "refs"
GEN = OUT / "generated"
for d in (REF, GEN):
    d.mkdir(parents=True, exist_ok=True)

repo = "SynDataLab-JA/irodori-clones-3m"
revision = "ce53b9287f04a2506c08f77b3b8b5287caed6bb4"
speaker_number = 1639
parquet_name = f"data/train-{speaker_number - 1:05d}-of-10000.parquet"
parquet_path = Path(hf_hub_download(repo_id=repo, repo_type="dataset", filename=parquet_name, revision=revision))
rows = pq.read_table(parquet_path).to_pylist()

ref_paths = []
for out_index, source_index in enumerate((20, 29, 112), 1):
    row = rows[source_index - 1]
    audio = row["audio"]
    payload = bytes(audio["bytes"])
    wav, sr = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    wav = wav.mean(axis=1)
    path = REF / f"ref_{out_index:02d}.wav"
    sf.write(path, wav, sr, subtype="PCM_16")
    ref_paths.append(path)

client = Client("Aratako/Irodori-TTS-v4-Small-Demo", verbose=True, download_files=str(OUT / "downloads"))
text = "ん……ごめん、まだちょっと眠くて。あと五分だけ、このままでいさせて……🥱"
caption = (
    "若い成人の中高音で、やわらかく丸い声質。"
    "眠気で全身の力が抜け、まぶたが重い。息を少し多く含ませ、声量は小さく、"
    "一語ずつ遅く、語尾を長く下げる。あくびをこらえるような近距離の話し方。"
    "決して叫ばず、元気にせず、明るく張らない。"
    "防音された静かなスタジオで高品質な近接マイクを使った、透明でこもりのない乾いた音。"
    "ヒス、部屋鳴り、電話音、過度なノイズ抑制感はない。"
)

result = client.predict(
    text=text,
    caption=caption,
    uploaded_audios=[handle_file(str(p)) for p in ref_paths],
    num_steps=40,
    num_candidates=4,
    seed_raw="2026080401",
    seconds_raw="",
    duration_scale=1.15,
    t_schedule_mode="linear",
    sway_coeff=-1.0,
    cfg_guidance_mode="independent",
    cfg_scale_text=3.0,
    cfg_scale_caption=5.0,
    cfg_scale_speaker=5.2,
    cfg_scale_raw="",
    cfg_min_t=0.5,
    cfg_max_t=1.0,
    context_kv_cache=True,
    max_text_len_raw="",
    max_caption_len_raw="",
    truncation_factor_raw="",
    rescale_k_raw="",
    rescale_sigma_raw="",
    speaker_kv_scale_raw="1.05",
    api_name="/gradio_inference",
)

endpoint = next(ep for ep in client.endpoints.values() if getattr(ep, "api_name", None) == "/gradio_inference")
serialized = []
for index, value in enumerate(result):
    if index < 32 and isinstance(value, dict) and value.get("visible") and value.get("value"):
        local = Path(endpoint._download_file({"path": str(value["value"])}))
        dst = GEN / f"candidate_{index + 1:02d}.wav"
        shutil.copy2(local, dst)
        serialized.append(str(dst))
    elif index == 32:
        (OUT / "run_log.txt").write_text(str(value), encoding="utf-8")

(OUT / "request.json").write_text(json.dumps({
    "text": text,
    "caption": caption,
    "references": [str(p) for p in ref_paths],
    "generated": serialized,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"generated": serialized, "result_count": len(result)}, ensure_ascii=False, indent=2))
