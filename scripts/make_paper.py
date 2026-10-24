"""Build the research paper's figures and PDF.

    python scripts/make_paper.py figures   # results/*.json -> docs/paper/figures/*.png
    python scripts/make_paper.py pdf       # docs/SWALLOHear_Research_Paper.md -> docs/SWALLOHear_Research_Paper.pdf

Dev-only tools (not in requirements.txt): pip install playwright markdown   (uses the installed Microsoft Edge).
Every number in the figures is read from the results files written by the experiment scripts.
"""
import json, pathlib, sys

import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "results"; FIG = ROOT / "docs" / "paper" / "figures"
PAPER_MD = ROOT / "docs" / "SWALLOHear_Research_Paper.md"; PAPER_PDF = PAPER_MD.with_suffix(".pdf")
TEAL, AMBER, SLATE, RED, GREEN, INK = "#1B7F7A", "#E0A458", "#7A8A94", "#C8553D", "#2E9E6B", "#244668"
LEVELS = ["clean", "20", "10", "5", "0"]


def load(name):
    return json.loads((RES / name).read_text())


def style(fig, title, h=420, w=900):
    fig.update_layout(template="plotly_white", width=w, height=h, title=dict(text=title, x=0.01, font=dict(size=17)),
                      font=dict(family="Segoe UI, Arial, sans-serif", size=13, color="#1f2a30"), margin=dict(l=70, r=30, t=70, b=60),
                      legend=dict(orientation="h", y=-0.18, x=0))
    return fig


def err(ci, point):
    return dict(type="data", symmetric=False, array=[ci[1] - point], arrayminus=[point - ci[0]], color="#444", thickness=1.2, width=5)


def figures():
    ex, rv, bs, bl = load("experiments.json"), load("reliability_v2.json"), load("bootstrap.json"), load("baselines.json")
    e24, e3 = rv["E2_E4"], rv["E3"]
    bkey = {"clean": "clean", "20": "20dB", "10": "10dB", "5": "5dB"}
    figs = {}

    # Fig 3: detectors on clean audio
    m0, m1 = bl["M0 energy"]["IoU0.5"], bl["M1 RandomForest"]["IoU0.5"]; aug = e24["RF noise-augmented"]["clean"]
    fig = go.Figure()
    for name, d, c in (("Energy baseline (M0)", m0, SLATE), ("Random Forest, clean-trained (M1)", m1, INK), ("Random Forest, noise-augmented (final)", aug, TEAL)):
        fig.add_bar(name=name, x=["Precision", "Recall", "F1"], y=[d["precision"], d["recall"], d["f1"]], marker_color=c,
                    text=[f"{v:.2f}" for v in (d["precision"], d["recall"], d["f1"])], textposition="outside")
    fig.update_yaxes(range=[0, 0.85], title="score (IoU ≥ 0.5)")
    figs["fig3_detectors"] = style(fig, "Figure 3. Event detection on clean audio, 27 held-out test participants")

    # Fig 4: noise robustness with bootstrap CIs
    fig = go.Figure()
    for name, key, bkey_rf, c in (("clean-trained RF", "RF clean-trained", "clean_rf", SLATE), ("noise-augmented RF", "RF noise-augmented", "aug_rf", TEAL)):
        xs = ["clean" if l == "clean" else f"{l} dB" for l in LEVELS]; ys = [e24[key][l]["f1"] for l in LEVELS]
        lo = [bs[bkey[l]][bkey_rf]["f1_ci"][0] if l in bkey else None for l in LEVELS]
        hi = [bs[bkey[l]][bkey_rf]["f1_ci"][1] if l in bkey else None for l in LEVELS]
        fig.add_trace(go.Scatter(x=xs, y=ys, name=name, mode="lines+markers", line=dict(color=c, width=3), marker=dict(size=9),
                                 error_y=dict(type="data", symmetric=False, array=[(h - y) if h is not None else 0 for y, h in zip(ys, hi)],
                                              arrayminus=[(y - l_) if l_ is not None else 0 for y, l_ in zip(ys, lo)], color=c, thickness=1.2, width=5)))
    fig.update_yaxes(range=[0, 0.65], title="event F1"); fig.update_xaxes(title="white noise added (SNR)")
    figs["fig4_noise"] = style(fig, "Figure 4. Robustness to white noise (error bars: participant-level 95% CI)")

    # Fig 5: AUROC raw vs learned
    lv = ["clean", "20", "10", "5"]; fig = go.Figure()
    for name, k, c in (("raw detector confidence", "auroc_model_confidence", SLATE), ("learned reliability score", "auroc_learned", TEAL)):
        pts = [bs[bkey[l]][k]["point"] for l in lv]; cis = [bs[bkey[l]][k]["ci"] for l in lv]
        fig.add_bar(name=name, x=["clean" if l == "clean" else f"{l} dB" for l in lv], y=pts, marker_color=c, text=[f"{p:.2f}" for p in pts],
                    textposition="outside", error_y=dict(type="data", symmetric=False, array=[ci[1] - p for p, ci in zip(pts, cis)],
                                                        arrayminus=[p - ci[0] for p, ci in zip(pts, cis)], color="#444", thickness=1.2, width=5))
    fig.add_hline(y=0.5, line=dict(dash="dash", color=RED), annotation_text="0.5 = chance")
    fig.update_yaxes(range=[0, 1.05], title="AUROC: is this detection correct?")
    figs["fig5_auroc"] = style(fig, "Figure 5. Which score tells correct from wrong detections?")

    # Fig 6: ordinary vs reliability-aware
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Clean audio", "20 dB white noise"))
    for col, lvl in ((1, "clean"), (2, "20 dB")):
        for mode, name, c in (("ordinary", "Ordinary output (all detections)", SLATE), ("reliability_aware", "Reliability-aware (Confident only)", TEAL)):
            d = e3[lvl][mode]
            fig.add_bar(name=name, x=["Precision", "Recall", "F1"], y=[d["precision"], d["recall"], d["f1"]], marker_color=c, showlegend=col == 1,
                        text=[f"{v:.2f}" for v in (d["precision"], d["recall"], d["f1"])], textposition="outside", row=1, col=col)
    fig.update_yaxes(range=[0, 0.85])
    figs["fig6_reliability_aware"] = style(fig, "Figure 6. Reporting only Confident events trades recall for precision")

    # Fig 7: quality gate
    lv5 = ["clean", "20 dB", "10 dB", "5 dB", "0 dB"]; sh = [e3[l]["flagged_inconclusive_share"] for l in lv5]
    fig = go.Figure(go.Bar(x=lv5, y=sh, marker_color=[TEAL, AMBER, AMBER, RED, RED], text=[f"{v:.0%}" for v in sh], textposition="outside"))
    fig.update_yaxes(range=[0, 1.1], tickformat=".0%", title="recordings withheld (Inconclusive)")
    figs["fig7_quality_gate"] = style(fig, "Figure 7. Share of test recordings the quality gate withholds", h=380)

    # Fig 8: risk-coverage of the raw detector score vs the reliability-aware point
    rc = ex["M1 RF"]["risk_coverage"]; taus = sorted(rc, key=float)
    # τ = 0.3–0.5 land on almost the same point, so label that cluster once
    labels = ["τ = 0.3–0.5" if t == "0.5" else ("" if float(t) < 0.5 else f"τ = {t}") for t in taus]
    pos = ["bottom left" if t == "0.6" else "top right" for t in taus]
    fig = go.Figure(go.Scatter(x=[rc[t]["recall"] for t in taus], y=[rc[t]["precision"] for t in taus], mode="lines+markers+text",
                               text=labels, textposition=pos, name="threshold on raw detector confidence",
                               line=dict(color=SLATE, width=2.5)))
    ra = e3["clean"]["reliability_aware"]
    fig.add_trace(go.Scatter(x=[ra["recall"]], y=[ra["precision"]], mode="markers+text", text=["learned reliability, τ=0.5"], textposition="top center",
                             marker=dict(size=15, color=TEAL, symbol="star"), name="learned reliability score"))
    fig.update_xaxes(title="recall (share of real swallows reported)", range=[-0.02, 0.7]); fig.update_yaxes(title="precision", range=[0, 0.85])
    figs["fig8_risk_coverage"] = style(fig, "Figure 8. Filtering by raw confidence barely raises precision; the learned score does")

    # Fig 9: reliability model coefficients
    import joblib
    rel = joblib.load(ROOT / "models" / "event_reliability.joblib"); coef = rel.steps[-1][1].coef_[0]
    names = ["Mean frame score", "Peak frame score", "Score spread", "Duration", "Mean loudness above floor", "Peak loudness above floor", "Recording SNR"]
    order = sorted(range(7), key=lambda i: coef[i])
    fig = go.Figure(go.Bar(x=[coef[i] for i in order], y=[names[i] for i in order], orientation="h",
                           marker_color=[TEAL if coef[i] > 0 else AMBER for i in order], text=[f"{coef[i]:+.2f}" for i in order], textposition="outside"))
    fig.update_xaxes(title="weight per standard deviation (log-odds)", range=[-0.9, 0.9])
    figs["fig9_reliability_weights"] = style(fig, "Figure 9. What the reliability model has learned", h=400)

    # Fig 2: data split
    split = {"Train": (121, 765, 1320), "Validation": (26, 154, 265), "Test": (27, 171, 288)}
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Participants", "Recordings", "Labelled swallows"))
    for col in range(3):
        fig.add_bar(x=list(split), y=[v[col] for v in split.values()], marker_color=[INK, AMBER, TEAL], showlegend=False,
                    text=[str(v[col]) for v in split.values()], textposition="outside", row=1, col=col + 1)
    for col, top in ((1, 150), (2, 950), (3, 1600)):
        fig.update_yaxes(range=[0, top], row=1, col=col)
    figs["fig2_split"] = style(fig, "Figure 2. Participant-disjoint 70/15/15 split (no person appears in two parts)", h=380)

    render(figs)


PIPE_HTML = """<div id="fig1_pipeline" style="width:1100px;padding:24px;font-family:'Segoe UI',Arial,sans-serif;background:#fff">
<div style="font-size:19px;font-weight:700;margin-bottom:14px;color:#1f2a30">Figure 1. The SWALLOHear pipeline</div>
<div style="display:flex;gap:10px;align-items:stretch">{boxes}</div>
<div style="margin-top:14px;font-size:13px;color:#5b6770">The web app, the mobile app (through the API) and the experiment scripts all call the same Python
package, so what users see is exactly what the experiments measured.</div></div>"""
BOXES = [("1 · Audio in", "WAV/FLAC/M4A upload, demo clip, microphone; resampled to 4 kHz mono", INK),
         ("2 · Quality gate", "SNR, clipping, dropouts, bandwidth, length → withhold if poor", AMBER),
         ("3 · Preprocess", "20–1800 Hz band-pass, robust normalisation, 64 ms frames / 16 ms hop", SLATE),
         ("4 · Detector", "noise-trained Random Forest scores every frame (81 features)", INK),
         ("5 · Events", "start ≥ 0.70, continue ≥ 0.65, merge gaps < 0.4 s, min 150 ms", SLATE),
         ("6 · Reliability", "learned model scores each event → Confident / Low-confidence", TEAL),
         ("7 · Output", "verdict, timeline, explanations, rhythm, exports, report", GREEN)]


def render(figs):
    from playwright.sync_api import sync_playwright
    FIG.mkdir(parents=True, exist_ok=True)
    boxes = "".join(f'<div style="flex:1;border-radius:10px;padding:12px;background:{c}14;border:2px solid {c}">'
                    f'<div style="font-weight:700;color:{c};font-size:14px">{t}</div><div style="font-size:12px;color:#33404a;margin-top:6px">{d}</div></div>'
                    + ('<div style="align-self:center;color:#9aa3ab;font-size:20px">→</div>' if i < len(BOXES) - 1 else "")
                    for i, (t, d, c) in enumerate(BOXES))
    parts = [PIPE_HTML.format(boxes=boxes)]
    for i, (name, fig) in enumerate(figs.items()):
        parts.append(f'<div id="{name}" style="display:inline-block">{fig.to_html(full_html=False, include_plotlyjs=(i == 0), config={"staticPlot": True})}</div>')
    html = "<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0;background:#fff'>" + "".join(parts) + "</body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True); page = b.new_page(device_scale_factor=2)
        page.set_content(html); page.wait_for_timeout(2500)
        for name in ["fig1_pipeline", *figs]:
            page.locator(f"#{name}").screenshot(path=str(FIG / f"{name}.png")); print("  saved", name)
        b.close()


PDF_CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1f2a30; }
h1 { font-size: 22pt; color: #1B7F7A; margin: 0 0 4pt; } h2 { font-size: 15pt; border-bottom: 2px solid #1B7F7A; padding-bottom: 3pt; margin-top: 22pt; break-after: avoid; }
h3 { font-size: 12pt; margin-top: 14pt; break-after: avoid; } h4 { font-size: 11pt; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9pt; break-inside: avoid; }
th, td { border: 1px solid #cfd8d5; padding: 4pt 6pt; vertical-align: top; text-align: left; } th { background: #eef4f2; }
img { max-width: 100%; display: block; margin: 8pt auto; break-inside: avoid; } p img { display: inline; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f3f5f4; padding: 0 2pt; border-radius: 2pt; }
pre { background: #f3f5f4; padding: 8pt; border-radius: 4pt; font-size: 8.5pt; white-space: pre-wrap; break-inside: avoid; }
blockquote { border-left: 4px solid #E0A458; background: #fff8e6; margin: 8pt 0; padding: 6pt 10pt; }
a { color: #1B7F7A; text-decoration: none; } hr { border: 0; border-top: 1px solid #cfd8d5; margin: 14pt 0; }
.pagebreak { break-after: page; }
"""


def pdf():
    import markdown
    from playwright.sync_api import sync_playwright
    body = markdown.markdown(PAPER_MD.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "toc", "sane_lists"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{PDF_CSS}</style></head><body>{body}</body></html>"
    tmp = PAPER_MD.parent / "_paper_build.html"; tmp.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="msedge", headless=True); page = b.new_page()
            page.goto(tmp.resolve().as_uri()); page.wait_for_load_state("networkidle")
            page.pdf(path=str(PAPER_PDF), format="A4", print_background=True, display_header_footer=True,
                     header_template="<div></div>",
                     footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#888'>SWALLOHear · Team RIPARION · PJDSC 2026 · page <span class='pageNumber'></span> of <span class='totalPages'></span></div>",
                     margin=dict(top="16mm", bottom="18mm", left="14mm", right="14mm"))
            b.close()
    finally:
        tmp.unlink(missing_ok=True)
    print("  saved", PAPER_PDF.relative_to(ROOT))


if __name__ == "__main__":
    {"figures": figures, "pdf": pdf}[sys.argv[1] if len(sys.argv) > 1 else "figures"]()
