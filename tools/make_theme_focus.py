#!/usr/bin/env python3
"""Work out which part of each theme image should stay in the banner.

The banner is a wide, short strip, so a square photo loses most of its height.
Centring blindly cuts faces in half. This measures where the detail actually
is -- faces, produce and text carry fine detail, while sky, walls and blurred
backgrounds do not -- and records that as a focal point for CSS object-position.

    python3 tools/make_theme_focus.py themes

Writes the "focus" values back into themes/THEMES.json.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_icon import read_png  # noqa: E402

SAMPLE_HEIGHT = 120


def detail_by_row(rows):
    """Per-row detail: how much neighbouring pixels differ across the row."""
    scores = []
    for row in rows:
        total = 0
        for x in range(1, len(row)):
            r1, g1, b1, _ = row[x - 1]
            r2, g2, b2, _ = row[x]
            total += abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
        scores.append(total / max(1, len(row) - 1))
    return scores


def focal_percent(scores):
    """Centre of mass of the detail, as a percentage down the image."""
    if not scores:
        return 50.0
    floor = min(scores)
    weights = [s - floor for s in scores]
    total = sum(weights)
    if total <= 0:
        return 50.0
    centre = sum(i * w for i, w in enumerate(weights)) / total
    percent = centre / max(1, len(scores) - 1) * 100.0
    # A banner crops around this point, so keep it off the very edges or the
    # crop has nothing to work with on one side.
    return round(max(20.0, min(80.0, percent)), 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("themes", nargs="?", default="themes")
    args = ap.parse_args(argv)

    meta_path = os.path.join(args.themes, "THEMES.json")
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)

    focus = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in sorted(os.listdir(args.themes)):
            stem, ext = os.path.splitext(name)
            if ext.lower() not in (".png", ".jpg", ".jpeg"):
                continue
            src = os.path.join(args.themes, name)
            small = os.path.join(tmp, f"{stem}.png")
            result = subprocess.run(
                ["sips", "-s", "format", "png", "-Z", str(SAMPLE_HEIGHT), src,
                 "--out", small], capture_output=True)
            if result.returncode != 0 or not os.path.isfile(small):
                continue
            try:
                _, _, rows = read_png(small)
            except Exception:
                continue
            focus[stem] = focal_percent(detail_by_row(rows))
            print(f"  {stem:16} focus {focus[stem]:5.1f}%")

    # THEMES.json holds a description per theme; keep that shape and add focus.
    out = {}
    for stem, value in focus.items():
        existing = meta.get(stem)
        description = existing if isinstance(existing, str) else (
            (existing or {}).get("description", "Your own image"))
        out[stem] = {"description": description, "focus": value}
    for stem, existing in meta.items():
        if stem not in out:
            out[stem] = existing

    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n  wrote {meta_path} ({len(focus)} themes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
