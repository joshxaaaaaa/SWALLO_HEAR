"""Final analysis path used by the web app and the bootstrap script: noise-augmented RF + learned event-reliability model + signal-quality gate."""
from __future__ import annotations
import json, pathlib, time
import numpy as np, joblib
from .preprocess import preprocess, frame_times, frame_signal
from .features import frame_energy_db
from .postprocess import scores_to_events
from .reliability import signal_quality

def event_features(p, e, floor, snr):
    """Feature order MUST match scripts/run_reliability_v2.py (table())."""
    return [p.mean(), p.max(), p.std(), len(p) * 0.016, e.mean() - floor, e.max() - floor, snr]

class Analyzer:
    def __init__(self, models_dir="models", config="configs/final.json", results="results/reliability_v2.json", tau=None, snr_min=None):
        md = pathlib.Path(models_dir); self.rf = joblib.load(md / "rf_mic_aug.joblib"); self.rel = joblib.load(md / "event_reliability.joblib")
        c = json.load(open(config)); self.hi, self.lo, self.merge, self.tau, self.snr_min = c["hi"], c["lo"], c["merge_gap_s"], c["tau"], c["snr_min"]
        try:
            r = json.load(open(results))["reliability"]; self.tau, self.snr_min = r["tau"], r["snr_min"]
        except Exception: pass
        if tau is not None: self.tau = tau
        if snr_min is not None: self.snr_min = snr_min

    def analyze(self, signal, orig_nyquist=2000.0):
        return self.assemble(self.score(signal, orig_nyquist))

    def score(self, signal, orig_nyquist=2000.0):
        """Expensive half: preprocessing, quality indicators and per-frame RF scores. Cache this; assemble() is cheap."""
        t0 = time.perf_counter(); xp, meta = preprocess(signal); q = signal_quality(signal, xp, meta, orig_nyquist)
        p = self.rf.predict_proba(xp); e = frame_energy_db(frame_signal(xp))
        return dict(p=p, e=e, floor=float(np.percentile(e, 10)), t=frame_times(len(p)), quality=q,
                    orig_nyquist=float(orig_nyquist), latency_s=time.perf_counter() - t0)

    def assemble(self, scored, hi=None, lo=None, merge=None, tau=None, snr_min=None):
        """Cheap half: quality gate, event assembly and reliability scoring. None means the validated setting."""
        t0 = time.perf_counter(); p, e, floor, t, q = (scored[k] for k in ("p", "e", "floor", "t", "quality"))
        hi = self.hi if hi is None else hi; lo = self.lo if lo is None else lo; merge = self.merge if merge is None else merge
        tau = self.tau if tau is None else tau; snr_min = self.snr_min if snr_min is None else snr_min
        codes = []
        if q["snr_db"] < snr_min: codes.append("LOW_SNR")
        if q["clip_frac"] > 0.02: codes.append("CLIPPING")
        if q["flat_frac"] > 0.30: codes.append("FLATLINE")
        if scored["orig_nyquist"] < 1000: codes.append("LOW_BANDWIDTH")
        if q["duration_s"] < 1.0: codes.append("TOO_SHORT")
        if q["duration_s"] > 120: codes.append("TOO_LONG")
        fr = scores_to_events(p, hi=hi, lo=lo, merge_gap_s=merge); evs = []
        if fr:
            X = np.array([event_features(p[s:e_ + 1], e[s:e_ + 1], floor, q["snr_db"]) for s, e_ in fr]); sc = self.rel.predict_proba(X)[:, 1]
            for (s, e_), sco, x in zip(fr, sc, X):
                evs.append(dict(onset_s=float(t[s]), offset_s=float(t[e_]), duration_ms=float((t[e_] - t[s]) * 1000), reliability=float(sco),
                                model_confidence=float(x[0]), tier="Confident" if sco >= tau else "Low-confidence", features=[float(v) for v in x]))
        status = "Inconclusive" if codes else ("No event" if not evs else "Analyzable")
        return dict(status=status, reason_codes=codes, events=evs if not codes else [], withheld_candidates=evs if codes else [],
                    quality=q, frame_prob=p, frame_t=t, latency_s=scored["latency_s"] + time.perf_counter() - t0, tau=tau, snr_min=snr_min)
