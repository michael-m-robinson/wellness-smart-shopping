#!/usr/bin/env python3
"""Draw the backdrop for the install window.

A soft wash picked from the app icon, a hairline arrow from where the app sits
to where it is dropped, and the one instruction. Standard library only.

    python3 tools/make_dmg_art.py app/art/dmg-background.png
"""

import argparse
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_icon import content_bounds, crop, read_png  # noqa: E402

WIDTH, HEIGHT = 700, 460
# The gap between the two icons, in the window's own coordinates.
ARROW_CENTRE = (349, 196)
ARROW_WIDTH = 168
# Sampled from the icon: green on the left, blue on the right.
GREEN = (0x3F, 0xB9, 0x8B)
BLUE = (0x2E, 0x96, 0xD8)


def write_png(path, pixels, width=WIDTH, height=HEIGHT):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw += bytes(pixels[y * width + x])

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n"
                 + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                 + chunk(b"IEND", b""))


def box_scale(rows, target_width):
    """Area-average down to a target width, keeping the aspect ratio.

    The artwork is several times larger than it will be shown, so averaging
    each destination pixel over the source block it covers keeps the edges
    clean where nearest-neighbour would break them up.
    """
    height, width = len(rows), len(rows[0])
    scale = target_width / float(width)
    target_height = max(1, int(round(height * scale)))
    out = []
    for ty in range(target_height):
        y0 = int(ty * height / target_height)
        y1 = max(y0 + 1, int((ty + 1) * height / target_height))
        line = []
        for tx in range(target_width):
            x0 = int(tx * width / target_width)
            x1 = max(x0 + 1, int((tx + 1) * width / target_width))
            r = g = b = a = n = 0
            for sy in range(y0, y1):
                row = rows[sy]
                for sx in range(x0, x1):
                    pr, pg, pb, pa = row[sx]
                    # Weight colour by alpha so transparent pixels do not
                    # wash the edges toward black.
                    r += pr * pa; g += pg * pa; b += pb * pa
                    a += pa; n += 1
            if a:
                line.append((r // a, g // a, b // a, a // n))
            else:
                line.append((0, 0, 0, 0))
        out.append(line)
    return out


def blend(base, colour, alpha):
    return tuple(int(round(b + (c - b) * alpha)) for b, c in zip(base, colour))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--arrow", help="artwork to place between the two icons")
    args = ap.parse_args(argv)

    px = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            # Very pale diagonal wash, so icon labels stay readable on it.
            t = (x / WIDTH) * 0.75 + (y / HEIGHT) * 0.25
            tint = blend(GREEN, BLUE, t)
            colour = blend((255, 255, 255), tint, 0.10)
            px.append(list(colour))

    def put(x, y, colour, alpha):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and alpha > 0:
            i = y * WIDTH + x
            px[i] = list(blend(px[i], colour, min(1.0, alpha)))

    if args.arrow and os.path.isfile(args.arrow):
        tile = crop(*((read_png(args.arrow)[2],) + content_bounds(read_png(args.arrow)[2])))
        scaled = box_scale(tile, ARROW_WIDTH)
        oy = ARROW_CENTRE[1] - len(scaled) // 2
        ox = ARROW_CENTRE[0] - len(scaled[0]) // 2
        for y, row in enumerate(scaled):
            for x, (r, g, b, a) in enumerate(row):
                put(ox + x, oy + y, (r, g, b), a / 255.0)
        print(f"  arrow {len(scaled[0])}x{len(scaled)} at {ARROW_CENTRE}")

    write_png(args.out, px)
    print(f"  wrote {args.out} ({WIDTH}x{HEIGHT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
