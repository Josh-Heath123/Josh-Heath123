"""
build_stages.py - writes assets/stages.svg, four panels showing how the
knight is made: the glyph outline, a slice of the distance field, the lit
render, and the same render as characters.

    python tools/build_stages.py

The README shows assets/stages.webp, a 2x export of this SVG: panels 2 and 3
are embedded PNGs, and a raster avoids any image proxy that refuses data:
URIs inside an SVG.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image

import knight
from svg_ascii import font_face, row_text

ROOT = Path(__file__).resolve().parent.parent
W, H = 960, 318
PW, PH = 200, 220            # panel size
GAP = (W - 4 * PW) / 5
TOP = 40
YAW = np.radians(28.0)
INK, BONE, DUST, MUTED, JAC = "#0c0b10", "#efe8da", "#8a83a3", "#8f889c", "#a08ae8"


def png_uri(rgb: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgb.astype(np.uint8)).save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def outline_panel(x0):
    """The glyph contours, scaled into the panel."""
    polys = [knight.HEAD, knight.EYE, knight.NOSTRIL, knight.MANE]
    allp = np.vstack(polys)
    lo, hi = allp.min(0), allp.max(0)
    s = 0.82 * min(PW / (hi[0] - lo[0]), PH / (hi[1] - lo[1]))
    cx = x0 + PW / 2 - s * (lo[0] + hi[0]) / 2
    cy = TOP + PH / 2 + s * (lo[1] + hi[1]) / 2
    out = []
    for i, p in enumerate(polys):
        pts = " ".join(f"{cx + s * x:.1f},{cy - s * y:.1f}" for x, y in p)
        out.append(f'<polygon points="{pts}" fill="none" stroke="{JAC if i == 0 else DUST}" '
                   f'stroke-width="{1.4 if i == 0 else 1}" stroke-linejoin="round"/>')
    for x, y in knight.HEAD[::4]:
        out.append(f'<circle cx="{cx + s * x:.1f}" cy="{cy - s * y:.1f}" r="1.6" fill="{BONE}"/>')
    return "".join(out)


def field_panel():
    """Side-on slice (z = 0) of the knight's distance field, as contour bands."""
    n = 2  # supersample
    xs = np.linspace(-1.05, 1.25, PW * n)
    ys = np.linspace(2.75, -0.05, PH * n)
    X, Y = np.meshgrid(xs, ys)
    d = knight.sd_knight(X, Y, np.zeros_like(X))
    ink, jac, bone = hexrgb(INK), hexrgb(JAC), hexrgb(BONE)
    band = 0.5 + 0.5 * np.cos(d * 2 * np.pi / 0.12)          # rings every 0.12 units
    fade = np.exp(-2.2 * np.abs(d))[..., None]
    outside = ink + (jac - ink) * (0.18 + 0.30 * band[..., None]) * fade
    inside = ink + (bone - ink) * (0.10 + 0.16 * band[..., None])
    rgb = np.where((d < 0)[..., None], inside, outside)
    rgb = np.where((np.abs(d) < 0.008)[..., None], bone, rgb)  # the zero set
    img = Image.fromarray(rgb.astype(np.uint8)).resize((PW, PH), Image.LANCZOS)
    return png_uri(np.asarray(img))


def lit_panel():
    """The lit render at one ray per pixel, before it becomes characters."""
    lp, lb, cov = knight.render_frame(YAW, PW, PH, ss=2, cell_aspect=1.0)
    lum = np.where(cov > 0.5, lp, lb * 1.4)
    g = (np.clip(lum, 0, 1) ** 0.9)[..., None]
    rgb = hexrgb(INK) + (hexrgb(BONE) - hexrgb(INK)) * g
    return png_uri(rgb)


def glyph_panel(x0):
    cols, rows = 46, 25
    frame = knight.to_glyphs(*knight.render_frame(YAW, cols, rows))
    fs = PW / cols / 0.6
    ch = PH / rows
    out = []
    for r, (hi, lo, bd) in enumerate(frame):
        y = TOP + (r + 1) * ch - 2
        for s, cls in ((hi, "hi"), (lo, "lo"), (bd, "bd")):
            out.append(row_text(s, x0, y, fs * 0.6, cls))
    return "".join(out), fs, "".join(c for row in frame for s in row for c in s)


def build(out: Path):
    xs = [GAP + i * (PW + GAP) for i in range(4)]
    glyphs, gfs, gtext = glyph_panel(xs[3])
    labels = [("01  outline", "DejaVu Sans U+265E"), ("02  distance field", "d(p) < 0 inside, rings every 0.12"),
              ("03  light", "key, rim, occlusion, shadow"), ("04  glyphs", "ramp  .,-~:;=!*#$@")]
    parts = []
    for i, x in enumerate(xs):
        parts.append(f'<rect x="{x - .5:.1f}" y="{TOP - .5}" width="{PW + 1}" height="{PH + 1}" rx="6" '
                     f'fill="none" stroke="#2a2537"/>')
        parts.append(f'<text class="lab" x="{x:.1f}" y="{TOP + PH + 22}">{escape(labels[i][0])}</text>')
        parts.append(f'<text class="cap" x="{x:.1f}" y="{TOP + PH + 38}">{escape(labels[i][1])}</text>')
        if i < 3:
            ax = x + PW + GAP / 2
            parts.append(f'<path d="M{ax - 6:.1f} {TOP + PH / 2} h12 m-4 -4 l4 4 l-4 4" fill="none" '
                         f'stroke="{MUTED}" stroke-width="1.2"/>')
    parts.append(outline_panel(xs[0]))
    parts.append(f'<image x="{xs[1]}" y="{TOP}" width="{PW}" height="{PH}" href="{field_panel()}"/>')
    parts.append(f'<image x="{xs[2]}" y="{TOP}" width="{PW}" height="{PH}" href="{lit_panel()}"/>')
    parts.append(glyphs)
    text = "".join(a + b for a, b in labels) + gtext + " "
    css = (font_face("JBM", "jetbrains-mono-latin-400-normal.woff2", text)
           + "text{white-space:pre;font-family:'JBM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
           + f".lab{{font-size:12px;fill:{BONE}}}.cap{{font-size:10.5px;fill:{MUTED}}}"
           + f".hi,.lo,.bd{{font-size:{gfs:.2f}px}}.hi{{fill:{BONE}}}.lo{{fill:{DUST}}}.bd{{fill:{JAC};opacity:.75}}")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" xml:space="preserve" role="img" aria-labelledby="t">
<title id="t">How the knight is made: the glyph outline, a slice of its distance field, the lit render, and the same render as ASCII characters.</title>
<defs><style>{css}</style><clipPath id="c"><rect width="{W}" height="{H}" rx="14"/></clipPath></defs>
<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{INK}"/>{"".join(parts)}</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="13.5" fill="none" stroke="#2a2537"/>
</svg>
'''
    out.write_text(svg, encoding="utf-8")
    print(f"{out}: {len(svg) / 1024:.0f} KiB")


if __name__ == "__main__":
    build(ROOT / "assets" / "stages.svg")
