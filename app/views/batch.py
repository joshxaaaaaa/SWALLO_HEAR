"""Batch page: run many recordings at once with the current detector settings and compare them."""
from __future__ import annotations
import json

import numpy as np
import streamlit as st
import plotly.graph_objects as go

from swallohear import io as sio
from views import common as C


def render():
    st.markdown("### Batch analysis")
    st.caption("Analyse several recordings in one go with the detector settings from the sidebar, then compare them side by side.")
    clips = C.demo_clips()
    names = [C.demo_name(p) for p in clips]

    with st.container(border=True):
        a, b = st.columns(2)
        picked = a.multiselect("Demo clips", names, default=names, key="batch_demos")
        files = b.file_uploader("Add your own (WAV or FLAC)", type=["wav", "flac"], accept_multiple_files=True, key="batch_files")
        c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
        noise_on = c1.toggle("Add noise to every file", key="batch_noise_on")
        kind = c2.selectbox("Noise type", C.NOISE_KINDS, key="batch_kind", disabled=not noise_on)
        snr = c3.slider("SNR", -5, 30, 10, key="batch_snr", disabled=not noise_on, format="%d dB")
        go_ = st.button(f"Analyse {len(picked) + len(files or [])} recordings", type="primary", icon=":material/play_arrow:",
                        disabled=not (picked or files))

    cfg = C.current_settings()
    if go_:
        jobs = [(n, lambda p=clips[names.index(n)]: sio.load_audio(str(p)), C.demo_meta(clips[names.index(n)]).get("reference_events_s", []))
                for n in picked]
        jobs += [(f.name, lambda f=f: sio.load_audio(f.getvalue()), []) for f in files or []]
        rows, bar = [], st.progress(0.0, text="Starting…")
        for k, (name, load, ref) in enumerate(jobs):
            bar.progress(k / len(jobs), text=f"Analysing {name}…")
            try:
                audio = load(); x = np.asarray(audio["signal"], dtype=np.float32)
                if noise_on:
                    x = C.add_noise(x, snr, kind)
                _, r = C.analyze(x, float(audio.get("orig_nyquist", 2000.0)), cfg)
            except Exception as exc:
                rows.append(dict(recording=name, status=f"error: {exc}")); continue
            ev, q = r["events"], r["quality"]
            rel = [e["reliability"] for e in ev]
            sc = C.match(ev, ref)[0] if ref else None
            rows.append(dict(recording=name, status=r["status"], reasons=", ".join(r["reason_codes"]), duration_s=round(q["duration_s"], 1),
                             snr_db=round(q["snr_db"], 1), confident=sum(e["tier"] == "Confident" for e in ev),
                             low=sum(e["tier"] == "Low-confidence" for e in ev), mean_reliability=round(float(np.mean(rel)), 3) if rel else None,
                             per_min=round(len(ev) / max(q["duration_s"] / 60, 1e-9), 1), labels=len(ref) if ref else None,
                             f1=round(sc["f1"], 3) if sc else None))
        bar.empty()
        st.session_state["batch_rows"] = dict(rows=rows, cfg=cfg, noise=f"{kind} @ {snr} dB" if noise_on else "none")

    res = st.session_state.get("batch_rows")
    if not res:
        st.info("Choose recordings above and press **Analyse**.")
        return
    rows = res["rows"]
    if res["cfg"] != cfg:
        st.warning("Detector settings changed since this batch ran. Press **Analyse** again to refresh.", icon=":material/sync_problem:")

    ok = [r for r in rows if r.get("status") in C.STATUS]
    m = st.columns(4)
    m[0].metric("Recordings", len(rows), border=True)
    m[1].metric("Withheld", sum(r["status"] == "Inconclusive" for r in ok), border=True)
    m[2].metric("Confident events", sum(r["confident"] for r in ok), border=True)
    f1s = [r["f1"] for r in ok if r.get("f1") is not None]
    m[3].metric("Mean F1 vs expert", f"{np.mean(f1s):.2f}" if f1s else "–", help="Only recordings with expert labels.", border=True)

    st.dataframe(rows, hide_index=True, width="stretch", column_config={
        "recording": "Recording", "status": "Status", "reasons": "Reason codes", "duration_s": "Length (s)",
        "snr_db": st.column_config.NumberColumn("SNR (dB)", format="%.1f"), "confident": "Confident", "low": "Low-conf.",
        "mean_reliability": st.column_config.ProgressColumn("Mean reliability", min_value=0.0, max_value=1.0, format="%.2f"),
        "per_min": "Events/min", "labels": "Expert labels",
        "f1": st.column_config.ProgressColumn("F1 vs expert", min_value=0.0, max_value=1.0, format="%.2f")})

    if ok:
        fig = go.Figure()
        for status, (colour, *_rest) in C.STATUS.items():
            sub = [r for r in ok if r["status"] == status]
            if sub:
                fig.add_trace(go.Scatter(x=[r["snr_db"] for r in sub], y=[r["confident"] + r["low"] for r in sub], mode="markers+text",
                                         text=[r["recording"] for r in sub], textposition="top center", name=status,
                                         marker=dict(size=14, color=colour, line=dict(width=1, color="white")),
                                         hovertemplate="%{text}<br>SNR %{x:.1f} dB · %{y} events<extra></extra>"))
        fig.add_vline(x=cfg["snr_min"], line=dict(color=C.RED, dash="dash"), annotation_text="quality gate")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="estimated SNR (dB)", yaxis_title="events reported",
                          legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, config=C.CHART_CFG, width="stretch")

    cols = ["recording", "status", "reasons", "duration_s", "snr_db", "confident", "low", "mean_reliability", "per_min", "labels", "f1"]
    a, b = st.columns(2)
    a.download_button("Batch results (CSV)", C.to_csv(rows, cols), "swallohear_batch.csv", "text/csv", icon=":material/download:", width="stretch")
    b.download_button("Batch results (JSON)", json.dumps(res, indent=1), "swallohear_batch.json", "application/json",
                      icon=":material/data_object:", width="stretch")
