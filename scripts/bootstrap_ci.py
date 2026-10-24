"""Step 7: participant-level bootstrap confidence intervals for the headline comparisons. Run:  python scripts/bootstrap_ci.py
Loads the trained models (no retraining). ~5 minutes. Writes results/bootstrap.json"""
import sys, json, pathlib, argparse, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd, joblib
from sklearn.metrics import roc_auc_score
from swallohear.preprocess import preprocess, frame_times, frame_signal
from swallohear.features import frame_energy_db
from swallohear.postprocess import scores_to_events
from swallohear.metrics import match_events
from swallohear.reliability import signal_quality
from swallohear.final import event_features
ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data/interim"); ap.add_argument("--out", default="results"); ap.add_argument("--B", type=int, default=1000); a = ap.parse_args()
root = pathlib.Path(a.root); SIG, LAB = root / "signals" / "signals", root / "labels" / "labels"
R = pd.read_csv(root / "index.csv"); S = json.load(open(root / "splits.json")); ok = R[R.labels_inside_signal & R.start_lt_end]
test = ok[ok.participant.isin(S["test"])]; pid = dict(zip(R.recording, R.participant)); pre = dict(zip(R.recording, R.prefix))
cfg = json.load(open("configs/final.json")); rv = json.load(open("results/reliability_v2.json"))["reliability"]; tau, snr_min = rv["tau"], rv["snr_min"]
rf_c, rf_a, rel = joblib.load("models/rf_mic.joblib"), joblib.load("models/rf_mic_aug.joblib"), joblib.load("models/event_reliability.joblib")
RV = json.load(open("results/reliability_v2.json")); PR = RV.get("params") or {"RF clean-trained": [0.7, 0.65, 0.4], "RF noise-augmented": [0.7, 0.65, 0.4]}  # fallback = values printed by the final run_reliability_v2.py
P_CLEAN = tuple(PR["RF clean-trained"]); P_AUG = tuple(PR["RF noise-augmented"])   # tuned on validation by run_reliability_v2.py
def get(rid):
    x = np.load(SIG / f"{rid}.npy", mmap_mode="r")[:, 0].astype(np.float32); d = pd.read_csv(LAB / f"{rid}.csv")
    return x, [(float(s) / 60, float(e) / 60) for s, e in zip(d.start, d.end)]
def add_noise(x, ev, snr, seed):
    t = np.arange(len(x)) / 4000; m = np.zeros(len(x), bool)
    for s, e in ev: m |= (t >= s) & (t <= e)
    Pw = np.mean(x[m] ** 2) if m.any() else np.mean(x ** 2); return x + np.random.default_rng(seed).standard_normal(len(x)).astype(np.float32) * np.sqrt(Pw / 10 ** (snr / 10))
data = {r: get(r) for r in test.recording}
def run(snr):
    """per participant: dict(method -> [tp, fp, fn, minutes]) and event list (rel score, model confidence, correct)"""
    per = {}
    for i, (rid, (x, ev)) in enumerate(data.items()):
        if snr is not None: x = add_noise(x, ev, snr, 1000 + i)
        xp, meta = preprocess(x); q = signal_quality(x, xp, meta, 2000.0); e = frame_energy_db(frame_signal(xp)); fl = float(np.percentile(e, 10)); t = frame_times(len(e)); mins = len(x) / 4000 / 60
        d = per.setdefault(pid[rid], dict(clean_rf=np.zeros(4), aug_rf=np.zeros(4), rel=np.zeros(4), ev=[], grp=pre[rid]))
        for key, m, prm in (("clean_rf", rf_c, P_CLEAN), ("aug_rf", rf_a, P_AUG)):
            p = m.predict_proba(xp); fr = scores_to_events(p, hi=prm[0], lo=prm[1], merge_gap_s=prm[2]); pred = [(float(t[s]), float(t[k])) for s, k in fr]
            pairs, fp, fn = match_events(pred, ev, 0.5); d[key] += np.array([len(pairs), len(fp), len(fn), mins])
            if key == "aug_rf":
                good = {a_ for a_, _ in pairs}; keep_tp = keep_fp = 0
                for j, (s, k) in enumerate(fr):
                    f = event_features(p[s:k + 1], e[s:k + 1], fl, q["snr_db"]); sc = rel.predict_proba(np.array([f]))[0, 1]; d["ev"].append((sc, f[0], j in good))
                    if sc >= tau and q["snr_db"] >= snr_min: keep_tp += j in good; keep_fp += j not in good
                d["rel"] += np.array([keep_tp, keep_fp, len(ev) - keep_tp, mins])
    return per
def agg(per, key, ids): v = sum(per[i][key] for i in ids); return v
def f1(v): return 2 * v[0] / max(2 * v[0] + v[1] + v[2], 1)
def prec(v): return v[0] / max(v[0] + v[1], 1)
def fpm(v): return v[1] / max(v[3], 1e-9)
def ci(vals):
    vals = [v for v in vals if not np.isnan(v)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else [float('nan'), float('nan')]
rng = np.random.default_rng(0); out = {}; t0 = time.time()
for snr in (None, 20, 10, 5):
    per = run(snr); ids = list(per); lab = "clean" if snr is None else f"{snr}dB"; r = {}
    boots = [[ids[j] for j in rng.integers(0, len(ids), len(ids))] for _ in range(a.B)]
    point = lambda key, fn_: fn_(agg(per, key, ids))
    for key in ("clean_rf", "aug_rf", "rel"):
        r[key] = dict(f1=point(key, f1), f1_ci=ci([f1(agg(per, key, b)) for b in boots]), precision=point(key, prec), precision_ci=ci([prec(agg(per, key, b)) for b in boots]), fp_per_min=point(key, fpm), fp_per_min_ci=ci([fpm(agg(per, key, b)) for b in boots]))
    r["f1_diff_aug_minus_clean"] = dict(point=f1(agg(per, "aug_rf", ids)) - f1(agg(per, "clean_rf", ids)), ci=ci([f1(agg(per, "aug_rf", b)) - f1(agg(per, "clean_rf", b)) for b in boots]))
    r["fp_per_min_reduction_rel_vs_ordinary"] = dict(point=fpm(agg(per, "aug_rf", ids)) - fpm(agg(per, "rel", ids)), ci=ci([fpm(agg(per, "aug_rf", b)) - fpm(agg(per, "rel", b)) for b in boots]))
    def auc_pair(b):
        ev = [e for i in b for e in per[i]["ev"]]; y = [e[2] for e in ev]
        return (roc_auc_score(y, [e[0] for e in ev]), roc_auc_score(y, [e[1] for e in ev])) if 0 < sum(y) < len(y) else (np.nan, np.nan)
    a0 = auc_pair(ids); bs = np.array([auc_pair(b) for b in boots]); r["auroc_learned"] = dict(point=a0[0], ci=ci(bs[:, 0])); r["auroc_model_confidence"] = dict(point=a0[1], ci=ci(bs[:, 1]))
    r["auroc_diff"] = dict(point=a0[0] - a0[1], ci=ci(bs[:, 0] - bs[:, 1]))
    r["by_group_aug_rf_f1"] = {g: f1(sum(per[i]["aug_rf"] for i in ids if per[i]["grp"] == g)) for g in ("ns", "s")}
    chk = RV["E2_E4"]["RF noise-augmented"][str(snr) if snr else "clean"]["f1"]; mine = f1(agg(per, "aug_rf", ids)); r["consistency_vs_main_run"] = dict(main=chk, bootstrap_script=mine)
    print(f"[{lab}] CONSISTENCY CHECK noise-augmented F1: main run {chk:.3f} vs this script {mine:.3f} -> {'OK' if abs(chk-mine) < 0.005 else 'MISMATCH - DO NOT USE'}")
    out[lab] = r; print(f"[{lab}] F1 clean-trained {r['clean_rf']['f1']:.3f} {r['clean_rf']['f1_ci']} | aug {r['aug_rf']['f1']:.3f} {r['aug_rf']['f1_ci']} | diff {r['f1_diff_aug_minus_clean']['point']:.3f} CI {np.round(r['f1_diff_aug_minus_clean']['ci'],3).tolist()}")
    print(f"      AUROC learned {r['auroc_learned']['point']:.3f} {np.round(r['auroc_learned']['ci'],3).tolist()} vs model-confidence {r['auroc_model_confidence']['point']:.3f} {np.round(r['auroc_model_confidence']['ci'],3).tolist()} | diff CI {np.round(r['auroc_diff']['ci'],3).tolist()}")
    print(f"      precision ordinary {r['aug_rf']['precision']:.3f} {np.round(r['aug_rf']['precision_ci'],3).tolist()} -> reliability-aware {r['rel']['precision']:.3f} {np.round(r['rel']['precision_ci'],3).tolist()} | FP/min {r['aug_rf']['fp_per_min']:.2f} -> {r['rel']['fp_per_min']:.2f} (reduction CI {np.round(r['fp_per_min_reduction_rel_vs_ordinary']['ci'],2).tolist()}) | by group F1 {r['by_group_aug_rf_f1']}  ({time.time()-t0:.0f}s)")
pathlib.Path(a.out).mkdir(exist_ok=True); json.dump(out, open(pathlib.Path(a.out) / "bootstrap.json", "w"), indent=1, default=float); print("wrote", pathlib.Path(a.out) / "bootstrap.json")
