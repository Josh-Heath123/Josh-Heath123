"""
build_hero.py - writes assets/hero.svg, the animated header of the profile.

    python tools/build_hero.py            # 72 frames, about 3 minutes
    python tools/build_hero.py --frames 12 --out /tmp/test.svg

Also writes hero-still.svg (frame 0, no animation) next to it.

Left: a man-page style header and the name. Right: the knight from
knight.py turning once every 5.76 s, with a live readout of the yaw angle
and frame number underneath.
"""

from __future__ import annotations

import argparse
from multiprocessing import Pool
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import knight
from svg_ascii import font_face, frame_css, frames_svg

ROOT = Path(__file__).resolve().parent.parent

W, H = 960, 600
COLS, ROWS = 108, 62
FS = 8.0                    # art font size in px
CW, CH = FS * 0.6, 9.2      # JetBrains Mono advance is 0.6 em
ART_X, ART_Y = 414.0, 4.0
START_DEG = 28.0            # frame 0, also the reduced-motion still

INK, BONE, DUST, MUTED, JAC = "#0c0b10", "#efe8da", "#8a83a3", "#8f889c", "#a08ae8"


def _frame(i_n):
    i, n = i_n
    theta = np.radians(START_DEG + 360.0 * i / n)
    return knight.to_glyphs(*knight.render_frame(theta, COLS, ROWS))


def text(x, y, s, cls, anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text class="{cls}" x="{x}" y="{y}"{a}>{escape(s)}</text>'


def build(n_frames: int, out: Path):
    with Pool() as pool:
        frames = pool.map(_frame, [(i, n_frames) for i in range(n_frames)])
    write(frames, out, animated=True)
    # The README swaps this in through <picture> for prefers-reduced-motion,
    # because a media query inside an SVG loaded as an <img> is not reliable.
    write(frames, out.with_name(out.stem + "-still.svg"), animated=False)


def write(frames, out: Path, animated: bool):
    n_frames = len(frames)
    period = round(0.08 * n_frames, 3)
    hud_y = ART_Y + (ROWS + 1) * CH + 6
    readout = [text(ART_X + 8, hud_y, f"yaw {(START_DEG + 360 * i / n_frames) % 360:05.1f}\u00b0  "
                    f"frame {i + 1:02d}/{n_frames}", "hud") for i in range(n_frames)]
    if animated:
        static_art, animated_art = frames_svg(frames, ["hi", "lo", "bd"], ART_X, ART_Y, CW, CH, period, readout)
    else:
        static_art, _ = frames_svg(frames[:1], ["hi", "lo", "bd"], ART_X, ART_Y, CW, CH, period)
        animated_art = readout[0]

    lx = 52
    left = [
        text(lx, 50, "JOSH(1)", "man"),
        text(W - 40, 50, "JOSH(1)", "man", "end"),
        text(W / 2, 50, "General Commands Manual", "man", "middle"),
        text(lx - 4, 200, "Joshua", "name"),
        text(lx - 4, 274, "Heath", "name"),
        text(lx, 318, "Computer Science · University of Pretoria", "sub"),
        text(lx, 370, "Full stack, with a focus on data: the", "body"),
        text(lx, 390, "pipeline, the API and the interface,", "body"),
        text(lx, 410, "taken all the way to production.", "body"),
    ]
    spec = [("CAPSTONE", "EquityLens, client AWS"), ("STUDYING", "BSc CS, class of 2026"),
            ("BASED", "Pretoria, South Africa"), ("MOVES", "two forward, one across")]
    for k, (key, val) in enumerate(spec):
        y = 470 + k * 21
        left.append(text(lx, y, key, "key"))
        left.append(text(lx + 86, y, val, "val"))
    cursor_x = lx + 86 + len(spec[-1][1]) * 7.2 + 4
    left.append(f'<rect class="cur" x="{cursor_x:.1f}" y="{470 + 3 * 21 - 10}" width="7" height="12"/>')
    left.append(text(ART_X + 8 + 25 * CW * 1.25, hud_y, "sdf raymarch · ramp .,-~:;=!*#$@", "hud"))

    all_text = "".join(t for fr in frames for row in fr for t in row) + "".join(
        [s for _, s in spec] + [k for k, _ in spec]) + \
        "JOSH(1)General Commands ManualComputer Science · University of PretoriaFull stack, with a focus on data: " \
        "\u00a0thepipeline, the API and the interface,taken all the way to production.yaw frame 0123456789/.°" \
        "sdf raymarch · ramp .,-~:;=!*#$@"
    css = (
        font_face("JBM", "jetbrains-mono-latin-400-normal.woff2", all_text)
        + font_face("JBM", "jetbrains-mono-latin-700-normal.woff2", "JoshuaHeath", 700)
        + "text{white-space:pre;font-family:'JBM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
        + f".hi,.lo,.bd{{font-size:{FS}px}}.hi{{fill:{BONE}}}.lo{{fill:{DUST}}}.bd{{fill:{JAC};opacity:.75}}"
        + f".man{{font-size:11px;fill:{MUTED};letter-spacing:.5px}}"
        + f".name{{font-size:72px;font-weight:700;fill:{BONE};letter-spacing:-2px}}"
        + f".sub{{font-size:13px;fill:{JAC}}}.body{{font-size:13px;fill:#cfc8bb}}"
        + f".key{{font-size:12px;fill:{MUTED};letter-spacing:1px}}.val{{font-size:12px;fill:{BONE}}}"
        + f".hud{{font-size:10px;fill:{MUTED}}}"
        + f".cur{{fill:{JAC}}}"
        + (".cur{animation:blink 1.1s step-end infinite}@keyframes blink{50%{opacity:0}}"
           + frame_css(n_frames, period) if animated else "")
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" xml:space="preserve" role="img" aria-labelledby="t d">
<title id="t">Joshua Heath</title>
<desc id="d">A chess knight drawn in ASCII characters {'turns slowly' if animated else 'stands'} on a checkerboard, next to the name Joshua Heath, Computer Science, University of Pretoria.</desc>
<defs>
<style>{css}</style>
<radialGradient id="glow" cx="72%" cy="62%" r="55%"><stop offset="0" stop-color="#1b1726"/><stop offset="1" stop-color="{INK}"/></radialGradient>
<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".022"/></pattern>
<clipPath id="panel"><rect width="{W}" height="{H}" rx="14"/></clipPath>
</defs>
<g clip-path="url(#panel)">
<rect width="{W}" height="{H}" fill="url(#glow)"/>
{static_art}{animated_art}
{"".join(left)}
<rect width="{W}" height="{H}" fill="url(#scan)"/>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="13.5" fill="none" stroke="#2a2537"/>
</svg>
'''
    out.write_text(svg, encoding="utf-8")
    size = len(svg.encode("utf-8")) / 1024
    print(f"{out.name}: {size:.0f} KiB" + (f", {n_frames} frames, {period}s loop" if animated else ", still"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=72)
    ap.add_argument("--out", type=Path, default=ROOT / "assets" / "hero.svg")
    args = ap.parse_args()
    build(args.frames, args.out)
