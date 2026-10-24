"""SWALLOHear HTTP API for the mobile app (RESEARCH USE ONLY).

Run from the repo folder:   python api/server.py            (listens on 0.0.0.0:8000)

Wraps the same models and helpers as the web app (app/views/common.py), so results are identical.
Built on Starlette + uvicorn, which Streamlit already installs, so no extra compiled packages are needed.
Phone recordings (M4A/AAC/WebM) are decoded with imageio-ffmpeg.
"""
from __future__ import annotations
import sys, pathlib, json, base64, io, time, uuid, logging, tempfile, subprocess, argparse
from collections import OrderedDict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import numpy as np
from PIL import Image
from scipy.signal import welch
from plotly.colors import sequential
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, HTMLResponse
from starlette.routing import Route

from views import common as C  # same helpers as the web app; Streamlit caches work outside its runtime
from swallohear import io as sio, synth

logging.getLogger("streamlit").setLevel(logging.ERROR)
for name in list(logging.root.manager.loggerDict):
    if name.startswith("streamlit"):
        logging.getLogger(name).setLevel(logging.ERROR)

MAX_BYTES = 20 * 1024 * 1024
SWEEP_LEVELS = [None, 30, 20, 15, 10, 5, 0]
RECORDINGS: OrderedDict[str, dict] = OrderedDict()   # rec_id -> loaded audio
ANALYSES: OrderedDict[str, dict] = OrderedDict()     # analysis id -> everything the report and audio endpoints need


def _remember(store: OrderedDict, key: str, value: dict, limit: int = 40):
    store[key] = value; store.move_to_end(key)
    while len(store) > limit:
        store.popitem(last=False)


def _err(msg: str, code: int = 400):
    return JSONResponse({"error": msg}, status_code=code)


# ----------------------------------------------------------------------------- audio
def _decode(data: bytes, name: str) -> dict:
    """WAV/FLAC directly; anything else (M4A, AAC, WebM, MP3, 3GP) through ffmpeg."""
    try:
        return sio.load_audio(data)
    except Exception:
        pass
    import imageio_ffmpeg
    suffix = pathlib.Path(name).suffix or ".bin"
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / f"in{suffix}"; dst = pathlib.Path(td) / "out.wav"
        src.write_bytes(data)
        p = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", str(dst)],
                           capture_output=True, timeout=60)
        if p.returncode != 0 or not dst.exists():
            raise ValueError("Could not decode this audio file.")
        return sio.load_audio(dst.read_bytes())


def _apply_stress(x0: np.ndarray, stress: dict) -> tuple[np.ndarray, str]:
    x, parts = x0, []
    if stress.get("noise_kind") and stress.get("snr") is not None:
        x = C.add_noise(x, float(stress["snr"]), stress["noise_kind"]); parts.append(f"{stress['noise_kind'].lower()} noise at {int(stress['snr'])} dB")
    if stress.get("clip"):
        x = C.add_clipping(x); parts.append("clipping")
    return x, " + ".join(parts)


def _settings(raw: dict | None) -> dict:
    cfg = C.validated(C.load_analyzer())
    for k in C.SETTINGS:
        if raw and raw.get(k) is not None:
            cfg[k] = float(raw[k])
    cfg["lo"] = min(cfg["lo"], cfg["hi"])
    return cfg


# ----------------------------------------------------------------------------- payload pieces
_VIRIDIS = None


def _viridis_lut() -> np.ndarray:
    global _VIRIDIS
    if _VIRIDIS is None:
        stops = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in sequential.Viridis], float)
        pos = np.linspace(0, 1, len(stops)); grid = np.linspace(0, 1, 256)
        _VIRIDIS = np.stack([np.interp(grid, pos, stops[:, c]) for c in range(3)], 1).astype(np.uint8)
    return _VIRIDIS


def _spectrogram_png(x: np.ndarray) -> str | None:
    if len(x) < 256:
        return None
    _f, _t, S, lo, hi = C._spec(x, max_cols=900)
    z = np.clip((S - lo) / max(hi - lo, 1e-9), 0, 1)[::-1]          # high frequencies on top
    img = Image.fromarray(_viridis_lut()[(z * 255).astype(np.uint8)])
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _envelope(x: np.ndarray, n: int = 1200) -> dict:
    step = max(1, len(x) // n); m = len(x) // step; xs = x[: m * step].reshape(m, step)
    return dict(t=((np.arange(m) * step + step / 2) / C.FS).round(4).tolist(), lo=xs.min(1).round(5).tolist(), hi=xs.max(1).round(5).tolist())


def _frames(r: dict, n: int = 2400) -> dict:
    t, p = np.asarray(r["frame_t"]), np.asarray(r["frame_prob"])
    if len(p) > n:
        k = int(np.ceil(len(p) / n)); m = len(p) // k
        t, p = t[: m * k].reshape(m, k).mean(1), p[: m * k].reshape(m, k).max(1)
    return dict(t=t.round(4).tolist(), p=p.round(4).tolist())


def _event_json(i: int, e: dict) -> dict:
    ex = C.explain(e["features"]); up, down = C.top_reasons(ex)
    return dict(index=i, onset_s=e["onset_s"], offset_s=e["offset_s"], duration_ms=e["duration_ms"], reliability=e["reliability"],
                model_confidence=e["model_confidence"], tier=e["tier"], features=e["features"], explain=ex, up=up, down=down)


def _payload(aid: str, rec: dict, x: np.ndarray, s: dict, r: dict, cfg: dict, stress_note: str) -> dict:
    q = r["quality"]; events, withheld = r["events"], r["withheld_candidates"]
    shown = events or withheld; faded = not events
    e = np.asarray(s["e"]); counts, edges = np.histogram(e, bins=40)
    f, P = welch(x, fs=C.FS, nperseg=min(1024, len(x)))
    expert = None
    if rec["ref"]:
        sc, pairs, matched_ref = C.match(shown, rec["ref"])
        expert = dict(tp=sc["tp"], fp=sc["fp"], fn=sc["fn"], precision=sc["precision"], recall=sc["recall"], f1=sc["f1"],
                      onset_err_ms=float(np.median(sc["onset_err"]) * 1000) if sc["onset_err"] else None,
                      offset_err_ms=float(np.median(sc["offset_err"]) * 1000) if sc["offset_err"] else None,
                      pairs={str(k): v for k, v in pairs.items()}, matched_ref=sorted(matched_ref))
    colour, icon, head, text = C.STATUS[r["status"]]
    changed = [k for k in C.SETTINGS if abs(cfg[k] - C.validated(C.load_analyzer())[k]) > 1e-6]
    return dict(
        id=aid, rec_id=rec["id"], label=rec["label"], note=rec["note"], source=rec["source"],
        status=r["status"], verdict=dict(colour=colour, icon=icon, headline=head, text=text),
        reason_codes=r["reason_codes"], reason_help={c: C.CODE_HELP.get(c, "") for c in r["reason_codes"]},
        settings=cfg, changed=changed, stress=stress_note or None,
        duration_s=q["duration_s"], orig_fs=rec["orig_fs"], nyquist=rec["nyq"], latency_s=r["latency_s"],
        quality=q, checks=[dict(name=n, value=v, limit=l, ok=bool(ok)) for n, v, l, ok in C.quality_checks(q, rec["nyq"], cfg["snr_min"])],
        counts=dict(confident=sum(ev["tier"] == "Confident" for ev in events), low=sum(ev["tier"] == "Low-confidence" for ev in events),
                    withheld=len(withheld)),
        rate_per_min=len(shown) / max(q["duration_s"] / 60.0, 1e-9),
        events=[_event_json(i, ev) for i, ev in enumerate(shown)], faded=faded,
        frames=_frames(r), envelope=_envelope(x), spectrogram=_spectrogram_png(x),
        energy=dict(counts=counts.tolist(), edges=edges.round(2).tolist(), floor=float(np.percentile(e, 10)), peak=float(np.percentile(e, 95))),
        psd=dict(f=f.round(1).tolist(), db=(10 * np.log10(P + 1e-15)).round(2).tolist()),
        ref=rec["ref"], expert=expert, rhythm=C.rhythm(shown, q["duration_s"]),
        audio_url=f"/api/analysis/{aid}/audio.wav",
    )


# ----------------------------------------------------------------------------- endpoints
async def health(_: Request):
    return JSONResponse({"ok": True, "service": "swallohear", "time": time.time()})


async def meta(_: Request):
    A = C.load_analyzer()
    demos = []
    for p in C.demo_clips():
        m = C.demo_meta(p); a = sio.load_audio(str(p))
        demos.append(dict(name=C.demo_name(p), note=m.get("note", ""), labels=len(m.get("reference_events_s", [])), duration_s=a["duration_s"]))
    rv = json.loads((ROOT / "results" / "reliability_v2.json").read_text()) if (ROOT / "results" / "reliability_v2.json").exists() else {}
    return JSONResponse(dict(
        validated=C.validated(A), noise_kinds=C.NOISE_KINDS, demos=demos,
        features=[dict(name=n, help=h, fmt=f) for n, h, f in C.FEATURES], code_help=C.CODE_HELP,
        status={k: dict(colour=v[0], icon=v[1], headline=v[2], text=v[3]) for k, v in C.STATUS.items()},
        results=dict(E2_E4=rv.get("E2_E4", {}), E3=rv.get("E3", {})),
    ))


async def load(request: Request):
    """Load a recording once: demo clip, uploaded file or synthetic signal. Returns rec_id for later analyses."""
    form = await request.form()
    source = form.get("source", "demo")
    ref, note, label = [], "", ""
    try:
        if source == "demo":
            name = form.get("demo"); clips = {C.demo_name(p): p for p in C.demo_clips()}
            if name not in clips:
                return _err(f"Unknown demo clip: {name}")
            audio = sio.load_audio(str(clips[name])); meta_ = C.demo_meta(clips[name])
            ref, note, label = meta_.get("reference_events_s", []), meta_.get("note", ""), name
        elif source == "synthetic":
            n, dur, seed = int(form.get("n", 4)), float(form.get("duration", 20)), int(form.get("seed", 0))
            sig, ev = synth.make_recording(duration_s=dur, n_events=n, snr_db=20.0, seed=seed)
            audio = dict(signal=sig, fs=C.FS, orig_fs=C.FS, orig_nyquist=2000.0, duration_s=len(sig) / C.FS)
            ref, note, label = [list(e) for e in ev], "synthetic signal for smoke-testing, not clinical data", f"synthetic_seed{seed}"
        else:
            up = form.get("file")
            if up is None:
                return _err("No file uploaded.")
            data = await up.read()
            if len(data) > MAX_BYTES:
                return _err("File too large (max 20 MB).")
            audio = _decode(data, up.filename or "upload"); label = form.get("label") or pathlib.Path(up.filename or "upload").stem
    except Exception as exc:
        return _err(f"Could not read this recording: {exc}")
    rid = uuid.uuid4().hex[:12]
    rec = dict(id=rid, x0=np.asarray(audio["signal"], dtype=np.float32), nyq=float(audio.get("orig_nyquist", 2000.0)),
               orig_fs=int(audio.get("orig_fs", C.FS)), label=label, ref=[list(map(float, r)) for r in ref], note=note, source=source)
    _remember(RECORDINGS, rid, rec)
    return JSONResponse(dict(rec_id=rid, label=label, duration_s=len(rec["x0"]) / C.FS, labels=len(ref), note=note))


async def analyze(request: Request):
    body = await request.json()
    rec = RECORDINGS.get(body.get("rec_id", ""))
    if rec is None:
        return _err("Recording expired; load it again.", 404)
    cfg = _settings(body.get("settings")); x, stress_note = _apply_stress(rec["x0"], body.get("stress") or {})
    s, r = C.analyze(x, rec["nyq"], cfg)
    aid = uuid.uuid4().hex[:12]
    _remember(ANALYSES, aid, dict(rec=rec, x=x, r=r, cfg=cfg, stress=stress_note, notes={}))
    return JSONResponse(_payload(aid, rec, x, s, r, cfg, stress_note))


async def sweep(request: Request):
    body = await request.json()
    rec = RECORDINGS.get(body.get("rec_id", ""))
    if rec is None:
        return _err("Recording expired; load it again.", 404)
    cfg = _settings(body.get("settings")); kind = body.get("noise_kind") or C.NOISE_KINDS[0]
    out = []
    for lvl in SWEEP_LEVELS:
        xs = rec["x0"] if lvl is None else C.add_noise(rec["x0"], lvl, kind)
        _, rr = C.analyze(xs, rec["nyq"], cfg)
        shown = rr["events"] or rr["withheld_candidates"]
        f1 = C.match(shown, rec["ref"])[0]["f1"] if rec["ref"] and rr["events"] else (0.0 if rec["ref"] else None)
        out.append(dict(level="clean" if lvl is None else f"{lvl} dB", status=rr["status"],
                        confident=sum(e["tier"] == "Confident" for e in rr["events"]), low=sum(e["tier"] == "Low-confidence" for e in rr["events"]),
                        withheld=len(rr["withheld_candidates"]), est_snr=round(rr["quality"]["snr_db"], 1), f1=f1))
    return JSONResponse(dict(rows=out, snr_min=cfg["snr_min"], noise_kind=kind))


async def audio(request: Request):
    a = ANALYSES.get(request.path_params["aid"])
    if a is None:
        return Response(status_code=404)
    x = a["x"]; t0, t1 = request.query_params.get("t0"), request.query_params.get("t1")
    data = C.wav(x, float(t0), float(t1)) if t0 is not None and t1 is not None else C.wav(x)
    return Response(data, media_type="audio/wav", headers={"Cache-Control": "max-age=3600"})


async def notes(request: Request):
    a = ANALYSES.get(request.path_params["aid"])
    if a is None:
        return _err("Analysis expired.", 404)
    a["notes"] = {str(k): str(v) for k, v in ((await request.json()).get("notes") or {}).items()}
    return JSONResponse({"ok": True, "report_url": f"/api/analysis/{request.path_params['aid']}/report.html"})


async def report(request: Request):
    a = ANALYSES.get(request.path_params["aid"])
    if a is None:
        return HTMLResponse("<p>This analysis has expired. Run it again in the app.</p>", status_code=404)
    rec, r = a["rec"], a["r"]; shown = r["events"] or r["withheld_candidates"]
    changed = [k for k in C.SETTINGS if abs(a["cfg"][k] - C.validated(C.load_analyzer())[k]) > 1e-6]
    notes_ = {f"{rec['label']}|{k}": v for k, v in a["notes"].items()}   # app sends onset strings ("4.75") as keys
    html = C.build_report(label=rec["label"], r=r, x=a["x"], nyq=rec["nyq"], cfg=a["cfg"], changed=changed, stress=a["stress"],
                          ref=rec["ref"], notes=notes_, explanations=[C.explain(e["features"]) for e in shown])
    return HTMLResponse(html)


async def batch(request: Request):
    form = await request.form()
    cfg = _settings(json.loads(form.get("settings") or "{}"))
    noise_kind, snr = form.get("noise_kind") or None, form.get("snr")
    clips = {C.demo_name(p): p for p in C.demo_clips()}
    jobs = [(n, lambda p=clips[n]: sio.load_audio(str(p)), C.demo_meta(clips[n]).get("reference_events_s", []))
            for n in json.loads(form.get("demos") or "[]") if n in clips]
    for up in form.getlist("files"):
        data = await up.read()
        jobs.append((up.filename, lambda d=data, n=up.filename: _decode(d, n), []))
    rows = []
    for name, loader, ref in jobs:
        try:
            a_ = loader(); x = np.asarray(a_["signal"], dtype=np.float32)
            if noise_kind and snr is not None:
                x = C.add_noise(x, float(snr), noise_kind)
            _, r = C.analyze(x, float(a_.get("orig_nyquist", 2000.0)), cfg)
        except Exception as exc:
            rows.append(dict(recording=name, status=f"error: {exc}")); continue
        ev, q = r["events"], r["quality"]; rel = [e["reliability"] for e in ev]
        sc = C.match(ev, ref)[0] if ref else None
        rows.append(dict(recording=name, status=r["status"], reasons=", ".join(r["reason_codes"]), duration_s=round(q["duration_s"], 1),
                         snr_db=round(q["snr_db"], 1), confident=sum(e["tier"] == "Confident" for e in ev),
                         low=sum(e["tier"] == "Low-confidence" for e in ev), mean_reliability=round(float(np.mean(rel)), 3) if rel else None,
                         per_min=round(len(ev) / max(q["duration_s"] / 60, 1e-9), 1), labels=len(ref) if ref else None,
                         f1=round(sc["f1"], 3) if sc else None))
    return JSONResponse(dict(rows=rows, settings=cfg, noise=f"{noise_kind} @ {snr} dB" if noise_kind else "none"))


app = Starlette(
    routes=[
        Route("/api/health", health), Route("/api/meta", meta),
        Route("/api/load", load, methods=["POST"]), Route("/api/analyze", analyze, methods=["POST"]),
        Route("/api/sweep", sweep, methods=["POST"]), Route("/api/batch", batch, methods=["POST"]),
        Route("/api/analysis/{aid}/audio.wav", audio), Route("/api/analysis/{aid}/notes", notes, methods=["POST"]),
        Route("/api/analysis/{aid}/report.html", report),
    ],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])],
)


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser(); ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    C.load_analyzer()  # load models before the first request
    print(f"SWALLOHear API on http://{a.host}:{a.port}  (research use only)")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
