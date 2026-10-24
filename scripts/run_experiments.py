"""Step 4: reliability experiments (E1-E4 core). Run from the repo folder:  python scripts/run_experiments.py
Everything is fit on TRAIN or VAL participants only; TEST is used once for reporting.
Writes results/experiments.json and models/rf_mic.joblib."""
import sys, json, pathlib, argparse, time, itertools
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, joblib
from swallohear.preprocess import preprocess, frame_times
from swallohear.features import frame_features
from swallohear.detectors import EnergyDetector, RFDetector
from swallohear.postprocess import scores_to_events
from swallohear.metrics import match_events, ece
from swallohear.reliability import fit_temperature, calibrate, signal_quality, Thresholds, reason_codes

ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data/interim"); ap.add_argument("--out", default="results")
ap.add_argument("--neg_keep", type=float, default=0.25); ap.add_argument("--trees", type=int, default=100); a = ap.parse_args()
root = pathlib.Path(a.root); SIG, LAB = root / "signals" / "signals", root / "labels" / "labels"
R = pd.read_csv(root / "index.csv"); S = json.load(open(root / "splits.json")); ok = R[R.labels_inside_signal & R.start_lt_end]
labelled = set(R.recording); empty = sorted(p.stem for p in SIG.glob("*.npy") if p.stem not in labelled)
recs = {k: ok[ok.participant.isin(S[k])].recording.tolist() for k in ("train", "val", "test")}
part = dict(zip(R.recording, R.participant)); rng = np.random.default_rng(0)

def get(rid, ch):
    x = np.load(SIG / f"{rid}.npy", mmap_mode="r")[:, ch].astype(np.float32)
    ev = []
    if rid in labelled:
        d = pd.read_csv(LAB / f"{rid}.csv"); ev = [(float(s) / 60, float(e) / 60) for s, e in zip(d.start, d.end)]
    return x, ev
def flab(n, ev):
    t = frame_times(n); y = np.zeros(n)
    for s, e in ev: y[(t >= s) & (t <= e)] = 1
    return y
def train_rf(ch):
    X, Y = [], []
    for rid in recs["train"] + empty[:200]:
        x, ev = get(rid, ch); F = frame_features(preprocess(x)[0]); y = flab(len(F), ev); k = (y == 1) | (rng.random(len(y)) < a.neg_keep)
        X.append(F[k]); Y.append(y[k])
    return RFDetector(a.trees).fit(np.vstack(X), np.concatenate(Y))
def load(split, ch): return {rid: get(rid, ch) for rid in recs[split]}
def probs(det, data, noise_db=None):
    out = {}
    for i, (rid, (x, ev)) in enumerate(data.items()):
        if noise_db is not None:
            m = np.zeros(len(x), bool); t = np.arange(len(x)) / 4000
            for s, e in ev: m |= (t >= s) & (t <= e)
            P = np.mean(x[m] ** 2) if m.any() else np.mean(x ** 2)
            x = x + np.random.default_rng(1000 + i).standard_normal(len(x)).astype(np.float32) * np.sqrt(P / 10 ** (noise_db / 10))
        xp, meta = preprocess(x); p = det.predict_proba(x if det.name == "M0 energy" else xp)
        out[rid] = dict(p=p, ev=ev, dur=len(x) / 4000, q=signal_quality(x, xp, meta, 2000.0))
    return out
def cands(d, hi, lo, merge):
    fr = scores_to_events(d["p"], hi=hi, lo=lo, merge_gap_s=merge); t = frame_times(len(d["p"]))
    return fr, [(float(t[s]), float(t[e])) for s, e in fr]
def f1c(tp, fp, fn): return 2 * tp / max(2 * tp + fp + fn, 1)
def score(P, hi, lo, merge, T=None, tau=None, snr_min=None):
    """ordinary output if tau is None; otherwise reliability-aware (confident tier of non-Inconclusive recordings)."""
    tp = fp = fn = 0; mins = 0; kept = tot = 0
    for rid, d in P.items():
        fr, pred = cands(d, hi, lo, merge); nref = len(d["ev"]); mins += d["dur"] / 60; tot += len(pred)
        if tau is not None:
            if snr_min is not None and d["q"]["snr_db"] < snr_min: pred = []
            else:
                pc = calibrate(d["p"], T); conf = [pc[s:e + 1].mean() for s, e in fr]
                pred = [pv for pv, c in zip(pred, conf) if c >= tau]
        pairs, f_, n_ = match_events(pred, d["ev"], 0.5); tp += len(pairs); fp += len(f_); fn += nref - len(pairs); kept += len(pred)
    return dict(precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), f1=f1c(tp, fp, fn), fp_per_min=fp / max(mins, 1e-9), reported=kept, candidates=tot, tp=tp, fp=fp, fn=fn)
def tune(P):
    best = None
    for hi, gap, merge in itertools.product([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], [0.05, 0.1, 0.2], [0.05, 0.2, 0.4]):
        lo = max(0.02, hi - gap); r = score(P, hi, lo, merge)
        if best is None or r["f1"] > best[0]: best = (r["f1"], hi, lo, merge)
    return best[1:]
def show(tag, r): print(f"  {tag:<34} P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f} FP/min={r['fp_per_min']:.2f} reported={r['reported']}/{r['candidates']}")
res = {}; t0 = time.time()

print("Training RF (microphone) ..."); rf = train_rf(0); joblib.dump(rf, "models/rf_mic.joblib", compress=3); print(f"  done {time.time()-t0:.0f}s")
dets = {"M0 energy": EnergyDetector(), "M1 RF": rf}
Vd, Td = load("val", 0), load("test", 0)
for name, det in dets.items():
    print(f"\n######## {name}")
    Pv = probs(det, Vd); hi, lo, merge = tune(Pv); print(f"tuned on VAL: hi={hi} lo={round(lo,2)} merge={merge}")
    Pt = probs(det, Td); r = {"params": dict(hi=hi, lo=lo, merge=merge)}
    r["clean_ordinary"] = score(Pt, hi, lo, merge); print("E1 clean test, ordinary output:"); show("ordinary (all detections)", r["clean_ordinary"])
    # ---- calibration (frame level) ----
    pv = np.concatenate([d["p"] for d in Pv.values()]); yv = np.concatenate([flab(len(d["p"]), d["ev"]) for d in Pv.values()])
    pt = np.concatenate([d["p"] for d in Pt.values()]); yt = np.concatenate([flab(len(d["p"]), d["ev"]) for d in Pt.values()])
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    T = fit_temperature(lg(pv), yv); e0, e1 = ece(pt, yt), ece(calibrate(pt, T), yt)
    r["calibration"] = dict(T=T, ece_before=e0, ece_after=e1); print(f"E3 frame-level ECE on test: before={e0:.4f}  after temperature scaling (T={T:.2f})={e1:.4f}")
    # ---- choose tau_hi and snr_min on VAL ----
    taus = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]; tv = {t: score(Pv, hi, lo, merge, T, t) for t in taus}
    good = [t for t in taus if tv[t]["precision"] >= 0.7 and tv[t]["reported"] >= 10]
    tau = good[0] if good else max(taus, key=lambda t: tv[t]["precision"] if tv[t]["reported"] >= 0.2 * tv[t]["candidates"] else -1)
    snrs = [-99, 4, 8, 12]; snr_min = max(snrs, key=lambda s: score(Pv, hi, lo, merge, T, tau, s)["f1"])
    r["selected_on_val"] = dict(tau_hi=tau, snr_min=snr_min, target_precision_reached=bool(good)); print(f"selected on VAL: tau_hi={tau} (target precision 0.7 reached: {bool(good)}), snr_min={snr_min}")
    print("E3 risk-coverage on TEST (confident-only vs threshold):"); r["risk_coverage"] = {}
    for t in taus:
        x = score(Pt, hi, lo, merge, T, t); r["risk_coverage"][t] = x; show(f"tau={t}", x)
    r["reliability_clean"] = score(Pt, hi, lo, merge, T, tau, snr_min); show("RELIABILITY-AWARE (val-chosen)", r["reliability_clean"])
    # ---- E2 noise robustness ----
    print("E2 noise robustness on TEST (white noise; operating point fixed from clean VAL):"); r["noise"] = {}
    for snr in (20, 10, 5, 0):
        Pn = probs(det, Td, noise_db=snr); o = score(Pn, hi, lo, merge); rel = score(Pn, hi, lo, merge, T, tau, snr_min)
        inc = np.mean([d["q"]["snr_db"] < snr_min for d in Pn.values()]); r["noise"][snr] = dict(ordinary=o, reliability=rel, inconclusive_share=float(inc))
        print(f" SNR {snr:>2} dB  (recordings flagged low-SNR: {inc:.0%})"); show("ordinary", o); show("reliability-aware", rel)
    res[name] = r

print("\n######## E4 channel ablation: RF on anteroposterior accelerometer (research upper bound, NOT usable with a microphone/stethoscope)")
rf1 = train_rf(1); V1, T1 = load("val", 1), load("test", 1); Pv1 = probs(rf1, V1); hi, lo, merge = tune(Pv1); r1 = score(probs(rf1, T1), hi, lo, merge)
res["E4_RF_AP_accel"] = r1; show("RF A-P accelerometer (test)", r1)
pathlib.Path(a.out).mkdir(exist_ok=True); json.dump(res, open(pathlib.Path(a.out) / "experiments.json", "w"), indent=1, default=float)
print(f"\nwrote {pathlib.Path(a.out)/'experiments.json'}  (total {time.time()-t0:.0f}s)")
