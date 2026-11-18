"""
build_hero.py - writes the animated header: an ASCII jellyfish above the name.

    python tools/build_hero.py                  # assets/hero.svg, hero-m.svg and the stills
    python tools/build_hero.py --frames 24      # a quicker, choppier test build
    python tools/build_hero.py --mono           # the jellyfish in greys instead of colour

GitHub shows README images through <img>: no script, no external files, but
CSS animation and SMIL both play. So the file is built in layers:

  frames     one <g> per frame of jelly.py's simulation (one beat, 2 s),
             shown in turn by a CSS step animation, as in svg_ascii.py
  colour     every glyph is painted by channel (bell, rim, arms, tentacles...)
             with a vertical gradient whose stops are animated by SMIL over
             six beats. On each beat a white-hot front runs down the body
             and leaves the next palette behind it. Colour is animated once
             for the whole file, not baked into each frame, which keeps the
             file small and lets the colour cycle (12 s) outlast the motion
             loop (2 s).
  bloom      a blur of the frames, merged back under them
  scene      faint drifting streaks, twinkling sparks and small jellyfish in
             the distance, animated with plain CSS transforms
  intro      the first time it plays, the animal is drawn in from the top

Writes hero.svg (960 wide) and hero-m.svg (480 wide, for phones), plus a
-still version of each for prefers-reduced-motion.
"""

from __future__ import annotations

import argparse
import colorsys
import math
import random
from multiprocessing import Pool
from pathlib import Path
from xml.sax.saxutils import escape

import jelly
from svg_ascii import font_face

ROOT = Path(__file__).resolve().parent.parent
PERIOD = 2.0          # one beat, and one motion loop
BEATS = 6             # palettes in the colour cycle
CYCLE = PERIOD * BEATS
SWEEP = 1.1           # seconds for the white-hot front to run from bell to tips

# Palettes, one per beat: for each channel, colours at the top, middle and bottom
# of the body. Picked from the reference recording: blue, cyan and pink,
# magenta and cyan, green and orange, red and violet, indigo and gold.
PALETTES = [
    dict(bell=("#a9bcff", "#4560f5", "#5a3fd8"), accent=("#c3a8ff", "#8b6cff", "#6f4fe6"),
         arm=("#8f7cff", "#7d6af2", "#5c4fd0"), armhi=("#d4c8ff", "#b9a8ff", "#9a88f0"),
         tent=("#aebfe8", "#8fa2d8", "#56618f")),
    dict(bell=("#7ff0f7", "#3c93f2", "#6a4fe6"), accent=("#e08cff", "#c06cf0", "#8a5ce8"),
         arm=("#ff6fb4", "#ff4f9f", "#d63f86"), armhi=("#ffc6e2", "#ffa3cf", "#f07ab4"),
         tent=("#bcd2ec", "#9ab4dc", "#5b6a94")),
    dict(bell=("#ff86d8", "#b552ea", "#6c48e2"), accent=("#ffb3e6", "#ff86d0", "#c85ce0"),
         arm=("#56e0f2", "#3fd0ec", "#2fa3d0"), armhi=("#c4f7ff", "#a0efff", "#70d8f0"),
         tent=("#dcc4ee", "#c4a6e2", "#6e5a96")),
    dict(bell=("#93f59f", "#33c8a6", "#2f80e2"), accent=("#dcf57a", "#b4ee6a", "#5ad89a"),
         arm=("#ffa548", "#ff8f2e", "#e0701f"), armhi=("#ffdca0", "#ffc678", "#f0a050"),
         tent=("#c6e2d2", "#a6ccbc", "#5c7a74")),
    dict(bell=("#ff6a46", "#ffa23e", "#d65a32"), accent=("#ffd75a", "#ffc23a", "#ff8a3a"),
         arm=("#b28aff", "#9a6cf5", "#7a50d8"), armhi=("#e0d0ff", "#c8b2ff", "#a68af0"),
         tent=("#f0d4b4", "#dcb894", "#8a6a5a")),
    dict(bell=("#9a80ff", "#4f60f2", "#3a40d2"), accent=("#d08aff", "#b46cf0", "#7a54e0"),
         arm=("#ffe060", "#ffd23a", "#e0ae20"), armhi=("#fff4b8", "#ffeb8a", "#f0d060"),
         tent=("#d6d0ac", "#bcb48c", "#6c6650")),
]

# CSS class per channel, and which palette entry paints it.
CHANNELS = {
    jelly.BELL: ("b", "bell"), jelly.ACCENT: ("a", "accent"), jelly.EDGE: ("e", "edge"),
    jelly.INNER: ("i", "inner"), jelly.ARM: ("r", "arm"), jelly.ARMHI: ("h", "armhi"),
    jelly.TENT: ("t", "tent"), jelly.GLINT: ("g", None),
}

INK, PAPER, GREY, MUTED, LINE = "#000000", "#fafafa", "#a1a1a1", "#6f6f6f", "#262626"


# ---- colour helpers -----------------------------------------------------------

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hexc(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in c)


def mix(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def grey(c):
    y = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    y = 0.25 + 0.75 * y ** 0.8
    return (y, y, y)


def palette_colour(p, name, u, mono):
    """Colour of channel `name` in palette p at body position u (0 top .. 1 bottom)."""
    pal = PALETTES[p]
    if name in ("edge", "inner"):
        base = palette_colour(p, "bell", u, False)
        c = mix(base, (1, 1, 1), 0.55) if name == "edge" else mix(grey(base), base, 0.45)
        if name == "inner":
            c = mix(c, (1, 1, 1), 0.15)
    else:
        top, mid, bot = (rgb(x) for x in pal[name])
        # the bell's gradient runs over the top third of the body; arms and
        # tentacles over the rest
        if name in ("bell", "accent"):
            k = min(1.0, u / 0.36)
        else:
            k = min(1.0, max(0.0, (u - 0.28) / 0.72))
        c = mix(top, mid, k / 0.5) if k < 0.5 else mix(mid, bot, (k - 0.5) / 0.5)
    return grey(c) if mono else c


def stop_animation(name, u, mono):
    """SMIL values/keyTimes for one gradient stop over the whole colour cycle."""
    t_hit = u * SWEEP                 # when the front reaches this stop, into each beat
    keys, vals = [], []
    for b in range(BEATS):
        old = palette_colour((b - 1) % BEATS, name, u, mono)
        new = palette_colour(b, name, u, mono)
        hot = mix(new, (1, 1, 1), 0.78)
        t0 = b * PERIOD
        for dt, c in ((0.0, old), (max(0.0, t_hit - 0.03), old), (t_hit + 0.07, hot), (t_hit + 0.42, new)):
            keys.append((t0 + dt) / CYCLE)
            vals.append(hexc(c))
    keys.append(1.0)
    vals.append(vals[0])
    # keyTimes must not decrease; tidy the rounding
    out_k, last = [], -1.0
    for k in keys:
        k = max(k, last)
        out_k.append(k)
        last = k
    return ";".join(f"{k:.4f}" for k in out_k), ";".join(vals)


def gradients(y_top, y_bot, mono, animated, stops=11):
    out = []
    for _, (cls, name) in CHANNELS.items():
        if name is None:
            continue
        g = [f'<linearGradient id="g{cls}" gradientUnits="userSpaceOnUse" x1="0" y1="{y_top:.1f}" x2="0" y2="{y_bot:.1f}">']
        for j in range(stops):
            u = j / (stops - 1)
            first = hexc(palette_colour(0, name, u, mono))
            if animated:
                kt, vals = stop_animation(name, u, mono)
                g.append(f'<stop offset="{u:.2f}" stop-color="{first}"><animate attributeName="stop-color" '
                         f'dur="{CYCLE:g}s" repeatCount="indefinite" calcMode="linear" keyTimes="{kt}" values="{vals}"/></stop>')
            else:
                g.append(f'<stop offset="{u:.2f}" stop-color="{first}"/>')
        g.append("</linearGradient>")
        out.append("".join(g))
    return "".join(out)


# ---- frames -------------------------------------------------------------------

def _frame(args):
    lay, i, n = args
    g, ch, info = jelly.frame(lay, i * PERIOD / n, PERIOD)
    return g, ch


def row_svg(glyphs, chans, y, x0, cw):
    """One row: runs of one channel, each new segment placed with x."""
    cols = len(glyphs)
    parts, c = [], 0
    while c < cols:
        if chans[c] == 0 or glyphs[c] == " ":
            c += 1
            continue
        # a segment: glyphs and short gaps (< 4 blanks) of any channel
        start = c
        seg = []
        cur_cls, buf = None, []
        while c < cols:
            if chans[c] == 0 or glyphs[c] == " ":
                gap = 0
                while c + gap < cols and (chans[c + gap] == 0 or glyphs[c + gap] == " "):
                    gap += 1
                if c + gap >= cols or gap >= 4:
                    break
                buf.append(" " * gap)
                c += gap
                continue
            cls = CHANNELS[int(chans[c])][0]
            if cls != cur_cls:
                if buf:
                    seg.append((cur_cls, "".join(buf)))
                cur_cls, buf = cls, []
            buf.append(escape(glyphs[c]))
            c += 1
        if buf:
            seg.append((cur_cls, "".join(buf)))
        x = f"{x0 + start * cw:.1f}"
        for k, (cls, s) in enumerate(seg):
            xa = f' x="{x}"' if k == 0 else ""
            parts.append(f'<tspan class="{cls}"{xa}>{s}</tspan>')
    if not parts:
        return ""
    return f'<text y="{y:.1f}">{"".join(parts)}</text>'


def frame_group(frame, x0, y0, cw, chh, extra=""):
    g, ch = frame
    rows = [row_svg(g[r], ch[r], y0 + (r + 0.78) * chh, x0, cw) for r in range(len(g))]
    return "".join(r for r in rows if r) + extra


# ---- scene --------------------------------------------------------------------

SMALL = [  # a small jellyfish in the distance; its tentacles alternate between two rows
    ' .-""-. ',
    '/      \\',
    "'-.~~.-'",
    " ) ( ) (",
    "( ) ( ) ",
    " ) ( ) (",
]
SMALL_B = [SMALL[0], SMALL[1], SMALL[2], "( ) ( ) ", " ) ( ) (", "( ) ( ) "]


def scene(W, H_scene, cw, chh, fs, spots, seed, animated):
    rnd = random.Random(seed)
    out, css = [], []
    # streaks: faint vertical lines drifting down
    for k in range(int(W / 24)):
        x = rnd.uniform(8, W - 8)
        h = rnd.uniform(60, 220)
        y = rnd.uniform(-h, H_scene)
        op = rnd.uniform(0.05, 0.13)
        dur = rnd.uniform(9, 16)
        style = f' style="animation:drift {dur:.1f}s linear {-rnd.uniform(0, dur):.1f}s infinite"' if animated else ""
        out.append(f'<rect class="sk" x="{x:.1f}" y="{y:.1f}" width=".8" height="{h:.0f}" opacity="{op:.2f}"{style}/>')
    # sparks
    for k in range(int(W / 14)):
        x = rnd.uniform(10, W - 10)
        y = rnd.uniform(10, H_scene - 10)
        ch = rnd.choice("+++**.")
        dur = rnd.uniform(2.5, 6.0)
        style = f' style="animation:tw {dur:.1f}s ease-in-out {-rnd.uniform(0, dur):.1f}s infinite"' if animated else ""
        out.append(f'<text class="sp" x="{x:.1f}" y="{y:.1f}"{style}>{ch}</text>')
    # small jellyfish
    for (x, y, tint, op, size) in spots:
        dur = rnd.uniform(5, 8)
        anim = f' style="animation:bob {dur:.1f}s ease-in-out {-rnd.uniform(0, dur):.1f}s infinite"' if animated else ""
        def rows(src, lo, hi):
            return "".join(f'<text x="{x:.1f}" y="{y + (i + 1) * size * 1.12:.1f}">{escape(src[i]).replace(" ", chr(160))}</text>'
                           for i in range(lo, hi))
        dome = rows(SMALL, 0, 3)
        if animated:
            body = dome + f'<g class="wa">{rows(SMALL, 3, 6)}</g><g class="wb">{rows(SMALL_B, 3, 6)}</g>'
        else:
            body = dome + rows(SMALL, 3, 6)
        out.append(f'<g fill="{tint}" opacity="{op}" font-size="{size}"{anim}>{body}</g>')
    return "".join(out)


def sparks(cx, cy, scale, fs, seed):
    """On the last beat of the colour cycle the animal throws sparks all round, as in the reference."""
    rnd = random.Random(seed)
    els, css = [], []
    start, end = (BEATS - 1) * PERIOD / CYCLE * 100, ((BEATS - 1) * PERIOD + 1.5) / CYCLE * 100
    for k in range(26):
        a = 2 * math.pi * k / 26 + rnd.uniform(-0.12, 0.12)
        r = scale * rnd.uniform(0.9, 1.75)
        dx, dy = r * math.cos(a) * 1.25, r * math.sin(a) * 0.95 + scale * 0.25
        ch = rnd.choice("**++.")
        name = f"s{k}"
        css.append(f"@keyframes {name}{{0%,{start:.2f}%{{opacity:0;transform:translate(0,0)}}"
                   f"{start + 0.6:.2f}%{{opacity:1}}{end:.2f}%{{opacity:0;transform:translate({dx:.0f}px,{dy:.0f}px)}}"
                   f"100%{{opacity:0;transform:translate({dx:.0f}px,{dy:.0f}px)}}}}")
        els.append(f'<text class="bu" x="{cx:.1f}" y="{cy:.1f}" style="animation:{name} {CYCLE:g}s cubic-bezier(.2,.7,.3,1) infinite">{ch}</text>')
    return "".join(els), "".join(css)


# ---- the file -----------------------------------------------------------------

def build(variant: str, n: int, mono: bool, out_dir: Path):
    if variant == "desktop":
        W, H = 960, 680
        FS = 8.0
        lay = jelly.Layout(cols=200, rows=58, cw=FS * 0.6, ch=FS * 1.12, cx=480, top=30, radius=128, height=154, tentacles=16)
        spots = [(96, 92, "#e0606e", 0.55, 10), (52, 352, "#5a8ae0", 0.42, 8.5), (812, 128, "#5a8ae0", 0.50, 10),
                 (858, 360, "#c06ae0", 0.36, 8), (236, 236, "#5ac0d0", 0.22, 6.5), (700, 430, "#e0a05a", 0.20, 6.5)]
        name_y, role_y, meta_y = 566, 604, 640
        name_fs, role_fs, meta_fs = 54, 17, 11.5
        scene_h = 530
    else:
        W, H = 480, 590
        FS = 6.4
        lay = jelly.Layout(cols=125, rows=66, cw=FS * 0.6, ch=FS * 1.12, cx=240, top=28, radius=104, height=126, tentacles=16)
        spots = [(22, 60, "#e0606e", 0.50, 7.5), (404, 104, "#5a8ae0", 0.46, 7.5), (14, 300, "#c06ae0", 0.30, 6),
                 (416, 330, "#e0a05a", 0.24, 6)]
        name_y, role_y, meta_y = 478, 510, 540
        name_fs, role_fs, meta_fs = 40, 15, 10
        scene_h = 440

    with Pool() as pool:
        frames = pool.map(_frame, [(lay, i, n) for i in range(n)])

    # vertical extent of the body, for the gradients
    y_top = lay.top - lay.ch * 2
    y_bot = lay.top + lay.height * (1.34 + lay.tent_len * 1.1)
    used = set("".join("".join(r) for fr in frames for r in fr[0]))

    for animated in (True, False):
        fr = frames if animated else frames[:1]
        groups = []
        for i, f in enumerate(fr):
            body = frame_group(f, 0, 0, lay.cw, lay.ch)
            if animated:
                groups.append(f'<g class="f{" f0" if i == 0 else ""}" style="animation-delay:{i * PERIOD / n - PERIOD:.3f}s">{body}</g>')
            else:
                groups.append(f"<g>{body}</g>")
        art = "".join(groups)

        name, role = "Joshua Heath", "Full-stack developer, focused on data"
        meta = "BSC COMPUTER SCIENCE  ·  UNIVERSITY OF PRETORIA  ·  CLASS OF 2026"
        meta_lines = [meta] if variant == "desktop" else ["BSC COMPUTER SCIENCE", "UNIVERSITY OF PRETORIA  \u00b7  CLASS OF 2026"]
        css = [
            font_face("GM", "GeistMono-Regular.woff2", "".join(used) + "+*.-\"'~()/\\|_:" + meta),
            font_face("G", "Geist-SemiBold.woff2", name, 600),
            font_face("G", "Geist-Regular.woff2", role, 400),
            "text{white-space:pre;font-family:'GM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}",
            f".art text{{font-size:{FS}px}}",
            ".b{fill:url(#gb)}.a{fill:url(#ga)}.e{fill:url(#ge)}.i{fill:url(#gi)}.r{fill:url(#gr)}"
            ".h{fill:url(#gh)}.t{fill:url(#gt)}.g{fill:#fff}",
            f".sp{{fill:#8a97b8;font-size:{FS + 1}px}}.sk{{fill:url(#streak)}}",
            f".nm{{font-family:'G',system-ui,sans-serif;font-weight:600;font-size:{name_fs}px;fill:{PAPER};letter-spacing:-1.5px}}",
            f".ro{{font-family:'G',system-ui,sans-serif;font-size:{role_fs}px;fill:{GREY}}}",
            f".me{{font-size:{meta_fs}px;fill:{MUTED};letter-spacing:1.6px}}",
        ]
        if animated:
            pct = 100.0 / n
            css += [
                f".f{{visibility:hidden;animation:play {PERIOD}s step-end infinite}}"
                f"@keyframes play{{0%{{visibility:visible}}{pct:.4f}%{{visibility:hidden}}}}",
                "@keyframes drift{from{transform:translateY(-40px)}to{transform:translateY(60px)}}",
                "@keyframes tw{0%,100%{opacity:.15}50%{opacity:.9}}",
                "@keyframes bob{0%,100%{transform:translateY(-4px)}50%{transform:translateY(5px)}}",
                ".wb{visibility:hidden}.wa,.wb{animation:wig 1.6s step-end infinite}.wb{animation-delay:-.8s}"
                "@keyframes wig{0%{visibility:visible}50%{visibility:hidden}}",
                f".haze{{transform-box:fill-box;transform-origin:50% 40%;animation:breathe {PERIOD}s infinite}}"
                "@keyframes breathe{0%{transform:scale(1)}28%{transform:scale(.88,.94)}100%{transform:scale(1)}}",
                "@media (prefers-reduced-motion:reduce){.f,.sk,.sp,.haze,g{animation:none!important}.f0{visibility:visible}}",
            ]

        burst, burst_css = sparks(lay.cx, lay.top + lay.height * 0.75, lay.radius, FS, 11) if animated else ("", "")
        css.append(f".bu{{fill:#fff;font-size:{FS + 2}px;opacity:0}}" + burst_css)
        reveal = ""
        clip = ""
        if animated:
            # the base height is the full scene, so a renderer without SMIL still shows the animal
            reveal = (f'<clipPath id="reveal"><rect x="0" y="0" width="{W}" height="{scene_h + 40}">'
                      f'<animate attributeName="height" values="0;{scene_h + 40}" dur="1.8s" begin="0s" fill="freeze" '
                      f'calcMode="spline" keyTimes="0;1" keySplines=".3 0 .4 1"/></rect></clipPath>')
            clip = ' clip-path="url(#reveal)"'

        haze_c = hexc(palette_colour(0, "bell", 0.2, mono))
        haze_anim = ""
        if animated:
            vals = ";".join(hexc(mix(palette_colour(b, "bell", 0.25, mono), (0, 0, 0), 0.1)) for b in list(range(BEATS)) + [0])
            kts = ";".join(f"{(b * PERIOD + 0.4) / CYCLE:.4f}" if 0 < b < BEATS else ("0" if b == 0 else "1") for b in range(BEATS + 1))
            haze_anim = f'<animate attributeName="stop-color" dur="{CYCLE:g}s" repeatCount="indefinite" keyTimes="{kts}" values="{vals}"/>'

        hx, hy = lay.cx, lay.top + lay.height * 0.55
        desc = ("An ASCII-art jellyfish, drawn in glowing coloured characters, pulses and drifts in the dark; "
                "on every beat a bright wave runs down its body and changes its colours. Small jellyfish float in the "
                "distance. Below it: Joshua Heath, full-stack developer focused on data; BSc Computer Science, "
                "University of Pretoria, class of 2026.")
        if not animated:
            desc = desc.replace("pulses and drifts", "hangs").replace("; on every beat a bright wave runs down its body and changes its colours", "")
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" xml:space="preserve" role="img" aria-labelledby="t d">
<title id="t">Joshua Heath</title>
<desc id="d">{escape(desc)}</desc>
<defs>
<style>{"".join(css)}</style>
{gradients(y_top, y_bot, mono, animated)}
<radialGradient id="hz"><stop offset="0" stop-color="{haze_c}" stop-opacity=".36">{haze_anim}</stop><stop offset="1" stop-color="{haze_c}" stop-opacity="0">{haze_anim}</stop></radialGradient>
<linearGradient id="streak" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9fb0d0" stop-opacity="0"/><stop offset=".5" stop-color="#9fb0d0"/><stop offset="1" stop-color="#9fb0d0" stop-opacity="0"/></linearGradient>
<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{INK}" stop-opacity="0"/><stop offset="1" stop-color="{INK}"/></linearGradient>
<filter id="bloom" x="-10%" y="-10%" width="120%" height="120%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="{FS * 0.42:.2f}" result="b"/><feGaussianBlur in="SourceGraphic" stdDeviation="{FS * 1.3:.2f}" result="w"/><feMerge><feMergeNode in="w"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="card"><rect width="{W}" height="{H}" rx="16"/></clipPath>
{reveal}
</defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{H}" fill="{INK}"/>
{scene(W, scene_h, lay.cw, lay.ch, FS, spots, 7, animated)}
<ellipse class="haze" cx="{hx:.0f}" cy="{hy:.0f}" rx="{lay.radius * 1.9:.0f}" ry="{lay.height * 1.5:.0f}" fill="url(#hz)"/>
<g class="art" filter="url(#bloom)"{clip}>{art}{burst}</g>
<rect y="{scene_h - 70}" width="{W}" height="90" fill="url(#fade)"/>
<rect y="{scene_h + 20}" width="{W}" height="{H - scene_h}" fill="{INK}"/>
<text class="nm" x="{W / 2}" y="{name_y}" text-anchor="middle">{escape(name)}</text>
<text class="ro" x="{W / 2}" y="{role_y}" text-anchor="middle">{escape(role)}</text>
{"".join(f'<text class="me" x="{W / 2}" y="{meta_y + k * 18}" text-anchor="middle">{escape(m)}</text>' for k, m in enumerate(meta_lines))}
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" fill="none" stroke="{LINE}"/>
</svg>
'''
        suffix = ("" if variant == "desktop" else "-m") + ("" if animated else "-still")
        path = out_dir / f"hero{suffix}.svg"
        path.write_text(svg, encoding="utf-8")
        print(f"{path.name}: {len(svg.encode()) / 1024:.0f} KiB" + (f", {n} frames, {PERIOD}s loop" if animated else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=48)
    ap.add_argument("--mono", action="store_true")
    ap.add_argument("--variant", choices=["desktop", "mobile", "both"], default="both")
    ap.add_argument("--out", type=Path, default=ROOT / "assets")
    args = ap.parse_args()
    for v in (["desktop", "mobile"] if args.variant == "both" else [args.variant]):
        build(v, args.frames, args.mono, args.out)
