#!/usr/bin/env python3
"""Generate the bundled image themes.

These images are drawn from scratch here rather than downloaded, so they carry
no third-party licence and can be redistributed freely with the project under
the same MIT terms. Pure standard library: shapes are signed-distance fields
rendered to a pixel buffer, which is then written as a PNG by hand.

    python3 tools/make_themes.py
"""

import math
import os
import struct
import zlib

W, H = 400, 600
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "themes")


# --------------------------------------------------------------------------- png
def write_png(path, pixels, width=W, height=H):
    """pixels: flat list of (r,g,b) tuples, row-major."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        for x in range(width):
            r, g, b = pixels[y * width + x]
            raw += bytes((r, g, b))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


# ------------------------------------------------------------------------ shapes
def circle(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) - r


def ellipse(cx, cy, rx, ry, rot=0.0):
    ct, st = math.cos(-rot), math.sin(-rot)

    def f(x, y):
        dx, dy = x - cx, y - cy
        ux, uy = dx * ct - dy * st, dx * st + dy * ct
        # normalised distance, scaled back so the falloff stays in pixels
        k = math.hypot(ux / rx, uy / ry)
        return (k - 1.0) * min(rx, ry)
    return f


def leaf(cx, cy, size, rot=0.0):
    """Two overlapping circles make a pointed leaf."""
    off = size * 0.55
    ct, st = math.cos(rot), math.sin(rot)
    ax, ay = cx - off * ct, cy - off * st
    bx, by = cx + off * ct, cy + off * st
    a, b = circle(ax, ay, size), circle(bx, by, size)
    return lambda x, y: max(a(x, y), b(x, y))


def blend(dst, src, alpha):
    return tuple(int(round(d + (s - d) * alpha)) for d, s in zip(dst, src))


def render(bg_top, bg_bottom, shapes, grain=3):
    """shapes: list of (sdf, colour, alpha, softness)."""
    px = []
    for y in range(H):
        t = y / (H - 1)
        # ease the gradient so it reads as light rather than a flat ramp
        e = t * t * (3 - 2 * t)
        base = tuple(int(round(a + (b - a) * e)) for a, b in zip(bg_top, bg_bottom))
        for x in range(W):
            c = base
            for sdf, colour, alpha, soft in shapes:
                d = sdf(x, y)
                if d < soft:
                    # smooth edge: 1 inside, 0 at the softness boundary
                    a = alpha if d <= -soft else alpha * (0.5 - 0.5 * math.sin(
                        math.pi * max(-1.0, min(1.0, d / soft)) / 2))
                    if a > 0.002:
                        c = blend(c, colour, a)
            if grain:
                n = ((x * 1103515245 + y * 12345) >> 8) % (grain * 2 + 1) - grain
                c = tuple(max(0, min(255, v + n)) for v in c)
            px.append(c)
    return px


# ------------------------------------------------------------------------ themes
def fresh_greens():
    leafy = (72, 138, 84)
    return render((233, 244, 232), (176, 214, 180), [
        (ellipse(200, 470, 230, 170), (200, 228, 199), 0.55, 40),
        (leaf(150, 250, 84, math.radians(-38)), leafy, 0.85, 2.0),
        (leaf(236, 300, 70, math.radians(28)), (94, 160, 102), 0.80, 2.0),
        (leaf(196, 180, 54, math.radians(-8)), (120, 182, 126), 0.70, 2.0),
        (circle(200, 392, 8), (58, 104, 66), 0.85, 1.5),
        (ellipse(200, 452, 5, 70), (58, 104, 66), 0.55, 1.5),
    ])


def farm_market():
    return render((253, 243, 227), (228, 196, 154), [
        (ellipse(200, 500, 250, 180), (243, 222, 190), 0.6, 45),
        (circle(148, 300, 62), (214, 96, 70), 0.88, 2.0),       # tomato
        (circle(252, 322, 54), (232, 154, 62), 0.88, 2.0),      # orange
        (circle(200, 232, 46), (150, 176, 92), 0.85, 2.0),      # greens
        (leaf(148, 232, 26, math.radians(-30)), (104, 148, 88), 0.9, 1.5),
        (ellipse(200, 402, 150, 26), (198, 154, 110), 0.5, 6),  # shelf
    ])


def citrus():
    return render((255, 249, 226), (250, 206, 122), [
        (circle(200, 300, 132), (250, 190, 78), 0.55, 30),
        (circle(200, 300, 96), (252, 208, 106), 0.9, 2.0),
        (circle(200, 300, 90), (255, 232, 168), 0.55, 2.0),
    ] + [
        # citrus segments
        (ellipse(200 + 60 * math.cos(a), 300 + 60 * math.sin(a), 30, 15, a),
         (250, 176, 66), 0.75, 2.0)
        for a in [math.radians(d) for d in range(0, 360, 45)]
    ] + [
        (leaf(268, 206, 34, math.radians(-40)), (126, 172, 96), 0.9, 1.5),
    ])


def berry():
    return render((243, 234, 247), (188, 158, 208), [
        (ellipse(200, 480, 240, 170), (212, 188, 226), 0.5, 40),
        (circle(166, 306, 50), (108, 66, 138), 0.88, 2.0),
        (circle(238, 286, 42), (138, 86, 164), 0.88, 2.0),
        (circle(206, 358, 36), (86, 52, 112), 0.85, 2.0),
        (leaf(200, 224, 40, math.radians(-15)), (112, 158, 104), 0.9, 1.5),
    ])


def harvest():
    return render((248, 238, 220), (206, 162, 112), [
        (ellipse(200, 500, 250, 175), (232, 208, 174), 0.55, 45),
        (circle(200, 318, 86), (206, 118, 56), 0.9, 2.0),       # squash
        (ellipse(200, 318, 26, 86), (222, 146, 80), 0.45, 3),
        (ellipse(200, 318, 58, 86), (222, 146, 80), 0.35, 3),
        (ellipse(200, 222, 10, 30), (122, 96, 62), 0.9, 1.5),   # stem
        (leaf(252, 234, 32, math.radians(30)), (140, 152, 86), 0.85, 1.5),
    ])


def ocean_calm():
    return render((232, 243, 248), (150, 194, 214), [
        (ellipse(200, 470, 250, 180), (186, 216, 230), 0.55, 45),
        (ellipse(200, 300, 120, 70, math.radians(-12)), (94, 150, 178), 0.85, 2.5),
        (ellipse(170, 288, 40, 26, math.radians(-12)), (196, 226, 238), 0.55, 2.5),
        (circle(250, 286, 7), (238, 248, 252), 0.9, 1.2),
        (ellipse(200, 402, 160, 16), (120, 168, 192), 0.45, 8),
    ])


THEMES = {
    "fresh-greens": (fresh_greens, "Leafy greens on a soft light wash"),
    "farm-market":  (farm_market, "Warm market stall with tomato and citrus"),
    "citrus":       (citrus, "Bright citrus slice"),
    "berry":        (berry, "Deep berry tones"),
    "harvest":      (harvest, "Autumn squash and earth tones"),
    "ocean-calm":   (ocean_calm, "Cool blues, calm and clean"),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, (fn, desc) in THEMES.items():
        path = os.path.join(OUT, f"{name}.png")
        write_png(path, fn())
        print(f"  {name:14} {os.path.getsize(path)//1024:4} KB  {desc}")
    with open(os.path.join(OUT, "THEMES.json"), "w") as fh:
        import json
        json.dump({n: d for n, (_, d) in THEMES.items()}, fh, indent=2)
    print(f"\nWrote {len(THEMES)} themes to {OUT}")


if __name__ == "__main__":
    main()
