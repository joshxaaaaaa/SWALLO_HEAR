"""Event-based evaluation: one-to-one IoU matching, onset/offset error, ECE."""
from __future__ import annotations
import numpy as np

def iou(a, b):
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0])); union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0

def match_events(pred, ref, thr=0.5):
    """Greedy one-to-one matching by IoU. Returns (pairs[(pi, ri)], fp_idx, fn_idx)."""
    cand = sorted(((iou(p, r), i, j) for i, p in enumerate(pred) for j, r in enumerate(ref)), reverse=True)
    up, ur, pairs = set(), set(), []
    for v, i, j in cand:
        if v < thr: break
        if i in up or j in ur: continue
        up.add(i); ur.add(j); pairs.append((i, j))
    return pairs, [i for i in range(len(pred)) if i not in up], [j for j in range(len(ref)) if j not in ur]

def event_scores(pred, ref, thr=0.5):
    pairs, fp, fn = match_events(pred, ref, thr); tp = len(pairs)
    P = tp / (tp + len(fp)) if tp + len(fp) else 0.0; R = tp / (tp + len(fn)) if tp + len(fn) else 0.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    on = [pred[i][0] - ref[j][0] for i, j in pairs]; off = [pred[i][1] - ref[j][1] for i, j in pairs]
    return dict(tp=tp, fp=len(fp), fn=len(fn), precision=P, recall=R, f1=F, onset_err=on, offset_err=off)

def ece(conf, correct, n_bins=15):
    """Expected calibration error with equal-mass bins."""
    conf, correct = np.asarray(conf, float), np.asarray(correct, float)
    if len(conf) == 0: return float("nan")
    o = np.argsort(conf); bins = np.array_split(o, n_bins)
    return float(sum(len(b) / len(conf) * abs(conf[b].mean() - correct[b].mean()) for b in bins if len(b)))
