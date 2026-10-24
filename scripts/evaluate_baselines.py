"""Step 3: train M1 (Random Forest) on TRAIN, tune post-processing on VAL, report TEST for M0 and M1.
Run from the repo folder:   python scripts/evaluate_baselines.py
Writes results/baselines.json. Nothing is tuned on the test participants."""
import sys, json, pathlib, argparse, time, itertools
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from swallohear.data import load_recording
from swallohear.preprocess import preprocess, frame_times
from swallohear.features import frame_features
from swallohear.detectors import EnergyDetector, RFDetector
from swallohear.postprocess import scores_to_events
from swallohear.metrics import event_scores

ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data/interim"); ap.add_argument("--out", default="results")
ap.add_argument("--neg_keep", type=float, default=0.25, help="fraction of non-swallow frames kept for RF training")
ap.add_argument("--max_train_recs", type=int, default=0, help="debug: limit training recordings"); a = ap.parse_args()
root = pathlib.Path(a.root); sig, lab = root / "signals" / "signals", root / "labels" / "labels"
R = pd.read_csv(root / "index.csv"); S = json.load(open(root / "splits.json")); ok = R[R.labels_inside_signal & R.start_lt_end]
all_ids = sorted(p.stem for p in sig.glob("*.npy")); labelled = set(R.recording)
empty = [r for r in all_ids if r not in labelled]       # label files with no swallows -> negative recordings
recs_of = {k: ok[ok.participant.isin(S[k])].recording.tolist() for k in ("train", "val", "test")}
print({k: len(v) for k, v in recs_of.items()}, "| empty-label recordings (no participant info, used as train negatives only):", len(empty))

def frame_labels(n, events):
    t = frame_times(n); y = np.zeros(n)
    for s, e in events: y[(t >= s) & (t <= e)] = 1
    return y

rng = np.random.default_rng(0)
t0 = time.time(); X, Y = [], []
train_ids = recs_of["train"][: a.max_train_recs or None]
for i, rid in enumerate(train_ids + (empty[:200] if not a.max_train_recs else [])):
    try: x, ev = load_recording(sig, lab, rid) if rid in labelled else (np.load(sig / f"{rid}.npy")[:, 0].astype(np.float32), [])
    except Exception as e: print("skip", rid, e); continue
    xp, _ = preprocess(x); F = frame_features(xp); y = frame_labels(len(F), ev)
    keep = (y == 1) | (rng.random(len(y)) < a.neg_keep); X.append(F[keep]); Y.append(y[keep])
    if i % 100 == 0: print(f"  features {i}/{len(train_ids)} ({time.time()-t0:.0f}s)")
X, Y = np.vstack(X), np.concatenate(Y); print("training frames", X.shape, "positive share", round(float(Y.mean()), 3))
rf = RFDetector(n_estimators=100).fit(X, Y); print(f"RF trained in {time.time()-t0:.0f}s")

def probs_for(split, det):
    out = {}
    for rid in recs_of[split]:
        x, ev = load_recording(sig, lab, rid)
        inp = x if det.name == "M0 energy" else preprocess(x)[0]
        out[rid] = (det.predict_proba(inp), ev, len(x) / 4000)
    return out

def evaluate(P, hi, lo, merge, iou_thr):
    tp = fp = fn = 0; mins = 0.0; on, off = [], []; per_part = {}
    pid = dict(zip(R.recording, R.participant))
    for rid, (p, ev, dur) in P.items():
        fr = scores_to_events(p, hi=hi, lo=lo, merge_gap_s=merge); t = frame_times(len(p))
        pred = [(float(t[s]), float(t[e])) for s, e in fr]; sc = event_scores(pred, ev, iou_thr)
        tp += sc["tp"]; fp += sc["fp"]; fn += sc["fn"]; mins += dur / 60; on += sc["onset_err"]; off += sc["offset_err"]
        d = per_part.setdefault(pid[rid], [0, 0, 0, 0.0]); d[0] += sc["tp"]; d[1] += sc["fp"]; d[2] += sc["fn"]; d[3] += dur / 60
    f1 = lambda tp, fp, fn: 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), f1=f1(tp, fp, fn),
                fp_per_min=fp / max(mins, 1e-9), onset_med_ms=1000 * float(np.median(on)) if on else None,
                offset_med_ms=1000 * float(np.median(off)) if off else None,
                onset_abs_med_ms=1000 * float(np.median(np.abs(on))) if on else None, offset_abs_med_ms=1000 * float(np.median(np.abs(off))) if off else None,
                _per_part=per_part)

def boot_ci(per_part, n=1000, seed=0):
    ids = list(per_part); r = np.random.default_rng(seed); v = np.array([per_part[i][:3] for i in ids]); out = []
    for _ in range(n):
        s = v[r.integers(0, len(ids), len(ids))].sum(0); out.append(2 * s[0] / max(2 * s[0] + s[1] + s[2], 1))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]

results = {}
for det in (EnergyDetector(), rf):
    print(f"\n=== {det.name} ===")
    Pv = probs_for("val", det); best = None
    for hi, gap, merge in itertools.product([0.3, 0.4, 0.5, 0.6, 0.7], [0.1, 0.2], [0.05, 0.2, 0.4]):
        lo = max(0.05, hi - gap); r = evaluate(Pv, hi, lo, merge, 0.5)
        if best is None or r["f1"] > best[0]: best = (r["f1"], hi, lo, merge)
    _, hi, lo, merge = best; print(f"tuned on VAL: hi={hi} lo={round(lo,2)} merge={merge}s  (val F1@IoU0.5 = {best[0]:.3f})")
    Pt = probs_for("test", det); results[det.name] = dict(params=dict(hi=hi, lo=lo, merge_gap_s=merge))
    for thr in (0.5, 0.3):
        r = evaluate(Pt, hi, lo, merge, thr); ci = boot_ci(r.pop("_per_part")); r["f1_ci95"] = ci; results[det.name][f"IoU{thr}"] = r
        print(f"TEST IoU>={thr}: P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f} (95% CI {ci[0]:.3f}-{ci[1]:.3f})  FP/min={r['fp_per_min']:.2f}  "
              f"|onset err| med={r['onset_abs_med_ms']} ms  |offset err| med={r['offset_abs_med_ms']} ms  (tp={r['tp']} fp={r['fp']} fn={r['fn']})")
pathlib.Path(a.out).mkdir(exist_ok=True); json.dump(results, open(pathlib.Path(a.out) / "baselines.json", "w"), indent=1)
print("\nwrote", pathlib.Path(a.out) / "baselines.json")
