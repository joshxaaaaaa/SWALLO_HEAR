"""Dataset utilities for Khalifa et al. (2021), Zenodo 10.5281/zenodo.4539695.

IMPORTANT: the record page does not document file naming, label file format, participant IDs or stroke flags.
Run scripts/prepare_data.py --audit on the downloaded files first, then fill in `parse_labels` / `participant_of`.
Known from the record: signals are N x 4 arrays (mic, A-P, S-I, M-L) at 4 kHz; labels are VFSS frame numbers; sample = frame * 4000 / 60.
"""
from __future__ import annotations
import hashlib, random
import numpy as np

MD5 = {"labels.zip": "5af27a544839b404f359e3d72b5026e2", "signals.zip": "ea0e725848c6092f946b06198f293f0d"}

def md5sum(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""): h.update(b)
    return h.hexdigest()

def frames_to_samples(frame):  # VFSS 60 fps -> 4 kHz samples
    return np.asarray(frame) * 4000.0 / 60.0

def participant_split(ids, fractions=(0.70, 0.15, 0.15), seed=0):
    """Participant-disjoint train/val/test split (unique IDs shuffled with a fixed seed)."""
    u = sorted(set(ids)); random.Random(seed).shuffle(u)
    n = len(u); a = int(round(fractions[0] * n)); b = a + int(round(fractions[1] * n))
    return u[:a], u[a:b], u[b:]


# ---------- real dataset access (format confirmed on the downloaded files) ----------
# signals/<id>.npy : float64 array (N, 4) = [microphone, A-P, S-I, M-L] @ 4 kHz
# labels/<id>.csv  : participant, file_num, swallow_num, start, end, duration, fnames  (start/end = VFSS frame numbers @ 60 fps)
# <id> like "ns011a_1" (prefix ns / s = group letter; its meaning, e.g. stroke, is UNVERIFIED)
import pathlib
import pandas as pd

def read_labels(label_dir):
    rows = []
    for f in sorted(pathlib.Path(label_dir).glob("*.csv")):
        d = pd.read_csv(f); d["recording"] = f.stem
        d["prefix"] = "".join(ch for ch in f.stem if ch.isalpha())[:2] if f.stem.startswith("ns") else "s"
        rows.append(d)
    return pd.concat(rows, ignore_index=True)

def load_recording(signal_dir, label_dir, rec_id, channel=0):
    """Returns (signal float32 @4 kHz from the chosen channel, events [(onset_s, offset_s), ...])."""
    x = np.load(pathlib.Path(signal_dir) / f"{rec_id}.npy")[:, channel].astype(np.float32)
    d = pd.read_csv(pathlib.Path(label_dir) / f"{rec_id}.csv")
    return x, [(float(a) / 60.0, float(b) / 60.0) for a, b in zip(d["start"], d["end"])]

def stratified_participant_split(participants, groups, fractions=(0.70, 0.15, 0.15), seed=0):
    """Participant-disjoint split, done separately inside each group so every split contains each group."""
    tr, va, te = [], [], []
    for g in sorted(set(groups.values())):
        a, b, c = participant_split([p for p in participants if groups[p] == g], fractions, seed)
        tr += a; va += b; te += c
    return sorted(tr), sorted(va), sorted(te)
