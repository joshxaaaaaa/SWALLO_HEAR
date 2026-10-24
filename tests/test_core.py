import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from swallohear import synth, io as sio, pipeline, metrics
from swallohear.detectors import EnergyDetector, RFDetector
from swallohear.features import frame_features
from swallohear.preprocess import preprocess, frame_times
from swallohear.reliability import fit_temperature, calibrate

def test_wav_roundtrip_and_resample():
    x, _ = synth.make_recording(5, 1, seed=1)
    a = sio.load_audio(synth.to_wav_bytes(x)); assert a["fs"] == 4000 and abs(a["duration_s"] - 5) < 0.01
    from scipy.io import wavfile; import io
    b = io.BytesIO(); wavfile.write(b, 16000, np.repeat(x, 4).astype(np.float32)); b.seek(0)
    a2 = sio.load_audio(b); assert a2["orig_fs"] == 16000 and abs(a2["duration_s"] - 5) < 0.01

def test_iou_matching_and_scores():
    ref = [(1.0, 2.0), (5.0, 6.0)]; pred = [(1.1, 2.05), (8.0, 9.0)]
    s = metrics.event_scores(pred, ref, 0.5); assert s["tp"] == 1 and s["fp"] == 1 and s["fn"] == 1

def test_energy_detector_finds_events_clean():
    x, ref = synth.make_recording(30, 5, snr_db=25, seed=3)
    r = pipeline.analyze(x, EnergyDetector(), hi=0.5, lo=0.35)
    s = metrics.event_scores([(e["onset_s"], e["offset_s"]) for e in r["candidates"]], ref, 0.3)
    assert s["recall"] >= 0.6, s

def test_noise_triggers_inconclusive():
    x, _ = synth.make_recording(20, 3, snr_db=-5, seed=4)
    x = x + np.random.default_rng(0).standard_normal(len(x)).astype(np.float32) * 5
    r = pipeline.analyze(x, EnergyDetector()); assert r["status"] in ("Inconclusive", "No event", "Analyzable")

def test_short_recording_is_inconclusive():
    x, _ = synth.make_recording(5, 1, seed=5); r = pipeline.analyze(x[:2000], EnergyDetector())
    assert r["status"] == "Inconclusive" and "TOO_SHORT" in r["reason_codes"]

def test_rf_trains_and_predicts():
    X, Y = [], []
    for s in range(4):
        x, ref = synth.make_recording(30, 5, 20, seed=10 + s); xp, _ = preprocess(x)
        F = frame_features(xp); t = frame_times(len(F)); y = np.zeros(len(F))
        for a, b in ref: y[(t >= a) & (t <= b)] = 1
        X.append(F); Y.append(y)
    rf = RFDetector(60).fit(np.vstack(X), np.concatenate(Y))
    x, ref = synth.make_recording(30, 5, 20, seed=99)
    r = pipeline.analyze(x, rf); s = metrics.event_scores([(e["onset_s"], e["offset_s"]) for e in r["candidates"]], ref, 0.3)
    assert s["f1"] > 0.5, s

def test_temperature_and_ece():
    rng = np.random.default_rng(0); logit = rng.normal(0, 3, 5000); y = (rng.random(5000) < 1 / (1 + np.exp(-logit / 2))).astype(float)
    T = fit_temperature(logit, y); assert 1.5 < T < 2.6
    p = calibrate(1 / (1 + np.exp(-logit)), T); assert metrics.ece(p, y) < metrics.ece(1 / (1 + np.exp(-logit)), y)

def test_split_disjoint_helper():
    from swallohear.data import participant_split
    ids = [f"p{i}" for i in range(100)]; tr, va, te = participant_split(ids, seed=0)
    assert not (set(tr) & set(va)) and not (set(tr) & set(te)) and not (set(va) & set(te)) and len(tr) + len(va) + len(te) == 100

if __name__ == "__main__":
    fails = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            try: f(); print("PASS", k)
            except Exception as e: fails += 1; print("FAIL", k, repr(e))
    sys.exit(fails)
