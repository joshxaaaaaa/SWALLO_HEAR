"""Signal-quality index, temperature scaling, calibrated event confidence, four-state output."""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import minimize_scalar
from .features import frame_energy_db
from .preprocess import frame_signal

def signal_quality(x_raw, x_proc, meta, orig_nyquist=2000.0) -> dict:
    e = frame_energy_db(frame_signal(x_proc))
    floor, peak = np.percentile(e, 10), np.percentile(e, 95)
    flat = float(np.mean(np.abs(np.diff(x_raw)) < 1e-7)) if len(x_raw) > 1 else 1.0
    return dict(snr_db=float(peak - floor), clip_frac=meta.get("clip_frac", 0.0), flat_frac=flat,
                duration_s=len(x_raw) / 4000, orig_nyquist=float(orig_nyquist))

@dataclass
class Thresholds:           # all to be FIT ON VALIDATION DATA ONLY (see scripts/evaluate.py)
    tau_hi: float = 0.75
    tau_lo: float = 0.45
    u_max: float = 0.25
    snr_min: float = 6.0
    clip_max: float = 0.02
    flat_max: float = 0.30
    dur_min: float = 1.0
    dur_max: float = 120.0
    bw_min: float = 1000.0   # original Nyquist must cover swallow band

def reason_codes(q: dict, th: Thresholds) -> list[str]:
    r = []
    if q["snr_db"] < th.snr_min: r.append("LOW_SNR")
    if q["clip_frac"] > th.clip_max: r.append("CLIPPING")
    if q["flat_frac"] > th.flat_max: r.append("FLATLINE")
    if q["orig_nyquist"] < th.bw_min: r.append("LOW_BANDWIDTH")
    if q["duration_s"] < th.dur_min: r.append("TOO_SHORT")
    if q["duration_s"] > th.dur_max: r.append("TOO_LONG")
    return r

def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Temperature scaling on validation frames (minimize NLL)."""
    def nll(T):
        p = 1 / (1 + np.exp(-logits / T)); p = np.clip(p, 1e-7, 1 - 1e-7)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))
    return float(minimize_scalar(nll, bounds=(0.05, 10), method="bounded").x)

def calibrate(p: np.ndarray, T: float) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6); return 1 / (1 + np.exp(-np.log(p / (1 - p)) / T))

def classify(events, p_mean, p_std, q, th: Thresholds):
    """events: list of dicts with onset_s, offset_s; p_mean/p_std per event (calibrated conf, ensemble std).
    Returns (record_status, annotated events)."""
    codes = reason_codes(q, th)
    out = []
    if codes:
        return "Inconclusive", out, codes
    for ev, c, u in zip(events, p_mean, p_std):
        tier = "Confident" if (c >= th.tau_hi and u <= th.u_max) else ("Low-confidence" if c >= th.tau_lo else None)
        if tier: out.append({**ev, "confidence": float(c), "uncertainty": float(u), "tier": tier})
    return ("Analyzable" if out else "No event"), out, codes
