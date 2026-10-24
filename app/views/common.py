"""Shared model access, detector settings, signal helpers and chart builders for every page."""
from __future__ import annotations
import sys, pathlib, json, csv, io

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import spectrogram

from swallohear import TARGET_FS as FS, synth, metrics
from swallohear.final import Analyzer

# ----------------------------------------------------------------------------- look & words
TEAL, AMBER, SLATE, GREEN, RED = "#1B7F7A", "#E0A458", "#7A8A94", "#2E9E6B", "#C8553D"
TIER_COLOR = {"Confident": TEAL, "Low-confidence": AMBER}


def is_dark() -> bool:
    return st.session_state.get("theme_choice") == "dark"


def ink() -> str:
    """Line colour for waveforms and spectra that reads on the current background."""
    return "#C9D6E3" if is_dark() else "#244668"
STATUS = {  # colour, icon, headline, explanation
    "Analyzable":   (TEAL,  "✓", "Events detected",
                     "The recording passed the quality gate and the detector found swallowing-related events."),
    "No event":     (SLATE, "○", "No event detected",
                     "Quality was good enough to analyse, but nothing crossed the detection threshold. This does not prove no swallow occurred."),
    "Inconclusive": (AMBER, "!", "Result withheld",
                     "Signal quality was too poor to judge, so the system withholds its result rather than guessing."),
}
CODE_HELP = {
    "LOW_SNR": "Background noise is close to the level of the sounds we need.",
    "CLIPPING": "The recording is distorted because the input level was too high.",
    "FLATLINE": "Long stretches of the signal are perfectly flat, which usually means a dropout.",
    "LOW_BANDWIDTH": "The file was recorded at too low a sample rate to carry swallow sounds.",
    "TOO_SHORT": "The recording is under 1 second.",
    "TOO_LONG": "The recording is over 120 seconds.",
}
# Order matches swallohear.final.event_features
FEATURES = [
    ("Mean frame score", "Average detector score across the event.", "{:.2f}"),
    ("Peak frame score", "Highest detector score inside the event.", "{:.2f}"),
    ("Score spread", "How much the detector score wobbles inside the event (std).", "{:.2f}"),
    ("Duration", "Event length.", "{:.2f} s"),
    ("Mean loudness above floor", "Average frame energy above the recording's noise floor.", "{:.1f} dB"),
    ("Peak loudness above floor", "Loudest frame above the noise floor.", "{:.1f} dB"),
    ("Recording SNR", "Estimated signal-to-noise of the whole recording.", "{:.1f} dB"),
]
CHART_CFG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "autoScale2d"]}
DEMO_DIR = ROOT / "data" / "demo"
SETTINGS = ("tau", "hi", "lo", "merge", "snr_min")

# A sidebar slot the entry script reserves above the shared settings, so pages can put their inputs on top.
sidebar_top = None


# ----------------------------------------------------------------------------- model & settings
@st.cache_resource(show_spinner="Loading trained models…")
def load_analyzer() -> Analyzer:
    return Analyzer(str(ROOT / "models"), str(ROOT / "configs" / "final.json"), str(ROOT / "results" / "reliability_v2.json"))


def validated(A: Analyzer) -> dict:
    return dict(tau=float(A.tau), hi=float(A.hi), lo=float(A.lo), merge=float(A.merge), snr_min=float(A.snr_min))


def current_settings() -> dict:
    cfg = {k: float(st.session_state[f"set_{k}"]) for k in SETTINGS}
    cfg["lo"] = min(cfg["lo"], cfg["hi"])
    return cfg


def settings_changed(A: Analyzer) -> list[str]:
    cur, ref = current_settings(), validated(A)
    return [k for k in SETTINGS if abs(cur[k] - ref[k]) > 1e-6]


@st.cache_data(show_spinner=False, max_entries=96)
def score(signal: np.ndarray, nyq: float) -> dict:
    return load_analyzer().score(signal, orig_nyquist=nyq)


def analyze(signal: np.ndarray, nyq: float, cfg: dict | None = None):
    """Returns (scored, result). Scoring is cached, so changing cfg only re-runs the cheap assembly."""
    s = score(np.asarray(signal, dtype=np.float32), float(nyq))
    return s, load_analyzer().assemble(s, **(cfg or current_settings()))


# ----------------------------------------------------------------------------- signal helpers
NOISE_KINDS = ["White", "Pink", "Mains hum (60 Hz)"]


def add_noise(x: np.ndarray, snr_db: float, kind: str = "White", seed: int = 0) -> np.ndarray:
    """Approximate stress test: noise at `snr_db` relative to whole-signal RMS."""
    rng, n = np.random.default_rng(seed), len(x)
    if kind == "Pink":
        f = np.fft.rfftfreq(n, 1 / FS); spec = np.fft.rfft(rng.standard_normal(n))
        spec[1:] /= np.sqrt(f[1:]); spec[0] = 0; nz = np.fft.irfft(spec, n)
    elif kind.startswith("Mains"):
        t = np.arange(n) / FS
        nz = sum(np.sin(2 * np.pi * 60 * k * t + rng.uniform(0, 2 * np.pi)) / k for k in (1, 2, 3, 5)) + 0.05 * rng.standard_normal(n)
    else:
        nz = rng.standard_normal(n)
    nz = nz / (float(np.sqrt(np.mean(np.square(nz)))) or 1.0)
    rms = float(np.sqrt(np.mean(np.square(x)))) or 1.0
    return (x + nz * rms / 10 ** (snr_db / 20.0)).astype(np.float32)


def add_clipping(x: np.ndarray, gain: float = 4.0) -> np.ndarray:
    peak = float(np.max(np.abs(x))) or 1.0
    return np.clip(x / peak * gain, -1.0, 1.0).astype(np.float32)


def wav(x: np.ndarray, t0: float | None = None, t1: float | None = None, pad: float = 0.25) -> bytes:
    if t0 is not None:
        x = x[max(0, int((t0 - pad) * FS)): min(len(x), int((t1 + pad) * FS))]
    return synth.to_wav_bytes(x)


def demo_clips() -> list[pathlib.Path]:
    return sorted(DEMO_DIR.glob("*.wav")) if DEMO_DIR.exists() else []


def demo_meta(path: pathlib.Path) -> dict:
    m = path.with_suffix(".json")
    return json.loads(m.read_text()) if m.exists() else {}


def demo_name(path: pathlib.Path) -> str:
    return path.stem.replace("demo_", "")


def to_csv(rows: list[dict], cols: list[str]) -> str:
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    return buf.getvalue()


def match(events: list[dict], ref: list) -> tuple[dict, dict, set]:
    """Scores plus maps pred index -> ref index and the set of matched ref indices."""
    pred = [(e["onset_s"], e["offset_s"]) for e in events]
    refs = [tuple(v) for v in ref]
    pairs, _, _ = metrics.match_events(pred, refs, thr=0.5)
    return metrics.event_scores(pred, refs, thr=0.5), dict(pairs), {j for _, j in pairs}


# ----------------------------------------------------------------------------- UI bits
def verdict(status: str, codes: list[str], subtitle: str = ""):
    colour, icon, head, text = STATUS[status]
    chips = "".join(f'<span class="sh-chip" title="{CODE_HELP.get(c, "")}">{c.replace("_", " ").title()}</span>' for c in codes)
    st.markdown(
        f'<div class="sh-verdict" style="--c:{colour}"><div class="sh-icon">{icon}</div><div>'
        f'<h3>{head}</h3><p>{text}</p>{f"<div class=sh-chips>{chips}</div>" if chips else ""}'
        f'{f"<small>{subtitle}</small>" if subtitle else ""}</div></div>', unsafe_allow_html=True)


def tier_badge(tier: str):
    st.badge(tier, color="blue" if tier == "Confident" else "orange",
             icon=":material/verified:" if tier == "Confident" else ":material/help:")


# ----------------------------------------------------------------------------- charts
def _envelope(x: np.ndarray, t0: float = 0.0, max_pts: int = 5000):
    n = len(x); step = max(1, n // max(1, max_pts // 2))
    if step == 1:
        return t0 + np.arange(n) / FS, x
    m = n // step; xs = x[: m * step].reshape(m, step)
    t = t0 + (np.arange(m) * step + step / 2) / FS
    return np.repeat(t, 2), np.column_stack([xs.min(1), xs.max(1)]).ravel()


def _spec(x: np.ndarray, max_cols: int = 1200):
    f, t, S = spectrogram(x, fs=FS, nperseg=256, noverlap=192)
    S = 10 * np.log10(S + 1e-12)
    if S.shape[1] > max_cols:
        k = int(np.ceil(S.shape[1] / max_cols)); m = S.shape[1] // k
        S = S[:, : m * k].reshape(len(f), m, k).mean(2); t = t[: m * k].reshape(m, k).mean(1)
    lo, hi = np.percentile(S, [5, 99.5])
    return f, t, S, lo, hi


def timeline(x, r, events, *, faded=False, show_spec=True, ref=(), show_ref=False, selected=None, hi=0.7, lo=0.65, height=None,
             line=None, for_print=False):
    """`line` overrides the waveform colour; `for_print` uses SVG instead of WebGL, which browsers often leave blank when printing."""
    rows = 3 if show_spec and len(x) >= 256 else 2
    titles = ("Waveform", "Spectrogram (0–2 kHz)", "Detector score per 16 ms frame") if rows == 3 else ("Waveform", "Detector score per 16 ms frame")
    heights = [0.34, 0.33, 0.33] if rows == 3 else [0.55, 0.45]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=heights, subplot_titles=titles)

    tw, yw = _envelope(x, max_pts=2500 if for_print else 5000)
    trace = go.Scatter if for_print else go.Scattergl
    fig.add_trace(trace(x=tw, y=yw, mode="lines", line=dict(width=0.8, color=line or ink()), hoverinfo="skip", name="waveform"), row=1, col=1)
    if rows == 3:
        f, ts, S, zlo, zhi = _spec(x)
        fig.add_trace(go.Heatmap(x=ts, y=f, z=S, zmin=zlo, zmax=zhi, colorscale="Viridis", showscale=False,
                                 hovertemplate="%{x:.2f} s · %{y:.0f} Hz · %{z:.0f} dB<extra></extra>"), row=2, col=1)
    sr = rows
    fig.add_trace(go.Scatter(x=r["frame_t"], y=r["frame_prob"], mode="lines", line=dict(width=1.5, color=SLATE),
                             fill="tozeroy", fillcolor="rgba(122,138,148,.12)", name="score",
                             hovertemplate="%{x:.2f} s · score %{y:.2f}<extra></extra>"), row=sr, col=1)
    fig.add_hline(y=hi, line=dict(color=TEAL, width=1, dash="dash"), row=sr, col=1,
                  annotation_text=f"start {hi:.2f}", annotation_font_size=10, annotation_position="top left")
    fig.add_hline(y=lo, line=dict(color=TEAL, width=1, dash="dot"), row=sr, col=1,
                  annotation_text=f"continue {lo:.2f}", annotation_font_size=10, annotation_position="bottom left")

    if show_ref:
        for s, e in ref:
            for rr in range(1, rows + 1):
                fig.add_vrect(x0=s, x1=e, fillcolor="rgba(0,0,0,0)", line=dict(width=1.5, dash="dot", color=GREEN), row=rr, col=1)

    op = 0.08 if faded else 0.2
    for i, e in enumerate(events):
        c = TIER_COLOR[e["tier"]]; sel = i == selected
        for rr in range(1, rows + 1):
            fig.add_vrect(x0=e["onset_s"], x1=e["offset_s"], fillcolor=c, opacity=0.35 if sel else op,
                          line=dict(width=2 if sel else 0, color=c), layer="below", row=rr, col=1)
    if events:
        fig.add_trace(go.Scatter(
            x=[(e["onset_s"] + e["offset_s"]) / 2 for e in events], y=[1.07] * len(events), mode="markers+text",
            marker=dict(size=[24 if i == selected else 18 for i in range(len(events))], color=[TIER_COLOR[e["tier"]] for e in events],
                        line=dict(width=2, color="white"), opacity=0.5 if faded else 1),
            text=[str(i + 1) for i in range(len(events))], textfont=dict(color="white", size=11),
            customdata=[[i, e["reliability"], e["tier"], e["onset_s"], e["offset_s"]] for i, e in enumerate(events)],
            hovertemplate="<b>Event %{text}</b><br>%{customdata[3]:.2f}–%{customdata[4]:.2f} s<br>"
                          "%{customdata[2]} · reliability %{customdata[1]:.2f}<br><i>click to inspect</i><extra></extra>",
            name="events"), row=sr, col=1)

    fig.update_yaxes(title_text="amplitude", row=1, col=1, showticklabels=False)
    if rows == 3:
        fig.update_yaxes(title_text="Hz", row=2, col=1)
    fig.update_yaxes(title_text="score", range=[0, 1.15], tickvals=[0, 0.5, 1], row=sr, col=1)
    fig.update_xaxes(title_text="time (s)", row=sr, col=1)
    fig.update_layout(height=height or (600 if rows == 3 else 440), margin=dict(l=10, r=10, t=30, b=10), showlegend=False,
                      hovermode="closest", dragmode="zoom", clickmode="event+select")
    fig.update_annotations(font_size=12)
    return fig


def event_zoom(x, r, e, pad=1.0):
    t0, t1 = max(0.0, e["onset_s"] - pad), min(len(x) / FS, e["offset_s"] + pad)
    seg = x[int(t0 * FS): int(t1 * FS)]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.55, 0.45])
    tw, yw = _envelope(seg, t0, 3000)
    fig.add_trace(go.Scattergl(x=tw, y=yw, mode="lines", line=dict(width=0.8, color=ink()), hoverinfo="skip"), row=1, col=1)
    ft, fp = np.asarray(r["frame_t"]), np.asarray(r["frame_prob"]); m = (ft >= t0) & (ft <= t1)
    fig.add_trace(go.Scatter(x=ft[m], y=fp[m], mode="lines", line=dict(width=1.6, color=SLATE),
                             hovertemplate="%{x:.2f} s · %{y:.2f}<extra></extra>"), row=2, col=1)
    c = TIER_COLOR[e["tier"]]
    for rr in (1, 2):
        fig.add_vrect(x0=e["onset_s"], x1=e["offset_s"], fillcolor=c, opacity=0.22, line_width=0, row=rr, col=1)
    fig.update_yaxes(showticklabels=False, row=1, col=1); fig.update_yaxes(range=[0, 1], title_text="score", row=2, col=1)
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    return fig


def gauge(value: float, tau: float, tier: str):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number=dict(valueformat=".2f", font=dict(size=34)),
        gauge=dict(axis=dict(range=[0, 1], tickvals=[0, tau, 1], tickformat=".2f"), bar=dict(color=TIER_COLOR[tier], thickness=0.35),
                   steps=[dict(range=[0, tau], color="rgba(224,164,88,.15)"), dict(range=[tau, 1], color="rgba(27,127,122,.15)")],
                   threshold=dict(line=dict(color=ink(), width=3), thickness=0.8, value=tau))))
    fig.update_layout(height=190, margin=dict(l=34, r=34, t=24, b=0))
    return fig


def lanes(events, ref, pairs, matched_ref, duration):
    fig = go.Figure()
    for j, (s, e) in enumerate(ref):
        c = GREEN if j in matched_ref else RED
        fig.add_shape(type="rect", x0=s, x1=e, y0=1.6, y1=2.4, fillcolor=c, opacity=0.8, line_width=0)
    for i, ev in enumerate(events):
        c = GREEN if i in pairs else RED
        fig.add_shape(type="rect", x0=ev["onset_s"], x1=ev["offset_s"], y0=0.6, y1=1.4, fillcolor=c, opacity=0.8, line_width=0)
        fig.add_annotation(x=(ev["onset_s"] + ev["offset_s"]) / 2, y=1, text=str(i + 1), showarrow=False, font=dict(color="white", size=11))
    fig.add_trace(go.Scatter(x=[0, duration], y=[0, 0], mode="markers", marker=dict(opacity=0), hoverinfo="skip"))
    fig.update_yaxes(range=[0.3, 2.7], tickvals=[1, 2], ticktext=["System", "Expert"], showgrid=False)
    fig.update_xaxes(range=[0, duration], title_text="time (s)")
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    return fig


# ----------------------------------------------------------------------------- explanations
def explain(features) -> dict | None:
    """Exact per-feature contributions (log-odds) of the reliability model for one event.
    The model is StandardScaler -> LogisticRegression, so logit = intercept + sum(coef * standardised value)."""
    try:
        pipe = load_analyzer().rel
        sc, lr = pipe.steps[0][1], pipe.steps[-1][1]
        z = (np.asarray(features, float) - sc.mean_) / sc.scale_
        return dict(intercept=float(lr.intercept_[0]), contrib=(lr.coef_[0] * z).tolist(), typical=sc.mean_.tolist())
    except Exception:
        return None


def top_reasons(ex: dict | None, k: int = 2) -> tuple[list[str], list[str]]:
    if not ex:
        return [], []
    c = np.asarray(ex["contrib"]); order = np.argsort(-np.abs(c))
    up = [FEATURES[i][0] for i in order if c[i] > 0.05][:k]
    down = [FEATURES[i][0] for i in order if c[i] < -0.05][:k]
    return up, down


def explain_fig(ex: dict, tau: float):
    c = np.asarray(ex["contrib"]); order = list(np.argsort(-np.abs(c)))
    logit = ex["intercept"] + float(c.sum()); p = 1 / (1 + np.exp(-logit))
    fig = go.Figure(go.Waterfall(
        orientation="h", measure=["absolute"] + ["relative"] * len(order) + ["total"],
        y=["Average event"] + [FEATURES[i][0] for i in order] + ["This event"],
        x=[ex["intercept"]] + [float(c[i]) for i in order] + [0],
        text=[f"{ex['intercept']:+.2f}"] + [f"{c[i]:+.2f}" for i in order] + [f"{logit:+.2f} → {p:.2f}"], textposition="auto", cliponaxis=False,
        increasing=dict(marker=dict(color=TEAL)), decreasing=dict(marker=dict(color=AMBER)), totals=dict(marker=dict(color=SLATE)),
        connector=dict(line=dict(color="rgba(128,128,128,.35)", width=1)),
        hovertemplate="%{y}: %{x:+.2f}<extra></extra>"))
    t = float(np.log(tau / (1 - tau))) if 0 < tau < 1 else 0.0
    fig.add_vline(x=t, line=dict(color=RED, dash="dash"), annotation_text=f"threshold {tau:.2f}", annotation_position="top")
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=360, margin=dict(l=10, r=40, t=30, b=10), xaxis_title="← less reliable   ·   evidence (log-odds)   ·   more reliable →",
                      showlegend=False)
    return fig


# ----------------------------------------------------------------------------- rhythm
def rhythm(events: list[dict], duration: float) -> dict:
    ev = sorted(events, key=lambda e: e["onset_s"]); on = np.array([e["onset_s"] for e in ev]); n = len(ev)
    iei = np.diff(on)
    gaps = ([ev[0]["onset_s"]] + [b["onset_s"] - a["offset_s"] for a, b in zip(ev, ev[1:])] + [duration - ev[-1]["offset_s"]]) if n else [duration]
    cv = float(iei.std() / iei.mean()) if len(iei) > 1 and iei.mean() > 0 else None
    return dict(n=n, rate=n / max(duration / 60, 1e-9), iei=iei.tolist(), onsets=on.tolist(),
                mean_iei=float(iei.mean()) if len(iei) else None, median_iei=float(np.median(iei)) if len(iei) else None,
                cv=cv, regularity=None if cv is None else ("steady" if cv < 0.25 else "moderate" if cv < 0.5 else "irregular"),
                longest_gap=float(max(gaps)))


def rhythm_figs(events: list[dict], duration: float):
    ev = sorted(events, key=lambda e: e["onset_s"])
    cum = go.Figure()
    for name, sub, colour in (("All events", ev, SLATE), ("Confident only", [e for e in ev if e["tier"] == "Confident"], TEAL)):
        xs = [0.0] + [e["onset_s"] for e in sub] + [duration]; ys = [0] + list(range(1, len(sub) + 1)) + [len(sub)]
        cum.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(shape="hv", width=2.5, color=colour), name=name,
                                 hovertemplate="%{x:.1f} s · %{y} events<extra></extra>"))
    cum.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="time (s)", yaxis_title="events so far",
                      legend=dict(orientation="h", y=-0.3))
    iei = np.diff([e["onset_s"] for e in ev])
    bars = go.Figure(go.Bar(x=[f"{i + 1}→{i + 2}" for i in range(len(iei))], y=iei, marker_color=TEAL,
                            hovertemplate="events %{x}: %{y:.1f} s apart<extra></extra>"))
    if len(iei):
        bars.add_hline(y=float(iei.mean()), line=dict(dash="dash", color=SLATE), annotation_text=f"mean {iei.mean():.1f} s")
    bars.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="consecutive events", yaxis_title="seconds apart")
    return cum, bars


# ----------------------------------------------------------------------------- quality checks
def quality_checks(q: dict, nyq: float, snr_min: float) -> list[tuple[str, str, str, bool]]:
    return [
        ("Signal-to-noise", f"{q['snr_db']:.1f} dB", f"≥ {snr_min:.1f} dB", q["snr_db"] >= snr_min),
        ("Clipped samples", f"{q['clip_frac']:.2%}", "≤ 2%", q["clip_frac"] <= 0.02),
        ("Flat (dropout) samples", f"{q['flat_frac']:.2%}", "≤ 30%", q["flat_frac"] <= 0.30),
        ("Original bandwidth", f"{nyq:.0f} Hz", "≥ 1000 Hz", nyq >= 1000),
        ("Duration", f"{q['duration_s']:.1f} s", "1–120 s", 1.0 <= q["duration_s"] <= 120),
    ]


# ----------------------------------------------------------------------------- printable report
def build_report(*, label, r, x, nyq, cfg, changed, stress, ref, notes, explanations) -> str:
    """Self-contained HTML report (plotly.js inlined so it works offline). Uses no Streamlit calls,
    so it can run in the download button's background thread."""
    import html, time as _t
    e_ = html.escape
    q, events, withheld = r["quality"], r["events"], r["withheld_candidates"]
    shown, faded = (events or withheld), not events
    colour, _icon, head, text = STATUS[r["status"]]
    rh = rhythm(shown, q["duration_s"])

    def fig_html(fig, first=False):
        fig.update_layout(template="plotly_white", paper_bgcolor="white", plot_bgcolor="white", font=dict(color="#1f2a30"))
        return fig.to_html(full_html=False, include_plotlyjs=first, config={"displayModeBar": False, "staticPlot": False})

    tl = timeline(x, r, shown, faded=faded, show_spec=True, ref=ref, show_ref=bool(ref), hi=cfg["hi"], lo=cfg["lo"],
                  height=520, line="#244668", for_print=True)
    figs = [("Timeline", fig_html(tl, first=True))]
    if len(shown) >= 2:
        cum, _ = rhythm_figs(shown, q["duration_s"])
        figs.append(("Events over time", fig_html(cum)))

    rows = ""
    for i, ev in enumerate(shown):
        up, down = top_reasons(explanations[i] if i < len(explanations) else None)
        call = notes.get(f"{label}|{ev['onset_s']:.2f}", "")
        rows += (f"<tr><td>{i + 1}</td><td>{ev['onset_s']:.2f}–{ev['offset_s']:.2f} s</td><td>{ev['duration_ms']:.0f} ms</td>"
                 f"<td><span class=bar><i style='width:{ev['reliability'] * 100:.0f}%;background:{TIER_COLOR[ev['tier']]}'></i></span> {ev['reliability']:.2f}</td>"
                 f"<td style='color:{TIER_COLOR[ev['tier']]};font-weight:600'>{ev['tier']}</td>"
                 f"<td>{e_(', '.join(up)) or '–'}</td><td>{e_(', '.join(down)) or '–'}</td><td>{e_(call) or '–'}</td></tr>")
    checks = "".join(f"<tr><td>{'✔' if ok else '✘'}</td><td>{n}</td><td>{v}</td><td>{lim}</td></tr>"
                     for n, v, lim, ok in quality_checks(q, nyq, cfg["snr_min"]))
    settings = "".join(f"<tr><td>{k}</td><td>{v:.3g}</td><td>{'changed' if k in changed else 'validated'}</td></tr>" for k, v in cfg.items())
    expert = ""
    if ref:
        s, _, _ = match(shown, ref)
        expert = (f"<h2>Agreement with expert labels</h2><p>{s['tp']} matched · {s['fp']} false detections · {s['fn']} missed · "
                  f"precision {s['precision']:.2f} · recall {s['recall']:.2f} · F1 {s['f1']:.2f}. "
                  "A detection counts as matched when it overlaps a labelled swallow by at least half. One clip proves nothing.</p>")
    rhythm_txt = (f"{rh['n']} events, {rh['rate']:.1f} per minute"
                  + (f", mean interval {rh['mean_iei']:.1f} s" if rh["mean_iei"] is not None else "")
                  + (f", {rh['regularity']} rhythm (CV {rh['cv']:.2f})" if rh["cv"] is not None else "")
                  + f", longest quiet gap {rh['longest_gap']:.1f} s.")

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SWALLOHear report · {e_(label)}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#1f2a30;background:#fff;max-width:960px;margin:2rem auto;padding:0 16px;line-height:1.45}}
h1{{margin:0;font-size:1.7rem}} h1 span{{color:{TEAL}}} h2{{font-size:1.1rem;margin:1.6rem 0 .5rem;border-bottom:1px solid #dde3e0;padding-bottom:.25rem}}
.meta{{color:#6a7780;font-size:.9rem}} .warn{{background:#fff8e1;border:1px solid #f0d58a;border-radius:8px;padding:.6rem .9rem;font-size:.9rem;margin:1rem 0}}
.verdict{{border-left:6px solid {colour};background:color-mix(in srgb,{colour} 10%,white);border-radius:8px;padding:.8rem 1rem}}
.verdict b{{font-size:1.2rem}} .grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:.5rem;margin:1rem 0}}
.card{{border:1px solid #dde3e0;border-radius:8px;padding:.5rem .7rem}} .card small{{color:#6a7780;display:block}} .card b{{font-size:1.3rem}}
table{{width:100%;border-collapse:collapse;font-size:.88rem}} th,td{{text-align:left;padding:.35rem .5rem;border-bottom:1px solid #eef1ef;vertical-align:top}}
th{{color:#6a7780;font-weight:600}} .bar{{display:inline-block;width:60px;height:8px;background:#eef1ef;border-radius:4px;vertical-align:middle}}
.bar i{{display:block;height:8px;border-radius:4px}} .two{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}}
.fig{{break-inside:avoid}} footer{{color:#6a7780;font-size:.8rem;margin-top:2rem}}
@media print{{body{{margin:0}} .noprint{{display:none}} h2{{break-after:avoid}} table,.fig,.verdict,.grid{{break-inside:avoid}}}}
@media (max-width:640px){{.grid{{grid-template-columns:repeat(2,1fr)}} .two{{grid-template-columns:1fr}}}}
</style></head><body>
<p class="noprint meta">Tip: press Ctrl+P (or ⌘P) and choose "Save as PDF" to keep a PDF copy.</p>
<h1>SWALLO<span>Hear</span> analysis report</h1>
<div class="meta">{e_(label)} · {q['duration_s']:.1f} s · generated {_t.strftime('%Y-%m-%d %H:%M')}{(' · stress test: ' + e_(stress)) if stress else ''}</div>
<div class="warn"><b>Research prototype, not a diagnostic device.</b> It detects swallowing-related acoustic events. It does not assess dysphagia,
aspiration or pneumonia, and must not be used to make care decisions.</div>
<div class="verdict"><b>{head}</b><br>{text}{('<br><small>Reasons: ' + e_(', '.join(r['reason_codes'])) + '</small>') if r['reason_codes'] else ''}</div>
<div class="grid">
<div class="card"><small>Confident</small><b>{sum(ev['tier'] == 'Confident' for ev in events)}</b></div>
<div class="card"><small>Low-confidence</small><b>{sum(ev['tier'] == 'Low-confidence' for ev in events)}</b></div>
<div class="card"><small>Withheld</small><b>{len(withheld)}</b></div>
<div class="card"><small>Estimated SNR</small><b>{q['snr_db']:.1f} dB</b></div>
<div class="card"><small>Event rate</small><b>{rh['rate']:.1f}/min</b></div></div>
{''.join(f'<h2>{t}</h2><div class="fig">{h}</div>' for t, h in figs)}
<h2>Events{' (withheld, shown for inspection only)' if faded and shown else ''}</h2>
{'<table><tr><th>#</th><th>Time</th><th>Length</th><th>Reliability</th><th>Tier</th><th>Raised by</th><th>Lowered by</th><th>Reviewer call</th></tr>' + rows + '</table>' if shown else '<p>No events.</p>'}
<p class="meta">"Raised by" / "Lowered by" are the measurements that pushed the reliability model's score up or down most for that event.</p>
<h2>Swallow rhythm</h2><p>{rhythm_txt}</p>
{expert}
<div class="two"><div><h2>Quality gate</h2><table><tr><th></th><th>Check</th><th>Value</th><th>Limit</th></tr>{checks}</table></div>
<div><h2>Detector settings</h2><table><tr><th>Setting</th><th>Value</th><th></th></tr>{settings}</table></div></div>
<h2>Limits</h2><p>Accuracy is modest (event F1 about 0.49 on 27 held-out participants) and nowhere near clinical standard. Noise tests use synthetic
noise, not real rooms. Results come from one public dataset (Khalifa et al., 2021, CC BY 4.0) and have not been validated on Philippine data,
phones or low-cost microphones.</p>
<footer>SWALLOHear · Team RIPARION · research use only</footer>
</body></html>"""
