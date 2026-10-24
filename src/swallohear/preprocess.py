"""Band-pass, robust normalization, framing, quality indicators."""
from __future__ import annotations
import numpy as np
from scipy.signal import butter, sosfiltfilt
from . import TARGET_FS

FRAME = 256   # 64 ms @ 4 kHz
HOP = 64      # 16 ms

def bandpass(x, fs=TARGET_FS, lo=20.0, hi=1800.0, order=4):
    sos = butter(order, [lo, hi], btype="band", fs=fs, output="sos")
    return sosfiltfilt(sos, x).astype(np.float32)

def robust_norm(x):
    med = np.median(x); mad = np.median(np.abs(x - med)) * 1.4826
    return ((x - med) / (mad + 1e-8)).astype(np.float32)

def frame_signal(x, frame=FRAME, hop=HOP):
    if len(x) < frame: x = np.pad(x, (0, frame - len(x)))
    n = 1 + (len(x) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]

def frame_times(n_frames, frame=FRAME, hop=HOP, fs=TARGET_FS):
    """Center time (s) of each frame."""
    return (np.arange(n_frames) * hop + frame / 2) / fs

def preprocess(x, fs=TARGET_FS, filt=True):
    raw = np.asarray(x, dtype=np.float32)
    clip_frac = float(np.mean(np.abs(raw) >= 0.999 * max(np.max(np.abs(raw)), 1e-9))) if np.max(np.abs(raw)) >= 0.99 else 0.0
    y = bandpass(raw, fs) if filt else raw
    return robust_norm(y), dict(clip_frac=clip_frac)
