#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from pykakasi import kakasi
from rapidfuzz import fuzz
from scipy.signal import butter, resample_poly, sosfiltfilt

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import irodori_clear_rebuild_spec as spec  # noqa: E402

IRODORI_REPO = Path.cwd().resolve()
if not (IRODORI_REPO / "irodori_tts").is_dir():
    IRODORI_REPO = Path("Irodori-TTS").resolve()
sys.path.insert(0, str(IRODORI_REPO))

from irodori_tts.inference_runtime import RuntimeKey, SamplingRequest, download_hf_checkpoint, get_cached_runtime, save_wav  # noqa: E402

VOICE_INDEX = int(os.environ.get("VOICE_INDEX", "0"))
VOICE = spec.VOICES[VOICE_INDEX]
ROOT = Path.cwd()
WORK = ROOT / "clear_voice_work" / f"voice_{VOICE_INDEX:02d}"
OUT = ROOT / "clear_voice_output" / f"voice_{VOICE_INDEX:02d}"
MONO_DIR = OUT / "モノラル" / str(VOICE["folder"])
ASMR_DIR = OUT / "耳元ステレオ" / str(VOICE["folder"])
VALIDATION_DIR = OUT / "検証"
CANDIDATE_DIR = WORK / "候補"
ANCHOR_DIR = WORK / "基準声"
for directory in (WORK, OUT, MONO_DIR, ASMR_DIR, VALIDATION_DIR, CANDIDATE_DIR, ANCHOR_DIR):
    directory.mkdir(parents=True, exist_ok=True)

CHECKPOINT = "Aratako/Irodori-TTS-600M-v3-VoiceDesign"
TARGET_SR = 48000
NUM_STEPS = 40
MAX_CANDIDATES = 8
MIN_CANDIDATES = 3
MIN_ACCEPTED = 2
KAKASI = kakasi()


def log(message: str) -> None:
    print(message, flush=True)
    with (VALIDATION_DIR / "実行ログ.txt").open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def safe_component(value: str, limit: int = 120) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or "名称なし")[:limit]


def to_hiragana(value: str) -> str:
    chunks: list[str] = []
    for item in KAKASI.convert(unicodedata.normalize("NFKC", str(value))):
        chunks.append(str(item.get("hira") or item.get("orig") or ""))
    return re.sub(r"[^0-9a-zぁ-んゔー]", "", "".join(chunks).lower())


def resample_mono(signal: np.ndarray, sample_rate: int, target_rate: int = TARGET_SR) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32)
    if signal.ndim > 1:
        signal = np.mean(signal, axis=1)
    if sample_rate != target_rate:
        divisor = math.gcd(int(sample_rate), int(target_rate))
        signal = resample_poly(signal, target_rate // divisor, sample_rate // divisor).astype(np.float32)
    return np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def trim_silence(signal: np.ndarray, sample_rate: int, before: float = 0.10, after: float = 0.18) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32)
    if signal.size == 0:
        return signal
    peak = float(np.max(np.abs(signal)))
    threshold = max(10.0 ** (-54.0 / 20.0), peak * 0.008)
    active = np.flatnonzero(np.abs(signal) >= threshold)
    if active.size == 0:
        return signal
    start = max(0, int(active[0]) - int(before * sample_rate))
    end = min(signal.size, int(active[-1]) + 1 + int(after * sample_rate))
    return signal[start:end]


def rms_dbfs(signal: np.ndarray) -> float:
    return 20.0 * math.log10(max(float(np.sqrt(np.mean(np.square(signal)) + 1e-12)), 1e-12))


def normalize_rms_and_peak(signal: np.ndarray, target_rms: float, peak_limit_db: float = -1.0) -> np.ndarray:
    current = rms_dbfs(signal)
    signal = np.asarray(signal, dtype=np.float32) * (10.0 ** ((float(target_rms) - current) / 20.0))
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    limit = 10.0 ** (float(peak_limit_db) / 20.0)
    if peak > limit and peak > 0:
        signal *= limit / peak
    return np.clip(signal, -1.0, 1.0).astype(np.float32)


def transparent_process(signal: np.ndarray, sample_rate: int, target_rms: float) -> np.ndarray:
    signal = resample_mono(signal, sample_rate, TARGET_SR)
    signal -= float(np.mean(signal))
    if signal.size > 64:
        signal = sosfiltfilt(butter(2, 55.0 / (TARGET_SR / 2.0), btype="highpass", output="sos"), signal).astype(np.float32)
        spectrum = np.fft.rfft(signal)
        freqs = np.fft.rfftfreq(signal.size, 1.0 / TARGET_SR)
        gain_db = np.zeros_like(freqs, dtype=np.float64)
        gain_db -= 1.1 * np.exp(-0.5 * ((np.log2(np.maximum(freqs, 1.0) / 300.0)) / 0.85) ** 2)
        shelf = 1.0 / (1.0 + np.exp(-(freqs - 6200.0) / 1400.0))
        gain_db += 1.15 * shelf
        mask = freqs > 17000.0
        gain_db[mask] *= np.clip((22000.0 - freqs[mask]) / 5000.0, 0.0, 1.0)
        signal = np.fft.irfft(spectrum * (10.0 ** (gain_db / 20.0)), n=signal.size).astype(np.float32)
    return normalize_rms_and_peak(trim_silence(signal, TARGET_SR), target_rms)


def audio_metrics(signal: np.ndarray, sample_rate: int) -> dict[str, float]:
    signal = np.asarray(signal, dtype=np.float32)
    duration = float(signal.size / sample_rate)
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(signal)) + 1e-12)) if signal.size else 0.0
    clip_ratio = float(np.mean(np.abs(signal) >= 0.999)) if signal.size else 1.0
    if signal.size < 2048:
        flatness, centroid, high_ratio = 1.0, 0.0, 1.0
    else:
        n_fft, hop = 2048, 512
        count = 1 + max(0, (signal.size - n_fft) // hop)
        indices = np.arange(n_fft)[None, :] + hop * np.arange(count)[:, None]
        frames = signal[indices] * np.hanning(n_fft)[None, :]
        power = np.abs(np.fft.rfft(frames, axis=1)) ** 2 + 1e-12
        freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)
        sums = np.maximum(np.sum(power, axis=1), 1e-12)
        centroid = float(np.mean(np.sum(power * freqs[None, :], axis=1) / sums))
        flatness = float(np.mean(np.exp(np.mean(np.log(power), axis=1)) / np.mean(power, axis=1)))
        high_ratio = float(np.mean(np.sum(power[:, freqs >= 7000.0], axis=1) / sums))
    return {
        "duration_sec": duration,
        "peak_dbfs": 20.0 * math.log10(max(peak, 1e-12)),
        "rms_dbfs": 20.0 * math.log10(max(rms, 1e-12)),
        "clip_ratio": clip_ratio,
        "spectral_flatness": flatness,
        "spectral_centroid_hz": centroid,
        "high_frequency_ratio": high_ratio,
    }


def quality_score(metrics: dict[str, float], requested_seconds: float) -> float:
    duration_score = math.exp(-((float(metrics["duration_sec"]) - requested_seconds) / 1.0) ** 2)
    clip_score = max(0.0, 1.0 - float(metrics["clip_ratio"]) / 0.00025)
    flat_score = math.exp(-((float(metrics["spectral_flatness"]) - 0.025) / 0.07) ** 2)
    centroid_score = math.exp(-((float(metrics["spectral_centroid_hz"]) - 2300.0) / 1700.0) ** 2)
    high_score = math.exp(-((float(metrics["high_frequency_ratio"]) - 0.055) / 0.065) ** 2)
    return float(np.clip(0.25 * duration_score + 0.30 * clip_score + 0.15 * flat_score + 0.15 * centroid_score + 0.15 * high_score, 0.0, 1.0))


def transcribe(path: Path, whisper: WhisperModel) -> tuple[str, list[dict[str, Any]]]:
    segments, _ = whisper.transcribe(str(path), language="ja", beam_size=5, best_of=5, temperature=0.0, condition_on_previous_text=False, word_timestamps=True, vad_filter=True, vad_parameters={"min_silence_duration_ms":160})
    text_parts: list[str] = []
    words: list[dict[str, Any]] = []
    for segment in segments:
        text_parts.append(str(segment.text))
        for word in segment.words or []:
            words.append({"text":str(word.word),"start":float(word.start),"end":float(word.end)})
    return "".join(text_parts).strip(), words


def asr_evaluation(target_text: str, transcript: str, mode: str) -> dict[str, Any]:
    target, actual = to_hiragana(target_text), to_hiragana(transcript)
    ratio = float(fuzz.ratio(target, actual) / 100.0)
    delta = len(actual) - len(target)
    laugh_ok = True if mode != "laugh" else "ふふ" in actual
    threshold = 0.95 if mode in {"asmr","laugh"} else 0.97
    return {"target_hiragana":target,"actual_hiragana":actual,"asr_ratio":ratio,"length_delta":delta,"laugh_ok":laugh_ok,"accepted":bool(ratio >= threshold and -2 <= delta <= 1 and laugh_ok)}


def trim_hallucinated_tail(path: Path, target_text: str, whisper: WhisperModel) -> tuple[Path, str]:
    transcript, words = transcribe(path, whisper)
    target = to_hiragana(target_text)
    if not words or len(to_hiragana(transcript)) <= len(target) + 1:
        return path, transcript
    cumulative, best_score, best_end = "", 0.0, 0.0
    for word in words:
        cumulative += str(word["text"])
        normalized = to_hiragana(cumulative)
        score = float(fuzz.ratio(target, normalized) / 100.0)
        if score > best_score:
            best_score, best_end = score, float(word["end"])
        if score >= 0.97 and len(normalized) >= len(target) - 1:
            best_end = float(word["end"])
            break
    if best_score < 0.94 or best_end <= 0:
        return path, transcript
    signal, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(signal, axis=1).astype(np.float32)
    cut = min(mono.size, int((best_end + 0.18) * int(sample_rate)))
    if cut < int(sample_rate):
        return path, transcript
    trimmed_path = path.with_name(path.stem + "_末尾切除.wav")
    sf.write(trimmed_path, mono[:cut], int(sample_rate), subtype="PCM_24")
    transcript2, _ = transcribe(trimmed_path, whisper)
    if fuzz.ratio(target, to_hiragana(transcript2)) >= fuzz.ratio(target, to_hiragana(transcript)):
        return trimmed_path, transcript2
    trimmed_path.unlink(missing_ok=True)
    return path, transcript


def make_ear_stereo(signal: np.ndarray, voice_number: int) -> np.ndarray:
    side = -1 if voice_number % 2 else 1
    delay_samples = int(round(TARGET_SR * 0.00023))
    near = np.asarray(signal, dtype=np.float32).copy()
    far = np.pad(near, (delay_samples, 0))[: near.size]
    if far.size > 64:
        far = sosfiltfilt(butter(2, 6500.0 / (TARGET_SR / 2.0), btype="lowpass", output="sos"), far).astype(np.float32)
    near *= 10.0 ** (0.55 / 20.0)
    far *= 10.0 ** (-1.35 / 20.0)
    stereo = np.column_stack((near, far)) if side < 0 else np.column_stack((far, near))
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    limit = 10.0 ** (-1.0 / 20.0)
    if peak > limit and peak > 0:
        stereo *= limit / peak
    return stereo.astype(np.float32)


def build_runtime() -> Any:
    checkpoint_path = download_hf_checkpoint(CHECKPOINT)
    runtime, _ = get_cached_runtime(RuntimeKey(checkpoint=str(checkpoint_path), model_device="cpu", codec_repo="Aratako/Semantic-DACVAE-Japanese-32dim", model_precision="fp32", codec_device="cpu", codec_precision="fp32", compile_model=False, compile_dynamic=False))
    return runtime


def synthesize(runtime: Any, *, text: str, caption: str, reference: str | None, seed: int, seconds: float, output_path: Path) -> dict[str, Any]:
    messages: list[str] = []
    result = runtime.synthesize(SamplingRequest(text=text, caption=caption, ref_wav=reference, ref_wavs=None, ref_latent=None, ref_latents=None, ref_embed=None, no_ref=reference is None, ref_normalize_db=-18.0, ref_ensure_max=True, num_candidates=1, decode_mode="sequential", seconds=float(seconds), duration_scale=1.0, min_seconds=0.5, max_seconds=12.0, max_ref_seconds=8.0, max_text_len=None, max_caption_len=None, num_steps=NUM_STEPS, cfg_scale_text=3.6, cfg_scale_caption=3.0, cfg_scale_speaker=4.3 if reference is not None else 0.0, cfg_guidance_mode="independent", cfg_scale=None, cfg_min_t=0.5, cfg_max_t=1.0, truncation_factor=None, rescale_k=None, rescale_sigma=None, context_kv_cache=True, speaker_kv_scale=None, speaker_kv_min_t=None, speaker_kv_max_layers=None, speaker_uncond_mode="mask", seed=int(seed), t_schedule_mode="linear", sway_coeff=-1.0, trim_tail=True, lora_adapter=None), log_fn=messages.append)
    save_wav(output_path, result.audios[0].float(), result.sample_rate)
    return {"seed":int(result.used_seed),"sample_rate":int(result.sample_rate),"stage_timings":result.stage_timings,"total_to_decode":float(result.total_to_decode),"messages":[*messages,*result.messages]}


def candidate_durations(base: float) -> list[float]:
    return [max(2.4, base + offset) for offset in (-0.35,-0.15,0.0,0.20,0.38,-0.50,0.58,0.78)]


def generate_candidates(runtime: Any, whisper: WhisperModel, *, label: str, target_text: str, caption: str, reference: str | None, base_seed: int, base_seconds: float, target_rms: float, mode: str, output_directory: Path) -> tuple[Path, list[dict[str, Any]]]:
    output_directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    accepted: list[tuple[Path, dict[str, Any]]] = []
    for number, seconds in enumerate(candidate_durations(base_seconds), 1):
        raw_path = output_directory / f"候補_{number:02d}_生.wav"
        generation = synthesize(runtime, text=target_text, caption=caption, reference=reference, seed=base_seed + number * 1009, seconds=seconds, output_path=raw_path)
        working_path, first_transcript = trim_hallucinated_tail(raw_path, target_text, whisper)
        raw_signal, raw_sr = sf.read(working_path, dtype="float32", always_2d=True)
        processed = transparent_process(np.mean(raw_signal, axis=1).astype(np.float32), int(raw_sr), target_rms)
        processed_path = output_directory / f"候補_{number:02d}_整音.wav"
        sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")
        transcript, words = transcribe(processed_path, whisper)
        asr = asr_evaluation(target_text, transcript, mode)
        metrics = audio_metrics(processed, TARGET_SR)
        quality = quality_score(metrics, seconds)
        hard_ok = float(metrics["clip_ratio"]) <= 0.00005 and float(metrics["spectral_flatness"]) <= 0.20 and 650.0 <= float(metrics["spectral_centroid_hz"]) <= 5200.0
        is_accepted = bool(asr["accepted"] and hard_ok)
        record = {"label":label,"candidate":number,"requested_seconds":seconds,"raw_path":str(raw_path),"processed_path":str(processed_path),"first_transcript":first_transcript,"transcript":transcript,"word_count":len(words),**asr,**metrics,"quality_score":quality,"hard_quality_ok":hard_ok,"accepted":is_accepted,"generation":generation}
        records.append(record)
        log(f"{VOICE['folder']} / {label} / candidate={number} asr={asr['asr_ratio']:.3f} delta={asr['length_delta']} quality={quality:.3f} accepted={is_accepted}")
        if is_accepted:
            accepted.append((processed_path, record))
        if number >= MIN_CANDIDATES and len(accepted) >= MIN_ACCEPTED:
            break
    if not accepted:
        records.sort(key=lambda item:(float(item["asr_ratio"]),float(item["quality_score"])), reverse=True)
        raise RuntimeError(f"厳格条件を通る候補がありません: {VOICE['folder']} / {label}; best_asr={records[0]['asr_ratio']:.3f}, transcript={records[0]['transcript']!r}")
    accepted.sort(key=lambda item:(float(item[1]["asr_ratio"]),float(item[1]["quality_score"])), reverse=True)
    return accepted[0][0], records


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    flat_rows: list[dict[str, Any]] = []
    for row in rows:
        flat_rows.append({key:(json.dumps(value,ensure_ascii=False,default=str) if isinstance(value,(dict,list,tuple)) else value) for key,value in row.items()})
    fields: list[str] = []
    for row in flat_rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=fields,extrasaction="ignore"); writer.writeheader(); writer.writerows(flat_rows)


def main() -> None:
    log(f"開始: {VOICE['folder']}")
    whisper = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=max(2, os.cpu_count() or 2))
    runtime = build_runtime()
    anchor_path, anchor_records = generate_candidates(runtime, whisper, label="基準声", target_text=spec.ANCHOR_TEXT, caption=f"{VOICE['caption']} {spec.ANCHOR_STYLE} {spec.QUALITY_STYLE}", reference=None, base_seed=int(VOICE["seed"]), base_seconds=float(spec.ANCHOR_SECONDS), target_rms=-19.5, mode="neutral", output_directory=ANCHOR_DIR)
    anchor_signal, anchor_sr = sf.read(anchor_path,dtype="float32",always_2d=True)
    final_anchor = ANCHOR_DIR / "採用した基準声.wav"
    sf.write(final_anchor,np.mean(anchor_signal,axis=1).astype(np.float32),int(anchor_sr),subtype="PCM_24")
    candidates_all: list[dict[str,Any]]=[]; finals: list[dict[str,Any]]=[]
    for style in spec.STYLES:
        number=int(style["number"]); label=str(style["label"])
        caption="声質は参照音声と同じ人物として保つ。"+str(style["caption"])+" 発音を明瞭にし、指定された台詞以外の言葉、うめき声、悲鳴、笑い声を最後に追加しない。"
        selected, records = generate_candidates(runtime, whisper, label=label, target_text=str(style["text"]), caption=caption, reference=str(final_anchor.resolve()), base_seed=int(VOICE["seed"])+number*100000, base_seconds=float(style["seconds"]), target_rms=float(style["target_rms"]), mode=str(style["mode"]), output_directory=CANDIDATE_DIR/f"{number:02d}_{safe_component(label)}")
        candidates_all.extend([{"voice":VOICE["folder"],"style_number":number,"style_label":label,**record} for record in records])
        name=f"{number:02d}_{safe_component(label)}_{safe_component(style['short'])}.wav"
        final_path=MONO_DIR/name
        signal,sr=sf.read(selected,dtype="float32",always_2d=True); mono=np.mean(signal,axis=1).astype(np.float32)
        sf.write(final_path,mono,int(sr),subtype="PCM_24")
        transcript,_=transcribe(final_path,whisper); final_asr=asr_evaluation(str(style["text"]),transcript,str(style["mode"]))
        if not final_asr["accepted"]:
            raise RuntimeError(f"最終WAVのASR再検査に失敗: {name}: {transcript!r}")
        finals.append({"voice_number":VOICE["number"],"voice_folder":VOICE["folder"],"style_number":number,"style_label":label,"target_text":style["text"],"file":str(final_path.relative_to(OUT)),"transcript":transcript,**final_asr,**audio_metrics(mono,int(sr))})
        if str(style["mode"])=="asmr":
            sf.write(ASMR_DIR/name,make_ear_stereo(mono,int(VOICE["number"])),TARGET_SR,subtype="PCM_24")
    write_csv(VALIDATION_DIR/"全候補検査.csv",candidates_all); write_csv(VALIDATION_DIR/"最終WAV検査.csv",finals); write_csv(VALIDATION_DIR/"基準声候補検査.csv",anchor_records)
    summary={"checkpoint":CHECKPOINT,"voice":VOICE,"num_steps":NUM_STEPS,"guidance":{"text":3.6,"caption":3.0,"speaker":4.3,"mode":"independent"},"schedule":"linear","emoji_in_input":False,"fixed_seconds":True,"strict_asr_required":True,"final_mono_wavs":len(finals),"asmr_stereo_wavs":len(list(ASMR_DIR.glob('*.wav'))),"human_listening":False}
    (VALIDATION_DIR/"集計.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (VALIDATION_DIR/"生成条件.txt").write_text("旧版の長すぎる自動継続、末尾の意味不明発話、高すぎるcaption CFG、20ステップ、絵文字依存、旧合成話者参照を廃止。\n600M-v3-VoiceDesignで基準声を参照なしから新規作成し、40ステップ・linear・短いひらがな台詞・固定秒数・低いcaption CFG・厳格ASRで再生成。\nASR条件を通らない音声は成果物に入れず、候補生成そのものを失敗扱いにする。\n",encoding="utf-8")
    log(f"完了: {VOICE['folder']} mono={len(finals)} asmr={len(list(ASMR_DIR.glob('*.wav')))}")


if __name__ == "__main__":
    main()
