"""Regenerate the screenshots, demo GIF and demo video in docs/ by driving the real app in a browser.

Run from the repo folder:   python scripts/capture_docs.py
Needs (dev only, not in requirements.txt):  pip install playwright
Uses the installed Microsoft Edge (channel="msedge"); pass --browser chrome to use Google Chrome instead.
"""
import argparse, pathlib, shutil, subprocess, sys, time, urllib.request

from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
PORT = 8505
URL = f"http://localhost:{PORT}"
W, H = 1440, 900

ap = argparse.ArgumentParser(); ap.add_argument("--browser", default="msedge", choices=["msedge", "chrome"]); a = ap.parse_args()


def start_server():
    exe = pathlib.Path(sys.executable).with_name("streamlit.exe" if sys.platform == "win32" else "streamlit")
    proc = subprocess.Popen([str(exe), "run", "app/streamlit_app.py", "--server.port", str(PORT), "--server.headless", "true"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=1); return proc
        except Exception:
            time.sleep(1)
    proc.kill(); raise SystemExit("Streamlit did not start")


def settle(page, ms=900):
    """Wait until Streamlit has finished re-running the script."""
    page.wait_for_timeout(300)
    try:
        page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"] [data-testid=\"stStatusWidgetRunningIcon\"]')"
                               " && !document.body.innerText.includes('Running...')", timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


class Shots:
    def __init__(self, page):
        self.page, self.frames = page, []

    def take(self, name=None, frame=True, top=None):
        """Screenshot the viewport. `top` scrolls that locator to the top of the view first."""
        if top is not None:
            top.evaluate("e => e.scrollIntoView({block: 'start'})"); self.page.wait_for_timeout(500)
        png = self.page.screenshot()
        if name:
            (OUT / f"{name}.png").write_bytes(png)
            print("  saved", name)
        if frame:
            self.frames.append(png)


def tab(page, name):
    page.get_by_role("tab", name=name).first.click(); settle(page)
    return page.get_by_role("tab", name=name).first


def pick_clip(page, clip):
    page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]').first.click()
    page.get_by_role("option", name=clip).first.click(); settle(page, 1500)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    vid_dir = ROOT / "docs" / "_video_tmp"; shutil.rmtree(vid_dir, ignore_errors=True)
    proc = start_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=a.browser, headless=True)
            ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(vid_dir),
                                      record_video_size={"width": W, "height": H}, color_scheme="light")
            page = ctx.new_page(); s = Shots(page)
            page.goto(URL); page.get_by_text("Events detected").first.wait_for(timeout=120000); settle(page, 1500)

            print("Analyze page")
            s.take("01_analyze_overview")
            chart = page.locator(".js-plotly-plot").first
            s.take("02_timeline", top=page.get_by_role("tab", name="Timeline").first)
            marker = chart.locator(".scatterlayer .trace").last.locator(".point").nth(1)
            marker.click(force=True); settle(page, 1500)
            s.take("03_event_card", top=page.get_by_text("Event 2 of 2").first)

            pick_clip(page, "s007a_2")
            t = tab(page, "Events (6)")
            s.take("04_events_table", top=t)
            s.take("05_why_this_score", top=page.get_by_text("Why event").first)
            t = tab(page, "Rhythm")
            s.take("06_rhythm", top=t)
            t = tab(page, "Robustness lab")
            page.get_by_role("button", name="Run sweep").click(); settle(page, 2500)
            s.take("07_robustness_lab", top=t)
            t = tab(page, "Signal quality")
            s.take("08_signal_quality", top=t)
            t = tab(page, "Expert comparison")
            s.take("09_expert_comparison", top=t)

            print("Stress test")
            page.locator('[data-testid="stSidebar"]').get_by_text("Stress test").click(); page.wait_for_timeout(500)
            page.locator('[data-testid="stSidebar"]').get_by_text("Add noise").click(); settle(page, 1500)
            page.locator('[data-testid="stMain"]').evaluate("e => e.scrollTo(0, 0)"); page.wait_for_timeout(400)
            s.take("10_stress_test_withheld")
            page.locator('[data-testid="stSidebar"]').get_by_text("Add noise").click(); settle(page, 1200)

            print("Compare / Batch / Method")
            page.get_by_role("link", name="Compare").click(); settle(page, 2500)
            s.take("11_compare")
            s.take("12_compare_timelines", top=page.get_by_text("Detector score, overlaid").first)
            page.get_by_role("link", name="Batch").click(); settle(page, 1500)
            page.get_by_role("button", name="Analyse").click(); settle(page, 4000)
            s.take("13_batch", top=page.get_by_text("Batch analysis").first)
            page.get_by_role("link", name="Method & results").click(); settle(page, 1500)
            s.take("14_method_results", top=page.get_by_text("What the experiments showed").first)

            print("Dark mode")
            page.get_by_role("link", name="Analyze").click(); settle(page, 1500)
            page.locator("button:has-text('dark_mode')").first.click(); settle(page, 2500)
            s.take("15_dark_mode")
            page.locator("button:has-text('light_mode')").first.click(); settle(page, 1500)

            video = page.video
            ctx.close(); browser.close()
            (ROOT / "docs" / "demo.webm").write_bytes(pathlib.Path(video.path()).read_bytes())
            print("  saved demo.webm")

        frames = [Image.open(__import__("io").BytesIO(b)).convert("RGB").resize((960, 600), Image.LANCZOS) for b in s.frames]
        frames = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
        frames[0].save(ROOT / "docs" / "demo.gif", save_all=True, append_images=frames[1:], duration=1800, loop=0, optimize=True)
        print("  saved demo.gif")
    finally:
        proc.terminate(); shutil.rmtree(vid_dir, ignore_errors=True)


if __name__ == "__main__":
    run()
