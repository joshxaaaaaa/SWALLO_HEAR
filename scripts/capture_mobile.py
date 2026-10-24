"""Phone-sized screenshots of the Expo app (its web build) for docs/MOBILE_GUIDE.md.

Needs the API and the Expo web server running first:
    python api/server.py
    cd mobile && npx expo start --web --port 8081
Then from the repo folder:   python scripts/capture_mobile.py        (dev only: pip install playwright)
"""
import argparse, pathlib, sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "mobile"
ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://localhost:8081"); ap.add_argument("--browser", default="msedge")
a = ap.parse_args()


def settle(page, ms=1200):
    page.wait_for_load_state("networkidle"); page.wait_for_timeout(ms)


def shot(page, name, top=None):
    if top is not None:
        top.first.evaluate("e => e.scrollIntoView({block: 'start'})"); page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / f"{name}.png")); print("  saved", name)


def tab(page, label):
    page.get_by_role("button", name=label, exact=False).first.click(); settle(page)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel=a.browser, headless=True)
        page = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "React DevTools" not in m.text else None)
        page.goto(a.url); page.get_by_text("Events detected").first.wait_for(timeout=120000); settle(page, 2000)

        shot(page, "m01_analyze")
        shot(page, "m02_timeline", page.get_by_text("Spectrogram", exact=True))
        page.get_by_role("button", name="Event 2", exact=True).click(); settle(page)
        shot(page, "m03_event_card", page.get_by_text("Event 2 of 2"))

        page.get_by_role("button", name="Clip").click(); page.get_by_text("s007a_2", exact=True).last.click(); settle(page, 2500)
        tab(page, "Events (6)"); shot(page, "m04_events", page.get_by_text("Events (6)"))
        shot(page, "m05_why_this_score", page.get_by_text("Why event"))
        tab(page, "Rhythm"); shot(page, "m06_rhythm", page.get_by_text("Confident events only"))
        tab(page, "Robustness"); page.get_by_role("button", name="▶ Run sweep").click()
        page.get_by_text("Once the estimated SNR").wait_for(timeout=120000); settle(page)
        shot(page, "m07_robustness", page.get_by_text("How does this recording hold up"))
        tab(page, "Quality"); shot(page, "m08_quality", page.get_by_text("Quality gate", exact=True))
        tab(page, "Expert"); shot(page, "m09_expert", page.get_by_role("button", name="Expert"))

        page.get_by_role("button", name="Detector settings").click(); page.wait_for_timeout(1200)
        shot(page, "m10_settings"); page.get_by_role("button", name="Done").click(); page.wait_for_timeout(800)

        page.get_by_role("button", name="Stress test").click(); page.get_by_role("switch", name="Add noise").first.click(); settle(page, 2500)
        shot(page, "m11_stress_withheld", page.get_by_text("Stress test"))
        page.get_by_role("switch", name="Add noise").first.click(); settle(page)

        page.get_by_text("Compare", exact=False).first.click(); page.get_by_text("Side by side").wait_for(timeout=120000); settle(page, 2000)
        shot(page, "m12_compare", page.get_by_text("Compare two recordings"))
        shot(page, "m13_compare_overlay", page.get_by_text("Side by side"))
        page.get_by_text("Batch", exact=False).first.click(); settle(page)
        page.get_by_role("button", name="Analyse 7 recordings", exact=False).click()
        page.get_by_text("Mean F1 vs expert").wait_for(timeout=180000); settle(page)
        shot(page, "m14_batch", page.get_by_text("Mean F1 vs expert"))
        page.get_by_text("Method & results", exact=False).first.click(); settle(page)
        shot(page, "m15_method", page.get_by_text("What the experiments showed"))

        page.get_by_text("Analyze", exact=False).first.click(); settle(page)
        page.get_by_role("button", name="Dark mode").first.click(); settle(page)
        shot(page, "m16_dark_mode")
        b.close()
    if errors:
        print("PAGE ERRORS:", *errors, sep="\n  "); sys.exit(1)
    print("no page errors")


if __name__ == "__main__":
    main()
