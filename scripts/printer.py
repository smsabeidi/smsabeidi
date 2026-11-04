"""Line-printer primitives: green-bar paper, ribbon ink, banner letters, the feed.

Everything here returns SVG strings. GitHub renders a README's images through an
<img>, so nothing outside the file can reach them: no scripts, no web fonts, no
linked styles. Type and motion therefore live inside each SVG, and the fonts
travel with it as base64.
"""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LINE = 18  # one printed line; three of them make one green bar, as on real stock
BAR = LINE * 3
HOLE_PITCH = LINE * 2

# Plain continuous stationery. Both themes keep a real sheet of paper, because
# paper doesn't turn black at night. The dark one only dims it so it doesn't glare.
THEMES = {
    "light": {"paper": "#fbfdfa", "bar": "#dcefe0", "edge": "#b9cdbe", "preprint": "#7fae8c", "ink": "#1c2733", "red": "#c2201a"},
    "dark": {"paper": "#e8ede6", "bar": "#cbe2d1", "edge": "#9fb8a6", "preprint": "#6f9c7c", "ink": "#1c2733", "red": "#b51c16"},
}

# 5x7 dot-matrix capitals for the banner page that opens every print job.
BANNER = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
}


def font_face() -> str:
    faces = []
    for weight in (400, 600):
        data = base64.b64encode((ROOT / f"fonts/plex-mono-{weight}.woff2").read_bytes()).decode()
        faces.append(f"@font-face{{font-family:Plex;font-weight:{weight};src:url(data:font/woff2;base64,{data})}}")
    return "".join(faces)


def text(x: float, y: float, content: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f'<text x="{x:g}" y="{y:g}"{attr}>{escape(content, quote=False)}</text>'


def layer(rows: list[str], x: float, y: float, advance: float, line: float) -> str:
    """Rows of art as compact <text> runs. Leading blanks become an x offset."""
    runs = []
    for index, row in enumerate(rows):
        body = row.lstrip(" ")
        if body:
            indent = x + (len(row) - len(body)) * advance
            runs.append(f'<text x="{indent:.1f}" y="{y + index * line:.1f}">{escape(body, quote=False)}</text>')
    return "".join(runs)


def banner(word: str, x: float, y: float, cell_w: float, cell_h: float) -> str:
    """Big letters built from the letter itself, like a job's banner page."""
    rows = [" ".join(BANNER[ch][r].replace("0", " ").replace("1", ch) for ch in word) for r in range(7)]
    return f'<g class="banner">{layer(rows, x, y, cell_w, cell_h)}</g>'


def perforated(width: float, y: float, colour: str) -> str:
    return f'<path d="M0 {y}H{width}" stroke="{colour}" stroke-dasharray="2 3" fill="none"/>'


def paper(width: int, height: int, theme: dict, margin: int = 28) -> str:
    """A fan-fold sheet: tractor holes punched through, bars between the margins."""
    edge = theme["edge"]
    outline = f"M0 0H{width}V{height}H0Z"
    radius = 3.6 if margin >= 24 else 2.8
    for x in (margin / 2, width - margin / 2):
        y = HOLE_PITCH / 2
        while y < height:
            outline += f"M{x - radius} {y}a{radius} {radius} 0 1 0 {2 * radius} 0a{radius} {radius} 0 1 0 {-2 * radius} 0Z"
            y += HOLE_PITCH
    bars = "".join(
        f'<rect x="{margin}" y="{y}" width="{width - 2 * margin}" height="{BAR}" fill="{theme["bar"]}"/>'
        for y in range(BAR, height, BAR * 2)
    )
    return (
        f'<path d="{outline}" fill="{theme["paper"]}" fill-rule="evenodd" stroke="{edge}"/>{bars}'
        f'<path d="M{margin} 0V{height}M{width - margin} 0V{height}" stroke="{edge}" stroke-dasharray="1 3" fill="none"/>'
        f'{perforated(width, 0.5, edge)}{perforated(width, height - 0.5, edge)}'
    )


def base_css(theme: dict) -> str:
    return (
        font_face()
        + f"text{{font-family:Plex,ui-monospace,Menlo,Consolas,monospace;fill:{theme['ink']};white-space:pre}}"
        + f".red{{fill:{theme['red']}}}.strong{{font-weight:600}}.pre{{fill:{theme['preprint']}}}"
    )


def document(width: int, height: int, css: str, body: str, title: str, desc: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'role="img" aria-labelledby="t d"><title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>'
        f"<style>{css}</style>{body}</svg>\n"
    )
