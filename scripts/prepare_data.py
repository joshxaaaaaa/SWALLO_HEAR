"""Step 1: verify and audit the Zenodo download. Usage:
  python scripts/prepare_data.py --dir data/raw   (folder containing signals.zip and labels.zip)
Extracts to data/interim and prints what is actually in the files, so we can verify participant IDs, stroke flags and label format
BEFORE writing the parser. Nothing here assumes an undocumented format."""
import argparse, sys, zipfile, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from swallohear.data import md5sum, MD5

ap = argparse.ArgumentParser(); ap.add_argument("--dir", default="data/raw"); ap.add_argument("--out", default="data/interim")
a = ap.parse_args(); raw = pathlib.Path(a.dir)
for name, want in MD5.items():
    p = raw / name
    if not p.exists(): print(f"MISSING {p}"); continue
    got = md5sum(p); print(f"{name}: md5 {'OK' if got == want else 'MISMATCH ' + got}")
    with zipfile.ZipFile(p) as z:
        names = z.namelist(); print(f"  {len(names)} entries; first 15:"); [print("   ", n) for n in names[:15]]
        print("  extensions:", dict(collections.Counter(pathlib.Path(n).suffix for n in names)))
        z.extractall(pathlib.Path(a.out) / name.replace(".zip", ""))
print("\nNext: open a label file and a signal file (e.g. scipy.io.loadmat / numpy.load / pandas.read_csv),")
print("decide how participant ID is encoded, then implement parse_labels() in src/swallohear/data.py.")
