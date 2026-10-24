"""Step 5: (a) noise-augmented training, (b) a LEARNED event-reliability model, (c) data-driven signal-quality cutoff.
Run from the repo folder:  python scripts/run_reliability_v2.py
Fit on TRAIN (out-of-fold, participant-grouped) and VAL only; TEST used once for reporting. Writes results/reliability_v2.json"""
import sys, json, pathlib, argparse, time, itertools
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score
from swallohear.preprocess import preprocess, frame_times, frame_signal
from swallohear.features import frame_features, frame_energy_db
from swallohear.detectors import RFDetector
from swallohear.postprocess import scores_to_events
from swallohear.metrics import match_events, ece
from swallohear.reliability import signal_quality

ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data/interim"); ap.add_argument("--out", default="results")
ap.add_argument("--neg_keep", type=float, default=0.25); ap.add_argument("--trees", type=int, default=100); a = ap.parse_args()
root = pathlib.Path(a.root); SIG, LAB = root / "signals" / "signals", root / "labels" / "labels"
R = pd.read_csv(root / "index.csv"); S = json.load(open(root / "splits.json")); ok = R[R.labels_inside_signal & R.start_lt_end]
labelled = set(R.recording); empty = sorted(p.stem for p in SIG.glob("*.npy") if p.stem not in labelled)
recs = {k: ok[ok.participant.isin(S[k])].recording.tolist() for k in ("train", "val", "test")}; part = dict(zip(R.recording, R.participant))
SNRS = (20, 10, 5, 0); t0 = time.time()

def get(rid, ch=0):
    x = np.load(SIG / f"{rid}.npy", mmap_mode="r")[:, ch].astype(np.float32); ev = []
    if rid in labelled:
        d = pd.read_csv(LAB / f"{rid}.csv"); ev = [(float(s) / 60, float(e) / 60) for s, e in zip(d.start, d.end)]
    return x, ev
def flab(n, ev):
    t = frame_times(n); y = np.zeros(n)
    for s, e in ev: y[(t >= s) & (t <= e)] = 1
    return y
def add_noise(x, ev, snr, seed):
    t = np.arange(len(x)) / 4000; m = np.zeros(len(x), bool)
    for s, e in ev: m |= (t >= s) & (t <= e)
    P = np.mean(x[m] ** 2) if m.any() else np.mean(x ** 2)
    return x + np.random.default_rng(seed).standard_normal(len(x)).astype(np.float32) * np.sqrt(P / 10 ** (snr / 10))
def feats_labels(x, ev, rng, keep_neg):
    F = frame_features(preprocess(x)[0]); y = flab(len(F), ev); k = (y == 1) | (rng.random(len(y)) < keep_neg); return F[k], y[k]
def train_rf(rec_ids, augment, seed=0, with_empty=True):
    rng = np.random.default_rng(seed); X, Y = [], []
    for i, rid in enumerate(rec_ids + (empty[:200] if with_empty else [])):
        x, ev = get(rid)
        versions = [x] + ([add_noise(x, ev, s, 7000 + i + j) for j, s in enumerate((20, 10, 5))] if augment else [])
        if augment: versions = [versions[0], versions[1 + int(rng.integers(0, 3))]]   # clean + one random noisy copy
        for v in versions:
            f, y = feats_labels(v, ev, rng, a.neg_keep); X.append(f); Y.append(y)
    return RFDetector(a.trees, seed=seed).fit(np.vstack(X), np.concatenate(Y))
def analyse(det, data, snr=None, salt=0):
    out = {}
    for i, (rid, (x, ev)) in enumerate(data.items()):
        if snr is not None: x = add_noise(x, ev, snr, 1000 + i + salt)
        xp, meta = preprocess(x); p = det.predict_proba(xp); e = frame_energy_db(frame_signal(xp))
        out[rid] = dict(p=p, e=e, ev=ev, dur=len(x) / 4000, snr=signal_quality(x, xp, meta, 2000.0)["snr_db"], floor=float(np.percentile(e, 10)))
    return out
def table(P, params):
    hi, lo, merge = params; rows = []; nref = 0; mins = 0
    for rid, d in P.items():
        fr = scores_to_events(d["p"], hi=hi, lo=lo, merge_gap_s=merge); t = frame_times(len(d["p"]))
        pred = [(float(t[s]), float(t[e])) for s, e in fr]; pairs, _, _ = match_events(pred, d["ev"], 0.5); good = {i for i, _ in pairs}
        nref += len(d["ev"]); mins += d["dur"] / 60
        for i, (s, e) in enumerate(fr):
            pe = d["p"][s:e + 1]; en = d["e"][s:e + 1]
            rows.append(dict(rid=rid, snr=d["snr"], x=[pe.mean(), pe.max(), pe.std(), (e - s + 1) * 0.016, en.mean() - d["floor"], en.max() - d["floor"], d["snr"]], correct=int(i in good)))
    return rows, nref, mins
def metrics(rows, nref, mins, keep=None):
    k = [r for j, r in enumerate(rows) if keep is None or keep[j]]; tp = sum(r["correct"] for r in k); fp = len(k) - tp; fn = nref - tp
    return dict(precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), f1=2 * tp / max(2 * tp + fp + fn, 1), fp_per_min=fp / max(mins, 1e-9), reported=len(k), candidates=len(rows))
def tune(P):
    best = None
    for hi, gap, merge in itertools.product([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], [0.05, 0.1, 0.2], [0.05, 0.2, 0.4]):
        lo = max(0.02, hi - gap); r = metrics(*table(P, (hi, lo, merge)))
        if best is None or r["f1"] > best[0]: best = (r["f1"], (hi, lo, merge))
    return best[1]
def show(tag, r): print(f"  {tag:<36} P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f} FP/min={r['fp_per_min']:.2f} reported={r['reported']}/{r['candidates']}")

Vd = {r: get(r) for r in recs["val"]}; Td = {r: get(r) for r in recs["test"]}
print("Training RF-clean (loaded from models/rf_mic.joblib if present) and RF-augmented ...")
try: rf_clean = joblib.load("models/rf_mic.joblib")
except Exception: rf_clean = train_rf(recs["train"], False)
rf_aug = train_rf(recs["train"], True); joblib.dump(rf_aug, "models/rf_mic_aug.joblib", compress=3); print(f"  done {time.time()-t0:.0f}s")
res = {}; params = {}
for name, det in (("RF clean-trained", rf_clean), ("RF noise-augmented", rf_aug)):
    params[name] = tune(analyse(det, Vd)); print(f"{name}: tuned on VAL hi/lo/merge = {tuple(round(v,2) for v in params[name])}")
res["params"] = {k: [float(x) for x in v] for k, v in params.items()}
print("\n######## E4 + E2: clean-trained vs noise-augmented RF (ordinary output, test participants)"); res["E2_E4"] = {}
for name, det in (("RF clean-trained", rf_clean), ("RF noise-augmented", rf_aug)):
    res["E2_E4"][name] = {}
    for snr in (None,) + SNRS:
        r = metrics(*table(analyse(det, Td, snr), params[name])); res["E2_E4"][name]["clean" if snr is None else snr] = r; show(f"{name} @ {'clean' if snr is None else str(snr)+' dB'}", r)

print("\n######## Learned event-reliability model (trained on out-of-fold TRAIN events, noisy + clean)")
tr_p = sorted(set(part[r] for r in recs["train"])); rng = np.random.default_rng(1); rng.shuffle(tr_p); folds = np.array_split(tr_p, 3); X, Y = [], []
for k in range(3):
    held = set(folds[k]); fit_ids = [r for r in recs["train"] if part[r] not in held]; hold_ids = [r for r in recs["train"] if part[r] in held]
    m = train_rf(fit_ids, True, seed=k); hd = {r: get(r) for r in hold_ids}
    for j, snr in enumerate((None, 20, 10, 5)):
        rows, _, _ = table(analyse(m, hd, snr, salt=500 * j), params["RF noise-augmented"]); X += [r["x"] for r in rows]; Y += [r["correct"] for r in rows]
    print(f"  fold {k+1}/3 done ({time.time()-t0:.0f}s)")
X, Y = np.array(X), np.array(Y); print(f"  reliability training events: {len(Y)}  share correct: {Y.mean():.3f}")
rel = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X, Y); joblib.dump(rel, "models/event_reliability.joblib", compress=3); print("model sizes (MB):", {f.name: round(f.stat().st_size/1e6,1) for f in pathlib.Path("models").glob("*.joblib")})

det, prm = rf_aug, params["RF noise-augmented"]
Pv_clean = analyse(det, Vd); rv, nv, mv = table(Pv_clean, prm); sv = rel.predict_proba(np.array([r["x"] for r in rv]))[:, 1]
snr_min = float(np.percentile([d["snr"] for d in Pv_clean.values()], 5)); print(f"signal-quality cutoff (5th percentile of CLEAN val recordings): est. SNR < {snr_min:.1f} dB -> Inconclusive")
taus = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]; base_v = metrics(rv, nv, mv)
def mk(rows, sc, tau, snr_cut): return [(s >= tau) and (r["snr"] >= snr_cut) for r, s in zip(rows, sc)]
cand = [t for t in taus if metrics(rv, nv, mv, mk(rv, sv, t, snr_min))["precision"] >= base_v["precision"] + 0.10 and metrics(rv, nv, mv, mk(rv, sv, t, snr_min))["reported"] >= 0.25 * len(rv)]
tau = cand[-1] if cand else 0.5; print(f"tau_hi chosen on VAL: {tau}  (rule: precision at least +0.10 over ordinary while keeping >= 25% of detections; satisfied: {bool(cand)})")
res["reliability"] = dict(tau=tau, snr_min=snr_min, tau_rule_satisfied=bool(cand))

print("\n######## E3 on TEST: does the learned reliability score separate correct from wrong events?")
for cond in (None,) + SNRS:
    P = analyse(det, Td, cond); rows, nref, mins = table(P, prm); sc = rel.predict_proba(np.array([r["x"] for r in rows]))[:, 1]; yc = np.array([r["correct"] for r in rows])
    label = "clean" if cond is None else f"{cond} dB"; out = {}
    if len(set(yc)) == 2: out["auroc_mean_prob"] = float(roc_auc_score(yc, [r["x"][0] for r in rows])); out["auroc_learned"] = float(roc_auc_score(yc, sc))
    out["ordinary"] = metrics(rows, nref, mins); out["reliability_aware"] = metrics(rows, nref, mins, mk(rows, sc, tau, snr_min))
    out["flagged_inconclusive_share"] = float(np.mean([d["snr"] < snr_min for d in P.values()])); out["event_ece_learned"] = float(ece(sc, yc)) if len(yc) else None
    res.setdefault("E3", {})[label] = out
    print(f" [{label}] event AUROC  mean-prob={out.get('auroc_mean_prob', float('nan')):.3f}  learned={out.get('auroc_learned', float('nan')):.3f}  | event-level ECE (learned)={out['event_ece_learned']:.3f} | recordings flagged Inconclusive: {out['flagged_inconclusive_share']:.0%}")
    show("ordinary", out["ordinary"]); show("reliability-aware", out["reliability_aware"])
aug = params["RF noise-augmented"]; json.dump(dict(hi=aug[0], lo=aug[1], merge_gap_s=aug[2], tau=tau, snr_min=snr_min, note="written by scripts/run_reliability_v2.py; values selected on VALIDATION participants"), open("configs/final.json", "w"), indent=1)
pathlib.Path(a.out).mkdir(exist_ok=True); json.dump(res, open(pathlib.Path(a.out) / "reliability_v2.json", "w"), indent=1, default=float)
print(f"\nwrote {pathlib.Path(a.out)/'reliability_v2.json'}  (total {time.time()-t0:.0f}s)")
