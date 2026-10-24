"""Synthetic swallow-like audio for tests and smoke demos. NOT clinical data."""
from __future__ import annotations
import numpy as np
from . import TARGET_FS

def make_recording(duration_s=20.0, n_events=4, snr_db=20.0, fs=TARGET_FS, seed=0):
    rng = np.random.default_rng(seed); n = int(duration_s * fs)
    x = np.zeros(n); events = []
    starts = np.sort(rng.uniform(1.0, duration_s - 2.5, n_events))
    last = -9
    for s in starts:
        if s - last < 2.0: continue
        d = rng.uniform(0.5, 1.1); i0, i1 = int(s * fs), int((s + d) * fs); t = np.arange(i1 - i0) / fs
        env = np.sin(np.pi * t / d) ** 2
        burst = env * (np.sin(2 * np.pi * rng.uniform(150, 400) * t) + 0.5 * rng.standard_normal(len(t)))
        x[i0:i1] += burst; events.append((float(s), float(s + d))); last = s + d
    sig_rms = np.sqrt(np.mean(x[x != 0] ** 2)) if np.any(x != 0) else 1.0
    noise = rng.standard_normal(n) * sig_rms / (10 ** (snr_db / 20))
    return (x + noise).astype(np.float32), events

def to_wav_bytes(x, fs=TARGET_FS):
    import io
    from scipy.io import wavfile
    buf = io.BytesIO(); wavfile.write(buf, fs, (np.clip(x / (np.max(np.abs(x)) + 1e-9), -1, 1) * 32000).astype(np.int16)); return buf.getvalue()
