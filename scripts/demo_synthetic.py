"""End-to-end smoke test on SYNTHETIC audio (no dataset needed): train RF, evaluate vs M0, show reliability tiers."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from swallohear import synth, pipeline, metrics
from swallohear.detectors import EnergyDetector, RFDetector
from swallohear.features import frame_features
from swallohear.preprocess import preprocess, frame_times

X, Y = [], []
for s in range(6):
    x, ref = synth.make_recording(30, 5, 20, seed=s); xp, _ = preprocess(x); F = frame_features(xp); t = frame_times(len(F)); y = np.zeros(len(F))
    for a, b in ref: y[(t >= a) & (t <= b)] = 1
    X.append(F); Y.append(y)
rf = RFDetector(100).fit(np.vstack(X), np.concatenate(Y))
for snr in (25, 10, 5, 0):
    for det in (EnergyDetector(), rf):
        f1s = []; stats = []
        for s in range(100, 105):
            x, ref = synth.make_recording(30, 5, snr, seed=s); r = pipeline.analyze(x, det)
            f1s.append(metrics.event_scores([(e["onset_s"], e["offset_s"]) for e in r["candidates"]], ref, 0.3)["f1"]); stats.append(r["status"])
        print(f"SNR {snr:>2} dB  {det.name:<16} F1@IoU0.3 = {np.mean(f1s):.2f}  status={dict((k, stats.count(k)) for k in set(stats))}")
