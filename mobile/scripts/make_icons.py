"""Draws the SWALLOHear app icons (white waveform bars on teal) into mobile/assets/images/.
Run from the repo folder with the project venv:  python mobile/scripts/make_icons.py"""
import pathlib
from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "images"
TEAL = (27, 127, 122, 255)
BARS = [0.28, 0.52, 0.86, 0.62, 1.0, 0.7, 0.42, 0.24]   # a swallow-like burst


def glyph(size: int, scale: float, colour=(255, 255, 255, 255), bg=(0, 0, 0, 0)) -> Image.Image:
    """Waveform bars centred in a square; `scale` is the glyph's share of the canvas."""
    im = Image.new("RGBA", (size, size), bg); d = ImageDraw.Draw(im)
    span = size * scale; n = len(BARS); gap = span / n; w = gap * 0.56; x0 = (size - span) / 2 + (gap - w) / 2
    for i, h in enumerate(BARS):
        bh = span * h; x = x0 + i * gap; y = (size - bh) / 2
        d.rounded_rectangle([x, y, x + w, y + bh], radius=w / 2, fill=colour)
    return im


def main():
    big = Image.new("RGBA", (1024, 1024), TEAL); big.alpha_composite(glyph(1024, 0.56))
    big.save(OUT / "icon.png")
    big.resize((48, 48), Image.LANCZOS).save(OUT / "favicon.png")
    Image.new("RGBA", (512, 512), TEAL).save(OUT / "android-icon-background.png")
    glyph(512, 0.42).save(OUT / "android-icon-foreground.png")                 # inside the adaptive-icon safe zone
    glyph(432, 0.46, colour=(255, 255, 255, 255)).save(OUT / "android-icon-monochrome.png")
    glyph(400, 0.8).save(OUT / "splash-icon.png")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
