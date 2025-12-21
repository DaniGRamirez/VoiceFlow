#!/usr/bin/env python3
"""
Split a long WAV recording into short clips using simple energy-based VAD.

Typical use:
  - Record a long WAV saying "Claudia" many times with pauses.
  - Run this script to auto-cut each utterance into separate WAV clips.

Dependencies:
  pip install numpy scipy

Examples:
  python split_wake_clips.py input.wav out_clips
  python split_wake_clips.py input.wav out_clips --target_sr 16000 --mono --normalize
  python split_wake_clips.py input.wav out_clips --threshold 0.015 --padding_ms 200
"""

import os
import argparse
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly


def to_mono(x: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        return x
    # average channels to mono
    return x.mean(axis=1)


def int16_to_float(x: np.ndarray) -> np.ndarray:
    if x.dtype == np.int16:
        return x.astype(np.float32) / 32768.0
    if x.dtype == np.int32:
        return x.astype(np.float32) / 2147483648.0
    if x.dtype == np.uint8:
        return (x.astype(np.float32) - 128.0) / 128.0
    if np.issubdtype(x.dtype, np.floating):
        return x.astype(np.float32)
    return x.astype(np.float32)


def float_to_int16(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -1.0, 1.0)
    return (x * 32767.0).astype(np.int16)


def rms_energy(frames: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frames * frames) + 1e-12))


def smooth_ema(values: np.ndarray, alpha: float) -> np.ndarray:
    out = np.empty_like(values, dtype=np.float32)
    acc = 0.0
    for i, v in enumerate(values):
        acc = alpha * v + (1 - alpha) * acc
        out[i] = acc
    return out


def find_segments(
    x: np.ndarray,
    sr: int,
    frame_ms: int,
    hop_ms: int,
    threshold: float,
    min_speech_ms: int,
    min_silence_ms: int,
) -> list[tuple[int, int]]:
    """
    Returns list of (start_sample, end_sample) segments where energy > threshold.
    Uses hysteresis via min_silence_ms to close segments.
    """
    frame = int(sr * frame_ms / 1000)
    hop = int(sr * hop_ms / 1000)
    if frame <= 0 or hop <= 0:
        raise ValueError("frame_ms/hop_ms too small for given sample rate")

    # Compute RMS per hop window (centered-ish)
    energies = []
    positions = []
    for start in range(0, len(x) - frame + 1, hop):
        chunk = x[start : start + frame]
        energies.append(rms_energy(chunk))
        positions.append(start)
    energies = np.array(energies, dtype=np.float32)

    # Smooth energies (reduce jitter)
    energies_s = smooth_ema(energies, alpha=0.35)

    min_speech_frames = max(1, int(min_speech_ms / hop_ms))
    min_silence_frames = max(1, int(min_silence_ms / hop_ms))

    segments = []
    in_seg = False
    seg_start = 0
    silence_count = 0
    speech_frames = 0

    for i, e in enumerate(energies_s):
        pos = positions[i]
        is_speech = e >= threshold

        if not in_seg:
            if is_speech:
                in_seg = True
                seg_start = pos
                silence_count = 0
                speech_frames = 1
        else:
            if is_speech:
                speech_frames += 1
                silence_count = 0
            else:
                silence_count += 1
                if silence_count >= min_silence_frames:
                    # close segment
                    seg_end = pos  # end at start of sustained silence
                    if speech_frames >= min_speech_frames:
                        segments.append((seg_start, seg_end))
                    in_seg = False

    # close tail
    if in_seg and speech_frames >= min_speech_frames:
        segments.append((seg_start, len(x)))

    return segments, energies_s


def pad_and_limit(
    seg: tuple[int, int],
    sr: int,
    padding_ms: int,
    max_len_ms: int | None,
    total_len: int,
) -> tuple[int, int]:
    start, end = seg
    pad = int(sr * padding_ms / 1000)
    start = max(0, start - pad)
    end = min(total_len, end + pad)

    if max_len_ms is not None:
        max_len = int(sr * max_len_ms / 1000)
        if end - start > max_len:
            # keep centered around original segment midpoint
            mid = (start + end) // 2
            start = max(0, mid - max_len // 2)
            end = min(total_len, start + max_len)
    return start, end


def normalize_peak(x: np.ndarray, peak: float = 0.95) -> np.ndarray:
    m = float(np.max(np.abs(x)) + 1e-12)
    return x * (peak / m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_wav", help="Path to input WAV file (long recording).")
    ap.add_argument("out_dir", help="Output directory for clips.")
    ap.add_argument("--frame_ms", type=int, default=30, help="Analysis frame size in ms (default 30).")
    ap.add_argument("--hop_ms", type=int, default=10, help="Hop size in ms (default 10).")
    ap.add_argument("--threshold", type=float, default=0.012, help="Energy threshold (default 0.012).")
    ap.add_argument("--min_speech_ms", type=int, default=180, help="Minimum speech duration to keep (default 180).")
    ap.add_argument("--min_silence_ms", type=int, default=250, help="Silence required to close a segment (default 250).")
    ap.add_argument("--padding_ms", type=int, default=160, help="Padding before/after each clip (default 160).")
    ap.add_argument("--max_len_ms", type=int, default=1600, help="Max length per clip (default 1600).")
    ap.add_argument("--target_sr", type=int, default=0, help="Resample to this SR (e.g. 16000). 0 = keep.")
    ap.add_argument("--mono", action="store_true", help="Convert to mono.")
    ap.add_argument("--normalize", action="store_true", help="Peak normalize each clip.")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    sr, data = wavfile.read(args.input_wav)
    x = int16_to_float(data)

    if args.mono:
        x = to_mono(x)

    # Resample if requested
    if args.target_sr and args.target_sr != sr:
        # resample_poly expects 1D
        if x.ndim != 1:
            x = to_mono(x)
        # Use rational approximation: up/down
        # Good enough for voice.
        up = args.target_sr
        down = sr
        g = np.gcd(up, down)
        up //= g
        down //= g
        x = resample_poly(x, up, down).astype(np.float32)
        sr = args.target_sr

    segments, energies_s = find_segments(
        x,
        sr,
        frame_ms=args.frame_ms,
        hop_ms=args.hop_ms,
        threshold=args.threshold,
        min_speech_ms=args.min_speech_ms,
        min_silence_ms=args.min_silence_ms,
    )

    if not segments:
        print("No segments found. Try lowering --threshold (e.g. 0.008) or check input gain.")
        return

    # Post-process: pad + limit length
    final = []
    for seg in segments:
        s, e = pad_and_limit(
            seg,
            sr,
            padding_ms=args.padding_ms,
            max_len_ms=args.max_len_ms if args.max_len_ms > 0 else None,
            total_len=len(x),
        )
        # skip tiny
        if e - s < int(sr * 0.2):
            continue
        final.append((s, e))

    # Export clips
    for idx, (s, e) in enumerate(final, start=1):
        clip = x[s:e].copy()
        if args.normalize:
            clip = normalize_peak(clip, peak=0.95)

        out_path = os.path.join(args.out_dir, f"clip_{idx:04d}.wav")
        wavfile.write(out_path, sr, float_to_int16(clip))
    print(f"Saved {len(final)} clips to: {args.out_dir}")
    print("Tip: If you get too many tiny clips, raise --threshold or increase --min_speech_ms.")


if __name__ == "__main__":
    main()
