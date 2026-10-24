"""SWALLOHear web app (RESEARCH USE ONLY).

Run from the repo folder:   streamlit run app/streamlit_app.py

Uses the trained noise-augmented Random Forest + learned event-reliability model
+ signal-quality gate (src/swallohear/final.py). Pages live in app/views/.
"""
import streamlit as st
from streamlit import config as st_config

from views import common as C, analyze, batch, compare, about

st.set_page_config(page_title="SWALLOHear", page_icon=":material/graphic_eq:", layout="wide")

# Streamlit has no API for an in-app theme switch. The browser takes the theme from each run's
# session message, so set this session's choice on the server and rerun once when it differs.
# (On a shared server, two viewers with different choices each get one extra rerun.)
_want = "dark" if C.is_dark() else "light"
if st_config.get_option("theme.base") != _want:
    st_config.set_option("theme.base", _want)
    st.rerun()

st.markdown("""<style>
.block-container {padding-top:3.2rem; max-width:1440px;}
.sh-brand {display:flex; align-items:baseline; gap:.75rem; flex-wrap:wrap; margin-bottom:.1rem;}
.sh-brand b {font-size:1.9rem; letter-spacing:-.02em;}
.sh-brand b span {color:#1B7F7A;}
.sh-brand small {opacity:.65;}
.sh-verdict {display:flex; gap:1rem; align-items:flex-start; border-radius:14px; padding:1rem 1.25rem; margin:.4rem 0 1rem;
             background:color-mix(in srgb, var(--c) 13%, transparent); border:1px solid color-mix(in srgb, var(--c) 45%, transparent);}
.sh-icon {flex:none; width:2.4rem; height:2.4rem; border-radius:50%; background:var(--c); color:#fff;
          display:grid; place-items:center; font-weight:700; font-size:1.25rem;}
.sh-verdict h3 {margin:0; padding:0; font-size:1.3rem;}
.sh-verdict p {margin:.15rem 0 0; opacity:.85;}
.sh-verdict small {display:block; margin-top:.35rem; opacity:.7;}
.sh-chip {display:inline-block; border:1px solid var(--c); border-radius:999px; padding:.08rem .65rem; font-size:.8rem;
          margin:.5rem .35rem 0 0; cursor:help;}
</style>""", unsafe_allow_html=True)

# Page widgets are removed from session state when their page is not shown; re-asserting the keys keeps
# choices across page switches. Defaults live here so widgets never get both a default and a state value.
PERSIST = dict(theme_choice="light", src=None, demo_pick=None, syn_n=4, syn_dur=20, syn_seed=0, noise_on=False, noise_kind=C.NOISE_KINDS[0],
               noise_snr=10, clip_on=False, spec_on=True, sweep_kind=C.NOISE_KINDS[0], rh_conf=False,
               cmp_a_src=None, cmp_b_src=None, cmp_a_noise=None, cmp_b_noise=None, cmp_a_kind=None, cmp_b_kind=None,
               cmp_a_snr=None, cmp_b_snr=None, cmp_spec=False)
for k, v in PERSIST.items():
    if k in st.session_state:
        st.session_state[k] = st.session_state[k]
    elif v is not None:
        st.session_state[k] = v

try:
    A = C.load_analyzer()
except Exception as exc:
    st.error(f"Trained models not found in models/ ({exc}). Run the training scripts first.")
    st.stop()

VALID = C.validated(A)
for k in C.SETTINGS:
    st.session_state.setdefault(f"set_{k}", VALID[k])


def _reset():
    for k in C.SETTINGS:
        st.session_state[f"set_{k}"] = VALID[k]


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    C.sidebar_top = st.container()
    st.divider()
    changed = C.settings_changed(A)
    with st.expander("Detector settings" + (" · custom" if changed else ""), icon=":material/tune:", expanded=bool(changed)):
        st.slider("Reliability threshold (Confident tier)", 0.20, 0.90, step=0.05, key="set_tau",
                  help="Events whose reliability score reaches this are called Confident. Higher = fewer events, more of them correct.")
        st.slider("Start threshold", 0.30, 0.95, step=0.05, key="set_hi", help="Frame score that starts an event.")
        st.slider("Continue threshold", 0.20, 0.95, step=0.05, key="set_lo", help="Frame score that keeps an event going. Must not exceed the start threshold.")
        st.slider("Merge events closer than", 0.0, 1.5, step=0.1, key="set_merge", format="%.1f s")
        st.slider("Quality gate: minimum SNR", 0.0, 25.0, step=0.5, key="set_snr_min", format="%.1f dB")
        if st.session_state["set_lo"] > st.session_state["set_hi"]:
            st.warning("Continue threshold is above the start threshold; it is treated as equal.")
        if changed:
            st.caption("Moved off the validated values (" + ", ".join(changed) + "). Reported results use the validated values.")
        st.button("Reset to validated", icon=":material/restart_alt:", on_click=_reset, disabled=not changed, width="stretch")
    st.caption(":material/info: Research prototype, not a diagnostic device.")

# ----------------------------------------------------------------------------- header & pages
brand, mode = st.columns([6, 1], vertical_alignment="center")
brand.markdown('<div class="sh-brand"><b>SWALLO<span>Hear</span></b>'
               '<small>Reliability-aware swallowing-event analysis from neck-microphone audio · Team RIPARION</small></div>',
               unsafe_allow_html=True)
with mode:
    st.segmented_control("Theme", ["light", "dark"], key="theme_choice", required=True, label_visibility="collapsed",
                         format_func=lambda m: ":material/light_mode:" if m == "light" else ":material/dark_mode:",
                         help="Switch between light and dark mode.", width="stretch")
st.warning("**Research prototype, not a diagnostic device.** It detects swallowing-related acoustic events. It does not assess "
           "dysphagia, aspiration or pneumonia, and must not be used to make care decisions.", icon=":material/health_and_safety:")

pg = st.navigation([
    st.Page(analyze.render, title="Analyze", icon=":material/graphic_eq:", url_path="analyze", default=True),
    st.Page(compare.render, title="Compare", icon=":material/compare:", url_path="compare"),
    st.Page(batch.render, title="Batch", icon=":material/library_music:", url_path="batch"),
    st.Page(about.render, title="Method & results", icon=":material/science:", url_path="method"),
], position="top")
pg.run()
