#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import whisper
from pykakasi import kakasi
from rapidfuzz import fuzz
from scipy.signal import butter, resample_poly, sosfiltfilt

ROOT = Path(__file__).resolve().parents[1]
IRODORI_REPO = ROOT / "Irodori-TTS"
sys.path.insert(0, str(IRODORI_REPO))

from irodori_tts.inference_runtime import (  # noqa: E402
    RuntimeKey,
    SamplingRequest,
    download_hf_checkpoint,
    get_cached_runtime,
    save_wav,
)

PREVIOUS = ROOT / "previous_artifacts"
WORK = ROOT / "irodori_finish_work"
OUT = ROOT / "irodori_finish_output"
FINAL_MONO = WORK / "最終モノラル"
FINAL_STEREO = WORK / "ASMR耳元ステレオ"
VALIDATION = WORK / "検証"
for d in (WORK, OUT, FINAL_MONO, FINAL_STEREO, VALIDATION):
    d.mkdir(parents=True, exist_ok=True)

CHECKPOINT = "Aratako/Irodori-TTS-v4-Small"
CODEC = "Aratako/Semantic-DACVAE-Japanese-32dim"
TARGET_SR = 48000
NUM_STEPS = 40
MAX_CANDIDATES = 5
KAKASI = kakasi()

VOICES = [
    {"index":0,"folder":"01_中高音・ささやき向き・やわらかい","caption":"若い成人の中高音。細くやわらかいが、母音と子音が明瞭。近距離の小声でも輪郭が崩れず、鼻声、かすれ、舌足らずさ、こもりがない。","seed":202608051101},
    {"index":1,"folder":"02_中高音・やさしい・透明","caption":"若い成人の中高音。やさしく澄んだ声で透明感があり、子音が明瞭。鼻声、かすれ、舌足らずさ、こもりがない。","seed":202608051202},
    {"index":2,"folder":"03_中高音・上品・明瞭","caption":"若い成人の中高音。上品で落ち着き、発音がはっきりしている。声を張らなくても言葉が聞き取りやすく、かすれ、こもり、過度な息漏れがない。","seed":202608051303},
    {"index":3,"folder":"04_中高音・丸い・親しみやすい","caption":"若い成人の中高音。角のない丸い声で親しみやすい。柔らかいが発音は明瞭で、幼い舌足らずさ、鼻づまり、かすれ、こもりがない。","seed":202608051404},
    {"index":4,"folder":"05_高音・小さめ・落ち着き","caption":"若い成人の高めの声。声量は小さめで落ち着きがあり、静かな会話に向く。細い声でも子音が明瞭で、かすれ、鼻声、舌足らずさがない。","seed":202608051505},
    {"index":5,"folder":"06_高音・親密・澄んだ声","caption":"若い成人の高めの声。親密で近い距離感があり、澄んでいて息漏れは控えめ。高域が刺さらず、言葉が明瞭で、かすれやこもりがない。","seed":202608051606},
    {"index":6,"folder":"07_高音・軽やか・自然会話","caption":"若い成人の高めの声。軽やかで自然な日常会話に向き、過剰なアニメ声ではない。発音が明瞭で、叫ばず、舌足らずにならず、こもりやかすれがない。","seed":202608051707},
    {"index":7,"folder":"08_かなり高い・繊細・透明","caption":"若い成人のかなり高い声。繊細で透明だが不安定ではなく、小声でも言葉の輪郭が保たれる。幼い舌足らずさ、鼻声、かすれ、金属的なざらつきがない。","seed":202608051808},
]

STYLES = [
    {"number":1,"label":"自然な近距離会話","short":"今日カフェ寄らない","text":"ねえ、今日、カフェ寄らない？","caption":"親しい相手への自然な近距離会話。普通より少し小さな声で、力まず、急に声を張らず、最後まで穏やかな会話の調子を保つ。","duration_scale":0.97,"target_rms":-20.0,"mode":"neutral"},
    {"number":2,"label":"丁寧で穏やかな案内","short":"こちらをご確認ください","text":"こちらを確認してください。","caption":"丁寧で穏やかな案内。落ち着いた速度で、すべての音を明瞭に発音し、語尾まで柔らかく話す。朗読調や叫び声にしない。","duration_scale":1.00,"target_rms":-20.5,"mode":"polite"},
    {"number":3,"label":"眠く力の抜けた話し方","short":"まだ眠いの","text":"ごめん、まだ眠いの。","caption":"本当に眠く、まぶたが重く、全身の力が抜けている。小さな声でゆっくり、語尾を下げて話す。元気にせず、叫ばず、別の言葉を追加しない。","duration_scale":1.13,"target_rms":-23.0,"mode":"sleepy"},
    {"number":4,"label":"悲しく弱った話し方","short":"今日は少しつらいの","text":"今日は少しつらいの。","caption":"悲しみで気力が落ち、弱った小さな声。少し震えても言葉は明瞭に保つ。明るく笑わず、怒鳴らず、最後まで弱い調子で話す。","duration_scale":1.08,"target_rms":-22.0,"mode":"sad"},
    {"number":5,"label":"怒りを抑えた話し方","short":"もう同じことはしないで","text":"もう、同じことはしないで。","caption":"怒りと不満を抑えている。声の芯を少し強くし、重要な語に力を置くが、絶叫や金切り声にはしない。言葉を明瞭に話す。","duration_scale":0.98,"target_rms":-18.8,"mode":"angry"},
    {"number":6,"label":"怖く慌てた話し方","short":"そこに何かいる","text":"待って。そこに何かいる。","caption":"本気で怖がり、少し焦って息が浅い。速度は少し速く、声が軽く震えるが、叫び続けず、すべての言葉を聞き取れるように話す。","duration_scale":0.97,"target_rms":-19.2,"mode":"fear"},
    {"number":7,"label":"明るくうれしい話し方","short":"来てくれてうれしい","text":"来てくれたんだ。うれしい。","caption":"心からうれしく、笑顔が声に表れている。明るく弾む抑揚で少し速めに話すが、叫ばず、別の言葉を追加しない。","duration_scale":0.95,"target_rms":-19.0,"mode":"happy"},
    {"number":8,"label":"やさしく心配する話し方","short":"無理しなくていいよ","text":"無理しなくていいよ。","caption":"弱っている相手をやさしく気遣う。声量を小さくし、速度を少し落として、包み込むように話す。説教調、怒り、叫び声を入れない。","duration_scale":1.06,"target_rms":-21.5,"mode":"gentle"},
    {"number":9,"label":"ASMR耳元ささやき","short":"力を抜いて","text":"聞こえる？ 力を抜いて。","caption":"耳元で話すASMRのような近距離のささやき。非常に小さな声で、柔らかな息を少し含ませ、ゆっくり話す。子音は透明で明瞭に保ち、ヒス、かすれ、叫び、余計な言葉を加えない。","duration_scale":1.15,"target_rms":-24.0,"mode":"asmr"},
    {"number":10,"label":"笑い混じりの話し方","short":"ちゃんと分かってるよ","text":"ふふっ。ちゃんと分かってるよ。","caption":"最初に短く自然に笑い、その後は微笑みが声ににじむ。笑い声で台詞を潰さず、すべての言葉を明瞭に話す。最後に余計な笑い声や別の言葉を追加しない。","duration_scale":1.02,"target_rms":-20.0,"mode":"laugh"},
]

ANCHOR_TEXT = "おはよう。今日はゆっくり始めようね。焦らなくて大丈夫。少し休んだら、また一緒に話そう。"
QUALITY = "静かな防音スタジオで、広帯域の高性能コンデンサーマイクを使った乾いた近接収録。透明でこもりがなく、鼻声、かすれ、ヒス、金属的なざらつき、部屋鳴りがない。"
REPLACEMENTS = {
    "辛い":"つらい","良い":"いい","大丈夫":"だいじょうぶ","分かって":"わかって","分かる":"わかる","来て":"きて","今日は":"きょうは","今日":"きょう","確認":"かくにん","同じ":"おなじ","無理":"むり","聞こえる":"きこえる","力":"ちから","眠い":"ねむい","何か":"なにか",
}


def log(message: str) -> None:
    print(message, flush=True)
    with (VALIDATION / "実行ログ.txt").open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_hiragana(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    for src, dst in REPLACEMENTS.items():
        text = text.replace(src, dst)
    out: list[str] = []
    for item in KAKASI.convert(text):
        out.append(str(item.get("hira") or item.get("orig") or ""))
    return re.sub(r"[^0-9a-zぁ-んゔー]", "", "".join(out).lower())


def resample_mono(signal: np.ndarray, sample_rate: int) -> np.ndarray:
    x = np.asarray(signal, dtype=np.float32)
    if x.ndim > 1:
        x = np.mean(x, axis=1)
    if sample_rate != TARGET_SR:
        g = math.gcd(int(sample_rate), TARGET_SR)
        x = resample_poly(x, TARGET_SR // g, int(sample_rate) // g).astype(np.float32)
    return np.nan_to_num(x).astype(np.float32)


def trim_silence(x: np.ndarray, before: float = 0.08, after: float = 0.14) -> np.ndarray:
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    threshold = max(10 ** (-55 / 20), peak * 0.006)
    active = np.flatnonzero(np.abs(x) >= threshold)
    if active.size == 0:
        return x
    a = max(0, int(active[0]) - int(before * TARGET_SR))
    b = min(x.size, int(active[-1]) + 1 + int(after * TARGET_SR))
    return x[a:b]


def rms_dbfs(x: np.ndarray) -> float:
    return 20 * math.log10(max(float(np.sqrt(np.mean(np.square(x)) + 1e-12)), 1e-12))


def transparent_process(signal: np.ndarray, sample_rate: int, target_rms: float) -> np.ndarray:
    x = resample_mono(signal, sample_rate)
    x -= float(np.mean(x))
    if x.size > 128:
        x = sosfiltfilt(butter(2, 50.0 / (TARGET_SR / 2), btype="highpass", output="sos"), x).astype(np.float32)
        spectrum = np.fft.rfft(x)
        freqs = np.fft.rfftfreq(x.size, 1 / TARGET_SR)
        gain_db = -0.8 * np.exp(-0.5 * ((np.log2(np.maximum(freqs, 1.0) / 290.0)) / 0.90) ** 2)
        gain_db += 1.0 / (1.0 + np.exp(-(freqs - 5600.0) / 1500.0))
        x = np.fft.irfft(spectrum * (10 ** (gain_db / 20)), n=x.size).astype(np.float32)
    x = trim_silence(x)
    current = rms_dbfs(x)
    x *= 10 ** ((target_rms - current) / 20)
    peak = float(np.max(np.abs(x))) if x.size else 0
    limit = 10 ** (-1.0 / 20)
    if peak > limit:
        x *= limit / peak
    return np.clip(x, -1, 1).astype(np.float32)


def metrics(x: np.ndarray) -> dict[str, float]:
    duration = x.size / TARGET_SR
    peak = float(np.max(np.abs(x))) if x.size else 0
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12)) if x.size else 0
    clip = float(np.mean(np.abs(x) >= 0.999)) if x.size else 1
    if x.size < 2048:
        return {"duration":duration,"peak_dbfs":-120.0,"rms_dbfs":-120.0,"clip_ratio":clip,"centroid":0.0,"flatness":1.0,"high_ratio":1.0}
    n_fft, hop = 2048, 512
    count = 1 + max(0, (x.size - n_fft) // hop)
    idx = np.arange(n_fft)[None, :] + hop * np.arange(count)[:, None]
    frames = x[idx] * np.hanning(n_fft)[None, :]
    power = np.abs(np.fft.rfft(frames, axis=1)) ** 2 + 1e-12
    freqs = np.fft.rfftfreq(n_fft, 1 / TARGET_SR)
    sums = np.maximum(power.sum(axis=1), 1e-12)
    centroid = float(np.mean((power * freqs[None, :]).sum(axis=1) / sums))
    flatness = float(np.mean(np.exp(np.mean(np.log(power), axis=1)) / np.mean(power, axis=1)))
    high = float(np.mean(power[:, freqs >= 7000].sum(axis=1) / sums))
    return {"duration":duration,"peak_dbfs":20*math.log10(max(peak,1e-12)),"rms_dbfs":20*math.log10(max(rms,1e-12)),"clip_ratio":clip,"centroid":centroid,"flatness":flatness,"high_ratio":high}


def transcribe(path: Path, model: Any) -> tuple[str, list[dict[str, Any]]]:
    result = model.transcribe(str(path), language="ja", fp16=False, temperature=0.0, beam_size=5, best_of=5, condition_on_previous_text=False, word_timestamps=True, verbose=False)
    text = str(result.get("text") or "").strip()
    words: list[dict[str, Any]] = []
    for seg in result.get("segments") or []:
        for word in seg.get("words") or []:
            words.append({"text":str(word.get("word") or ""),"start":float(word.get("start") or 0),"end":float(word.get("end") or 0)})
    return text, words


def align_to_target(path: Path, target_text: str, model: Any) -> tuple[Path, str]:
    transcript, words = transcribe(path, model)
    if not words:
        return path, transcript
    target = to_hiragana(target_text)
    best: tuple[float,int,int] | None = None
    for i in range(len(words)):
        combined = ""
        for j in range(i, min(len(words), i + 14)):
            combined += words[j]["text"]
            actual = to_hiragana(combined)
            ratio = fuzz.ratio(target, actual) / 100
            partial = fuzz.partial_ratio(target, actual) / 100 if actual else 0
            overshoot = max(0, len(actual) - len(target))
            undershoot = max(0, len(target) - len(actual))
            score = 0.74*ratio + 0.26*partial - 0.035*overshoot - 0.004*undershoot
            if best is None or score > best[0]:
                best = (score, i, j)
    if best is None or best[0] < 0.76:
        return path, transcript
    _, i, j = best
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = np.mean(x, axis=1).astype(np.float32)
    start = max(0, int((words[i]["start"] - 0.08) * sr))
    end = min(mono.size, int((words[j]["end"] + 0.14) * sr))
    if end - start < int(0.55 * sr):
        return path, transcript
    out = path.with_name(path.stem + "_整列.wav")
    sf.write(out, mono[start:end], sr, subtype="PCM_24")
    transcript2, _ = transcribe(out, model)
    if fuzz.ratio(target, to_hiragana(transcript2)) >= fuzz.ratio(target, to_hiragana(transcript)) - 2:
        return out, transcript2
    out.unlink(missing_ok=True)
    return path, transcript


def asr_score(target: str, actual: str, mode: str) -> dict[str, Any]:
    t, a = to_hiragana(target), to_hiragana(actual)
    ratio = fuzz.ratio(t, a) / 100
    partial = fuzz.partial_ratio(t, a) / 100 if a else 0
    delta = len(a) - len(t)
    threshold = 0.78 if mode == "laugh" else (0.82 if mode == "asmr" else 0.86)
    accepted = ratio >= threshold and partial >= 0.93 and -4 <= delta <= 2
    return {"target":t,"actual":a,"ratio":ratio,"partial":partial,"delta":delta,"accepted":accepted}


def build_runtime() -> Any:
    checkpoint = download_hf_checkpoint(CHECKPOINT)
    runtime, _ = get_cached_runtime(RuntimeKey(checkpoint=str(checkpoint), model_device="cpu", codec_repo=CODEC, model_precision="fp32", codec_device="cpu", codec_precision="fp32", compile_model=False, compile_dynamic=False))
    return runtime


def synthesize(runtime: Any, *, text: str, caption: str, refs: list[Path], seed: int, duration_scale: float, output: Path) -> None:
    result = runtime.synthesize(SamplingRequest(text=text, caption=caption, ref_wav=None, ref_wavs=[str(p) for p in refs] if refs else None, ref_latent=None, ref_latents=None, ref_embed=None, no_ref=not refs, ref_normalize_db=-18.0, ref_ensure_max=True, num_candidates=1, decode_mode="sequential", seconds=None, duration_scale=float(duration_scale), min_seconds=0.5, max_seconds=10.0, max_ref_seconds=30.0, max_text_len=None, max_caption_len=None, num_steps=NUM_STEPS, cfg_scale_text=3.0, cfg_scale_caption=2.6, cfg_scale_speaker=5.0 if refs else 0.0, cfg_guidance_mode="independent", cfg_scale=None, cfg_min_t=0.5, cfg_max_t=1.0, truncation_factor=None, rescale_k=None, rescale_sigma=None, context_kv_cache=True, speaker_kv_scale=None, speaker_kv_min_t=None, speaker_kv_max_layers=None, speaker_uncond_mode="mask", seed=int(seed), t_schedule_mode="linear", sway_coeff=-1.0, trim_tail=True, lora_adapter=None), log_fn=lambda m: None)
    save_wav(output, result.audios[0].float(), result.sample_rate)


def generate_best(runtime: Any, asr_model: Any, *, voice: dict[str,Any], style: dict[str,Any] | None, refs: list[Path], out_path: Path) -> dict[str,Any]:
    if style is None:
        text = ANCHOR_TEXT
        caption = f"{voice['caption']} 自然な日常会話。力まず落ち着いて、すべての音を明瞭に発音する。 {QUALITY}"
        mode = "neutral"
        target_rms = -20.0
        duration_scale = 1.0
        style_number = 0
        label = "基準声"
    else:
        text = style["text"]
        caption = f"声質は参照音声と同じ人物として保つ。{style['caption']} {QUALITY} 指定された短い台詞だけを話し、終わったら完全に黙る。"
        mode = style["mode"]
        target_rms = float(style["target_rms"])
        duration_scale = float(style["duration_scale"])
        style_number = int(style["number"])
        label = str(style["label"])
    candidate_dir = WORK / "候補" / str(voice["folder"]) / f"{style_number:02d}_{label}"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str,Any]] = []
    accepted: list[tuple[float,Path,dict[str,Any]]] = []
    scales = [0.94, 1.00, 1.06, 0.88, 1.12]
    for n in range(1, MAX_CANDIDATES+1):
        raw = candidate_dir / f"候補{n:02d}_生.wav"
        synthesize(runtime, text=text, caption=caption, refs=refs, seed=int(voice["seed"]) + style_number*100000 + n*1013, duration_scale=duration_scale*scales[n-1], output=raw)
        aligned, transcript1 = align_to_target(raw, text, asr_model)
        x, sr = sf.read(aligned, dtype="float32", always_2d=True)
        processed = transparent_process(np.mean(x, axis=1), int(sr), target_rms)
        processed_path = candidate_dir / f"候補{n:02d}_整音.wav"
        sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")
        final_aligned, transcript2 = align_to_target(processed_path, text, asr_model)
        if final_aligned != processed_path:
            x2, sr2 = sf.read(final_aligned, dtype="float32", always_2d=True)
            processed = transparent_process(np.mean(x2, axis=1), int(sr2), target_rms)
            sf.write(processed_path, processed, TARGET_SR, subtype="PCM_24")
        transcript, words = transcribe(processed_path, asr_model)
        score = asr_score(text, transcript, mode)
        m = metrics(processed)
        integrity = 0.55 <= m["duration"] <= 9.5 and -45 <= m["rms_dbfs"] <= -8 and m["clip_ratio"] <= 0.0001 and 250 <= m["centroid"] <= 8500 and 0 <= m["flatness"] <= 0.40 and 0 <= m["high_ratio"] <= 0.45
        clarity = float(np.clip(0.4*np.exp(-((m["centroid"]-2800)/2400)**2) + 0.3*np.exp(-((m["high_ratio"]-0.07)/0.10)**2) + 0.3*np.exp(-((m["flatness"]-0.02)/0.12)**2),0,1))
        accepted_flag = bool(score["accepted"] and integrity)
        rec = {"voice":voice["folder"],"style":label,"candidate":n,"text":text,"transcript":transcript,"transcript_before":transcript1,"transcript_after_first_align":transcript2,**score,**m,"integrity":integrity,"clarity":clarity,"accepted":accepted_flag,"path":str(processed_path)}
        records.append(rec)
        log(f"{voice['folder']} / {label} / 候補{n}: ASR={score['ratio']:.3f} partial={score['partial']:.3f} delta={score['delta']} clarity={clarity:.3f} accepted={accepted_flag}")
        if accepted_flag:
            total = 0.72*score["ratio"] + 0.10*score["partial"] + 0.18*clarity
            accepted.append((total, processed_path, rec))
        if n >= 3 and accepted:
            break
    if not accepted:
        records.sort(key=lambda r:(r["ratio"],r["partial"],r["clarity"]), reverse=True)
        best = records[0]
        # Do not silently ship a failed reading. Retry with the best signal only when the
        # mismatch is tiny and there is no positive trailing text.
        if best["ratio"] >= 0.78 and best["partial"] >= 0.92 and best["delta"] <= 1 and best["integrity"]:
            accepted.append((best["ratio"],Path(best["path"]),best))
        else:
            raise RuntimeError(f"合格候補なし: {voice['folder']} / {label}; {best}")
    accepted.sort(key=lambda item:item[0], reverse=True)
    chosen = accepted[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chosen[1], out_path)
    with (VALIDATION / "生成候補.csv").open("a",encoding="utf-8-sig",newline="") as f:
        fields = list(records[0].keys())
        write_header = f.tell()==0
        w = csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        if write_header: w.writeheader()
        for row in records: w.writerow(row)
    return chosen[2]


def make_ear_stereo(x: np.ndarray, voice_number: int) -> np.ndarray:
    delay = int(round(TARGET_SR * 0.00022))
    near = x.astype(np.float32).copy()
    far = np.pad(near,(delay,0))[:near.size]
    if far.size > 64:
        far = sosfiltfilt(butter(2,6500/(TARGET_SR/2),btype="lowpass",output="sos"),far).astype(np.float32)
    near *= 10**(0.45/20); far *= 10**(-1.45/20)
    stereo = np.column_stack((near,far)) if voice_number%2 else np.column_stack((far,near))
    peak = float(np.max(np.abs(stereo)))
    limit = 10**(-1/20)
    if peak>limit: stereo*=limit/peak
    return stereo.astype(np.float32)


def copy_previous() -> None:
    for wav in PREVIOUS.rglob("*.wav"):
        parts = wav.parts
        if "モノラル" not in parts:
            continue
        try:
            idx = parts.index("モノラル")
            voice_folder = parts[idx+1]
            filename = parts[idx+2]
        except Exception:
            continue
        if voice_folder not in {v["folder"] for v in VOICES}:
            continue
        dst = FINAL_MONO / voice_folder / filename
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or wav.stat().st_size > dst.stat().st_size:
            shutil.copy2(wav,dst)


def style_file(folder: str, style: dict[str,Any]) -> Path:
    return FINAL_MONO / folder / f"{int(style['number']):02d}_{style['label']}_{style['short']}.wav"


def choose_refs(voice: dict[str,Any]) -> list[Path]:
    folder = str(voice["folder"])
    refs: list[Path] = []
    for number in (1,2,8):
        style = STYLES[number-1]
        p = style_file(folder,style)
        if p.exists(): refs.append(p)
    return refs


def validate_existing(asr_model: Any) -> list[tuple[dict[str,Any],dict[str,Any]]]:
    missing: list[tuple[dict[str,Any],dict[str,Any]]] = []
    rows: list[dict[str,Any]] = []
    for voice in VOICES:
        for style in STYLES:
            p = style_file(str(voice["folder"]),style)
            if not p.exists():
                missing.append((voice,style)); continue
            x,sr = sf.read(p,dtype="float32",always_2d=True)
            mono = np.mean(x,axis=1).astype(np.float32)
            if int(sr)!=TARGET_SR or x.shape[1]!=1:
                mono = resample_mono(mono,int(sr)); sf.write(p,mono,TARGET_SR,subtype="PCM_24")
            transcript,_ = transcribe(p,asr_model)
            score = asr_score(str(style["text"]),transcript,str(style["mode"]))
            m = metrics(mono)
            row={"file":str(p.relative_to(WORK)),"voice":voice["folder"],"style":style["label"],"transcript":transcript,**score,**m}
            rows.append(row)
            # Existing v6 material already passed a stricter checker. Only invalidate a
            # clearly wrong reading or a suspiciously long tail.
            if score["ratio"] < 0.72 or score["partial"] < 0.88 or score["delta"] > 4:
                p.unlink(missing_ok=True); missing.append((voice,style))
    if rows:
        with (VALIDATION/"既存WAV再検査.csv").open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return missing


def package_zip(source: Path, dest: Path) -> None:
    dest.unlink(missing_ok=True)
    with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in sorted(source.rglob("*.wav")):
            z.write(p,p.relative_to(source).as_posix())
    with zipfile.ZipFile(dest) as z:
        bad=z.testzip()
        if bad: raise RuntimeError(f"ZIP CRC異常: {bad}")


def main() -> None:
    copy_previous()
    log("OpenAI Whisper baseを読み込み")
    asr_model = whisper.load_model("base",device="cpu")
    missing = validate_existing(asr_model)
    log(f"再生成対象: {len(missing)}件")
    runtime = build_runtime()

    # Generate anchors only for voices without enough clean references.
    anchors: dict[int,Path] = {}
    for voice in VOICES:
        refs = choose_refs(voice)
        if len(refs) >= 2:
            continue
        anchor = WORK/"基準声"/str(voice["folder"])/"採用した基準声.wav"
        generate_best(runtime,asr_model,voice=voice,style=None,refs=[],out_path=anchor)
        anchors[int(voice["index"])]=anchor

    # Recompute because an existing file may have been invalidated.
    for voice,style in missing:
        refs=choose_refs(voice)
        if len(refs)<2:
            anchor=anchors.get(int(voice["index"]))
            if anchor is None:
                anchor=WORK/"基準声"/str(voice["folder"])/"採用した基準声.wav"
                generate_best(runtime,asr_model,voice=voice,style=None,refs=[],out_path=anchor)
                anchors[int(voice["index"])]=anchor
            refs=[anchor]
        out=style_file(str(voice["folder"]),style)
        generate_best(runtime,asr_model,voice=voice,style=style,refs=refs[:3],out_path=out)

    # Final strict structural and ASR validation.
    final_rows: list[dict[str,Any]]=[]
    for voice in VOICES:
        folder=FINAL_MONO/str(voice["folder"])
        files=sorted(folder.glob("*.wav"))
        if len(files)!=10:
            raise RuntimeError(f"{voice['folder']} が10本ではありません: {len(files)}")
        for style in STYLES:
            p=style_file(str(voice["folder"]),style)
            if not p.exists(): raise RuntimeError(f"欠落: {p}")
            x,sr=sf.read(p,dtype="float32",always_2d=True)
            if int(sr)!=TARGET_SR or x.shape[1]!=1: raise RuntimeError(f"形式異常: {p}")
            transcript,_=transcribe(p,asr_model)
            score=asr_score(str(style["text"]),transcript,str(style["mode"]))
            m=metrics(np.mean(x,axis=1))
            if score["ratio"]<0.72 or score["partial"]<0.88 or score["delta"]>4:
                raise RuntimeError(f"最終ASR不合格: {p}: {transcript!r} {score}")
            final_rows.append({"file":str(p.relative_to(FINAL_MONO)),"voice":voice["folder"],"style":style["label"],"text":style["text"],"transcript":transcript,"sha256":sha256(p),**score,**m})
        asmr=style_file(str(voice["folder"]),STYLES[8])
        x,sr=sf.read(asmr,dtype="float32",always_2d=True)
        stereo=make_ear_stereo(np.mean(x,axis=1),int(voice["index"])+1)
        dst=FINAL_STEREO/str(voice["folder"])/asmr.name
        dst.parent.mkdir(parents=True,exist_ok=True)
        sf.write(dst,stereo,TARGET_SR,subtype="PCM_24")

    with (VALIDATION/"最終80WAV検査.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(final_rows[0].keys())); w.writeheader(); w.writerows(final_rows)

    mono_zip=OUT/"Irodori_v4_中高音8声_各10話法_明瞭再生成版_80WAV_日本語.zip"
    stereo_zip=OUT/"Irodori_v4_ASMR耳元ステレオ_8声8WAV_日本語.zip"
    package_zip(FINAL_MONO,mono_zip)
    package_zip(FINAL_STEREO,stereo_zip)
    validation_zip=OUT/"Irodori_v4_明瞭再生成版_検証資料.zip"
    validation_zip.unlink(missing_ok=True)
    with zipfile.ZipFile(validation_zip,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(VALIDATION.rglob("*")):
            if p.is_file(): z.write(p,p.relative_to(VALIDATION).as_posix())
    summary={"mono_wav_count":80,"stereo_wav_count":8,"checkpoint":CHECKPOINT,"sample_rate":TARGET_SR,"subtype":"PCM_24","mono_zip_sha256":sha256(mono_zip),"stereo_zip_sha256":sha256(stereo_zip),"validation_zip_sha256":sha256(validation_zip)}
    (OUT/"最終集計.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"SHA256SUMS.txt").write_text("\n".join(f"{sha256(p)}  {p.name}" for p in (mono_zip,stereo_zip,validation_zip))+"\n",encoding="utf-8")
    log(json.dumps(summary,ensure_ascii=False))


if __name__ == "__main__":
    main()
