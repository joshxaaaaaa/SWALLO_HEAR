"""Compare page: two recordings (or one clip clean vs stressed) on aligned timelines with their numbers side by side."""
from __future__ import annotations

import numpy as np
import streamlit as st
import plotly.graph_objects as go

from swallohear import io as sio
from views import common as C

UPLOAD = "Upload a file…"
SIDES = ("a", "b")


def _preset(kind):
    names = [C.demo_name(p) for p in C.demo_clips()]
    if not names:
        return
    first = names[0]
    if kind == "noise":
        st.session_state.update(cmp_a_src=first, cmp_b_src=first, cmp_a_noise=False, cmp_b_noise=True, cmp_b_snr=5)
    elif kind == "clips":
        st.session_state.update(cmp_a_src=first, cmp_b_src=names[min(2, len(names) - 1)], cmp_a_noise=False, cmp_b_noise=False)


def _side(side, names, clips):
    """Inputs for one side. Returns (title, signal, nyquist, reference events, stress text) or None."""
    k = f"cmp_{side}_"
    if st.session_state.get(k + "src") not in names + [UPLOAD]:
        st.session_state[k + "src"] = names[0] if names else UPLOAD
    src = st.selectbox("Recording", names + [UPLOAD], key=k + "src")
    ref, title = [], src
    if src == UPLOAD:
        f = st.file_uploader("WAV or FLAC", type=["wav", "flac"], key=k + "file", label_visibility="collapsed")
        if f is None:
            return None
        audio, title = sio.load_audio(f.getvalue()), f.name
    else:
        path = clips[names.index(src)]
        audio, ref = sio.load_audio(str(path)), C.demo_meta(path).get("reference_events_s", [])
    x = np.asarray(audio["signal"], dtype=np.float32)
    a, b, c = st.columns([1, 1.4, 1.4], vertical_alignment="bottom")
    noise = a.toggle("Noise", key=k + "noise")
    kind = b.selectbox("Type", C.NOISE_KINDS, key=k + "kind", disabled=not noise, label_visibility="collapsed")
    snr = c.slider("SNR", -5, 30, key=k + "snr", disabled=not noise, format="%d dB", label_visibility="collapsed")
    stress = ""
    if noise:
        x = C.add_noise(x, snr, kind); stress = f"{kind.lower()} noise {snr} dB"
    return (title + (f" + {stress}" if stress else ""), x, float(audio.get("orig_nyquist", 2000.0)), ref, stress)


def _summary(r, ref, duration):
    ev = r["events"]; shown = ev or r["withheld_candidates"]
    rh = C.rhythm(shown, duration); rel = [e["reliability"] for e in ev]
    s = C.match(shown, ref)[0] if ref else None
    return {
        "Status": r["status"],
        "Confident events": sum(e["tier"] == "Confident" for e in ev),
        "Low-confidence events": sum(e["tier"] == "Low-confidence" for e in ev),
        "Withheld candidates": len(r["withheld_candidates"]),
        "Estimated SNR (dB)": round(r["quality"]["snr_db"], 1),
        "Mean reliability": round(float(np.mean(rel)), 2) if rel else None,
        "Events per minute": round(rh["rate"], 1),
        "Mean interval (s)": round(rh["mean_iei"], 1) if rh["mean_iei"] is not None else None,
        "F1 vs expert": round(s["f1"], 2) if s else None,
    }


def render():
    st.markdown("### Compare two recordings")
    st.caption("Analyse two recordings with the same detector settings and see them on aligned timelines. "
               "Use a preset or pick each side yourself.")
    clips = C.demo_clips(); names = [C.demo_name(p) for p in clips]
    for side in SIDES:  # defaults, set once so widgets never get both a default and a state value
        st.session_state.setdefault(f"cmp_{side}_noise", side == "b")
        st.session_state.setdefault(f"cmp_{side}_kind", C.NOISE_KINDS[0])
        st.session_state.setdefault(f"cmp_{side}_snr", 5)

    p1, p2, _ = st.columns([1, 1, 2])
    p1.button("Same clip: clean vs noisy", icon=":material/compare:", on_click=_preset, args=("noise",), width="stretch")
    p2.button("Two different clips", icon=":material/library_music:", on_click=_preset, args=("clips",), width="stretch")

    cfg = C.current_settings()
    cols, data = st.columns(2, gap="large"), {}
    for side, col, colour in zip(SIDES, cols, (C.TEAL, C.AMBER)):
        with col.container(border=True):
            st.markdown(f"<span style='color:{colour};font-weight:700'>●</span> **Recording {side.upper()}**", unsafe_allow_html=True)
            got = _side(side, names, clips)
        if got:
            title, x, nyq, ref, stress = got
            s, r = C.analyze(x, nyq, cfg)
            data[side] = dict(title=title, x=x, r=r, ref=ref, colour=colour, duration=r["quality"]["duration_s"])

    if len(data) < 2:
        st.info("Choose a recording on both sides to compare.")
        return

    A, B = data["a"], data["b"]
    st.markdown("##### Side by side")
    sa, sb = _summary(A["r"], A["ref"], A["duration"]), _summary(B["r"], B["ref"], B["duration"])

    def diff(k):
        va, vb = sa[k], sb[k]
        return f"{vb - va:+g}" if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool) else ""

    rows = [dict(metric=k, a=str(sa[k]) if sa[k] is not None else "–", b=str(sb[k]) if sb[k] is not None else "–", change=diff(k)) for k in sa]
    st.dataframe(rows, hide_index=True, width="stretch", column_config={
        "metric": "", "a": f"A · {A['title']}", "b": f"B · {B['title']}", "change": "B − A"})

    st.markdown("##### Detector score, overlaid")
    fig = go.Figure()
    for side, d in data.items():
        fig.add_trace(go.Scatter(x=d["r"]["frame_t"], y=d["r"]["frame_prob"], mode="lines", name=f"{side.upper()} · {d['title']}",
                                 line=dict(color=d["colour"], width=1.6), hovertemplate="%{x:.2f} s · %{y:.2f}<extra></extra>"))
        for e in d["r"]["events"]:
            fig.add_vrect(x0=e["onset_s"], x1=e["offset_s"], fillcolor=d["colour"], opacity=0.12, line_width=0)
    fig.add_hline(y=cfg["hi"], line=dict(color=C.SLATE, dash="dash"), annotation_text=f"start {cfg['hi']:.2f}")
    xmax = max(A["duration"], B["duration"])
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(title="time (s)", range=[0, xmax]),
                      yaxis=dict(title="score", range=[0, 1]), legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, config=C.CHART_CFG, width="stretch", key="cmp_overlay")

    show_spec = st.toggle("Show spectrograms", key="cmp_spec")
    for side, d in data.items():
        shown = d["r"]["events"] or d["r"]["withheld_candidates"]
        C.verdict(d["r"]["status"], d["r"]["reason_codes"], subtitle=f"Recording {side.upper()} · {d['title']}")
        f = C.timeline(d["x"], d["r"], shown, faded=not d["r"]["events"], show_spec=show_spec, ref=d["ref"], show_ref=bool(d["ref"]),
                       hi=cfg["hi"], lo=cfg["lo"], height=480 if show_spec else 340)
        f.update_xaxes(range=[0, xmax])
        st.plotly_chart(f, config=C.CHART_CFG, width="stretch", key=f"cmp_tl_{side}")
    st.caption("Both timelines share the same time axis. Dotted green outlines are expert labels where available.")
