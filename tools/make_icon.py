#!/usr/bin/env python3
"""Turn a square artwork into a macOS .icns (and the images the disk image needs).

The source art is usually a rounded tile floating on white, sometimes with a
reflection under it. macOS wants the tile itself, corner-rounded and on
transparency, so this finds the artwork, drops the reflection, rounds the
corners and renders every size the system asks for.

    python3 tools/make_icon.py app/art/icon-source.png app/Resources/AppIcon.icns

Standard library only: PNG is read and written here rather than pulled in.
"""

import argparse
import os
import struct
import subprocess
import sys
import tempfile
import zlib


# ----------------------------------------------------------------- png codec
def read_png(path):
    """Return (width, height, rows) with rows as lists of (r,g,b,a)."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    pos, idat, width = 8, bytearray(), None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlace or colour not in (2, 6):
                raise ValueError("expected an 8-bit RGB or RGBA, non-interlaced PNG")
            channels = 3 if colour == 2 else 4
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
        pos += 12 + length
    if width is None:
        raise ValueError("no IHDR")

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    rows, previous, at = [], bytearray(stride), 0
    for _ in range(height):
        filter_type = raw[at]; at += 1
        line = bytearray(raw[at:at + stride]); at += stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = previous[i]
            c = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                line[i] = (line[i] + a) & 0xFF
            elif filter_type == 2:
                line[i] = (line[i] + b) & 0xFF
            elif filter_type == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 0xFF
            elif filter_type == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        previous = line
        if channels == 3:
            rows.append([(line[i], line[i + 1], line[i + 2], 255)
                         for i in range(0, stride, 3)])
        else:
            rows.append([(line[i], line[i + 1], line[i + 2], line[i + 3])
                         for i in range(0, stride, 4)])
    return width, height, rows


def write_png(path, rows):
    height = len(rows)
    width = len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n"
                 + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                 + chunk(b"IEND", b""))


# ------------------------------------------------------------------ shaping
def content_bounds(rows, tolerance=246):
    """Bounding box of everything that is not the white surround."""
    height, width = len(rows), len(rows[0])
    top, left, right, bottom = height, width, -1, -1
    for y in range(height):
        row = rows[y]
        for x in range(width):
            r, g, b, a = row[x]
            if a > 8 and not (r >= tolerance and g >= tolerance and b >= tolerance):
                if y < top: top = y
                if y > bottom: bottom = y
                if x < left: left = x
                if x > right: right = x
    if bottom < 0:
        raise ValueError("the image looks blank")
    return left, top, right, bottom


def square_off(left, top, right, bottom):
    """Keep the tile, drop any reflection beneath it.

    These tiles are square and sit at the top of the artwork, with an optional
    faint echo below. A row-profile split was tried first and failed: the echo
    blends straight into the tile with no empty rows between them. Squaring on
    the width, anchored at the top, is both simpler and reliable.
    """
    width = right - left + 1
    height = bottom - top + 1
    if height > width:
        bottom = top + width - 1
    elif width > height:
        right = left + height - 1
    return left, top, right, bottom


def crop(rows, left, top, right, bottom):
    return [row[left:right + 1] for row in rows[top:bottom + 1]]


def round_corners(rows, radius_ratio=0.225, feather=1.4):
    """macOS icons are rounded tiles on transparency, not hard squares."""
    height, width = len(rows), len(rows[0])
    radius = min(width, height) * radius_ratio
    out = []
    for y in range(height):
        line = []
        for x in range(width):
            r, g, b, a = rows[y][x]
            # Distance outside the rounded rectangle, for the four corners only.
            dx = max(radius - x, x - (width - 1 - radius), 0.0)
            dy = max(radius - y, y - (height - 1 - radius), 0.0)
            if dx > 0 and dy > 0:
                distance = (dx * dx + dy * dy) ** 0.5
                if distance >= radius + feather:
                    alpha = 0.0
                elif distance <= radius - feather:
                    alpha = 1.0
                else:
                    alpha = (radius + feather - distance) / (2 * feather)
                a = int(round(a * alpha))
            line.append((r, g, b, a))
        out.append(line)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("icns")
    ap.add_argument("--png", help="also write the squared-off artwork here")
    ap.add_argument("--no-round", action="store_true",
                    help="keep hard corners (the art already has its own)")
    args = ap.parse_args(argv)

    width, height, rows = read_png(args.source)
    box = square_off(*content_bounds(rows))
    tile = crop(rows, *box)
    print(f"  artwork {width}x{height} -> tile {len(tile[0])}x{len(tile)}")
    if not args.no_round:
        tile = round_corners(tile)

    with tempfile.TemporaryDirectory() as tmp:
        master = os.path.join(tmp, "master.png")
        write_png(master, tile)
        if args.png:
            os.makedirs(os.path.dirname(os.path.abspath(args.png)), exist_ok=True)
            write_png(args.png, tile)

        iconset = os.path.join(tmp, "icon.iconset")
        os.makedirs(iconset)
        for size in (16, 32, 64, 128, 256, 512):
            for scale, suffix in ((1, ""), (2, "@2x")):
                px = size * scale
                out = os.path.join(iconset, f"icon_{size}x{size}{suffix}.png")
                subprocess.run(["sips", "-s", "format", "png", "-z", str(px), str(px),
                                master, "--out", out], check=True, capture_output=True)
        os.makedirs(os.path.dirname(os.path.abspath(args.icns)), exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", args.icns],
                       check=True, capture_output=True)
    size_kb = os.path.getsize(args.icns) // 1024
    print(f"  wrote {args.icns} ({size_kb} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
