"""Step 6: pick demo clips from the TEST participants only and write them to data/demo/ (WAV @4 kHz, microphone channel) + reference-label JSON.
Run from the repo folder:  python scripts/make_demo_clips.py
The source dataset is CC BY 4.0 (Khalifa et al., 2021): keep data/demo/ATTRIBUTION.txt with the clips."""
import sys, json, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import numpy as np, pandas as pd
from scipy.io import wavfile
ap = argparse.ArgumentParser(); ap.add_argument("--root", default="data/interim"); ap.add_argument("--out", default="data/demo"); ap.add_argument("--n", type=int, default=3); a = ap.parse_args()
root = pathlib.Path(a.root); R = pd.read_csv(root / "index.csv"); S = json.load(open(root / "splits.json")); out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
T = R[R.participant.isin(S["test"]) & R.labels_inside_signal & (R.n_swallows >= 2) & R.duration_s.between(6, 16)]
rng = np.random.default_rng(0)
def write(name, x, ev, note):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9; wavfile.write(out / f"{name}.wav", 4000, (x * 32000).astype(np.int16))
    json.dump(dict(reference_events_s=ev, note=note), open(out / f"{name}.json", "w"))
picked = []
for pre in ("ns", "s"):
    pool = T[T.prefix == pre]; pool = pool.iloc[rng.permutation(len(pool))][: a.n]
    for rid in pool.recording:
        d = pd.read_csv(root / "labels" / "labels" / f"{rid}.csv"); x = np.load(root / "signals" / "signals" / f"{rid}.npy", mmap_mode="r")[:, 0].astype(np.float32)
        ev = [(float(s) / 60, float(e) / 60) for s, e in zip(d.start, d.end)]; write(f"demo_{rid}", x, ev, "held-out test participant"); picked.append(rid)
        if len(picked) == 1:   # one deliberately noisy variant to show the Inconclusive state
            P = np.mean(np.concatenate([x[int(s * 4000):int(e * 4000)] for s, e in ev]) ** 2)
            xn = x + rng.standard_normal(len(x)).astype(np.float32) * np.sqrt(P / 10 ** (5 / 10)); write(f"demo_{rid}_noisy5dB", xn, ev, "same clip with synthetic white noise at 5 dB")
(out / "ATTRIBUTION.txt").write_text("Clips are excerpts (microphone channel) of: Khalifa, Y., Donohue, C., Coyle, J., & Sejdic, E. (2021). Swallowing high resolution cervical auscultation signals (Version 1) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.4539695  License: CC BY 4.0. Clips were amplitude-normalised; one is a synthetic-noise variant. Research use only.\n")
print("wrote", len(list(out.glob('*.wav'))), "clips to", out, ":", picked)
