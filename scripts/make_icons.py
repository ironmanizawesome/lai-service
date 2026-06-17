"""Generate PWA icons (no external assets, font-independent).

Draws a simple white leaf on a green rounded square. Reproducible — re-run to
regenerate. Outputs to static/icons/.

    python scripts/make_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"
GREEN = (34, 197, 94)        # tailwind green-500, matches --accent-ish theme
GREEN_DARK = (22, 130, 62)
WHITE = (255, 255, 255)


def _rounded_bg(size: int, pad_ratio: float = 0.0) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(size * pad_ratio)
    radius = int(size * 0.22)
    d.rounded_rectangle(
        [pad, pad, size - 1 - pad, size - 1 - pad],
        radius=radius, fill=GREEN,
    )
    return img


def _draw_leaf(img: Image.Image, size: int) -> None:
    d = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    # Leaf as two mirrored arcs (a pointed ellipse). Build a polygon.
    w = size * 0.30   # half-width
    h = size * 0.40   # half-height
    pts_right, pts_left = [], []
    steps = 40
    for i in range(steps + 1):
        t = i / steps
        # parametric pointed-leaf: x narrows to 0 at both tips
        y = cy - h + 2 * h * t
        # width profile: sin gives fat middle, zero at tips
        x_off = w * math.sin(math.pi * t)
        pts_right.append((cx + x_off, y))
        pts_left.append((cx - x_off, y))
    polygon = pts_right + list(reversed(pts_left))
    # rotate slightly for a natural tilt
    angle = math.radians(-18)
    ca, sa = math.cos(angle), math.sin(angle)
    rot = [
        (cx + (px - cx) * ca - (py - cy) * sa,
         cy + (px - cx) * sa + (py - cy) * ca)
        for px, py in polygon
    ]
    d.polygon(rot, fill=WHITE)
    # midrib vein
    tip = rot[0]
    base = rot[steps]
    d.line([base, tip], fill=GREEN, width=max(2, size // 64))


def make(size: int, name: str, maskable: bool = False) -> None:
    pad = 0.12 if maskable else 0.0   # maskable needs safe-zone padding
    img = _rounded_bg(size, pad_ratio=0.0 if maskable else 0.0)
    if maskable:
        # full-bleed green, leaf kept inside safe zone via smaller leaf
        img = Image.new("RGBA", (size, size), GREEN + (255,))
    _draw_leaf(img, size if not maskable else int(size * 0.78))
    if maskable:
        # redraw centered: easier to recompute on a fresh canvas
        img = Image.new("RGBA", (size, size), GREEN + (255,))
        inner = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        _draw_leaf(inner, int(size * 0.78))
        # center the smaller leaf
        img.alpha_composite(inner)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.convert("RGBA").save(OUT_DIR / name)
    print(f"  wrote {OUT_DIR / name}  ({size}x{size})")


if __name__ == "__main__":
    make(192, "icon-192.png")
    make(512, "icon-512.png")
    make(512, "icon-maskable-512.png", maskable=True)
    # Apple touch icon (no transparency, 180px)
    make(180, "apple-touch-icon.png")
    print("Done.")
