"""Frame features for M0/M1 (hand-crafted, ~40 dims + context)."""
from __future__ import annotations
import numpy as np
from scipy.fft import dct
from .preprocess import frame_signal
from . import TARGET_FS

def _mel_fb(n_fft, fs, n_mels=20, fmin=20, fmax=1900):
    mel = lambda f: 2595 * np.log10(1 + f / 700); inv = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = inv(np.linspace(mel(fmin), mel(fmax), n_mels + 2)); bins = np.floor((n_fft + 1) * pts / fs).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        for k in range(l, c): fb[m - 1, k] = (k - l) / max(c - l, 1)
        for k in range(c, r): fb[m - 1, k] = (r - k) / max(r - c, 1)
    return fb

_FB = None
def frame_energy_db(frames):
    return 10 * np.log10(np.mean(frames ** 2, axis=1) + 1e-10)

def frame_features(x, fs=TARGET_FS, context=5):
    global _FB
    F = frame_signal(x); n_fft = F.shape[1]
    if _FB is None: _FB = _mel_fb(n_fft, fs)
    win = np.hanning(n_fft); S = np.abs(np.fft.rfft(F * win, axis=1)) ** 2 + 1e-10
    freqs = np.fft.rfftfreq(n_fft, 1 / fs); tot = S.sum(1)
    rms = np.sqrt(np.mean(F ** 2, axis=1)); zcr = np.mean(np.abs(np.diff(np.sign(F), axis=1)) > 0, axis=1)
    cent = (S * freqs).sum(1) / tot; bw = np.sqrt((S * (freqs - cent[:, None]) ** 2).sum(1) / tot)
    roll = freqs[np.argmax(np.cumsum(S, 1) >= 0.85 * tot[:, None], axis=1)]
    flat = np.exp(np.mean(np.log(S), 1)) / np.mean(S, 1)
    bands = np.stack([np.log(S[:, (freqs >= a) & (freqs < b)].sum(1) + 1e-10)
                      for a, b in [(20, 100), (100, 200), (200, 350), (350, 500), (500, 800), (800, 1200), (1200, 1600), (1600, 2000)]], 1)
    mfcc = dct(np.log(S @ _FB.T + 1e-10), type=2, axis=1, norm="ortho")[:, :13]
    base = np.column_stack([np.log(rms + 1e-8), zcr, cent, bw, roll, flat, bands, mfcc])
    # context statistics (moving mean/std over +/- context frames)
    k = 2 * context + 1; pad = np.pad(base, ((context, context), (0, 0)), mode="edge")
    win_v = np.lib.stride_tricks.sliding_window_view(pad, k, axis=0)  # (n, d, k)
    return np.hstack([base, win_v.mean(-1), win_v.std(-1)]).astype(np.float32)
