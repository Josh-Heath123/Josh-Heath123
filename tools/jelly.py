"""
jelly.py - the ASCII jellyfish: a small simulation sampled onto a character grid.

Every frame is a grid of cells. Each cell holds one glyph and the channel it is
painted with (bell, bell accent, rim, inner bell, arms, tentacles, glints). The
SVG writer in build_hero.py turns the channels into gradient fills, so colour
is animated once for the whole loop instead of being baked into every frame.

The animal, top to bottom:
  bell      a dome that contracts and relaxes once per beat; shaded with a
            light from the upper left, radial canals and a slow noise mottle
  opening   seen from slightly below, so the far rim shows as a line of `_`
            and the inside of the bell shows through in light glyphs
  arms      four ribbons that spiral down from the middle of the opening
  tentacles fourteen filaments around the rim; a wave runs down each one, a
            beat behind the bell, so they trail the way a real one does

The loop is exactly one beat long, so frame N-1 runs back into frame 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Channels. 0 is empty; build_hero.py maps the rest to CSS classes.
EMPTY, BELL, ACCENT, EDGE, INNER, ARM, ARMHI, TENT, GLINT = range(9)

# Glyph tiers, faint to dense. Every tier holds several glyphs; a cell picks
# one by hashing its position and a slow clock, so the surface shimmers.
TIERS = [
    ".:",
    ":;!i",
    "!1il;",
    "rtjcvxz+=<>",
    "{}[]unoaeqz",
    "Q0aeo8$%",
    "$8B%#Q0",
    "#B8$%&@",
]


def _hash(*xs) -> np.ndarray:
    """Cheap deterministic per-cell hash in [0, 1)."""
    h = np.zeros(np.broadcast(*xs).shape, dtype=np.uint64)
    for i, x in enumerate(xs):
        h ^= (np.asarray(x, dtype=np.int64).astype(np.uint64) + np.uint64(0x9E3779B9 * (i + 1))) * np.uint64(0x85EBCA6B)
        h ^= h >> np.uint64(13)
        h *= np.uint64(0xC2B2AE35)
        h ^= h >> np.uint64(16)
    return (h % np.uint64(10007)).astype(np.float64) / 10007.0


def _noise(x, y, t, scale):
    """Smooth value-ish noise from a few sines; cheap and periodic in t."""
    return (np.sin(x / scale + 1.7 * np.sin(y / (scale * 1.3) + t))
            + np.sin(y / (scale * 0.8) - 0.6 * x / scale + 2.1)
            + np.sin((x + y) / (scale * 1.7) + 1.3 * np.cos(t))) / 3.0


def smoothstep(e0, e1, x):
    k = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return k * k * (3 - 2 * k)


def pulse(phase: float) -> float:
    """Contraction 0..1 over one beat: a quick squeeze, then a slow release."""
    p = phase % 1.0
    if p < 0.28:
        k = p / 0.28
        return k * k * (3 - 2 * k)
    k = (p - 0.28) / 0.72
    return 1.0 - (1 - (1 - k) ** 2.2)


@dataclass
class Layout:
    cols: int
    rows: int
    cw: float          # cell width in px
    ch: float          # cell height in px
    cx: float          # bell centre, px from the grid's left edge
    top: float         # bell apex at rest, px from the grid's top edge
    radius: float      # bell half-width at rest
    height: float      # apex to rim at rest
    tentacles: int = 14
    tent_len: float = 1.55   # tentacle length, in bell heights
    arm_len: float = 1.40    # arm length, in bell heights


def frame(lay: Layout, t: float, period: float):
    """One frame at time t (seconds). Returns (glyphs, channels) as 2D arrays."""
    R, C = lay.rows, lay.cols
    ys = (np.arange(R)[:, None] + 0.5) * lay.ch + np.zeros((1, C))
    xs = (np.arange(C)[None, :] + 0.5) * lay.cw + np.zeros((R, 1))
    phase = (t / period) % 1.0
    c = pulse(phase)
    w = 2 * math.pi * phase          # one turn per beat

    lum = np.zeros((R, C))
    chan = np.zeros((R, C), dtype=np.int8)
    glyph = np.full((R, C), " ", dtype="<U1")

    # ---- bell -------------------------------------------------------------
    rise = -lay.ch * 1.6 * math.sin(math.pi * min(1.0, phase / 0.75)) ** 2
    Rb = lay.radius * (1 - 0.13 * c)
    Hb = lay.height * (1 + 0.05 * c)
    top = lay.top + rise + lay.height * 0.04 * c
    cx = lay.cx + lay.cw * 0.8 * math.sin(w)        # a small sideways sway
    yc = top + Hb                                    # centre of the opening
    Rr = Rb * 0.98                                   # rim half-width
    e = Hb * (0.34 - 0.05 * c)                       # rim ellipse half-height (we look up into it)

    v = (ys - top) / Hb                              # 0 apex .. 1 rim
    prof = 0.24 + 0.76 * np.sin(np.clip(v / 0.62, 0, 1) * math.pi / 2) ** 0.9
    half = Rb * prof
    dx = xs - cx
    u = np.clip(dx / np.maximum(half, 1e-6), -1.2, 1.2)

    # the rim ellipse: its far arc is the back rim, its near arc the bottom of the bell
    ell = (dx / Rr) ** 2 + ((ys - yc) / e) ** 2
    dome = (v >= 0) & (np.abs(u) <= 1.0) & (ys <= yc)
    lower = (ell <= 1.0) & (ys > yc)
    sil = dome | lower
    # inside the opening: below the far arc
    far_arc_y = yc - e * np.sqrt(np.clip(1 - (dx / Rr) ** 2, 0, 1))
    opening = sil & (ell <= 1.0) & (ys >= far_arc_y)
    outer = sil & ~opening

    # shading on the outer surface
    nz = np.sqrt(np.clip(1 - u ** 2, 0, 1))
    ny = -(1 - np.clip(v, 0, 1)) * 0.9
    nx = u
    nrm = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2) + 1e-6
    L = np.array([-0.45, -0.65, 0.62])
    L = L / np.linalg.norm(L)
    diff = np.clip((nx * L[0] + ny * L[1] + nz * L[2]) / nrm, 0, 1)
    canals = 0.5 + 0.5 * np.cos(9.0 * np.arcsin(np.clip(u, -1, 1)) + 0.6 * math.sin(w))
    mottle = _noise(xs, ys, w, 9.0)
    crown = 1 - smoothstep(0.0, 0.9, v)              # the top of the bell is the densest
    lo = 0.22 + 0.55 * diff + 0.18 * crown + 0.10 * canals + 0.10 * mottle
    lo *= 0.92 + 0.08 * smoothstep(0.6, 1.0, nz)
    lum[outer] = lo[outer]
    chan[outer] = BELL
    accent = outer & (_noise(xs + 40, ys * 1.4, -w, 6.0) > 0.28)
    chan[accent] = ACCENT

    # the inside of the bell: lighter, with faint radial lines
    inner_l = 0.18 + 0.16 * (0.5 + 0.5 * np.cos(14 * np.arctan2(dx, (ys - far_arc_y + 6)) + w)) \
        + 0.08 * _noise(xs, ys, w, 5.0)
    lum[opening] = inner_l[opening]
    chan[opening] = INNER

    # ---- arms --------------------------------------------------------------
    La = lay.height * lay.arm_len * (1 - 0.04 * c)
    s = ys - (yc - e * 0.55)
    on = (s >= 0) & (s <= La)
    sn = np.clip(s / La, 0, 1)
    width = Rb * (0.56 * (1 - sn) ** 0.75 + 0.05)
    arm_mask = np.zeros((R, C), dtype=bool)
    arm_l = np.zeros((R, C))
    arm_edge = np.zeros((R, C), dtype="<U1")
    for i in range(4):
        th = 2 * math.pi * s / (La * 0.9) - w + i * math.pi / 2
        xi = cx + width * 0.55 * np.sin(th) + lay.cw * 2.5 * np.sin(2 * math.pi * sn - w) * sn
        hw = width * (0.22 + 0.16 * np.abs(np.cos(th))) + lay.cw * 0.4
        d = np.abs(xs - xi)
        m = on & (d <= hw)
        face = 0.5 + 0.5 * np.cos(th)
        l_here = 0.42 + 0.40 * face + 0.12 * (1 - sn) + 0.08 * _noise(xs, ys + i * 30, w, 4.0)
        take = m & (~arm_mask | (l_here > arm_l))
        arm_l[take] = l_here[take]
        # ribbon edges are drawn as strokes that follow the spiral
        slope = (width * 0.55 * np.cos(th) * 2 * math.pi / (La * 0.9))
        edge = m & (d > hw - lay.cw * 1.05)
        g = np.where(slope > 0.35, "\\", np.where(slope < -0.35, "/", "|"))
        arm_edge[edge & take] = g[edge & take]
        arm_mask |= m
    arm_cells = arm_mask & ~outer
    lum[arm_cells] = arm_l[arm_cells]
    chan[arm_cells] = ARM
    hi = arm_cells & (arm_l > 0.72)
    chan[hi] = ARMHI

    # ---- glyphs for body cells --------------------------------------------
    slow = int(t * 6)          # the shimmer changes a few times a second
    hsh = _hash(np.arange(R)[:, None] * 7 + np.zeros((1, C), int), np.arange(C)[None, :] + np.zeros((R, 1), int),
                np.full((R, C), slow))
    tier = np.clip((lum * len(TIERS)).astype(int), 0, len(TIERS) - 1)
    body = chan != EMPTY
    for k, chars in enumerate(TIERS):
        sel = body & (tier == k)
        idx = (hsh[sel] * len(chars)).astype(int) % len(chars)
        glyph[sel] = np.array(list(chars))[idx]
    ae = (arm_edge != "") & arm_cells
    glyph[ae] = arm_edge[ae]

    # ---- outlines ------------------------------------------------------------
    # The silhouette and the far rim get stroke glyphs chosen by edge direction.
    m = sil
    up = np.zeros_like(m); up[1:] = m[:-1]
    dn = np.zeros_like(m); dn[:-1] = m[1:]
    lf = np.zeros_like(m); lf[:, 1:] = m[:, :-1]
    rt = np.zeros_like(m); rt[:, :-1] = m[:, 1:]
    border = m & ~(up & dn & lf & rt)
    side = np.where(dx < 0, -1, 1)
    gy = ((ys - top) / max(Hb, 1)) < 0.06
    ch_side = np.where(side < 0, "/", "\\")
    steep = np.abs(u) > 0.97
    g = np.where(gy, "-", np.where(steep & (v > 0.35) & (ys <= yc), "|", ch_side))
    bottom = border & (ys > yc)
    gb = np.where(np.abs(dx) > Rr * 0.86, np.where(side < 0, "\\", "/"), "_")
    g = np.where(bottom, gb, g)
    glyph[border] = g[border]
    chan[border] = EDGE

    # far rim line
    rim_line = np.zeros((R, C), dtype=bool)
    rr = np.clip(((far_arc_y - (np.arange(R)[:, None] * lay.ch)) / lay.ch), -1, 2)
    rim_line = sil & (rr > 0) & (rr <= 1.0) & (np.abs(dx) < Rr * 0.97) & ~arm_cells
    gr = np.where(np.abs(dx) > Rr * 0.78, np.where(side < 0, "/", "\\"), "_")
    glyph[rim_line] = gr[rim_line]
    chan[rim_line] = EDGE

    # ---- tentacles -----------------------------------------------------------
    Lt = lay.height * lay.tent_len
    occupied = chan != EMPTY
    for k in range(lay.tentacles):
        a = 2 * math.pi * (k + 0.5) / lay.tentacles + 0.15
        front = math.sin(a) > -0.2
        bx = cx + Rr * 0.92 * math.cos(a)
        by = yc + e * 0.85 * math.sin(a) + lay.ch * 0.6
        rnd = math.sin(k * 12.9898) * 43758.5453
        rnd -= math.floor(rnd)
        length = Lt * (0.78 + 0.32 * rnd)
        spread = (bx - cx)
        amp0 = lay.cw * (0.9 + 0.8 * rnd)
        ph = k * 1.7 + rnd * 3
        prev = None
        n = int(length / (lay.ch * 0.45))
        for j in range(n + 1):
            s_ = length * j / n
            sn_ = s_ / length
            lag = phase - sn_ * 0.6                      # the wave reaches the tip later
            cl = pulse(lag)
            # at rest the tentacles draw in under the bell; a squeeze throws them out
            gather = -0.18 * smoothstep(0.0, 0.8, sn_)
            throw = 0.55 * cl * math.sin(math.pi * min(1.0, sn_ * 1.3)) ** 0.8
            x = (bx + spread * (gather + throw)
                 + (amp0 + 0.035 * s_) * math.sin(2 * math.pi * (s_ / (lay.height * 1.9)) - w + ph)
                 + lay.cw * 2.2 * sn_ ** 2 * math.sin(w + ph * 0.5))
            y = by + s_ * (1 - 0.06 * cl)
            col = int(x / lay.cw)
            row = int(y / lay.ch)
            if prev is not None:
                dxp, dyp = x - prev[0], y - prev[1]
                m_ = (dxp / lay.cw) / max(dyp / lay.ch, 1e-6)
                gch = "|" if abs(m_) < 0.32 else ("\\" if m_ > 0 else "/")
                for cc in (col, col + 1) if (k % 2 == 0 and sn_ < 0.7) else (col,):
                    if 0 <= row < R and 0 <= cc < C and not occupied[row, cc] and chan[row, cc] != TENT:
                        tip = sn_ > 0.9
                        glyph[row, cc] = ":" if tip and (row + cc) % 2 else gch
                        chan[row, cc] = TENT
                        lum[row, cc] = 0.5 * (1 - sn_) + 0.2
            prev = (x, y)
        if not front:
            continue

    # ---- glints ------------------------------------------------------------
    gl = _hash(np.arange(R)[:, None] * 13 + np.zeros((1, C), int), np.arange(C)[None, :] * 7 + np.zeros((R, 1), int),
               np.full((R, C), int(t * 5)))
    near = (chan == TENT) | (chan == ARM)
    spark = near & (gl > 0.985)
    glyph[spark] = np.where(gl[spark] > 0.993, "*", "+")
    chan[spark] = GLINT

    return glyph, chan, dict(top=top, yc=yc, Rb=Rb, Hb=Hb, cx=cx, c=c)
