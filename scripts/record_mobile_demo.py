"""Record a captioned walkthrough of every mobile-app feature, in an iPhone-sized frame, with a visible finger.

Records the Expo app's web build (same screens and code as the iOS/Android app) at iPhone size, 390 x 844.
Writes docs/mobile-demo/: walkthrough.mp4, one clip per feature in clips/, framed snapshots in snapshots/,
highlights.gif and chapters.json.

Needs, in two other terminals:   python api/server.py      and      cd mobile && npx expo start --port 8083
Then from the repo folder:       python scripts/record_mobile_demo.py [--url http://localhost:8083]
Dev-only tools (not in requirements.txt): pip install playwright imageio-ffmpeg   (uses the installed Microsoft Edge).
"""
import argparse, json, pathlib, shutil, subprocess, time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "mobile-demo"
ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://localhost:8083"); ap.add_argument("--index-only", action="store_true")
a = ap.parse_args()
APP = a.url.rstrip("/")
W, H = 1280, 900
PHONE_X, PHONE_Y = 110, 14            # outer frame position
BEZEL, SCREEN_W, SCREEN_H, STATUS = 12, 390, 844, 47

WRAPPER = f"""<!doctype html><html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{ margin:0; width:{W}px; height:{H}px; overflow:hidden; font-family:'Segoe UI',system-ui,sans-serif;
  background: radial-gradient(1200px 700px at 20% 20%, #1f4f4c 0%, #0f2427 55%, #0b1719 100%); color:#eaf2f1; }}
#phone {{ position:absolute; left:{PHONE_X}px; top:{PHONE_Y}px; width:{SCREEN_W + 2 * BEZEL}px; height:{SCREEN_H + 2 * BEZEL}px;
  background:#0b0b0d; border-radius:62px; box-shadow: 0 30px 80px rgba(0,0,0,.55), inset 0 0 0 2px #2b2b30; }}
#screen {{ position:absolute; left:{BEZEL}px; top:{BEZEL}px; width:{SCREEN_W}px; height:{SCREEN_H}px; border-radius:50px; overflow:hidden; background:#fff; }}
#status {{ position:absolute; left:0; top:0; width:100%; height:{STATUS}px; display:flex; align-items:center; justify-content:space-between;
  padding:0 30px 0 36px; font-weight:600; font-size:16px; color:#111; z-index:3; }}
#island {{ position:absolute; left:50%; top:11px; width:122px; height:35px; margin-left:-61px; background:#000; border-radius:20px; z-index:4; }}
#app {{ position:absolute; left:0; top:{STATUS}px; width:{SCREEN_W}px; height:{SCREEN_H - STATUS}px; border:0; background:#fff; }}
#home {{ position:absolute; left:50%; bottom:7px; width:134px; height:5px; margin-left:-67px; border-radius:3px; background:#111; z-index:5; pointer-events:none; }}
#sheet {{ position:absolute; left:0; top:{STATUS}px; width:100%; height:{SCREEN_H - STATUS}px; background:#fff; z-index:6;
  transform:translateY(105%); transition:transform .45s ease; border-radius:14px 14px 0 0; overflow:hidden; box-shadow:0 -6px 30px rgba(0,0,0,.25); }}
#sheet.up {{ transform:translateY(0); }}
#sheet .bar {{ height:44px; display:flex; align-items:center; justify-content:space-between; padding:0 16px; background:#f4f4f6; border-bottom:1px solid #ddd; font-size:14px; color:#333; }}
#sheet .bar b {{ color:#1B7F7A; font-weight:600; }}
#sheet iframe {{ width:100%; height:calc(100% - 44px); border:0; }}
#finger {{ position:absolute; left:0; top:0; width:46px; height:46px; margin:-23px 0 0 -23px; border-radius:50%; z-index:50; pointer-events:none;
  background:rgba(255,255,255,.38); border:2px solid rgba(20,40,40,.35); box-shadow:0 2px 10px rgba(0,0,0,.3);
  transition: left .45s cubic-bezier(.4,.1,.2,1), top .45s cubic-bezier(.4,.1,.2,1), transform .12s, opacity .3s; opacity:0; }}
#finger.down {{ transform:scale(.78); background:rgba(27,127,122,.45); }}
.ripple {{ position:absolute; width:46px; height:46px; margin:-23px 0 0 -23px; border-radius:50%; border:3px solid rgba(27,127,122,.85);
  pointer-events:none; z-index:49; animation: rip .55s ease-out forwards; }}
@keyframes rip {{ from {{ transform:scale(.6); opacity:1; }} to {{ transform:scale(2.1); opacity:0; }} }}
#panel {{ position:absolute; left:{PHONE_X + SCREEN_W + 2 * BEZEL + 70}px; top:70px; width:{W - (PHONE_X + SCREEN_W + 2 * BEZEL + 70) - 70}px; }}
#brand {{ font-size:30px; font-weight:800; letter-spacing:-.5px; }} #brand span {{ color:#5FD0C8; }}
#sub {{ font-size:15px; color:#9fb8b5; margin-top:4px; }}
#step {{ margin-top:46px; font-size:14px; letter-spacing:.12em; text-transform:uppercase; color:#5FD0C8; font-weight:700; }}
#title {{ font-size:38px; font-weight:700; margin-top:8px; line-height:1.15; }}
#body {{ font-size:19px; line-height:1.55; color:#cfe0de; margin-top:16px; min-height:150px; }}
#bar {{ margin-top:30px; height:6px; border-radius:3px; background:rgba(255,255,255,.12); overflow:hidden; }}
#bar i {{ display:block; height:100%; width:0; background:#5FD0C8; transition:width .6s; }}
#foot {{ position:absolute; left:{PHONE_X + SCREEN_W + 2 * BEZEL + 70}px; bottom:34px; font-size:13px; color:#86a3a0; width:600px; line-height:1.5; }}
</style></head><body>
<div id="phone"><div id="screen">
  <div id="status"><span id="clock">9:41</span><svg width="70" height="13" viewBox="0 0 70 13"><g fill="currentColor">
    <rect x="0" y="8" width="3" height="5" rx="1"/><rect x="5" y="6" width="3" height="7" rx="1"/><rect x="10" y="3" width="3" height="10" rx="1"/><rect x="15" y="0" width="3" height="13" rx="1"/>
    <path d="M30 4.5a8 8 0 0 1 11 0l-1.4 1.4a6 6 0 0 0-8.2 0zM32.8 7.3a4 4 0 0 1 5.4 0L35.5 10z"/>
    <rect x="47" y="1" width="20" height="11" rx="3" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="49" y="3" width="15" height="7" rx="1.5"/><rect x="68" y="4.5" width="1.6" height="4" rx=".8"/></g></svg></div>
  <div id="island"></div>
  <iframe id="app" allow="microphone; autoplay; clipboard-write" src="{APP}/"></iframe>
  <div id="sheet"><div class="bar"><span>🔒 localhost · report</span><b>Done</b></div><iframe id="sheetframe"></iframe></div>
  <div id="home"></div>
</div></div>
<div id="finger"></div>
<div id="panel"><div id="brand">SWALLO<span>Hear</span> mobile</div><div id="sub">Feature walkthrough · Team RIPARION · PJDSC 2026</div>
<div id="step"></div><div id="title"></div><div id="body"></div><div id="bar"><i></i></div></div>
<div id="foot">Recorded from the app's own code (its web build) at iPhone size, 390 × 844. On a real iPhone the same screens run natively
through Expo Go. Research prototype, not a diagnostic device. Demo audio: Khalifa et al. (2021), CC BY 4.0.</div>
<script>
const f = document.getElementById('finger');
window.setCaption = (n, total, title, body) => {{
  document.getElementById('step').textContent = n ? `Feature ${{n}} of ${{total}}` : '';
  document.getElementById('title').textContent = title; document.getElementById('body').textContent = body;
  document.querySelector('#bar i').style.width = (n ? 100 * n / total : 0) + '%'; }};
window.fingerShow = (x, y) => {{ f.style.transition = 'none'; f.style.left = x + 'px'; f.style.top = y + 'px'; f.offsetHeight;
  f.style.transition = ''; f.style.opacity = 1; }};
window.fingerTo = (x, y, ms) => {{ f.style.transitionDuration = `${{ms}}ms, ${{ms}}ms, .12s, .3s`; f.style.opacity = 1; f.style.left = x + 'px'; f.style.top = y + 'px'; }};
window.fingerHide = () => {{ f.style.opacity = 0; }};
window.fingerDown = (on) => f.classList.toggle('down', on);
window.ripple = (x, y) => {{ const r = document.createElement('div'); r.className = 'ripple'; r.style.left = x + 'px'; r.style.top = y + 'px';
  document.body.appendChild(r); setTimeout(() => r.remove(), 600); }};
window.setDark = (d) => {{ document.getElementById('status').style.color = d ? '#fff' : '#111'; document.getElementById('screen').style.background = d ? '#0E1117' : '#fff';
  document.getElementById('home').style.background = d ? '#fff' : '#111'; }};
window.showSheet = (url) => {{ document.getElementById('sheetframe').src = url; document.getElementById('sheet').classList.add('up'); }};
window.hideSheet = () => document.getElementById('sheet').classList.remove('up');
</script></body></html>"""

# Injected into every frame: smooth scrolling of the app's main scroll view (for natural-looking swipes).
FRAME_JS = """
window.__scroller = (el) => {
  // Start from the element itself, or (for page-level scrolls) whatever is under the middle of the screen:
  // inactive tabs stay mounted but hidden, so the first scrollable div in the DOM may not be the visible one.
  let n = el === document.body ? document.elementFromPoint(innerWidth / 2, innerHeight / 2) : el;
  while (n && n !== document.body) { const s = getComputedStyle(n);
    if (/(auto|scroll)/.test(s.overflowY) && n.scrollHeight > n.clientHeight + 5) return n; n = n.parentElement; }
  return null; };
window.__animScroll = (sc, to, ms) => new Promise(res => { const from = sc.scrollTop, t0 = performance.now();
  const step = (t) => { const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    sc.scrollTop = from + (to - from) * e; k < 1 ? requestAnimationFrame(step) : res(); }; requestAnimationFrame(step); });
window.__bring = (el, frac, ms) => { const sc = window.__scroller(el); if (!sc) return 0; const r = el.getBoundingClientRect(), s = sc.getBoundingClientRect();
  const to = Math.max(0, Math.min(sc.scrollHeight - sc.clientHeight, sc.scrollTop + (r.top - s.top) - sc.clientHeight * frac));
  const d = to - sc.scrollTop; if (Math.abs(d) < 4) return 0; window.__animScroll(sc, to, ms); return d; };
window.__scrollBy = (dy, ms) => { const sc = window.__scroller(document.body); if (!sc) return 0;
  const to = Math.max(0, Math.min(sc.scrollHeight - sc.clientHeight, sc.scrollTop + dy)); const d = to - sc.scrollTop; window.__animScroll(sc, to, ms); return d; };
window.__scrollTop = () => { const sc = window.__scroller(document.body); if (sc) window.__animScroll(sc, 0, 500); };
"""

SX0, SY0 = PHONE_X + BEZEL, PHONE_Y + BEZEL          # screen origin on the page
APP_TOP, APP_BOTTOM = SY0 + STATUS, SY0 + SCREEN_H


class Demo:
    def __init__(self, page):
        self.page, self.chapters, self.n, self.total, self.t0 = page, [], 0, 0, time.monotonic()
        self.app = page.frame_locator("#app")

    @property
    def frame(self):
        # The wrapper page is served from the app's origin too, so pick the #app iframe explicitly.
        return self.page.query_selector("#app").content_frame()

    def wait(self, ms):
        self.page.wait_for_timeout(ms)

    MIN_CHAPTER_S = 9.0   # long enough to read the caption

    def close_chapter(self):
        if not self.chapters:
            return
        shown = time.monotonic() - self.t0 - self.chapters[-1]["start"]
        if shown < self.MIN_CHAPTER_S:
            self.wait(int((self.MIN_CHAPTER_S - shown) * 1000))
        self.chapters[-1]["end"] = time.monotonic() - self.t0

    def chapter(self, slug, title, body):
        self.close_chapter()
        self.n += 1
        self.chapters.append(dict(n=self.n, slug=slug, title=title, body=body, start=time.monotonic() - self.t0))
        self.page.evaluate("([n,t,a,b]) => window.setCaption(n,t,a,b)", [self.n, self.total, title, body]); self.wait(900)

    def snap(self, name):
        OUT.joinpath("snapshots").mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(OUT / "snapshots" / f"{self.n:02d}_{name}.png"),
                             clip=dict(x=PHONE_X - 10, y=PHONE_Y - 6, width=SCREEN_W + 2 * BEZEL + 20, height=SCREEN_H + 2 * BEZEL + 12))

    # --- finger ----------------------------------------------------------------------------------------------
    def finger(self, x, y, ms=480):
        self.page.evaluate("([x,y,ms]) => window.fingerTo(x,y,ms)", [x, y, ms]); self.wait(ms + 80)

    def swipe(self, dy, ms=900):
        """Scroll the app by dy pixels with a matching finger swipe."""
        cx, y0 = SX0 + SCREEN_W * 0.62, APP_TOP + (APP_BOTTOM - APP_TOP) * (0.72 if dy > 0 else 0.3)
        self.finger(cx, y0, 350)
        moved = self.frame.evaluate("([dy,ms]) => window.__scrollBy(dy,ms)", [dy, ms])
        self.page.evaluate("()=>window.fingerDown(true)")
        self.page.evaluate("([x,y,ms]) => window.fingerTo(x,y,ms)", [cx, y0 - max(-320, min(320, moved or dy)) * 0.8, ms])
        self.wait(ms + 60); self.page.evaluate("()=>window.fingerDown(false)"); self.wait(250)

    def bring(self, loc, frac=0.35):
        """Swipe until the element sits about `frac` of the way down the screen."""
        loc.wait_for(state="visible", timeout=60000)
        el = loc.element_handle()
        box = loc.bounding_box()
        if box and APP_TOP + 30 < box["y"] and box["y"] + box["height"] < APP_BOTTOM - 90:
            return
        cx = SX0 + SCREEN_W * 0.62; up = box and box["y"] > APP_TOP
        y0 = APP_TOP + (APP_BOTTOM - APP_TOP) * (0.72 if up else 0.3)
        self.finger(cx, y0, 350); self.page.evaluate("()=>window.fingerDown(true)")
        d = self.frame.evaluate("([el,f,ms]) => window.__bring(el,f,ms)", [el, frac, 850]) or 0
        self.page.evaluate("([x,y,ms]) => window.fingerTo(x,y,ms)", [cx, y0 - max(-320, min(320, d)) * 0.8, 850])
        self.wait(920); self.page.evaluate("()=>window.fingerDown(false)"); self.wait(250)

    def tap(self, loc, pause=900, bring=True):
        if bring:
            self.bring(loc)
        box = loc.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.finger(x, y)
        self.page.evaluate("()=>window.fingerDown(true)"); self.page.evaluate("([x,y]) => window.ripple(x,y)", [x, y])
        self.page.mouse.click(x, y); self.wait(120); self.page.evaluate("()=>window.fingerDown(false)"); self.wait(pause)

    def drag(self, loc, frac_from, frac_to, pause=900):
        self.bring(loc, 0.4); box = loc.bounding_box()
        y = box["y"] + box["height"] / 2; x0 = box["x"] + box["width"] * frac_from; x1 = box["x"] + box["width"] * frac_to
        self.finger(x0, y); self.page.evaluate("()=>window.fingerDown(true)"); self.page.mouse.move(x0, y); self.page.mouse.down()
        for k in range(1, 21):
            x = x0 + (x1 - x0) * k / 20; self.page.mouse.move(x, y); self.page.evaluate("([x,y]) => window.fingerTo(x,y,40)", [x, y]); self.wait(35)
        self.page.mouse.up(); self.page.evaluate("()=>window.fingerDown(false)"); self.wait(pause)

    # --- app locators ----------------------------------------------------------------------------------------
    def btn(self, name, exact=False):
        return self.app.get_by_role("button", name=name, exact=exact).first

    def text(self, t, exact=False):
        return self.app.get_by_text(t, exact=exact).first

    def tab(self, name):
        return self.app.get_by_role("tab", name=name).first

    def settle(self, ms=1200):
        try:
            self.app.get_by_text("updating…").first.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass
        self.wait(ms)


def walkthrough(d: Demo, context):
    app = d.app
    d.total = 21
    d.page.evaluate("([n,t,a,b]) => window.setCaption(n,t,a,b)", [0, 0, "Feature walkthrough", "Every feature of the SWALLOHear mobile app, one by one."])
    app.get_by_text("Events detected").first.wait_for(timeout=180000); d.frame.evaluate(FRAME_JS); d.wait(2500)
    d.page.evaluate("([x,y]) => window.fingerShow(x,y)", [SX0 + SCREEN_W * 0.6, APP_TOP + 520])

    d.chapter("welcome", "Welcome", "The header has the light/dark switch and ⚙ for detector settings. The yellow banner is always there: SWALLOHear is a research prototype, not a diagnostic device.")
    d.finger(SX0 + 330, APP_TOP + 50); d.wait(900); d.snap("welcome")

    d.chapter("demo_clip", "Pick a recording", "Four sources: demo clips from held-out test participants, upload, the phone microphone, or synthetic test signals. Here: demo clip ns027d_1.")
    d.tap(d.btn("Clip")); d.wait(700); d.snap("clip_picker")
    d.tap(app.get_by_text("ns027d_1", exact=True).last, pause=1500)
    d.bring(d.text("Held-out test participant"), 0.3); d.wait(600)

    d.chapter("verdict", "Verdict and summary", "First the quality gate, then the verdict: events detected. The cards show confident and low-confidence events, event rate, estimated SNR against the gate, and processing time.")
    d.bring(d.text("Events detected"), 0.12); d.wait(1500); d.snap("verdict")
    d.bring(d.text("Processing time"), 0.45); d.wait(1500)

    d.chapter("timeline", "Timeline", "Waveform, spectrogram and detector score on one time axis. Teal = Confident, amber = Low-confidence, dotted green = expert labels. Zoom up to 8× and swipe sideways.")
    d.bring(d.btn("Timeline", exact=True), 0.05); d.wait(1200); d.snap("timeline")
    d.tap(app.get_by_role("switch", name="Expert labels"), pause=1100); d.tap(app.get_by_role("switch", name="Expert labels"), pause=900)
    d.tap(d.btn("2×", exact=True), pause=1300); d.tap(d.btn("1×", exact=True), pause=900)

    d.chapter("event_card", "Event card", "Tap a numbered marker to inspect an event: listen to just that sound, see its reliability against the threshold and what raised or lowered it, then record your own call.")
    d.tap(app.get_by_role("button", name="Event 2", exact=True), pause=1200)
    d.bring(d.text("Event 2 of 2"), 0.08); d.wait(900)
    d.tap(app.get_by_role("button", name="Play").nth(1), pause=1800, bring=False)
    d.tap(d.btn("Swallow", exact=True), pause=900); d.snap("event_card")
    d.bring(d.text("What pushed this event"), 0.3); d.wait(1500)

    d.chapter("why", "Events and “Why this score?”", "A table of every event, then an exact breakdown of the reliability score: it starts from an average event and each measurement pushes it up (teal) or down (amber).")
    d.bring(d.btn("Timeline", exact=True), 0.05); d.tap(d.btn("Events (2)"), pause=1300)
    d.tap(app.get_by_text("Low-confidence", exact=True).last, pause=1200)
    d.bring(d.text("Why event"), 0.08); d.wait(1800); d.snap("why_this_score")
    d.swipe(420); d.tap(d.btn("Raw detector confidence vs reliability"), pause=1500)
    d.tap(d.btn("⇪ Events (CSV)"), pause=1100)

    d.chapter("rhythm", "Rhythm", "How swallowing is spread over time: rate, mean interval, regularity and the longest pause, with events-over-time and interval charts. Shown here on clip s007a_2, which has six events.")
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(700)
    d.tap(d.btn("Clip")); d.tap(app.get_by_text("s007a_2", exact=True).last, pause=2200); d.settle()
    d.bring(d.btn("Timeline", exact=True), 0.05); d.tap(d.btn("Rhythm", exact=True), pause=1400); d.snap("rhythm")
    d.tap(app.get_by_role("switch", name="Confident events only"), pause=1200); d.tap(app.get_by_role("switch", name="Confident events only"), pause=800)
    d.swipe(380); d.wait(1200)

    d.chapter("robustness", "Robustness lab", "Re-runs the analysis at seven noise levels. Watch the events thin out and the quality gate start withholding results once the estimated SNR falls below the red line.")
    d.bring(d.btn("Timeline", exact=True), 0.05); d.tap(d.btn("Robustness", exact=True), pause=900)
    d.tap(d.btn("▶ Run sweep"), pause=400); app.get_by_text("Once the estimated SNR").first.wait_for(timeout=120000)
    d.bring(d.text("How does this recording hold up"), 0.05); d.wait(1500); d.snap("robustness"); d.swipe(420); d.wait(1200)

    d.chapter("quality", "Signal quality", "Every quality-gate check with its value and limit, how the SNR is estimated (noise floor vs peaks) and the average spectrum, where mains hum would show as spikes.")
    d.bring(d.btn("Timeline", exact=True), 0.05); d.tap(d.btn("Quality", exact=True), pause=1300); d.snap("quality"); d.swipe(520); d.wait(1000)

    d.chapter("expert", "Expert comparison", "For labelled clips: matched events, false detections, misses, precision, recall and F1, and Expert vs System lanes (green = matched, red = unmatched).")
    d.bring(d.btn("Timeline", exact=True), 0.05); d.tap(d.btn("Expert", exact=True), pause=1500); d.snap("expert"); d.swipe(300); d.wait(1000)

    d.chapter("session", "Session log", "Every analysis run in this session, with exports of the log and of all your calls on events.")
    d.bring(d.btn("Timeline", exact=True), 0.05); d.tap(d.btn("Session", exact=True), pause=1700); d.snap("session")

    d.chapter("stress", "Stress test", "Add white, pink or 60 Hz mains-hum noise, or simulate clipping. At 10 dB of white noise the estimated SNR drops below the gate and the result is withheld instead of guessed.")
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(700)
    d.tap(d.btn("Stress test"), pause=900); d.tap(app.get_by_role("switch", name="Add noise"), pause=2000); d.settle()
    d.bring(d.text("Result withheld"), 0.15); d.wait(1800); d.snap("stress_withheld")
    d.bring(d.btn("Pink", exact=True), 0.25); d.tap(d.btn("Pink", exact=True), pause=1600)
    d.tap(app.get_by_role("switch", name="Add noise"), pause=900)
    d.tap(app.get_by_role("switch", name="Simulate clipping (4× gain, hard-clipped)"), pause=1800); d.settle()
    d.bring(d.text("⚡ clipping"), 0.1); d.wait(1800)   # verdict depends on how much of the clip saturates
    d.bring(app.get_by_role("switch", name="Simulate clipping (4× gain, hard-clipped)"), 0.3)
    d.tap(app.get_by_role("switch", name="Simulate clipping (4× gain, hard-clipped)"), pause=1400); d.settle()

    d.chapter("settings", "Detector settings", "All five thresholds, live. Raising the reliability threshold makes fewer events Confident but more of them correct. “Reset to validated” restores the values the results were measured with.")
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(600)
    d.tap(d.btn("Detector settings"), pause=1200); d.snap("settings")
    d.drag(app.get_by_role("slider").first, 0.43, 0.15, pause=1200)
    d.tap(d.btn("Reset to validated"), pause=1000); d.tap(d.btn("Done", exact=True), pause=1200, bring=False)

    d.chapter("report", "Printable report", "📄 Report opens a self-contained report in the browser: verdict, timeline, every event with its reasons and your calls, rhythm, quality and limits, ready to share or save as PDF.")
    d.bring(d.btn("📄 Report"), 0.2)
    with context.expect_page() as pop:
        d.tap(d.btn("📄 Report"), pause=200, bring=False)
    popup = pop.value; url = popup.url; popup.close()
    d.page.evaluate("(u) => window.showSheet(u)", url); d.wait(3500); d.snap("report")
    d.finger(SX0 + 200, APP_TOP + 500, 350); d.page.mouse.move(SX0 + 200, APP_TOP + 500)
    for _ in range(6):
        d.page.mouse.wheel(0, 260); d.wait(450)
    d.wait(800); d.page.evaluate("() => window.hideSheet()"); d.wait(900)

    d.chapter("upload", "Upload a file", "Choose any audio file on the phone (WAV, FLAC, M4A, MP3, WebM; up to 120 s). It is sent to the analysis server and analysed exactly like the demo clips.")
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(600)
    d.tap(d.btn("Upload"), pause=900)
    with d.page.expect_file_chooser() as fc:
        d.tap(d.btn("Choose an audio file"), pause=200)
    fc.value.set_files(str(ROOT / "data" / "demo" / "demo_s041b_1.wav")); d.settle(2500)
    d.bring(d.text("demo_s041b_1"), 0.05); d.wait(1800); d.snap("upload")

    d.chapter("record", "Record with the microphone", "Rest the phone’s microphone lightly against the side of the throat and press record. When you stop, the recording is analysed straight away. (Here a test tone stands in for a throat recording.)")
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(600)
    d.tap(d.btn("Record"), pause=900); d.tap(d.btn("● Start recording"), pause=4500); d.snap("recording")
    d.tap(app.get_by_role("button", name="■ Stop recording", exact=False), pause=600); d.settle(2500)
    d.bring(d.text("microphone_"), 0.05); d.wait(2200)

    d.chapter("synthetic", "Synthetic test signals", "Generated swallow-like bursts with known positions, for checking the pipeline end to end. Sliders set the number of bursts, the length and the random seed.")
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(600)
    d.tap(d.btn("Synthetic"), pause=1500); d.settle(); d.snap("synthetic"); d.swipe(450); d.wait(1500)
    d.frame.evaluate("() => window.__scrollTop()"); d.wait(600); d.tap(d.btn("Demo"), pause=1500)

    d.chapter("compare", "Compare", "Two recordings side by side, here the same clip clean and with 5 dB of noise: a table with a B − A column, both detector scores overlaid, and timelines on a shared time axis.")
    d.tap(d.tab("Compare"), pause=500, bring=False); app.get_by_text("Side by side").first.wait_for(timeout=120000); d.wait(1500); d.snap("compare")
    d.tap(d.btn("Same clip: clean vs noisy"), pause=1500)
    d.bring(d.text("Side by side"), 0.05); d.wait(1800); d.swipe(500); d.wait(1500); d.swipe(600); d.wait(1500)

    d.chapter("batch", "Batch", "Analyse many recordings at once, with optional noise: totals, a table with mean reliability and F1, and an SNR-vs-events chart against the quality gate.")
    d.tap(d.tab("Batch"), pause=900, bring=False); d.tap(d.btn("Analyse 7 recordings"), pause=400)
    app.get_by_text("Mean F1 vs expert").first.wait_for(timeout=180000); d.bring(d.text("Mean F1 vs expert"), 0.1); d.wait(1500); d.snap("batch")
    d.swipe(500); d.wait(1500)

    d.chapter("method", "Method & results", "How the pipeline works and what the experiments showed: noise robustness, and ordinary vs reliability-aware output at each noise level, then the headline numbers and limits.")
    d.tap(d.tab("Method"), pause=1200, bring=False); d.snap("method")
    d.bring(d.text("Noise robustness (F1)"), 0.1); d.wait(1500)
    d.bring(d.btn("20 dB", exact=True), 0.2); d.tap(d.btn("20 dB", exact=True), pause=1300); d.tap(d.btn("5 dB", exact=True), pause=1300)
    d.tap(d.btn("clean", exact=True), pause=900); d.swipe(600); d.wait(1500)

    d.chapter("dark", "Dark mode", "☾ switches the whole app, charts included, and the choice stays as you move between tabs.")
    d.tap(d.tab("Analyze"), pause=900, bring=False); d.frame.evaluate("() => window.__scrollTop()"); d.wait(1200)
    d.tap(d.btn("Dark mode"), pause=300); d.page.evaluate("() => window.setDark(true)"); d.wait(1500); d.snap("dark_mode")
    d.swipe(700); d.wait(1200); d.tap(d.tab("Method"), pause=1500, bring=False); d.swipe(500); d.wait(1200)
    d.tap(d.tab("Analyze"), pause=700, bring=False); d.frame.evaluate("() => window.__scrollTop()"); d.wait(1200)
    d.tap(d.btn("Light mode"), pause=300); d.page.evaluate("() => window.setDark(false)"); d.wait(1200)

    d.close_chapter()
    d.page.evaluate("()=>window.fingerHide()")
    d.page.evaluate("([n,t,a,b]) => window.setCaption(n,t,a,b)", [0, 0, "That’s every feature",
                    "Code, models, the research paper and setup steps: github.com/jedelacruz/swallohear"]); d.wait(3500)


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(raw: pathlib.Path, chapters):
    ff = ffmpeg()
    full = OUT / "walkthrough.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-preset", "slow", "-crf", "27",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(full)], check=True)
    clips = OUT / "clips"; shutil.rmtree(clips, ignore_errors=True); clips.mkdir()
    for c in chapters:
        dst = clips / f"{c['n']:02d}_{c['slug']}.mp4"; c["clip"] = f"clips/{dst.name}"
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{max(0, c['start'] - 0.3):.2f}", "-to", f"{c['end'] + 0.2:.2f}", "-i", str(full),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)], check=True)
    # Highlights GIF: the timeline and event card chapters, phone frame only.
    pick = [c for c in chapters if c["slug"] in ("timeline", "event_card", "stress")]
    parts = []
    for c in pick:
        part = OUT / f"_gif_{c['slug']}.mp4"; parts.append(part)
        subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{c['start']:.2f}", "-t", f"{min(9, c['end'] - c['start']):.2f}", "-i", str(full),
                        "-vf", f"crop={SCREEN_W + 2 * BEZEL + 24}:{SCREEN_H + 2 * BEZEL + 16}:{PHONE_X - 12}:{PHONE_Y - 8}", "-an", str(part)], check=True)
    lst = OUT / "_gif_list.txt"; lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    joined = OUT / "_gif_joined.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(joined), "-vf",
                    "fps=9,scale=300:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                    str(OUT / "highlights.gif")], check=True)
    for p in [*parts, lst, joined]:
        p.unlink(missing_ok=True)
    return full


def write_index(chapters):
    """docs/mobile-demo/README.md: the video, the GIF and one row per feature (snapshot, clip, time in the full video)."""
    snaps = {p.name.split("_", 1)[0]: p.name for p in sorted((OUT / "snapshots").glob("*.png"))}
    mmss = lambda s: f"{int(s // 60)}:{int(s % 60):02d}"
    rows = "\n".join(
        f"| {c['n']} | <img src=\"snapshots/{snaps.get(f'{c['n']:02d}', '')}\" width=\"150\" alt=\"{c['title']}\"> | **{c['title']}**<br>{c['body']} | "
        f"{mmss(c['start'])} | [▶ clip]({c['clip']}) |" for c in chapters)
    total = mmss(chapters[-1]["end"]) if chapters else "?"
    (OUT / "README.md").write_text(f"""# SWALLOHear mobile app: feature walkthrough

A captioned walkthrough of **every feature of the mobile app**, one by one, with a finger indicator showing each tap,
swipe and drag.

<img src="highlights.gif" width="300" alt="Highlights: timeline, event card and stress test">

**▶ [Full walkthrough video](walkthrough.mp4)** ({total}). Each feature also has its own short clip in the table below.

> **How this was recorded.** These videos come from the app's own code (its web build, the same screens and features)
> shown at iPhone size (390 × 844) inside an iPhone frame, driven automatically by
> [`scripts/record_mobile_demo.py`](../../scripts/record_mobile_demo.py). On a real iPhone or Android phone the same
> screens run natively through Expo Go (see the [mobile app guide](../MOBILE_GUIDE.md)). In the *Record* step the
> browser's test tone stands in for a throat recording. Demo audio: Khalifa et al. (2021), CC BY 4.0.
> Research prototype, not a diagnostic device.

| # | Snapshot | Feature | Starts at | Clip |
|---|---|---|---|---|
{rows}

## Re-recording

Start the analysis server (`python api/server.py`) and Expo (`cd mobile && npx expo start --port 8083`), then run
`python scripts/record_mobile_demo.py`. It rewrites this folder: `walkthrough.mp4`, `clips/`, `snapshots/`,
`highlights.gif`, `chapters.json` and this page. Needs `pip install playwright imageio-ffmpeg` and Microsoft Edge.
""", encoding="utf-8")


def main():
    if "--index-only" in __import__("sys").argv:
        write_index(json.loads((OUT / "chapters.json").read_text(encoding="utf-8"))); return
    OUT.mkdir(parents=True, exist_ok=True); shutil.rmtree(OUT / "snapshots", ignore_errors=True)
    raw_dir = OUT / "_raw"; shutil.rmtree(raw_dir, ignore_errors=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True,
                              args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"])
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(raw_dir), record_video_size={"width": W, "height": H},
                            accept_downloads=True)
        ctx.grant_permissions(["microphone"], origin=APP)
        ctx.add_init_script(FRAME_JS)
        page = ctx.new_page()
        # Serve the phone frame from the app's own origin: Chromium grants the microphone by the top-level origin.
        page.route(f"{APP}/__demo_frame.html", lambda r: r.fulfill(body=WRAPPER, content_type="text/html; charset=utf-8"))
        page.goto(f"{APP}/__demo_frame.html")
        d = Demo(page)
        try:
            walkthrough(d, ctx)
        finally:
            video = page.video; ctx.close(); b.close()
        raw = pathlib.Path(video.path())
    full = encode(raw, d.chapters)
    shutil.rmtree(raw_dir, ignore_errors=True)
    for c in d.chapters:
        c["start"], c["end"] = round(c["start"], 1), round(c["end"], 1)
    (OUT / "chapters.json").write_text(json.dumps(d.chapters, indent=1, ensure_ascii=False), encoding="utf-8")
    write_index(d.chapters)
    print(f"saved {full.relative_to(ROOT)} ({full.stat().st_size / 1e6:.1f} MB), {len(d.chapters)} clips, snapshots, highlights.gif")


if __name__ == "__main__":
    main()
