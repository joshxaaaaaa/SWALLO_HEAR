"""Frame scores -> events (hysteresis, min duration, gap merge). Shared by all detectors."""
from __future__ import annotations
import numpy as np
from .preprocess import frame_times

def scores_to_events(p, hi=0.5, lo=0.35, min_dur_s=0.15, merge_gap_s=0.1, hop_s=0.016):
    """p: frame probabilities. Returns list of (start_frame, end_frame) inclusive."""
    active, segs, start = False, [], 0
    for i, v in enumerate(p):
        if not active and v >= hi: active, start = True, i
        elif active and v < lo: active = False; segs.append((start, i - 1))
    if active: segs.append((start, len(p) - 1))
    merged = []
    for s, e in segs:
        if merged and (s - merged[-1][1]) * hop_s <= merge_gap_s: merged[-1] = (merged[-1][0], e)
        else: merged.append((s, e))
    return [(s, e) for s, e in merged if (e - s + 1) * hop_s >= min_dur_s]

def events_to_times(events, n_frames):
    t = frame_times(n_frames)
    return [(float(t[s]), float(t[e])) for s, e in events]
