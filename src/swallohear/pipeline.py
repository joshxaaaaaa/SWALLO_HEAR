"""One function shared by the app, CLI and experiments, so what you demo is what you measured."""
from __future__ import annotations
import time
import numpy as np
from .preprocess import preprocess, frame_times
from .postprocess import scores_to_events
from .reliability import signal_quality, Thresholds, classify, calibrate, reason_codes

def analyze(signal, detector, orig_nyquist=2000.0, th: Thresholds | None = None, temperature: float = 1.0,
            hi=0.5, lo=0.35, ensemble=None) -> dict:
    th = th or Thresholds(); t0 = time.perf_counter()
    xp, meta = preprocess(signal)
    q = signal_quality(signal, xp, meta, orig_nyquist)
    members = ensemble or [detector]
    P = np.stack([m.predict_proba(xp if m.name != "M0 energy" else signal) for m in members])
    p = calibrate(P.mean(0), temperature); sd = P.std(0) if len(members) > 1 else np.zeros_like(p)
    frames = scores_to_events(p, hi=hi, lo=lo); t = frame_times(len(p))
    evs = [dict(onset_s=float(t[s]), offset_s=float(t[e]), duration_ms=float((t[e] - t[s]) * 1000)) for s, e in frames]
    conf = [float(p[s:e + 1].mean()) for s, e in frames]; unc = [float(sd[s:e + 1].mean()) for s, e in frames]
    status, tiered, codes = classify(evs, conf, unc, q, th)
    return dict(status=status, events=tiered, candidates=evs, reason_codes=codes, quality=q, frame_prob=p,
                frame_t=t, latency_s=time.perf_counter() - t0, detector=detector.name)
