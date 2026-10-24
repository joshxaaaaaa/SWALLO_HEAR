"""Analyze page: pick or record audio, see the verdict, explore events interactively, stress-test, export."""
from __future__ import annotations
import json, time, hashlib

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from scipy.signal import welch

from swallohear import io as sio, synth
from views import common as C

SWEEP_LEVELS = [None, 30, 20, 15, 10, 5, 0]
CALLS = ["Swallow", "Not swallow", "Unsure"]


# ----------------------------------------------------------------------------- input
def _source_panel(clips):
    """Draws the recording inputs in the sidebar. Returns (audio dict | None, label, reference events, note)."""
    st.markdown("#### Recording")
    options = (["Demo"] if clips else []) + ["Upload", "Record", "Synthetic"]
    icons = {"Demo": ":material/headphones:", "Upload": ":material/upload:", "Record": ":material/mic:", "Synthetic": ":material/science:"}
    if st.session_state.get("src") not in options:
        st.session_state["src"] = options[0]
    src = st.session_state["src"]
    grid = st.columns(2, gap="small")  # a 2x2 grid of equal-width buttons
    for i, o in enumerate(options):
        grid[i % 2].button(o, icon=icons[o], key=f"src_{o}", type="primary" if o == src else "secondary", width="stretch",
                           on_click=st.session_state.__setitem__, args=("src", o))

    audio, label, ref, note = None, "", [], ""
    if src == "Demo":
        names = [C.demo_name(p) for p in clips]
        if st.session_state.get("demo_pick") not in names:
            st.session_state["demo_pick"] = names[0]
        pick = st.selectbox("Clip", names, key="demo_pick",
                            format_func=lambda n: n.replace("_noisy", " · noisy ").replace("dB", " dB"))
        path = clips[names.index(pick)]
        audio, label = sio.load_audio(str(path)), pick
        meta = C.demo_meta(path); ref, note = meta.get("reference_events_s", []), meta.get("note", "")
        st.caption(f"{note.capitalize() + ' · ' if note else ''}{len(ref)} expert-labelled swallow{'s' * (len(ref) != 1)} · Khalifa et al. (2021), CC BY 4.0")
    elif src == "Upload":
        f = st.file_uploader("WAV or FLAC, up to 120 s", type=["wav", "flac"], key="upl")
        if f is not None:
            try:
                audio, label = sio.load_audio(f.getvalue()), f.name
            except Exception as exc:
                st.error(f"Could not read this file: {exc}")
        st.caption("Do not upload identifiable patient audio to a shared instance.")
    elif src == "Record":
        rec = st.audio_input("Record from your microphone", key="mic")
        st.caption("Rest the microphone lightly against the side of the throat, stay quiet, then swallow a few times.")
        if rec is not None:
            try:
                audio, label = sio.load_audio(rec.getvalue()), f"microphone_{time.strftime('%H%M%S')}"
            except Exception as exc:
                st.error(f"Could not read the recording: {exc}")
    else:
        n_ev = st.slider("Swallow-like bursts", 1, 10, key="syn_n")
        dur = st.slider("Length (s)", 10, 60, step=5, key="syn_dur")
        seed = st.number_input("Random seed", 0, 9999, step=1, key="syn_seed")
        sig, ev = synth.make_recording(duration_s=float(dur), n_events=n_ev, snr_db=20.0, seed=int(seed))
        audio = dict(signal=sig, fs=C.FS, orig_nyquist=2000.0, duration_s=len(sig) / C.FS)
        label, ref, note = f"synthetic_seed{int(seed)}", ev, "synthetic signal for smoke-testing, not clinical data"
        st.caption("Generated bursts are the reference labels.")
    return audio, label, ref, note


def _stress_panel():
    with st.expander("Stress test", icon=":material/tune:", expanded=bool(st.session_state.get("noise_on") or st.session_state.get("clip_on"))):
        noise_on = st.toggle("Add noise", key="noise_on", help="Mixes noise into the recording and re-runs the analysis.")
        kind = st.segmented_control("Noise type", C.NOISE_KINDS, key="noise_kind", disabled=not noise_on) or C.NOISE_KINDS[0]
        snr = st.slider("Noise level (SNR)", -5, 30, step=1, key="noise_snr", disabled=not noise_on, format="%d dB",
                        help="Lower means louder noise, relative to the whole recording's RMS.")
        clip_on = st.toggle("Simulate clipping", key="clip_on", help="Boosts the input 4× and hard-clips it, like a mic gain set too high.")
    return (kind, snr) if noise_on else None, clip_on


# ----------------------------------------------------------------------------- state helpers
def _note_key(label, e):
    return f"{label}|{e['onset_s']:.2f}"


def _store_call(nk, wk):
    notes = st.session_state.setdefault("notes", {})
    if st.session_state.get(wk):
        notes[nk] = st.session_state[wk]
    else:
        notes.pop(nk, None)


def _step(delta, n):
    st.session_state["sel_event"] = (st.session_state.get("sel_event", 0) + delta) % n


def _consume_click(key, picked):
    """Apply a chart/table selection only when it changed, so other controls can still move the selection.
    Reruns when the selected event changes, so every view drawn earlier in this run picks it up."""
    tok = tuple(picked)
    if tok != st.session_state.get(f"_last_{key}"):
        st.session_state[f"_last_{key}"] = tok
        if tok and tok[0] != st.session_state.get("sel_event"):
            st.session_state["sel_event"] = tok[0]; st.rerun()


# ----------------------------------------------------------------------------- sections
def _empty_state():
    st.markdown("### Analyse a recording")
    st.write("Pick a source in the sidebar to get started. Demo clips come from held-out test participants and carry expert labels.")
    cols = st.columns(3)
    for col, (icon, head, body) in zip(cols, [
        (":material/graphic_eq:", "See every event", "Waveform, spectrogram and detector score on one zoomable timeline. Click an event to inspect it."),
        (":material/tune:", "Tune and stress-test", "Move the detector thresholds live, add white, pink or mains-hum noise, and watch the quality gate react."),
        (":material/fact_check:", "Check and export", "Compare with expert labels, record your own call on each event, and download everything."),
    ]):
        with col.container(border=True):
            st.markdown(f"#### {icon} {head}"); st.caption(body)


def _metrics(r, shown, q, cfg):
    n_conf = sum(e["tier"] == "Confident" for e in r["events"])
    n_low = len(r["events"]) - n_conf
    rate = len(shown) / max(q["duration_s"] / 60.0, 1e-9)
    c = st.columns(5)
    c[0].metric("Confident events", n_conf, help="Reliability score at or above the threshold.", border=True)
    c[1].metric("Low-confidence", n_low, help="Detected, but the reliability model does not trust them.", border=True)
    c[2].metric("Event rate", f"{rate:.1f}/min", help="Detected events per minute of audio (withheld candidates included).", border=True)
    c[3].metric("Estimated SNR", f"{q['snr_db']:.1f} dB", f"{q['snr_db'] - cfg['snr_min']:+.1f} dB vs gate",
                help=f"The quality gate needs at least {cfg['snr_min']:.1f} dB.", border=True)
    c[4].metric("Processing time", f"{r['latency_s']:.2f} s", help=f"Time to analyse {q['duration_s']:.1f} s of audio on this machine.", border=True)


def _timeline_tab(x, r, shown, faded, ref, label, sig, cfg):
    a, b, c = st.columns([1, 1, 2])
    show_spec = a.toggle("Spectrogram", key="spec_on")
    show_ref = b.toggle("Expert labels", value=bool(ref), key="ref_on", disabled=not ref)
    if faded and shown:
        c.caption("Result withheld: candidates are shown faded for inspection only.")
    sel = st.session_state.get("sel_event", 0) if shown else None

    fig = C.timeline(x, r, shown, faded=faded, show_spec=show_spec, ref=ref, show_ref=show_ref and bool(ref),
                     selected=sel, hi=cfg["hi"], lo=cfg["lo"])
    fig.update_layout(uirevision=sig)
    key = "tl_" + hashlib.md5(f"{sig}|{json.dumps(cfg)}|{show_spec}".encode()).hexdigest()[:10]
    ev = st.plotly_chart(fig, key=key, on_select="rerun", selection_mode=("points",), config=C.CHART_CFG, width="stretch")
    last = len(fig.data) - 1
    picked = [p["point_index"] for p in (ev.selection.points if ev else []) if p.get("curve_number") == last] if shown else []
    _consume_click(key, picked)

    st.caption("Teal = Confident, amber = Low-confidence"
               + (", dotted green = expert labels" if show_ref and ref else "")
               + ". Drag to zoom, double-click to reset, click a numbered marker to inspect that event.")
    st.audio(C.wav(x), format="audio/wav")
    if shown:
        _event_card(x, r, shown, label, cfg)


def _event_card(x, r, shown, label, cfg):
    n = len(shown); i = min(st.session_state.get("sel_event", 0), n - 1); st.session_state["sel_event"] = i
    e = shown[i]
    with st.container(border=True):
        h1, h2, h3 = st.columns([0.12, 0.76, 0.12], vertical_alignment="center")
        h1.button("Prev", icon=":material/chevron_left:", on_click=_step, args=(-1, n), key="ev_prev", disabled=n < 2, width="stretch")
        h2.markdown(f"<div style='text-align:center'><b>Event {i + 1} of {n}</b> &nbsp;·&nbsp; "
                    f"{e['onset_s']:.2f}–{e['offset_s']:.2f} s &nbsp;·&nbsp; {e['duration_ms']:.0f} ms</div>", unsafe_allow_html=True)
        h3.button("Next", icon=":material/chevron_right:", on_click=_step, args=(1, n), key="ev_next", disabled=n < 2, width="stretch")

        c1, c2, c3 = st.columns([1.25, 1, 1.5])
        with c1:
            C.tier_badge(e["tier"])
            st.audio(C.wav(x, e["onset_s"], e["offset_s"]), format="audio/wav")
            st.caption("Clip includes 0.25 s either side of the event.")
            nk = _note_key(label, e); wk = f"call_{nk}"
            st.segmented_control("Your call", CALLS, key=wk, default=st.session_state.get("notes", {}).get(nk),
                                 on_change=_store_call, args=(nk, wk))
        with c2:
            st.plotly_chart(C.gauge(e["reliability"], cfg["tau"], e["tier"]), config={"displayModeBar": False},
                            width="stretch", key=f"g_{i}_{e['onset_s']:.2f}")
            st.caption(f"Reliability score. The marker is the threshold ({cfg['tau']:.2f}). Raw detector confidence: {e['model_confidence']:.2f}.")
            up, down = C.top_reasons(C.explain(e["features"]))
            if up or down:
                st.markdown((f":green[:material/arrow_upward:] {', '.join(up)}  \n" if up else "")
                            + (f":orange[:material/arrow_downward:] {', '.join(down)}" if down else ""),
                            help="What pushed this event's reliability score up or down most. Full breakdown on the Events tab.")
        with c3:
            st.plotly_chart(C.event_zoom(x, r, e), config={"displayModeBar": False}, width="stretch", key=f"z_{i}_{e['onset_s']:.2f}")


def _events_tab(shown, faded, label, sig, cfg, payload):
    if not shown:
        st.info("No events to list for this recording.")
        return
    if faded:
        st.warning("These candidates were withheld because the recording failed the quality gate. They are shown for inspection only.")
    notes = st.session_state.get("notes", {})
    rows = [{"#": i + 1, "onset_s": round(e["onset_s"], 2), "offset_s": round(e["offset_s"], 2), "duration_ms": round(e["duration_ms"]),
             "reliability": round(e["reliability"], 3), "model_confidence": round(e["model_confidence"], 3), "tier": e["tier"],
             "your_call": notes.get(_note_key(label, e), "")} for i, e in enumerate(shown)]
    key = "tbl_" + hashlib.md5(f"{sig}|{json.dumps(cfg)}".encode()).hexdigest()[:10]
    ev = st.dataframe(rows, key=key, on_select="rerun", selection_mode="single-row", hide_index=True, width="stretch",
                      column_config={
                          "#": st.column_config.NumberColumn(width="small"),
                          "onset_s": st.column_config.NumberColumn("Onset (s)", format="%.2f"),
                          "offset_s": st.column_config.NumberColumn("Offset (s)", format="%.2f"),
                          "duration_ms": st.column_config.NumberColumn("Duration (ms)"),
                          "reliability": st.column_config.ProgressColumn("Reliability", min_value=0.0, max_value=1.0, format="%.2f"),
                          "model_confidence": st.column_config.NumberColumn("Raw confidence", format="%.2f",
                                                                             help="The detector's own score. A poor guide to correctness (AUROC 0.53)."),
                          "tier": "Tier", "your_call": "Your call"})
    _consume_click(key, ev.selection.rows if ev else [])
    st.caption("Select a row to make it the inspected event on the Timeline tab and below.")

    i = min(st.session_state.get("sel_event", 0), len(shown) - 1); e = shown[i]
    ex = C.explain(e["features"])
    st.markdown(f"##### Why event {i + 1} scored {e['reliability']:.2f}")
    if ex:
        left, right = st.columns([1.35, 1])
        with left:
            st.plotly_chart(C.explain_fig(ex, cfg["tau"]), config={"displayModeBar": False}, width="stretch", key=f"why_{key}_{i}")
        with right:
            exp_rows = [dict(measurement=name, value=fmt.format(v), typical=fmt.format(t), effect=round(c, 2))
                        for (name, _h, fmt), v, t, c in zip(C.FEATURES, e["features"], ex["typical"], ex["contrib"])]
            st.dataframe(sorted(exp_rows, key=lambda d: -abs(d["effect"])), hide_index=True, width="stretch", column_config={
                "measurement": "Measurement", "value": "This event", "typical": "Typical event",
                "effect": st.column_config.NumberColumn("Effect", format="%+.2f", help="Push on the score in log-odds: positive = more reliable.")})
            up, down = C.top_reasons(ex)
            st.caption("The reliability model starts from an average event and adds or subtracts evidence for each measurement. "
                       + (f"Here **{up[0].lower()}** helped most" if up else "Nothing pushed it up much")
                       + (f" and **{down[0].lower()}** hurt most." if down else "."))
    else:
        st.info("The reliability model's structure is not a scaler + logistic regression, so it can't be broken down exactly.")

    with st.expander("Raw detector confidence vs reliability", icon=":material/scatter_plot:"):
        fig = go.Figure(go.Scatter(
            x=[s["model_confidence"] for s in shown], y=[s["reliability"] for s in shown], mode="markers+text",
            text=[str(k + 1) for k in range(len(shown))], textposition="top center",
            marker=dict(size=[16 if k == i else 11 for k in range(len(shown))], color=[C.TIER_COLOR[s["tier"]] for s in shown],
                        line=dict(width=1, color="white")),
            hovertemplate="event %{text}<br>raw %{x:.2f} · reliability %{y:.2f}<extra></extra>"))
        fig.add_hline(y=cfg["tau"], line=dict(dash="dash", color=C.SLATE), annotation_text=f"threshold {cfg['tau']:.2f}")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="raw detector confidence",
                          yaxis_title="reliability", yaxis_range=[0, 1.05])
        st.plotly_chart(fig, config={"displayModeBar": False}, width="stretch", key=f"scatter_{key}")
        st.caption("The tier comes from the separately trained reliability model, not from the detector's own confidence.")

    st.divider()
    d1, d2, d3 = st.columns(3)
    cols = ["#", "onset_s", "offset_s", "duration_ms", "reliability", "model_confidence", "tier", "your_call"]
    d1.download_button("Events (CSV)", C.to_csv(rows, cols), f"{label}_events.csv", "text/csv", icon=":material/download:", width="stretch")
    d2.download_button("Full result (JSON)", json.dumps(payload, indent=1), f"{label}_swallohear.json", "application/json",
                       icon=":material/data_object:", width="stretch")
    ann = [r_ for r_ in rows if r_["your_call"]]
    d3.download_button(f"My annotations ({len(ann)})", C.to_csv(ann, cols), f"{label}_annotations.csv", "text/csv",
                       icon=":material/rate_review:", width="stretch", disabled=not ann)


def _rhythm_tab(shown, faded, duration):
    if len(shown) < 2:
        st.info("Rhythm needs at least two events. Try a longer recording, or the Synthetic source with 60 s and 8–10 bursts.")
        return
    if faded:
        st.warning("The result was withheld; rhythm below uses the withheld candidates.")
    only_conf = st.toggle("Confident events only", key="rh_conf")
    evs = [e for e in shown if e["tier"] == "Confident"] if only_conf else shown
    rh = C.rhythm(evs, duration)
    c = st.columns(5)
    c[0].metric("Events", rh["n"], border=True)
    c[1].metric("Rate", f"{rh['rate']:.1f}/min", border=True)
    c[2].metric("Mean interval", f"{rh['mean_iei']:.1f} s" if rh["mean_iei"] is not None else "–",
                help="Average time from one event's onset to the next.", border=True)
    c[3].metric("Regularity", (rh["regularity"] or "–").capitalize(),
                f"CV {rh['cv']:.2f}" if rh["cv"] is not None else None, delta_color="off",
                help="Spread of the intervals (coefficient of variation): under 0.25 steady, 0.25–0.5 moderate, over 0.5 irregular.", border=True)
    c[4].metric("Longest quiet gap", f"{rh['longest_gap']:.1f} s", help="Longest stretch with no event, including the start and end.", border=True)
    cum, bars = C.rhythm_figs(evs if len(evs) >= 2 else shown, duration)
    a, b = st.columns(2)
    with a:
        st.markdown("##### Events over time")
        st.plotly_chart(cum, config=C.CHART_CFG, width="stretch", key="rh_cum")
        st.caption("A steady slope means steady swallowing; flat stretches are pauses.")
    with b:
        st.markdown("##### Time between consecutive events")
        st.plotly_chart(bars, config=C.CHART_CFG, width="stretch", key="rh_bars")
        st.caption("Similar bar heights mean a regular rhythm.")
    st.caption("Rhythm is descriptive only. Short clips give few intervals, and missed or false detections distort these numbers.")


def _robustness_tab(x0, nyq, ref, base_sig, cfg):
    st.markdown("##### How does this recording hold up as noise gets louder?")
    st.caption("Re-runs the full analysis at several noise levels on the original recording (any stress-test settings in the sidebar are ignored here).")
    a, b = st.columns([2, 1], vertical_alignment="bottom")
    kind = a.segmented_control("Noise type", C.NOISE_KINDS, key="sweep_kind") or C.NOISE_KINDS[0]
    skey = f"{base_sig}|{kind}|{json.dumps(cfg)}"
    store = st.session_state.setdefault("sweeps", {})
    if b.button("Run sweep", icon=":material/play_arrow:", type="primary", width="stretch"):
        out = []
        bar = st.progress(0.0, text="Analysing…")
        for k, lvl in enumerate(SWEEP_LEVELS):
            xs = x0 if lvl is None else C.add_noise(x0, lvl, kind)
            _, rr = C.analyze(xs, nyq, cfg)
            shown = rr["events"] or rr["withheld_candidates"]
            f1 = C.match(shown, ref)[0]["f1"] if ref and rr["events"] else (0.0 if ref else None)
            out.append(dict(level="clean" if lvl is None else f"{lvl} dB", status=rr["status"],
                            confident=sum(e["tier"] == "Confident" for e in rr["events"]),
                            low=sum(e["tier"] == "Low-confidence" for e in rr["events"]),
                            withheld=len(rr["withheld_candidates"]), est_snr=round(rr["quality"]["snr_db"], 1), f1=f1))
            bar.progress((k + 1) / len(SWEEP_LEVELS), text=f"Analysing… {out[-1]['level']}")
        bar.empty(); store[skey] = out
    out = store.get(skey)
    if not out:
        st.info("Press **Run sweep** to analyse the recording at 7 noise levels.")
        return

    lv = [o["level"] for o in out]
    fig = go.Figure()
    fig.add_bar(x=lv, y=[o["confident"] for o in out], name="Confident", marker_color=C.TEAL)
    fig.add_bar(x=lv, y=[o["low"] for o in out], name="Low-confidence", marker_color=C.AMBER)
    fig.add_bar(x=lv, y=[o["withheld"] for o in out], name="Withheld", marker_color="rgba(122,138,148,.45)")
    fig.add_trace(go.Scatter(x=lv, y=[o["est_snr"] for o in out], name="Estimated SNR", yaxis="y2", mode="lines+markers",
                             line=dict(color=C.ink(), width=2)))
    fig.add_trace(go.Scatter(x=lv, y=[cfg["snr_min"]] * len(lv), name="Quality gate", yaxis="y2", mode="lines",
                             line=dict(color=C.RED, dash="dash")))
    fig.update_layout(barmode="stack", height=360, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="added noise",
                      yaxis_title="events", yaxis2=dict(title="estimated SNR (dB)", overlaying="y", side="right", showgrid=False),
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, config=C.CHART_CFG, width="stretch", key=f"sweep_{hashlib.md5(skey.encode()).hexdigest()[:8]}")
    st.dataframe(out, hide_index=True, width="stretch", column_config={
        "level": "Noise", "status": "Status", "confident": "Confident", "low": "Low-conf.", "withheld": "Withheld",
        "est_snr": st.column_config.NumberColumn("Est. SNR (dB)", format="%.1f"),
        "f1": st.column_config.ProgressColumn("F1 vs expert", min_value=0.0, max_value=1.0, format="%.2f")})
    st.caption("Once the estimated SNR drops below the gate the system withholds its result instead of reporting events it cannot trust.")


def _quality_tab(xr, s, q, nyq, cfg, stress_note):
    checks = C.quality_checks(q, nyq, cfg["snr_min"])
    left, right = st.columns([1, 1.3])
    with left:
        st.markdown("##### Quality gate")
        for name, val, lim, ok in checks:
            with st.container(border=True):
                a, b, c = st.columns([0.12, 0.55, 0.33], vertical_alignment="center")
                a.markdown(":green[:material/check_circle:]" if ok else ":red[:material/error:]")
                b.markdown(f"**{name}**  \n<small>limit {lim}</small>", unsafe_allow_html=True)
                c.markdown(f"<div style='text-align:right;font-weight:600;color:{C.TEAL if ok else C.RED}'>{val}</div>", unsafe_allow_html=True)
        if stress_note:
            st.info(f"Stress test active: {stress_note}. This approximates, but does not exactly reproduce, the noise protocol in the reported experiments.")
    with right:
        st.markdown("##### How SNR is estimated")
        e = np.asarray(s["e"]); floor, peak = float(np.percentile(e, 10)), float(np.percentile(e, 95))
        fig = go.Figure(go.Histogram(x=e, nbinsx=60, marker_color="rgba(122,138,148,.6)", hovertemplate="%{x:.0f} dB · %{y} frames<extra></extra>"))
        fig.add_vline(x=floor, line=dict(color=C.AMBER, width=2), annotation_text="noise floor (10th pct)")
        fig.add_vline(x=peak, line=dict(color=C.TEAL, width=2), annotation_text="peaks (95th pct)", annotation_position="top left")
        fig.update_layout(height=230, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="frame energy (dB)", yaxis_title="frames", bargap=0.05)
        st.plotly_chart(fig, config={"displayModeBar": False}, width="stretch", key="q_hist")
        st.caption(f"SNR = peaks − floor = {peak - floor:.1f} dB. The {cfg['snr_min']:.1f} dB gate is roughly the worst clean recording seen in validation.")
        f, P = welch(xr, fs=C.FS, nperseg=min(1024, len(xr)))
        fig2 = go.Figure(go.Scatter(x=f, y=10 * np.log10(P + 1e-15), mode="lines", line=dict(color=C.ink(), width=1.4),
                                    hovertemplate="%{x:.0f} Hz · %{y:.0f} dB<extra></extra>"))
        fig2.add_vrect(x0=20, x1=1800, fillcolor=C.TEAL, opacity=0.07, line_width=0, annotation_text="analysis band", annotation_position="top left")
        fig2.update_layout(height=210, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="frequency (Hz)", yaxis_title="power (dB)")
        st.plotly_chart(fig2, config={"displayModeBar": False}, width="stretch", key="q_psd")
        st.caption("Average spectrum. Sharp spikes at 60, 120, 180 Hz point to mains hum; a raised flat line points to broadband hiss.")


def _expert_tab(shown, faded, ref, duration):
    if not ref:
        st.info("This recording has no expert reference labels, so agreement cannot be scored. Demo clips and synthetic signals carry labels.")
        return
    s, pairs, matched_ref = C.match(shown, ref)
    if faded:
        st.warning("The result was withheld; the comparison below uses the withheld candidates.")
    c = st.columns(6)
    for col, (k, v, h) in zip(c, [("Matched", s["tp"], "Detected and overlapping a label by at least half."),
                                  ("False detections", s["fp"], "Detected, but no label there."),
                                  ("Missed", s["fn"], "Labelled, but not detected."),
                                  ("Precision", f"{s['precision']:.2f}", None), ("Recall", f"{s['recall']:.2f}", None),
                                  ("F1", f"{s['f1']:.2f}", None)]):
        col.metric(k, v, help=h, border=True)
    st.plotly_chart(C.lanes(shown, ref, pairs, matched_ref, duration), config=C.CHART_CFG, width="stretch", key="lanes")
    st.caption("Green = matched, red = unmatched (a false detection in the System lane, a miss in the Expert lane).")
    if s["onset_err"]:
        st.caption(f"Median onset error {np.median(s['onset_err']) * 1000:+.0f} ms · median offset error "
                   f"{np.median(s['offset_err']) * 1000:+.0f} ms. Negative means the system fired early.")
    st.caption("**One clip proves nothing.** Across the 27 held-out test participants the system scores F1 around 0.49, "
               "and some 'false detections' are likely real swallows the dataset never labelled.")


def _session_tab():
    hist = st.session_state.get("history", [])
    if not hist:
        st.info("Analyses you run in this session will be listed here.")
        return
    st.markdown(f"##### {len(hist)} analys{'is' if len(hist) == 1 else 'es'} this session")
    st.dataframe(list(reversed(hist)), hide_index=True, width="stretch", column_config={
        "time": "Time", "recording": "Recording", "stress": "Stress test", "status": "Status", "confident": "Confident",
        "low": "Low-conf.", "snr_db": st.column_config.NumberColumn("SNR (dB)", format="%.1f"), "settings": "Settings"})
    a, b, c = st.columns(3)
    a.download_button("Session log (CSV)", C.to_csv(hist, list(hist[0])), "swallohear_session.csv", "text/csv",
                      icon=":material/download:", width="stretch")
    notes = st.session_state.get("notes", {})
    b.download_button(f"All annotations ({len(notes)})",
                      C.to_csv([{"recording": k.split("|")[0], "onset_s": k.split("|")[1], "your_call": v} for k, v in notes.items()],
                               ["recording", "onset_s", "your_call"]),
                      "swallohear_annotations.csv", "text/csv", icon=":material/rate_review:", width="stretch", disabled=not notes)
    if c.button("Clear session", icon=":material/delete_sweep:", width="stretch"):
        st.session_state["history"] = []; st.session_state["notes"] = {}; st.rerun()


# ----------------------------------------------------------------------------- page
def render():
    A = C.load_analyzer()
    clips = C.demo_clips()
    with C.sidebar_top:
        audio, label, ref, note = _source_panel(clips)
        stress, clip_on = _stress_panel()

    if audio is None:
        _empty_state()
        return

    x0 = np.asarray(audio["signal"], dtype=np.float32)
    nyq = float(audio.get("orig_nyquist", 2000.0))
    x, parts = x0, []
    if stress:
        x = C.add_noise(x, stress[1], stress[0]); parts.append(f"{stress[0].lower()} noise at {stress[1]} dB")
    if clip_on:
        x = C.add_clipping(x); parts.append("clipping")
    stress_note = " + ".join(parts)

    cfg = C.current_settings()
    with st.spinner("Analysing…"):
        s, r = C.analyze(x, nyq, cfg)
    q = r["quality"]
    shown, faded = (r["events"] or r["withheld_candidates"]), not r["events"]

    base_sig = f"{label}|{len(x0)}|{float(np.sum(np.abs(x0[::97]))):.4f}"
    sig = f"{base_sig}|{stress_note}"
    if st.session_state.get("_sig") != sig:
        st.session_state["_sig"] = sig; st.session_state["sel_event"] = 0
    if shown:
        st.session_state["sel_event"] = min(st.session_state.get("sel_event", 0), len(shown) - 1)

    changed = C.settings_changed(A)
    hist = st.session_state.setdefault("history", [])
    hkey = f"{sig}|{json.dumps(cfg)}"
    if st.session_state.get("_hkey") != hkey:
        st.session_state["_hkey"] = hkey
        hist.append(dict(time=time.strftime("%H:%M:%S"), recording=label, stress=stress_note or "none", status=r["status"],
                         confident=sum(e["tier"] == "Confident" for e in r["events"]),
                         low=sum(e["tier"] == "Low-confidence" for e in r["events"]), snr_db=round(q["snr_db"], 1),
                         settings="custom: " + ", ".join(changed) if changed else "validated"))

    # header
    h1, h2, h3 = st.columns([2.4, 2, 1], vertical_alignment="bottom")
    h1.markdown(f"### {label}")
    with h2:
        st.markdown(" ".join([f":gray-badge[:material/timer: {q['duration_s']:.1f} s]",
                              f":gray-badge[:material/graphic_eq: {audio.get('orig_fs', 4000) / 1000:.1f} kHz source]"]
                             + ([f":orange-badge[:material/bolt: {stress_note}]"] if stress_note else [])
                             + ([f":violet-badge[:material/tune: custom settings]"] if changed else [])))
    # Everything the report needs is captured now: the callable runs on a background thread without Streamlit context.
    rep = dict(label=label, r=r, x=x, nyq=nyq, cfg=cfg, changed=changed, stress=stress_note, ref=ref,
               notes=dict(st.session_state.get("notes", {})), explanations=[C.explain(e["features"]) for e in shown])
    h3.download_button("Report", lambda: C.build_report(**rep), f"{label}_report.html", "text/html", icon=":material/description:",
                       help="Printable HTML report: verdict, timeline, events with reasons, rhythm, quality and limits. "
                            "Open it and press Ctrl+P to save as PDF.", width="stretch", on_click="ignore")
    C.verdict(r["status"], r["reason_codes"], subtitle=f"Note: {note}" if note else "")
    _metrics(r, shown, q, cfg)
    st.write("")

    payload = dict(input=label, status=r["status"], reason_codes=r["reason_codes"], settings=cfg, stress_test=stress_note or None,
                   events=r["events"], withheld_candidates=r["withheld_candidates"], quality=q,
                   annotations={k: v for k, v in st.session_state.get("notes", {}).items() if k.startswith(label + "|")})
    tabs = st.tabs([":material/timeline: Timeline", f":material/list: Events ({len(shown)})", ":material/monitor_heart: Rhythm",
                    ":material/waves: Robustness lab", ":material/verified_user: Signal quality", ":material/fact_check: Expert comparison",
                    ":material/history: Session"])
    with tabs[0]:
        _timeline_tab(x, r, shown, faded, ref, label, sig, cfg)
    with tabs[1]:
        _events_tab(shown, faded, label, sig, cfg, payload)
    with tabs[2]:
        _rhythm_tab(shown, faded, q["duration_s"])
    with tabs[3]:
        _robustness_tab(x0, nyq, ref, base_sig, cfg)
    with tabs[4]:
        _quality_tab(x, s, q, nyq, cfg, stress_note)
    with tabs[5]:
        _expert_tab(shown, faded, ref, q["duration_s"])
    with tabs[6]:
        _session_tab()
