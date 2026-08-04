#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
import soundfile as sf
from huggingface_hub import hf_hub_download

IRODORI_REPO = Path.cwd().resolve()
if not (IRODORI_REPO / "irodori_tts").is_dir():
    IRODORI_REPO = Path("Irodori-TTS").resolve()
sys.path.insert(0, str(IRODORI_REPO))

from irodori_tts.inference_runtime import (  # noqa: E402
    RuntimeKey,
    SamplingRequest,
    download_hf_checkpoint,
    get_cached_runtime,
    save_wav,
)

OUT = Path("local_v3_test_output")
REF = OUT / "references"
OUT.mkdir(parents=True, exist_ok=True)
REF.mkdir(parents=True, exist_ok=True)

clone_repo = "SynDataLab-JA/irodori-clones-3m"
clone_revision = "ce53b9287f04a2506c08f77b3b8b5287caed6bb4"
speaker_number = 1639
parquet_name = f"data/train-{speaker_number - 1:05d}-of-10000.parquet"
parquet_path = Path(
    hf_hub_download(
        repo_id=clone_repo,
        repo_type="dataset",
        filename=parquet_name,
        revision=clone_revision,
    )
)
rows = pq.read_table(parquet_path).to_pylist()
reference_paths: list[str] = []
for order, row_number in enumerate((20, 29, 112), 1):
    cell = rows[row_number - 1]["audio"]
    payload = bytes(cell["bytes"])
    audio, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    path = REF / f"reference_{order:02d}.wav"
    sf.write(path, mono, sample_rate, subtype="PCM_16")
    reference_paths.append(str(path.resolve()))

checkpoint_path = download_hf_checkpoint("Aratako/Irodori-TTS-600M-v3-VoiceDesign")
key = RuntimeKey(
    checkpoint=str(checkpoint_path),
    model_device="cpu",
    codec_repo="Aratako/Semantic-DACVAE-Japanese-32dim",
    model_precision="fp32",
    codec_device="cpu",
    codec_precision="fp32",
    compile_model=False,
    compile_dynamic=False,
)
runtime, reloaded = get_cached_runtime(key)

text = "ん……ごめん、まだちょっと眠くて。あと五分だけ、このままでいさせて……🥱"
caption = (
    "声質は参照音声と同一人物として保つ。若い成人の中高音で、角のない丸い声質。"
    "本当に眠く、まぶたが重く、全身の力が抜けている。声量は小さく、息を少し多く含ませ、"
    "一語ずつ遅く、語尾を長く下げる。あくびをこらえるような近距離の話し方。"
    "元気にせず、明るく張らず、絶対に叫ばない。"
    "静かな防音スタジオで広帯域の高性能コンデンサーマイクを使った近接収録。"
    "透明でこもりがなく、子音が自然に明瞭。部屋鳴り、ヒス、電話音、金属的な歪みはない。"
)

messages: list[str] = []
result = runtime.synthesize(
    SamplingRequest(
        text=text,
        caption=caption,
        ref_wav=None,
        ref_wavs=reference_paths,
        ref_latent=None,
        ref_latents=None,
        ref_embed=None,
        no_ref=False,
        ref_normalize_db=-16.0,
        ref_ensure_max=True,
        num_candidates=1,
        decode_mode="sequential",
        seconds=None,
        duration_scale=1.16,
        max_ref_seconds=30.0,
        max_text_len=None,
        max_caption_len=None,
        num_steps=12,
        seed=202608041639,
        cfg_guidance_mode="alternating",
        cfg_scale_text=3.1,
        cfg_scale_caption=5.2,
        cfg_scale_speaker=5.2,
        cfg_scale=None,
        cfg_min_t=0.5,
        cfg_max_t=1.0,
        truncation_factor=None,
        rescale_k=None,
        rescale_sigma=None,
        context_kv_cache=True,
        speaker_kv_scale=1.05,
        speaker_kv_min_t=None,
        speaker_kv_max_layers=None,
        t_schedule_mode="sway",
        sway_coeff=-1.0,
        trim_tail=True,
        lora_adapter=None,
    ),
    log_fn=messages.append,
)

output_wav = save_wav(OUT / "中高音・やわらかい・丸い_眠く力の抜けた話し方_v3CPU試験.wav", result.audios[0].float(), result.sample_rate)
summary = {
    "checkpoint": str(checkpoint_path),
    "runtime_reloaded": reloaded,
    "sample_rate": result.sample_rate,
    "seed_used": result.used_seed,
    "output": str(output_wav),
    "messages": [*messages, *result.messages],
    "stage_timings": result.stage_timings,
    "total_to_decode": result.total_to_decode,
    "text": text,
    "caption": caption,
}
(OUT / "test_result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
