"""Step 2: build the recording index, run sanity checks, and write the participant-disjoint split.
Run from the repo folder:   python scripts/build_index.py
Writes data/interim/index.csv and data/interim/splits.json and prints a summary to paste back."""
import sys, json, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from swallohear.data import read_labels, stratified_participant_split

ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data/interim"); ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args(); root = pathlib.Path(a.root); sig_dir = root / "signals" / "signals"; lab_dir = root / "labels" / "labels"
L = read_labels(lab_dir)
recs = []
for rid, d in L.groupby("recording"):
    arr = np.load(sig_dir / f"{rid}.npy", mmap_mode="r"); n = arr.shape[0]
    end_s = d["end"].max() / 60.0
    recs.append(dict(recording=rid, participant=d["participant"].iloc[0], prefix=d["prefix"].iloc[0], n_swallows=len(d),
                     n_samples=n, channels=arr.shape[1], duration_s=n / 4000, last_label_end_s=end_s,
                     labels_inside_signal=bool(end_s * 4000 <= n), start_lt_end=bool((d["start"] < d["end"]).all()),
                     one_participant=bool(d["participant"].nunique() == 1)))
R = pd.DataFrame(recs); R.to_csv(root / "index.csv", index=False)
print(f"recordings: {len(R)}  participants: {R.participant.nunique()}  swallows: {int(R.n_swallows.sum())}  hours: {R.duration_s.sum()/3600:.2f}")
print("channels per file:", R.channels.value_counts().to_dict())
print("SANITY  labels inside signal:", int(R.labels_inside_signal.sum()), "/", len(R), "| start<end:", int(R.start_lt_end.sum()), "| one participant per file:", int(R.one_participant.sum()))
bad = R[~(R.labels_inside_signal & R.start_lt_end)]
if len(bad): print("PROBLEM FILES (first 10):", bad.recording.head(10).tolist())
both = R.groupby("participant").prefix.nunique(); print("participants appearing under both prefixes:", int((both > 1).sum()))
print("duration_s  min/median/max:", round(R.duration_s.min(), 1), round(R.duration_s.median(), 1), round(R.duration_s.max(), 1))
print("per prefix:\n", R.groupby("prefix").agg(participants=("participant", "nunique"), recordings=("recording", "size"), swallows=("n_swallows", "sum")))
ok = R[R.labels_inside_signal & R.start_lt_end]
grp = ok.groupby("participant").prefix.first().to_dict()
tr, va, te = stratified_participant_split(sorted(grp), grp, seed=a.seed)
assert not (set(tr) & set(va)) and not (set(tr) & set(te)) and not (set(va) & set(te)), "LEAKAGE"
json.dump(dict(seed=a.seed, train=tr, val=va, test=te), open(root / "splits.json", "w"), indent=1)
for name, ids in (("train", tr), ("val", va), ("test", te)):
    s = ok[ok.participant.isin(ids)]
    print(f"{name:5} participants={len(ids):3} recordings={len(s):4} swallows={int(s.n_swallows.sum()):4}  by prefix: {s.groupby('prefix').participant.nunique().to_dict()}")
print("Participant-disjoint check passed. Wrote", root / "index.csv", "and", root / "splits.json")
