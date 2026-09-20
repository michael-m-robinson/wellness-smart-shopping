#!/usr/bin/env python3
"""Draw the backdrop for the install window.

A soft wash picked from the app icon, a hairline arrow from where the app sits
to where it is dropped, and the one instruction. Standard library only.

    python3 tools/make_dmg_art.py app/art/dmg-background.png
"""

import argparse
import math
import os
import struct
import sys
import zlib

WIDTH, HEIGHT = 700, 460
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


def blend(base, colour, alpha):
    return tuple(int(round(b + (c - b) * alpha)) for b, c in zip(base, colour))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
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

    # A hairline arrow between the two icons, sitting under their labels.
    ink = (0x4A, 0x6E, 0x72)
    y_mid, x_from, x_to = 214, 300, 404
    for x in range(x_from, x_to + 1):
        # Fade in and out so it reads as a hint, not a rule.
        edge = min(x - x_from, x_to - x) / 26.0
        a = 0.34 * min(1.0, edge)
        put(x, y_mid, ink, a)
        put(x, y_mid + 1, ink, a * 0.5)
    for i in range(13):
        a = 0.34 * (1 - i / 16.0)
        for d in (-1, 1):
            put(x_to - i, y_mid + d * i // 1, ink, a)
            put(x_to - i, y_mid + d * i // 1 + 1, ink, a * 0.4)

    write_png(args.out, px)
    print(f"  wrote {args.out} ({WIDTH}x{HEIGHT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
