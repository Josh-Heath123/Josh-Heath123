"""
svg_ascii.py - helpers for turning ASCII frames into a self-contained SVG.

GitHub renders README images through <img>, so an SVG may not run scripts
or load anything from the network, but CSS animation inside it still plays.
Each frame is a <g>; one shared @keyframes rule shows a frame for 1/N of the
loop and every frame gets its own negative animation-delay. Rows that are
identical in every frame are drawn once, outside the frames.

Fonts are subset with fontTools and embedded as base64 WOFF2, so the grid
lines up the same way in every browser.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

FONTS = Path(__file__).parent / "fonts"


def font_face(family: str, file: str, text: str, weight: int = 400, unicode_range: str = "") -> str:
    """@font-face rule with a WOFF2 subset holding only the glyphs in text."""
    font = TTFont(FONTS / file)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6]  # keep the copyright/licence names
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(set(text + " "))))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    ur = f"unicode-range:{unicode_range};" if unicode_range else ""
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};{ur}"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")


def row_text(s: str, x0: float, y: float, cw: float, cls: str) -> str:
    """One row as a <text>, with leading blanks turned into an x offset."""
    stripped = s.rstrip()
    lead = len(stripped) - len(stripped.lstrip())
    body = stripped.lstrip()
    if not body:
        return ""
    # Interior blanks become no-break spaces: they keep their full advance
    # even in renderers that ignore xml:space / white-space:pre.
    body = escape(body).replace(" ", "\u00a0")
    return f'<text class="{cls}" x="{x0 + lead * cw:.1f}" y="{y:.1f}">{body}</text>'


def frames_svg(frames, layers, x0, y0, cw, ch, period, extra=None):
    """
    frames: list of frames; a frame is a list of rows; a row is a tuple of
            strings, one per layer.
    layers: CSS class name for each layer.
    extra:  optional list (one per frame) of SVG snippets drawn inside that
            frame, e.g. a frame counter.
    Returns (static_svg, animated_svg).
    """
    n = len(frames)
    rows = len(frames[0])
    static, per_frame = [], [[] for _ in range(n)]
    for li, cls in enumerate(layers):
        for r in range(rows):
            y = y0 + (r + 1) * ch
            variants = {fr[r][li] for fr in frames}
            if len(variants) == 1:
                static.append(row_text(frames[0][r][li], x0, y, cw, cls))
            else:
                for f in range(n):
                    per_frame[f].append(row_text(frames[f][r][li], x0, y, cw, cls))
    dt = period / n
    groups = []
    for f in range(n):
        body = "".join(per_frame[f]) + (extra[f] if extra else "")
        groups.append(f'<g class="f{" f0" if f == 0 else ""}" style="animation-delay:{f * dt - period:.3f}s">{body}</g>')
    return "".join(static), "".join(groups)


def frame_css(n: int, period: float) -> str:
    pct = 100.0 / n
    return (
        f".f{{visibility:hidden;animation:play {period:.3f}s step-end infinite}}"
        f"@keyframes play{{0%{{visibility:visible}}{pct:.4f}%{{visibility:hidden}}}}"
        "@media (prefers-reduced-motion:reduce){.f{animation:none}.f0{visibility:visible}}"
    )
