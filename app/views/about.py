"""Method & results page: how the pipeline works and what the experiments showed, drawn from results/."""
from __future__ import annotations
import json

import streamlit as st
import plotly.graph_objects as go

from views import common as C

LEVELS = ["clean", "20", "10", "5", "0"]


def _load(name):
    p = C.ROOT / "results" / name
    return json.loads(p.read_text()) if p.exists() else {}


def render():
    st.markdown("### How SWALLOHear works")
    steps = [
        (":material/verified_user:", "1 · Quality gate", "Estimate SNR and check clipping, dropouts, bandwidth and length. A failing recording is reported "
                                                         "**Inconclusive** and its events are withheld instead of guessed."),
        (":material/forest:", "2 · Detector", "A noise-trained Random Forest scores every 64 ms frame (16 ms hop) for how swallow-like it sounds."),
        (":material/join_inner:", "3 · Event assembly", "A higher threshold starts an event, a lower one continues it, and events close together are merged."),
        (":material/psychology:", "4 · Reliability", "A second model scores each event for how likely it is to be correct. That score, not the "
                                                    "detector's own confidence, decides the tier."),
    ]
    for col, (icon, head, body) in zip(st.columns(4), steps):
        with col.container(border=True):
            st.markdown(f"#### {icon}\n**{head}**"); st.caption(body)

    rv = _load("reliability_v2.json")
    e24, e3 = rv.get("E2_E4", {}), rv.get("E3", {})
    st.markdown("### What the experiments showed")
    st.caption("Held-out test set: 27 participants, 171 recordings, 288 labelled swallows. Thresholds were fit on training and validation participants only.")

    if e24:
        left, right = st.columns(2)
        with left:
            st.markdown("##### Noise robustness (F1)")
            fig = go.Figure()
            for name, colour in (("RF clean-trained", C.SLATE), ("RF noise-augmented", C.TEAL)):
                d = e24.get(name, {})
                fig.add_trace(go.Scatter(x=[l if l == "clean" else f"{l} dB" for l in LEVELS], y=[d.get(l, {}).get("f1") for l in LEVELS],
                                         mode="lines+markers", name=name.replace("RF ", ""), line=dict(color=colour, width=3), marker=dict(size=9),
                                         hovertemplate="%{x}: F1 %{y:.2f}<extra></extra>"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 0.6], title="F1"),
                              xaxis_title="white noise added", legend=dict(orientation="h", y=-0.25))
            st.plotly_chart(fig, config=C.CHART_CFG, width="stretch")
            st.caption("Training with noise keeps the detector working where the clean-trained one collapses.")
        with right:
            st.markdown("##### Ordinary vs reliability-aware output")
            lvl = st.segmented_control("Noise level", LEVELS, default="clean", key="about_lvl",
                                       format_func=lambda l: l if l == "clean" else f"{l} dB") or "clean"
            d = e3.get(lvl if lvl == "clean" else f"{lvl} dB", {})   # E3 is keyed "clean", "20 dB", …
            fig = go.Figure()
            for mode, colour, nm in (("ordinary", C.SLATE, "Ordinary"), ("reliability_aware", C.TEAL, "Reliability-aware")):
                m = d.get(mode, {})
                fig.add_bar(x=["Precision", "Recall", "F1"], y=[m.get("precision"), m.get("recall"), m.get("f1")], name=nm, marker_color=colour,
                            text=[f"{v:.2f}" if v is not None else "" for v in (m.get("precision"), m.get("recall"), m.get("f1"))], textposition="outside")
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 1]), barmode="group",
                              legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, config=C.CHART_CFG, width="stretch")
            if d:
                st.caption(f"Learned reliability AUROC {d.get('auroc_learned', float('nan')):.2f} vs raw detector confidence "
                           f"{d.get('auroc_mean_prob', float('nan')):.2f}. Reporting only Confident events trades recall for precision.")

    st.markdown("##### Headline numbers")
    st.markdown("""
| Finding | Number |
|---|---|
| Event detection on clean audio | F1 about 0.49 (energy baseline 0.28) |
| Raw model confidence as a guide to correctness | AUROC 0.53, barely better than chance |
| Learned reliability score | AUROC 0.79 |
| Reliability-aware output, clean audio | Precision 0.41 → 0.69, recall 0.63 → 0.33 |
| Noise-trained vs clean-trained at 10 dB | F1 0.39 vs 0.00 |
""")
    with st.expander("Limits you should hold in mind", icon=":material/warning:", expanded=True):
        st.markdown(
            "Accuracy is modest and nowhere near clinical standard. The noise tests use synthetic white noise, not real rooms. "
            "Results come from one split of one public dataset with 27 test participants. The dataset's participant groups were never "
            "verified, so no stroke-specific claim is made. Nothing here has been validated on Philippine data, phones or low-cost microphones.\n\n"
            "Full method, numbers and confidence intervals: `README.md` and `results/` in the repository.")
