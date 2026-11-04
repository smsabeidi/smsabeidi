#!/usr/bin/env python3
"""Turn a photo into the ASCII portrait on the hero sheet. Run locally, once.

    python3 scripts/portrait.py ~/photo.jpg

Cuts the background with rembg, pushes the tones high-key so skin stays open and
features stay dark, then picks, for every character cell, the glyph whose shape
and ink weight best match that patch of the image. The darkest cells get a second
strike, which is how line printers reached near-black on green-bar paper.

Writes data/portrait.json. The photo itself never enters this repository.
"""
from __future__ import annotations

import argparse
import io
import json
import string
from pathlib import Path

import cv2
import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GLYPHS = "".join(c for c in string.printable[:95] if not c.isspace())
CELL_W, CELL_H = 12, 20  # sampling grid per character, in the font's 3:5 box
DODGE_AND_BURN = (  # cx, cy, rx, ry, ink multiplier
    (430, 905, 250, 135, 0.45),  # open up the neck so the jaw and goatee separate
    (470, 548, 120, 48, 1.35),  # mouth
    (375, 345, 80, 30, 1.2),  # eyes
    (585, 360, 80, 30, 1.2),
)


def cut_out(photo: Path, box: tuple[int, int, int, int]) -> tuple[np.ndarray, np.ndarray]:
    from rembg import new_session, remove

    source = Image.open(photo).convert("RGB")
    cutout = remove(source, session=new_session("u2net_human_seg")).crop(box)
    rgba = np.asarray(cutout, dtype=np.float32)
    return rgba[..., :3], rgba[..., 3] / 255


def ink_map(rgb, alpha, black=3, white=93, clarity=1.0, sigma=16, knee=0.16, gamma=1.45, fade=0.84):
    """Desired ink per pixel, 0 for bare paper and 1 for solid black."""
    smooth = cv2.bilateralFilter(rgb.astype(np.uint8), 9, 34, 9)
    grey = cv2.cvtColor(smooth, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    low, high = np.percentile(grey[alpha > 0.6], [black, white])
    light = np.clip((grey - low) / (high - low), 0, 1)
    # Local contrast. The blur is masked so the background cannot halo the head.
    weight = cv2.GaussianBlur(alpha, (0, 0), sigma) + 1e-4
    local = cv2.GaussianBlur(light * alpha, (0, 0), sigma) / weight
    light = np.clip(light + clarity * (light - local), 0, 1)
    ink = np.clip((1 - light - knee) / (1 - knee), 0, 1) ** gamma * alpha
    height = ink.shape[0]
    falloff = np.clip((1 - np.arange(height) / height) / (1 - fade), 0, 1) ** 1.5
    return dodge_and_burn(ink * falloff[:, None])


def dodge_and_burn(ink: np.ndarray) -> np.ndarray:
    """Local exposure by hand, as in a darkroom. Tuned to the default crop."""
    y, x = np.mgrid[0 : ink.shape[0], 0 : ink.shape[1]].astype(np.float32)
    gain = np.ones_like(ink)
    for cx, cy, rx, ry, amount in DODGE_AND_BURN:
        spot = np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2) ** 1.5)
        gain *= 1 + (amount - 1) * spot
    return np.clip(ink * gain, 0, 1)


def load_font(path: Path) -> ImageFont.FreeTypeFont:
    font = TTFont(path)
    font.flavor = None
    buffer = io.BytesIO()
    font.save(buffer)
    buffer.seek(0)
    return ImageFont.truetype(buffer, round(CELL_W / 0.6))


def glyph_bitmaps(font: ImageFont.FreeTypeFont) -> np.ndarray:
    bitmaps = []
    for glyph in GLYPHS:
        canvas = Image.new("L", (CELL_W, CELL_H), 0)
        ImageDraw.Draw(canvas).text((CELL_W / 2, CELL_H * 0.78), glyph, fill=255, font=font, anchor="ms")
        bitmaps.append(np.asarray(canvas, dtype=np.float32).ravel() / 255)
    return np.stack(bitmaps)


def typeset(ink, cols, rows, kappa=0.56, weight=6.0, blank=0.035, overstrike=0.9):
    """Pick a glyph for every cell: shape error plus a penalty for wrong ink weight."""
    sampled = cv2.resize(ink, (cols * CELL_W, rows * CELL_H), interpolation=cv2.INTER_AREA)
    tone = cv2.resize(ink, (cols, rows), interpolation=cv2.INTER_AREA)
    regular = glyph_bitmaps(load_font(ROOT / "fonts/plex-mono-400.woff2"))
    bold = glyph_bitmaps(load_font(ROOT / "fonts/plex-mono-600.woff2"))
    candidates = np.concatenate([regular, bold])
    means = candidates.mean(axis=1)

    layers = {"regular": [], "bold": [], "over": []}
    for y in range(rows):
        line = {name: [" "] * cols for name in layers}
        for x in range(cols):
            if tone[y, x] < blank:
                continue
            patch = sampled[y * CELL_H : (y + 1) * CELL_H, x * CELL_W : (x + 1) * CELL_W].ravel() * kappa
            cost = ((candidates - patch) ** 2).mean(axis=1) + weight * (means - patch.mean()) ** 2
            best = int(cost.argmin())
            layer = "regular" if best < len(GLYPHS) else "bold"
            line[layer][x] = GLYPHS[best % len(GLYPHS)]
            if tone[y, x] >= overstrike:
                line["over"][x] = "M"
        for name, cells in line.items():
            layers[name].append("".join(cells).rstrip())
    return layers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photo", type=Path)
    parser.add_argument("--cols", type=int, default=154)
    parser.add_argument("--box", type=int, nargs=4, default=(150, 130, 1110, 1254), help="crop: left top right bottom")
    args = parser.parse_args()

    rgb, alpha = cut_out(args.photo, tuple(args.box))
    height, width = alpha.shape
    rows = round(args.cols * height / width * 0.6)
    portrait = {"cols": args.cols, "rows": rows, **typeset(ink_map(rgb, alpha), args.cols, rows)}
    (ROOT / "data/portrait.json").write_text(json.dumps(portrait, indent=0) + "\n")
    print(f"portrait: {args.cols} x {rows}")


if __name__ == "__main__":
    main()
