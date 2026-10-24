"""Audio loading: any WAV -> mono float32 at TARGET_FS, plus metadata for the quality card."""
from __future__ import annotations
import io
from math import gcd
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from . import TARGET_FS

def _to_float(x: np.ndarray) -> np.ndarray:
    if x.dtype == np.int16: return x.astype(np.float32) / 32768.0
    if x.dtype == np.int32: return x.astype(np.float32) / 2147483648.0
    if x.dtype == np.uint8: return (x.astype(np.float32) - 128.0) / 128.0
    return x.astype(np.float32)

def resample(x: np.ndarray, fs: int, target: int = TARGET_FS) -> np.ndarray:
    if fs == target: return x
    g = gcd(int(fs), int(target))
    return resample_poly(x, target // g, fs // g).astype(np.float32)  # anti-aliased polyphase

def load_audio(source, max_seconds: float = 120.0) -> dict:
    """source: path or file-like (WAV). Returns dict(signal, fs, orig_fs, duration_s, channels)."""
    if isinstance(source, (bytes, bytearray)): source = io.BytesIO(source)
    try:
        orig_fs, x = wavfile.read(source)
    except Exception:
        import soundfile as sf  # FLAC etc.
        if hasattr(source, "seek"): source.seek(0)
        x, orig_fs = sf.read(source, dtype="float32")
    x = _to_float(np.asarray(x))
    channels = 1 if x.ndim == 1 else x.shape[1]
    if x.ndim == 2: x = x.mean(axis=1)
    if len(x) / orig_fs > max_seconds: raise ValueError(f"Recording longer than {max_seconds:.0f} s")
    y = resample(x, orig_fs)
    return dict(signal=y, fs=TARGET_FS, orig_fs=int(orig_fs), duration_s=len(y) / TARGET_FS, channels=channels,
                orig_nyquist=orig_fs / 2)
