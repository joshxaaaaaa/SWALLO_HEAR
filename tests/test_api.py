"""Smoke test for the mobile API: starts api/server.py and calls every endpoint.
Run from the repo folder:  python tests/test_api.py      (needs models/ and data/demo/; M4A step needs imageio-ffmpeg)"""
import json, pathlib, subprocess, sys, tempfile, time, urllib.request, uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"


def call(path, data=None, ctype=None):
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": ctype} if ctype else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        return json.loads(body) if r.headers.get_content_type() == "application/json" else body


def post_json(path, obj):
    return call(path, json.dumps(obj).encode(), "application/json")


def post_form(path, fields, files=()):
    b = uuid.uuid4().hex; out = b""
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, name, data in files:
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n"
    return call(path, out + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}")


def main():
    proc = subprocess.Popen([sys.executable, str(ROOT / "api" / "server.py"), "--host", "127.0.0.1", "--port", "8765"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                call("/api/health"); break
            except Exception:
                time.sleep(1)
        meta = call("/api/meta"); print("meta: demos", len(meta["demos"]), "| tau", meta["validated"]["tau"])
        rec = post_form("/api/load", {"source": "demo", "demo": "s007a_2"}); print("load demo:", rec["label"], rec["duration_s"])
        a = post_json("/api/analyze", {"rec_id": rec["rec_id"]})
        assert a["status"] == "Analyzable" and len(a["events"]) == 6 and a["spectrogram"].startswith("data:image/png"), a["status"]
        print("analyze:", a["status"], a["counts"], "| expert F1", round(a["expert"]["f1"], 2), "| rhythm", a["rhythm"]["regularity"])
        noisy = post_json("/api/analyze", {"rec_id": rec["rec_id"], "stress": {"noise_kind": "White", "snr": 5}})
        assert noisy["status"] == "Inconclusive"; print("noise 5 dB:", noisy["status"], noisy["reason_codes"])
        custom = post_json("/api/analyze", {"rec_id": rec["rec_id"], "settings": {"tau": 0.2}})
        print("tau 0.2:", custom["counts"], "changed", custom["changed"])
        wav = call(a["audio_url"]); clip = call(a["audio_url"] + "?t0=6.27&t1=7.74"); print("audio bytes:", len(wav), "clip:", len(clip))
        sw = post_json("/api/sweep", {"rec_id": rec["rec_id"], "noise_kind": "Pink"}); print("sweep:", [r["status"][0] for r in sw["rows"]])
        n = post_json(f"/api/analysis/{a['id']}/notes", {"notes": {f"{a['events'][0]['onset_s']:.2f}": "Swallow"}})
        html = call(n["report_url"]); assert b"SWALLO" in html and b"Swallow" in html; print("report:", f"{len(html) / 1e6:.1f} MB")
        syn = post_form("/api/load", {"source": "synthetic", "n": 6, "duration": 30, "seed": 1}); print("synthetic:", syn["label"], syn["labels"], "labels")
        demo_wav = (ROOT / "data" / "demo" / "demo_ns027d_1.wav").read_bytes()
        up = post_form("/api/load", {"source": "upload"}, [("file", "clip.wav", demo_wav)]); print("upload wav:", up["duration_s"])
        try:
            import imageio_ffmpeg
            with tempfile.TemporaryDirectory() as td:
                src, dst = pathlib.Path(td) / "a.wav", pathlib.Path(td) / "a.m4a"; src.write_bytes(demo_wav)
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-ar", "44100", "-c:a", "aac", str(dst)], check=True)
                m4a = post_form("/api/load", {"source": "upload"}, [("file", "phone.m4a", dst.read_bytes())])
                r = post_json("/api/analyze", {"rec_id": m4a["rec_id"]}); print("upload m4a:", m4a["duration_s"], r["status"], r["counts"])
        except ImportError:
            print("upload m4a: skipped (pip install imageio-ffmpeg)")
        b = post_form("/api/batch", {"demos": json.dumps([d["name"] for d in meta["demos"]])}); print("batch:", [r["status"][0] for r in b["rows"]])
        print("API OK")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
