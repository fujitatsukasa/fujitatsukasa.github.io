#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import re
import shutil
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from gradio_client import Client, handle_file
from huggingface_hub import hf_hub_download
from rapidfuzz import fuzz
from scipy.signal import butter, resample_poly, sosfiltfilt
from transformers import HubertForSequenceClassification, Wav2Vec2FeatureExtractor

ROOT = Path.cwd()
WORK = ROOT / "irodori_v4_mid_high_work"
OUT = ROOT / "irodori_v4_mid_high_output"
MONO_ALL = OUT / "Irodori_v4_中高音8声_10話法_台詞感情一致_透明スタジオ原音"
MONO_MID = OUT / "Irodori_v4_中高音4声_10話法_台詞感情一致_透明スタジオ原音"
MONO_HIGH = OUT / "Irodori_v4_高音4声_10話法_台詞感情一致_透明スタジオ原音"
BINAURAL_ALL = OUT / "Irodori_v4_中高音8声_10話法_ASMRバイノーラル風"
VALIDATION = OUT / "検証資料"
DOWNLOADS = WORK / "gradio_downloads"
for directory in (WORK, OUT, MONO_ALL, MONO_MID, MONO_HIGH, BINAURAL_ALL, VALIDATION, DOWNLOADS):
    directory.mkdir(parents=True, exist_ok=True)

CLONE_REPO = "SynDataLab-JA/irodori-clones-3m"
CLONE_REVISION = "ce53b9287f04a2506c08f77b3b8b5287caed6bb4"
SPACE = "Aratako/Irodori-TTS-v4-Small-Demo"
TARGET_SR = 48000

QUALITY_CAPTION = (
    "静かな防音スタジオで、広帯域の高性能コンデンサーマイクを使った近接収録。"
    "透明で抜けがよく、こもりがなく、子音が自然に明瞭。"
    "部屋鳴り、ヒス、電話音、金属的な歪み、過度なノイズ抑制感はない。"
    "声を潰す強いコンプレッションは使わず、乾いた自然な音質。"
)

ANCHOR_TEXT = (
    "おはよう。今日は空気が澄んでいて、とても気持ちのいい朝ですね。"
    "少しゆっくり話しながら、これからの予定を確認していきましょう。"
    "分からないことがあれば、遠慮なく聞いてください。"
)
ANCHOR_STYLE = (
    "普段の自然な声で、力まず、穏やかに話す。声量は普通より少し小さく、"
    "一定の距離で、叫ばず、泣かず、笑い声や強い感情を入れない。"
)

VOICES = [
    {
        "number": 1,
        "group": "中高音",
        "folder": "01_中高音・囁き向き・近距離",
        "speaker_number": 4428,
        "base_caption": "若い成人の中高音。近距離でも刺さらない、細く柔らかい声。囁きや小声に向き、息は自然で、輪郭は透明。",
    },
    {
        "number": 2,
        "group": "中高音",
        "folder": "02_中高音・やさしい・透明",
        "speaker_number": 2022,
        "base_caption": "若い成人の中高音。やさしく澄んだ声で、声の芯は細すぎず、柔らかな透明感がある。",
    },
    {
        "number": 3,
        "group": "中高音",
        "folder": "03_中高音・丁寧・明瞭",
        "speaker_number": 1635,
        "base_caption": "若い成人の中高音。丁寧で発音が明瞭、上品で落ち着いた声。声を張らなくても言葉が聞き取りやすい。",
    },
    {
        "number": 4,
        "group": "中高音",
        "folder": "04_中高音・やわらかい・丸い",
        "speaker_number": 1639,
        "base_caption": "若い成人の中高音。角のない丸い声質で、柔らかく親しみやすい。近距離でも耳に痛くならない。",
    },
    {
        "number": 5,
        "group": "高音",
        "folder": "05_高音・小さめ・落ち着き",
        "speaker_number": 526,
        "base_caption": "若い成人の高めの声。声量は小さめで落ち着きがあり、明るすぎず、静かな会話に向く。",
    },
    {
        "number": 6,
        "group": "高音",
        "folder": "06_高音・親密・息少なめ",
        "speaker_number": 9925,
        "base_caption": "若い成人の高めの声。親密で近い距離感だが、息漏れは少なく、細部まで澄んで聞こえる。",
    },
    {
        "number": 7,
        "group": "高音",
        "folder": "07_高音・軽い・自然会話",
        "speaker_number": 3333,
        "base_caption": "若い成人の高めの声。軽やかで自然な日常会話に向き、過剰なアニメ声や叫び声にはしない。",
    },
    {
        "number": 8,
        "group": "高音",
        "folder": "08_かなり高い・繊細・透明",
        "speaker_number": 2829,
        "base_caption": "若い成人のかなり高い声。繊細で透明、細いが不安定ではなく、耳元の小声でも輪郭が保たれる。",
    },
]

STYLES = [
    {
        "number": 1,
        "label": "自然な近距離会話",
        "short": "駅前のカフェへ寄らない",
        "text": "ねえ、帰りに駅前のカフェへ寄らない？新しいメニュー、ちょっと気になってるんだ。",
        "caption": (
            "親しい相手と一対一で話す、ごく自然な日常会話。"
            "普通より少し小さな声で、適度な間と自然な抑揚。"
            "絶対に叫ばず、急に声を張らず、芝居がかった感情を足さない。"
        ),
        "duration_scale": 1.00,
        "caption_cfg": 4.2,
        "target_rms": -20.0,
        "angle": 0.0,
        "emotion": "neutral",
    },
    {
        "number": 2,
        "label": "丁寧で穏やかな案内",
        "short": "いつでも声をかけてください",
        "text": "こちらの資料をご確認ください。分からないところがあれば、いつでも声をかけてくださいね。",
        "caption": (
            "穏やかで丁寧な案内。落ち着いた速度で、語尾まで柔らかく明瞭に話す。"
            "事務的に冷たくせず、過剰に明るくせず、朗読調や叫び声にしない。"
        ),
        "duration_scale": 1.06,
        "caption_cfg": 4.4,
        "target_rms": -20.5,
        "angle": 0.0,
        "emotion": "neutral",
    },
    {
        "number": 3,
        "label": "眠く力の抜けた話し方",
        "short": "あと五分だけこのままで",
        "text": "ん……ごめん、まだちょっと眠くて。あと五分だけ、このままでいさせて……🥱",
        "caption": (
            "本当に眠く、まぶたが重く、全身の力が抜けている。"
            "声量は小さく、息を少し多く含ませ、一語ずつ遅く、語尾を長く下げる。"
            "あくびをこらえるような近距離の声。元気にせず、明るく張らず、絶対に叫ばない。"
        ),
        "duration_scale": 1.18,
        "caption_cfg": 5.2,
        "target_rms": -23.0,
        "angle": 24.0,
        "emotion": "sleepy",
    },
    {
        "number": 4,
        "label": "悲しく弱った話し方",
        "short": "少しだけそばにいて",
        "text": "大丈夫って言いたいのに、今日はうまく笑えないんだ。少しだけ、そばにいてくれる？……😢",
        "caption": (
            "悲しみで気力が落ち、今にも涙がこぼれそう。声は弱く少し震え、息が浅い。"
            "明るく笑わず、怒鳴らず、元気に持ち直さず、最後まで弱った調子を保つ。"
        ),
        "duration_scale": 1.13,
        "caption_cfg": 5.2,
        "target_rms": -22.0,
        "angle": -20.0,
        "emotion": "sad",
    },
    {
        "number": 5,
        "label": "怒りを抑えた話し方",
        "short": "もう同じことは繰り返さないで",
        "text": "それ、本気で言ってるの？私はずっと我慢してた。もう同じことは繰り返さないで。😠",
        "caption": (
            "怒りと不満が明確に伝わる。声の芯を強くし、重要語と語尾に力を置く。"
            "ただし絶叫や金切り声にはせず、感情を抑えながら低い圧を保つ。"
            "無感情や普通の会話に戻さず、怒りを最後まで維持する。"
        ),
        "duration_scale": 0.98,
        "caption_cfg": 5.2,
        "target_rms": -18.5,
        "angle": 10.0,
        "emotion": "angry",
    },
    {
        "number": 6,
        "label": "怖く慌てた話し方",
        "short": "急に離れないで怖いよ",
        "text": "待って、今そこから音がしたよね？お願い、急に離れないで……怖いよ。😰",
        "caption": (
            "本気で怖がり、焦って息が浅く、声が少し震えている。"
            "速度はやや速く、問いかけは切迫させる。"
            "ただし長い絶叫にはせず、台詞を聞き取れる範囲で恐怖と慌てを明確にする。"
        ),
        "duration_scale": 0.94,
        "caption_cfg": 5.3,
        "target_rms": -19.0,
        "angle": -32.0,
        "emotion": "fear",
    },
    {
        "number": 7,
        "label": "明るくうれしい話し方",
        "short": "ずっと楽しみにしてた",
        "text": "やった、ほんとに来てくれたんだ！うれしい。今日はずっと楽しみにしてたの。😊",
        "caption": (
            "心からうれしく、笑顔が声に表れている。明るく弾む抑揚で、少し速めに話す。"
            "悲しげ、眠そう、冷淡にはせず、喜びを最後まで明確に保つ。"
            "ただし音割れする叫び声にはしない。"
        ),
        "duration_scale": 0.96,
        "caption_cfg": 4.9,
        "target_rms": -18.8,
        "angle": 22.0,
        "emotion": "happy",
    },
    {
        "number": 8,
        "label": "やさしく心配する話し方",
        "short": "落ち着くまでここにいよう",
        "text": "無理して笑わなくていいよ。温かいものを飲んで、落ち着くまでここにいよう。",
        "caption": (
            "弱っている相手を責めずに気遣う、やさしく心配した声。"
            "声量を小さく、速度を少し落とし、包み込むように話す。"
            "説教調、怒り、過剰な明るさ、叫び声を入れない。"
        ),
        "duration_scale": 1.09,
        "caption_cfg": 4.8,
        "target_rms": -21.5,
        "angle": -16.0,
        "emotion": "gentle",
    },
    {
        "number": 9,
        "label": "ASMR耳元囁き",
        "short": "ゆっくり息を吸って力を抜いて",
        "text": "聞こえる？今は何も考えなくていいよ。ゆっくり息を吸って……そのまま、力を抜いて。👂😮‍💨",
        "caption": (
            "ASMRのような耳元の囁き。マイクから数センチの非常に近い距離で、"
            "声帯を強く鳴らさず、柔らかな息と小声だけでゆっくり話す。"
            "左右の耳へ語りかけるような親密さ。絶対に声を張らず、叫ばず、急に大きくしない。"
            "息は自然だがヒスにはせず、子音は透明に聞こえる。"
        ),
        "duration_scale": 1.22,
        "caption_cfg": 5.4,
        "target_rms": -25.0,
        "angle": 55.0,
        "emotion": "asmr",
    },
    {
        "number": 10,
        "label": "笑い混じりの話し方",
        "short": "そんなに真剣な顔しなくても",
        "text": "ふふっ、そんなに真剣な顔しなくても大丈夫。ちゃんと分かってるから。🤭",
        "caption": (
            "親しい相手に向けて、最初に短く本当に笑い、台詞の途中にも微笑みがにじむ。"
            "笑いを明確に入れるが、笑い声だけで台詞を潰さない。"
            "無感情や怒りにはせず、楽しそうな笑い混じりを最後まで保つ。"
        ),
        "duration_scale": 1.04,
        "caption_cfg": 5.3,
        "target_rms": -20.0,
        "angle": 34.0,
        "emotion": "happy",
    },
]

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)


def log(message: str) -> None:
    print(message, flush=True)
    with (VALIDATION / "実行ログ.txt").open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def safe_component(value: str, limit: int = 110) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" ._")
    return (value or "名称なし")[:limit]


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).lower()
    value = EMOJI_PATTERN.sub("", value)
    value = re.sub(r"[\s、。,.!！?？…・『』「」()（）\-ー]", "", value)
    return value


def decode_audio_cell(value: Any) -> tuple[np.ndarray, int]:
    if hasattr(value, "as_py"):
        value = value.as_py()
    payload: bytes | None = None
    if isinstance(value, dict) and value.get("bytes") is not None:
        payload = bytes(value["bytes"])
    elif isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
    if payload is None:
        raise RuntimeError("Parquet audio cell has no embedded bytes")
    signal, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
    return np.mean(signal, axis=1).astype(np.float32), int(sample_rate)


def resample_mono(signal: np.ndarray, sample_rate: int, target_rate: int) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32)
    if signal.ndim > 1:
        signal = np.mean(signal, axis=1)
    if sample_rate != target_rate:
        divisor = math.gcd(int(sample_rate), int(target_rate))
        signal = resample_poly(signal, target_rate // divisor, sample_rate // divisor).astype(np.float32)
    return np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def audio_metrics(signal: np.ndarray, sample_rate: int) -> dict[str, float]:
    signal = np.asarray(signal, dtype=np.float32)
    if signal.size == 0:
        raise RuntimeError("empty audio")
    peak = float(np.max(np.abs(signal)))
    rms = float(np.sqrt(np.mean(signal * signal) + 1e-12))
    duration = float(signal.size / sample_rate)
    clip_ratio = float(np.mean(np.abs(signal) >= 0.999))
    click_ratio = float(np.mean(np.abs(np.diff(signal)) > 0.34)) if signal.size > 1 else 1.0
    threshold = max(10 ** (-48 / 20), peak * 0.01)
    silence_ratio = float(np.mean(np.abs(signal) < threshold))

    analysis = resample_mono(signal, sample_rate, 16000)
    frame_length = 1024
    hop = 256
    if analysis.size < frame_length:
        analysis = np.pad(analysis, (0, frame_length - analysis.size))
    frames = np.lib.stride_tricks.sliding_window_view(analysis, frame_length)[::hop]
    window = np.hanning(frame_length).astype(np.float32)
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1)) + 1e-9
    power = spectrum * spectrum
    frequencies = np.fft.rfftfreq(frame_length, 1 / 16000)
    total_power = np.maximum(power.sum(axis=1), 1e-12)
    flatness = float(np.mean(np.exp(np.mean(np.log(power), axis=1)) / np.maximum(np.mean(power, axis=1), 1e-12)))
    high_ratio = float(np.mean(power[:, frequencies >= 5000].sum(axis=1) / total_power))
    centroid = float(np.mean((power * frequencies).sum(axis=1) / total_power))

    f0_values: list[float] = []
    periodicities: list[float] = []
    stride = max(1, len(frames) // 100)
    for frame in frames[::stride]:
        frame = frame - float(np.mean(frame))
        energy = float(np.sqrt(np.mean(frame * frame) + 1e-12))
        if energy < 0.008:
            continue
        autocorrelation = np.correlate(frame, frame, mode="full")[frame_length - 1 :]
        low_lag = int(16000 / 520)
        high_lag = min(len(autocorrelation), int(16000 / 60))
        if high_lag <= low_lag or autocorrelation[0] <= 1e-12:
            continue
        lag = int(np.argmax(autocorrelation[low_lag:high_lag]) + low_lag)
        periodicity = float(autocorrelation[lag] / autocorrelation[0])
        if periodicity >= 0.18 and lag > 0:
            f0_values.append(16000.0 / lag)
            periodicities.append(periodicity)
    f0_array = np.asarray(f0_values, dtype=np.float32)
    return {
        "duration_sec": duration,
        "peak_dbfs": 20.0 * math.log10(max(peak, 1e-12)),
        "rms_dbfs": 20.0 * math.log10(max(rms, 1e-12)),
        "clip_ratio": clip_ratio,
        "click_ratio": click_ratio,
        "silence_ratio": silence_ratio,
        "spectral_flatness": flatness,
        "high_frequency_ratio": high_ratio,
        "spectral_centroid_hz": centroid,
        "f0_median_hz": float(np.median(f0_array)) if f0_array.size else 0.0,
        "f0_std_hz": float(np.std(f0_array)) if f0_array.size else 0.0,
        "periodicity": float(np.median(periodicities)) if periodicities else 0.0,
    }


def quality_score(metrics: dict[str, float], target_rms: float) -> float:
    score = 1.0
    score -= min(0.40, metrics["clip_ratio"] * 300.0)
    score -= min(0.20, metrics["click_ratio"] * 60.0)
    score -= min(0.25, max(0.0, metrics["spectral_flatness"] - 0.14) * 2.5)
    score -= min(0.20, max(0.0, metrics["high_frequency_ratio"] - 0.25) * 1.5)
    score -= min(0.18, abs(metrics["rms_dbfs"] - target_rms) / 25.0)
    if not 2.0 <= metrics["duration_sec"] <= 28.0:
        score -= 0.25
    return float(np.clip(score, 0.0, 1.0))


def choose_reference_rows(rows: list[dict[str, Any]], reference_dir: Path) -> list[Path]:
    candidates: list[tuple[float, int, str, np.ndarray, dict[str, float]]] = []
    forbidden = re.compile(r"[!！]{2,}|[?？]{2,}|笑|泣|怒|怖|叫|咳|あくび|眠|ため息|ふふ|あは", re.I)
    for index, row in enumerate(rows, 1):
        text = str(row.get("text") or "")
        if EMOJI_PATTERN.search(text) or forbidden.search(text):
            continue
        try:
            signal, sample_rate = decode_audio_cell(row.get("audio"))
            signal = resample_mono(signal, sample_rate, TARGET_SR)
            metrics = audio_metrics(signal, TARGET_SR)
        except Exception:
            continue
        if not 3.0 <= metrics["duration_sec"] <= 12.0:
            continue
        score = quality_score(metrics, -19.0)
        score += 0.10 * max(0.0, 1.0 - abs(metrics["duration_sec"] - 7.0) / 7.0)
        score += 0.05 * max(0.0, 1.0 - metrics["silence_ratio"])
        candidates.append((score, index, text, signal, metrics))
    if len(candidates) < 3:
        raise RuntimeError(f"not enough neutral reference candidates: {len(candidates)}")
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[tuple[float, int, str, np.ndarray, dict[str, float]]] = []
    normalized_texts: list[str] = []
    for item in candidates:
        normalized = normalize_text(item[2])
        if any(fuzz.ratio(normalized, prior) > 65 for prior in normalized_texts):
            continue
        selected.append(item)
        normalized_texts.append(normalized)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        selected = candidates[:3]
    reference_paths: list[Path] = []
    for order, (_, source_index, text, signal, metrics) in enumerate(selected, 1):
        processed = transparent_studio_process(signal, target_rms=-20.0, style_label="参照")
        path = reference_dir / f"参照_{order:02d}.wav"
        sf.write(path, processed, TARGET_SR, subtype="PCM_24")
        reference_paths.append(path)
        (reference_dir / f"参照_{order:02d}.txt").write_text(
            json.dumps({"source_row": source_index, "text": text, "metrics": metrics}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return reference_paths


def call_space(
    client: Client,
    text: str,
    caption: str,
    reference_paths: list[Path],
    *,
    seed: int,
    duration_scale: float,
    caption_cfg: float,
    candidates: int = 4,
    retries: int = 5,
) -> list[Path]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            result = client.predict(
                text=text,
                caption=caption,
                uploaded_audios=[handle_file(str(path)) for path in reference_paths],
                num_steps=48,
                num_candidates=candidates,
                seed_raw=str(seed),
                seconds_raw="",
                duration_scale=duration_scale,
                t_schedule_mode="linear",
                sway_coeff=-1.0,
                cfg_guidance_mode="independent",
                cfg_scale_text=3.1,
                cfg_scale_caption=caption_cfg,
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
            paths: list[Path] = []
            for update in result[:32]:
                if not isinstance(update, dict) or not update.get("visible") or not update.get("value"):
                    continue
                path = Path(str(update["value"]))
                if path.exists() and path.is_file():
                    paths.append(path)
            if len(paths) < candidates:
                raise RuntimeError(f"expected {candidates} generated files, found {len(paths)}")
            return paths[:candidates]
        except Exception as exc:
            last_error = exc
            log(f"Space call failed attempt {attempt}/{retries}: {exc!r}")
            time.sleep(min(60, 5 * attempt))
    raise RuntimeError(f"Irodori v4 Space call failed: {last_error}")


def split_anchor(signal: np.ndarray, sample_rate: int, destination: Path) -> list[Path]:
    signal = resample_mono(signal, sample_rate, TARGET_SR)
    frame = int(TARGET_SR * 0.02)
    if signal.size < frame * 20:
        raise RuntimeError("anchor too short")
    envelope = np.asarray([
        float(np.sqrt(np.mean(signal[index : index + frame] ** 2) + 1e-12))
        for index in range(0, signal.size - frame + 1, frame)
    ])
    threshold = max(float(np.percentile(envelope, 18)) * 1.35, 10 ** (-43 / 20))
    quiet = envelope < threshold
    quiet_runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, flag in enumerate(quiet):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            if index - start >= 10:
                quiet_runs.append((start, index))
            start = None
    if start is not None and len(quiet) - start >= 10:
        quiet_runs.append((start, len(quiet)))
    target_frames = [len(envelope) / 3.0, len(envelope) * 2.0 / 3.0]
    split_frames: list[int] = []
    for target in target_frames:
        if quiet_runs:
            run = min(quiet_runs, key=lambda item: abs(((item[0] + item[1]) / 2.0) - target))
            split_frames.append(int((run[0] + run[1]) / 2.0))
        else:
            split_frames.append(int(target))
    split_samples = sorted({max(frame * 5, min(signal.size - frame * 5, value * frame)) for value in split_frames})
    if len(split_samples) != 2:
        split_samples = [signal.size // 3, signal.size * 2 // 3]
    segments = [signal[: split_samples[0]], signal[split_samples[0] : split_samples[1]], signal[split_samples[1] :]]
    paths: list[Path] = []
    fade = int(TARGET_SR * 0.015)
    for index, segment in enumerate(segments, 1):
        segment = trim_silence(segment)
        if segment.size < TARGET_SR * 1.5:
            raise RuntimeError("anchor segment too short")
        if segment.size > fade * 2:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            segment[:fade] *= ramp
            segment[-fade:] *= ramp[::-1]
        path = destination / f"v4参照_{index:02d}.wav"
        sf.write(path, segment, TARGET_SR, subtype="PCM_24")
        paths.append(path)
    return paths


def trim_silence(signal: np.ndarray) -> np.ndarray:
    if signal.size == 0:
        return signal
    peak = float(np.max(np.abs(signal)))
    threshold = max(0.001, peak * 0.015)
    active = np.flatnonzero(np.abs(signal) >= threshold)
    if active.size == 0:
        return signal
    padding = int(TARGET_SR * 0.08)
    start = max(0, int(active[0]) - padding)
    end = min(signal.size, int(active[-1]) + padding + 1)
    return signal[start:end]


def emotion_probabilities(
    signal: np.ndarray,
    sample_rate: int,
    extractor: Wav2Vec2FeatureExtractor,
    model: HubertForSequenceClassification,
) -> dict[str, float]:
    signal16 = resample_mono(signal, sample_rate, 16000)
    inputs = extractor(signal16, sampling_rate=16000, return_tensors="pt", padding=True)
    with torch.no_grad():
        logits = model(**inputs).logits[0]
        probabilities = torch.softmax(logits, dim=-1).cpu().numpy()
    output: dict[str, float] = {"neutral": 0.0, "happy": 0.0, "angry": 0.0, "sad": 0.0}
    conventional = {0: "neutral", 1: "happy", 2: "angry", 3: "sad"}
    for index, probability in enumerate(probabilities):
        label = str(model.config.id2label.get(index, conventional.get(index, str(index)))).lower()
        if label in {"neu", "neutral", "label_0"}:
            key = "neutral"
        elif label in {"hap", "happy", "label_1"}:
            key = "happy"
        elif label in {"ang", "angry", "label_2"}:
            key = "angry"
        elif label in {"sad", "label_3"}:
            key = "sad"
        else:
            key = conventional.get(index, "neutral")
        output[key] = float(probability)
    return output


def transcribe_score(signal: np.ndarray, sample_rate: int, target_text: str, whisper: WhisperModel) -> tuple[str, float]:
    signal16 = resample_mono(signal, sample_rate, 16000)
    segments, _ = whisper.transcribe(signal16, language="ja", beam_size=3, vad_filter=True, condition_on_previous_text=False)
    transcript = "".join(segment.text for segment in segments).strip()
    expected = normalize_text(target_text)
    actual = normalize_text(transcript)
    if not actual:
        return transcript, 0.0
    score = max(fuzz.ratio(expected, actual), 0.92 * fuzz.partial_ratio(expected, actual)) / 100.0
    return transcript, float(score)


def style_score(style: dict[str, Any], metrics: dict[str, float], emotions: dict[str, float]) -> float:
    rms = metrics["rms_dbfs"]
    f0 = metrics["f0_median_hz"]
    f0_std = metrics["f0_std_hz"]
    duration = metrics["duration_sec"]
    periodicity = metrics["periodicity"]
    flatness = metrics["spectral_flatness"]
    kind = style["emotion"]
    if kind == "neutral":
        return 0.65 * emotions["neutral"] + 0.15 * max(0.0, 1.0 - f0_std / 120.0) + 0.20 * max(0.0, 1.0 - abs(rms + 20.0) / 15.0)
    if kind == "sleepy":
        slow = min(1.0, duration / 11.0)
        low_energy = max(0.0, min(1.0, (-rms - 17.0) / 10.0))
        stable = max(0.0, 1.0 - f0_std / 90.0)
        return 0.35 * slow + 0.30 * low_energy + 0.20 * stable + 0.15 * (emotions["neutral"] + emotions["sad"])
    if kind == "sad":
        low_energy = max(0.0, min(1.0, (-rms - 16.0) / 12.0))
        return 0.62 * emotions["sad"] + 0.23 * low_energy + 0.15 * max(0.0, 1.0 - f0_std / 110.0)
    if kind == "angry":
        energy = max(0.0, min(1.0, (rms + 25.0) / 10.0))
        movement = min(1.0, f0_std / 120.0)
        return 0.62 * emotions["angry"] + 0.23 * energy + 0.15 * movement
    if kind == "fear":
        pitch = max(0.0, min(1.0, (f0 - 170.0) / 180.0))
        movement = min(1.0, f0_std / 130.0)
        speed = max(0.0, min(1.0, 8.5 / max(duration, 1.0)))
        return 0.35 * pitch + 0.30 * movement + 0.20 * speed + 0.15 * max(emotions["angry"], emotions["happy"])
    if kind == "happy":
        energy = max(0.0, min(1.0, (rms + 25.0) / 10.0))
        movement = min(1.0, f0_std / 120.0)
        return 0.62 * emotions["happy"] + 0.23 * energy + 0.15 * movement
    if kind == "gentle":
        low_energy = max(0.0, min(1.0, (-rms - 16.0) / 11.0))
        stable = max(0.0, 1.0 - f0_std / 100.0)
        return 0.45 * emotions["neutral"] + 0.20 * emotions["sad"] + 0.20 * low_energy + 0.15 * stable
    if kind == "asmr":
        low_energy = max(0.0, min(1.0, (-rms - 18.0) / 12.0))
        breath = max(0.0, min(1.0, (flatness - 0.015) / 0.16))
        slow = min(1.0, duration / 12.0)
        soft_periodicity = max(0.0, min(1.0, (0.75 - periodicity) / 0.55))
        return 0.32 * low_energy + 0.22 * breath + 0.24 * slow + 0.12 * soft_periodicity + 0.10 * emotions["neutral"]
    return emotions["neutral"]


def select_candidate(
    candidate_paths: list[Path],
    target_text: str,
    style: dict[str, Any],
    whisper: WhisperModel,
    extractor: Wav2Vec2FeatureExtractor,
    emotion_model: HubertForSequenceClassification,
) -> tuple[Path, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    for index, path in enumerate(candidate_paths, 1):
        signal, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        mono = np.mean(signal, axis=1).astype(np.float32)
        metrics = audio_metrics(mono, int(sample_rate))
        transcript, asr = transcribe_score(mono, int(sample_rate), target_text, whisper)
        emotions = emotion_probabilities(mono, int(sample_rate), extractor, emotion_model)
        quality = quality_score(metrics, float(style["target_rms"]))
        delivery = style_score(style, metrics, emotions)
        score = 0.48 * asr + 0.28 * delivery + 0.24 * quality
        if asr < 0.30:
            score -= 0.25
        record = {
            "candidate": index,
            "path": str(path),
            "transcript": transcript,
            "asr_score": asr,
            "delivery_score": delivery,
            "quality_score": quality,
            "final_score": score,
            **metrics,
            **{f"emotion_{key}": value for key, value in emotions.items()},
        }
        records.append(record)
    records.sort(key=lambda item: float(item["final_score"]), reverse=True)
    return Path(records[0]["path"]), records


def peaking_eq(signal: np.ndarray, sample_rate: int, frequency: float, gain_db: float, q: float) -> np.ndarray:
    a = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * math.pi * frequency / sample_rate
    alpha = math.sin(omega) / (2.0 * q)
    cos_omega = math.cos(omega)
    b0 = 1.0 + alpha * a
    b1 = -2.0 * cos_omega
    b2 = 1.0 - alpha * a
    a0 = 1.0 + alpha / a
    a1 = -2.0 * cos_omega
    a2 = 1.0 - alpha / a
    sos = np.asarray([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]], dtype=np.float64)
    return sosfiltfilt(sos, signal).astype(np.float32)


def transparent_studio_process(signal: np.ndarray, target_rms: float, style_label: str) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32)
    signal = signal - float(np.mean(signal))
    highpass_hz = 65.0 if "高" in style_label else 58.0
    highpass = butter(3, highpass_hz / (TARGET_SR / 2.0), btype="highpass", output="sos")
    try:
        signal = sosfiltfilt(highpass, signal).astype(np.float32)
    except ValueError:
        pass
    # Mild corrective EQ only. The v4 output is preferred over aggressive denoising.
    try:
        signal = peaking_eq(signal, TARGET_SR, 310.0, -1.4, 0.85)
        signal = peaking_eq(signal, TARGET_SR, 3700.0, 1.1, 0.80)
        signal = peaking_eq(signal, TARGET_SR, 10500.0, 0.7, 0.70)
    except ValueError:
        pass
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    active_threshold = max(0.001, peak * 0.012)
    active = np.abs(signal) >= active_threshold
    active_signal = signal[active] if np.any(active) else signal
    rms = float(np.sqrt(np.mean(active_signal * active_signal) + 1e-12))
    target_linear = 10.0 ** (target_rms / 20.0)
    if rms > 1e-9:
        gain = float(np.clip(target_linear / rms, 0.25, 4.0))
        signal *= gain
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    peak_limit = 10.0 ** (-1.0 / 20.0)
    if peak > peak_limit:
        signal *= peak_limit / peak
    return np.clip(signal, -0.99, 0.99).astype(np.float32)


def far_ear_filter(signal: np.ndarray) -> np.ndarray:
    lowpass = butter(2, 8500.0 / (TARGET_SR / 2.0), btype="lowpass", output="sos")
    try:
        softened = sosfiltfilt(lowpass, signal).astype(np.float32)
        return (0.72 * signal + 0.28 * softened).astype(np.float32)
    except ValueError:
        return signal


def delay_signal(signal: np.ndarray, samples: int) -> np.ndarray:
    if samples <= 0:
        return signal.copy()
    return np.pad(signal, (samples, 0))[: signal.size].astype(np.float32)


def binaural_like(signal: np.ndarray, angle_degrees: float, voice_number: int, style_number: int) -> np.ndarray:
    # Alternate side between voices so the pack does not lean permanently to one ear.
    angle = float(angle_degrees)
    if (voice_number + style_number) % 2 == 0:
        angle = -angle
    radians = math.radians(angle)
    itd_seconds = 0.00055 * abs(math.sin(radians))
    delay_samples = int(round(itd_seconds * TARGET_SR))
    ild_db = 4.5 * abs(math.sin(radians))
    far_gain = 10.0 ** (-ild_db / 20.0)
    near = signal.copy()
    far = far_ear_filter(delay_signal(signal, delay_samples)) * far_gain
    if angle > 0:
        left, right = far, near
    elif angle < 0:
        left, right = near, far
    else:
        left = signal.copy()
        right = signal.copy()
    stereo = np.stack([left, right], axis=1).astype(np.float32)
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    limit = 10.0 ** (-1.0 / 20.0)
    if peak > limit:
        stereo *= limit / peak
    return stereo


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def copy_to_group(source: Path, group_dir: Path, voice_folder: str, filename: str) -> None:
    destination = group_dir / voice_folder / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    client = Client(SPACE, verbose=True, download_files=str(DOWNLOADS))
    whisper = WhisperModel("tiny", device="cpu", compute_type="int8")
    emotion_extractor = Wav2Vec2FeatureExtractor.from_pretrained("superb/hubert-base-superb-er")
    emotion_model = HubertForSequenceClassification.from_pretrained("superb/hubert-base-superb-er")
    emotion_model.eval()

    all_validation: list[dict[str, Any]] = []
    selected_summary: list[dict[str, Any]] = []

    for voice in VOICES:
        voice_work = WORK / f"voice_{voice['number']:02d}"
        old_reference_dir = voice_work / "old_references"
        clean_reference_dir = voice_work / "v4_clean_references"
        anchor_candidates_dir = voice_work / "anchor_candidates"
        style_candidates_dir = voice_work / "style_candidates"
        for directory in (voice_work, old_reference_dir, clean_reference_dir, anchor_candidates_dir, style_candidates_dir):
            directory.mkdir(parents=True, exist_ok=True)

        speaker_number = int(voice["speaker_number"])
        parquet_name = f"data/train-{speaker_number - 1:05d}-of-10000.parquet"
        parquet_path = Path(
            hf_hub_download(
                repo_id=CLONE_REPO,
                repo_type="dataset",
                filename=parquet_name,
                revision=CLONE_REVISION,
                local_dir=WORK / "clone_repo",
            )
        )
        rows = pq.read_table(parquet_path).to_pylist()
        old_reference_paths = choose_reference_rows(rows, old_reference_dir)

        anchor_caption = f"{voice['base_caption']}{ANCHOR_STYLE}{QUALITY_CAPTION}"
        anchor_paths = call_space(
            client,
            ANCHOR_TEXT,
            anchor_caption,
            old_reference_paths,
            seed=2026080400 + int(voice["number"]) * 100,
            duration_scale=1.05,
            caption_cfg=4.4,
            candidates=4,
        )
        local_anchor_paths: list[Path] = []
        for index, source in enumerate(anchor_paths, 1):
            destination = anchor_candidates_dir / f"候補_{index:02d}.wav"
            shutil.copy2(source, destination)
            local_anchor_paths.append(destination)
        selected_anchor, anchor_records = select_candidate(
            local_anchor_paths,
            ANCHOR_TEXT,
            {"emotion": "neutral", "target_rms": -20.0},
            whisper,
            emotion_extractor,
            emotion_model,
        )
        anchor_signal, anchor_rate = sf.read(selected_anchor, dtype="float32", always_2d=True)
        anchor_mono = np.mean(anchor_signal, axis=1).astype(np.float32)
        clean_reference_paths = split_anchor(anchor_mono, int(anchor_rate), clean_reference_dir)
        log(f"Voice {voice['number']}/8 clean v4 reference selected: {selected_anchor.name}")

        for style in STYLES:
            full_caption = (
                f"声質は参照音声と同一人物として保つ。{voice['base_caption']}"
                f"{style['caption']}"
                "台詞の意味と感情を必ず一致させ、途中で普通声や叫び声へ勝手に変えない。"
                f"{QUALITY_CAPTION}"
            )
            seed = 2026080400 + int(voice["number"]) * 1000 + int(style["number"]) * 10
            generated_paths = call_space(
                client,
                str(style["text"]),
                full_caption,
                clean_reference_paths,
                seed=seed,
                duration_scale=float(style["duration_scale"]),
                caption_cfg=float(style["caption_cfg"]),
                candidates=4,
            )
            candidate_dir = style_candidates_dir / f"{int(style['number']):02d}_{safe_component(style['label'])}"
            candidate_dir.mkdir(parents=True, exist_ok=True)
            local_paths: list[Path] = []
            for index, source in enumerate(generated_paths, 1):
                destination = candidate_dir / f"候補_{index:02d}.wav"
                shutil.copy2(source, destination)
                local_paths.append(destination)
            selected_path, candidate_records = select_candidate(
                local_paths,
                str(style["text"]),
                style,
                whisper,
                emotion_extractor,
                emotion_model,
            )
            filename = f"{int(style['number']):02d}_{safe_component(style['label'])}_{safe_component(style['short'])}.wav"
            selected_signal, selected_rate = sf.read(selected_path, dtype="float32", always_2d=True)
            selected_mono = np.mean(selected_signal, axis=1).astype(np.float32)
            selected_mono = resample_mono(selected_mono, int(selected_rate), TARGET_SR)
            processed = transparent_studio_process(selected_mono, float(style["target_rms"]), str(voice["folder"]))

            mono_path = MONO_ALL / str(voice["folder"]) / filename
            mono_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(mono_path, processed, TARGET_SR, subtype="PCM_24")
            group_dir = MONO_MID if voice["group"] == "中高音" else MONO_HIGH
            copy_to_group(mono_path, group_dir, str(voice["folder"]), filename)

            stereo = binaural_like(processed, float(style["angle"]), int(voice["number"]), int(style["number"]))
            binaural_path = BINAURAL_ALL / str(voice["folder"]) / filename
            binaural_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(binaural_path, stereo, TARGET_SR, subtype="PCM_24")

            for record in candidate_records:
                all_validation.append({
                    "voice_number": voice["number"],
                    "voice_folder": voice["folder"],
                    "style_number": style["number"],
                    "style_label": style["label"],
                    "target_text": style["text"],
                    "selected": Path(record["path"]).resolve() == selected_path.resolve(),
                    **record,
                })
            best_record = candidate_records[0]
            selected_summary.append({
                "voice_number": voice["number"],
                "voice_folder": voice["folder"],
                "style_number": style["number"],
                "style_label": style["label"],
                "target_text": style["text"],
                "filename": filename,
                "selected_candidate": best_record["candidate"],
                "asr_transcript": best_record["transcript"],
                "asr_score": best_record["asr_score"],
                "delivery_score": best_record["delivery_score"],
                "quality_score": best_record["quality_score"],
                "final_score": best_record["final_score"],
                "emotion_model_note": "英語IEMOCAP由来の4感情モデルを補助指標としてのみ使用",
                "binaural_note": "汎用ITD・ILD・遠耳高域減衰によるバイノーラル風。実測HRTFやダミーヘッド録音ではない",
            })
            log(f"Voice {voice['number']}/8 style {style['number']}/10 selected candidate {best_record['candidate']} score={best_record['final_score']:.3f}")

    write_csv(VALIDATION / "全候補320本_検証台帳.csv", all_validation)
    write_csv(VALIDATION / "最終80本_選抜結果.csv", selected_summary)

    def validate_pack(directory: Path, expected_files: int, channels: int) -> dict[str, Any]:
        wavs = sorted(directory.rglob("*.wav"))
        if len(wavs) != expected_files:
            raise RuntimeError(f"{directory.name}: WAV count {len(wavs)} != {expected_files}")
        durations = 0.0
        hashes: set[bytes] = set()
        for path in wavs:
            signal, rate = sf.read(path, dtype="float32", always_2d=True)
            if int(rate) != TARGET_SR or signal.shape[1] != channels or signal.size == 0:
                raise RuntimeError(f"invalid WAV: {path}: rate={rate}, channels={signal.shape[1]}")
            durations += signal.shape[0] / rate
            hashes.add(np.asarray(signal, dtype=np.float32).tobytes())
        return {
            "directory": directory.name,
            "wav_count": len(wavs),
            "sample_rate": TARGET_SR,
            "channels": channels,
            "total_duration_sec": round(durations, 3),
            "exact_pcm_unique_count": len(hashes),
        }

    validation_summary = {
        "model": "Aratako/Irodori-TTS-v4-Small via official public Space",
        "voices": 8,
        "styles_per_voice": 10,
        "final_wavs": 80,
        "candidates_per_style": 4,
        "candidate_wavs_evaluated": 320,
        "selection": "Japanese Whisper tiny ASR + objective audio metrics + auxiliary SUPERB HuBERT emotion scores",
        "human_listening": False,
        "packs": [
            validate_pack(MONO_ALL, 80, 1),
            validate_pack(MONO_MID, 40, 1),
            validate_pack(MONO_HIGH, 40, 1),
            validate_pack(BINAURAL_ALL, 80, 2),
        ],
    }
    (VALIDATION / "最終検証結果.json").write_text(json.dumps(validation_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (VALIDATION / "最初に読んでください.txt").write_text(
        "以前の配布版では、元データの任意の発話へ『眠い』『怒り』などの名称を後付けしており、台詞・演技・ファイル名が一致していませんでした。\n"
        "本版は最新Irodori v4-Smallで、各ファイル専用の台詞、感情キャプション、絵文字制御を使って新規生成しています。\n"
        "各話法につき4候補を生成し、日本語ASR、音響品質、感情補助指標から1本を選びました。\n"
        "ただし80本すべてを人間が通し試聴して最終合格判定したものではありません。\n"
        "バイノーラル風版は汎用ITD・ILD処理であり、実測HRTFやダミーヘッドによる真のバイノーラル録音ではありません。\n",
        encoding="utf-8",
    )
    log(json.dumps(validation_summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
