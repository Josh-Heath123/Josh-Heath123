"""
knight.py - raymarch a Staunton chess knight into ASCII.

The piece is a signed distance field (SDF): a lathed pedestal plus an
extruded, rounded horse-head silhouette. Every character cell fires a few
rays, each ray is sphere-traced against the SDF, the hit is lit (key light,
rim light, ambient occlusion, soft shadow on the board), and the averaged
brightness is mapped onto donut.c's 12-character ramp. Cells on the outline
get a directional stroke (| / - \\) chosen from the coverage gradient.

Only numpy is required. Output is a list of frames; each frame is a list of
rows and each row is a (piece, board) pair of equal-length strings, so the
two layers can be coloured separately.
"""

from __future__ import annotations

import numpy as np

RAMP = ".,-~:;=!*#$@"  # the ramp from Andy Sloane's donut.c

# ---------------------------------------------------------------- geometry

# Pedestal profile in (radius, height), traced around the closed outline.
PEDESTAL = np.array([
    (0.00, 0.00), (0.92, 0.00), (0.92, 0.08), (0.86, 0.14), (0.78, 0.17),
    (0.78, 0.21), (0.84, 0.25), (0.84, 0.31), (0.74, 0.35), (0.62, 0.39),
    (0.60, 0.46), (0.70, 0.50), (0.70, 0.56), (0.60, 0.60), (0.00, 0.60),
])

# Horse head, facing +x. The outline, eye, nostril and mane groove are the
# contours of the DejaVu Sans black-knight glyph (U+265E), mirrored, scaled
# to 2 units tall and simplified with Ramer-Douglas-Peucker.
HEAD = np.array([
    (0.306, 2.196), (0.269, 2.233), (0.257, 2.279), (0.262, 2.314),
    (0.295, 2.398), (0.295, 2.438), (0.277, 2.475), (0.219, 2.520),
    (0.132, 2.424), (0.096, 2.352), (0.086, 2.282), (0.091, 2.239),
    (0.106, 2.212), (0.131, 2.196), (-0.092, 2.022), (-0.276, 1.807),
    (-0.424, 1.549), (-0.535, 1.249), (-0.610, 0.906), (-0.648, 0.520),
    (0.648, 0.520), (0.665, 0.647), (0.658, 0.743), (0.636, 0.812),
    (0.598, 0.880), (0.545, 0.947), (0.478, 1.012), (0.312, 1.137),
    (0.192, 1.255), (0.154, 1.311), (0.132, 1.364), (0.125, 1.433),
    (0.192, 1.312), (0.231, 1.268), (0.274, 1.237), (0.320, 1.219),
    (0.384, 1.213), (0.466, 1.104), (0.552, 1.039), (0.596, 1.023),
    (0.651, 1.017), (0.587, 1.156), (0.730, 1.049), (0.819, 1.083),
    (0.881, 1.132), (0.918, 1.198), (0.883, 1.298), (0.830, 1.491),
    (0.804, 1.672), (0.803, 1.829), (0.722, 1.973), (0.607, 2.114),
    (0.606, 2.162), (0.616, 2.180), (0.650, 2.209), (0.662, 2.243),
    (0.656, 2.317), (0.636, 2.396), (0.551, 2.357), (0.513, 2.328),
    (0.480, 2.291), (0.422, 2.196),
])

EYE = np.array([
    (0.650, 1.856), (0.648, 1.822), (0.637, 1.795), (0.577, 1.796),
    (0.536, 1.810), (0.516, 1.840), (0.512, 1.875), (0.499, 1.910),
    (0.456, 1.969), (0.504, 1.967), (0.573, 1.948), (0.623, 1.910),
    (0.642, 1.884),
])

NOSTRIL = np.array([
    (0.795, 1.254), (0.794, 1.210), (0.779, 1.187), (0.745, 1.183),
    (0.691, 1.202), (0.672, 1.216), (0.651, 1.252), (0.648, 1.274),
    (0.658, 1.319), (0.734, 1.303),
])

MANE = np.array([
    (0.130, 2.090), (0.060, 1.971), (-0.093, 1.832), (-0.219, 1.657),
    (-0.318, 1.445), (-0.389, 1.197), (-0.433, 0.912), (-0.449, 0.590),
    (-0.552, 0.590), (-0.516, 0.947), (-0.450, 1.261), (-0.352, 1.533),
    (-0.222, 1.761), (-0.062, 1.947),
])


def sd_polygon(px: np.ndarray, py: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Exact signed distance to a closed polygon (Inigo Quilez), vectorised."""
    d = (px - poly[0, 0]) ** 2 + (py - poly[0, 1]) ** 2
    s = np.ones_like(px)
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i - 1]
        bx, by = poly[i]
        ex, ey = ax - bx, ay - by
        wx, wy = px - bx, py - by
        h = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        dx, dy = wx - ex * h, wy - ey * h
        d = np.minimum(d, dx * dx + dy * dy)
        c1 = py >= by
        c2 = py < ay
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def sd_knight(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    # Pedestal: a 2D profile spun around the y axis.
    pedestal = sd_polygon(np.hypot(x, z), y, PEDESTAL) - 0.012

    # Head: silhouette extruded in z. It thins towards the ears and the
    # muzzle, and the large rounding radius turns the slab into a rounded
    # form instead of a cut-out.
    d_out = sd_polygon(x, y, HEAD)
    inner = np.clip(-d_out / 0.35, 0, 1)
    half = (0.31 - 0.06 * np.clip((y - 0.6) / 2.0, 0, 1) - 0.09 * np.clip((x - 0.35) / 0.6, 0, 1)) \
        * (0.62 + 0.38 * inner * (2 - inner))
    rnd = half * 0.85
    d2 = d_out + rnd
    dz = np.abs(z) - (half - rnd)
    head = np.minimum(np.maximum(d2, dz), 0) + np.hypot(np.maximum(d2, 0), np.maximum(dz, 0)) - rnd

    # Eye, nostril and mane groove: the glyph's inner contours, cut a little
    # way into both sides of the head.
    for poly, depth in ((EYE, 0.07), (NOSTRIL, 0.06), (MANE, 0.05)):
        cut = np.maximum(sd_polygon(x, y, poly), (half - depth) - np.abs(z))
        head = np.maximum(head, -cut)

    # Smooth union so the neck flows into the pedestal.
    k = 0.06
    h = np.clip(0.5 + 0.5 * (head - pedestal) / k, 0, 1)
    return head * (1 - h) + pedestal * h - k * h * (1 - h)


def scene(p: np.ndarray, theta: float) -> np.ndarray:
    """Distance to the knight after spinning it by theta about y."""
    c, s = np.cos(theta), np.sin(theta)
    x = c * p[..., 0] - s * p[..., 2]
    z = s * p[..., 0] + c * p[..., 2]
    return sd_knight(x, p[..., 1], z)


def normals(p: np.ndarray, theta: float) -> np.ndarray:
    e = 0.002
    k = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], dtype=float)
    n = sum(kk * scene(p + e * kk, theta)[..., None] for kk in k)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ---------------------------------------------------------------- rendering

def _norm(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def render_frame(theta: float, cols: int, rows: int, ss: int = 3, cell_aspect: float = 0.52,
                 eye=(0.0, 3.0, 8.6), target=(0.0, 1.12, 0.0), fov: float = 22.0,
                 board_square: float = 0.8, pool_inner: float = 1.8, pool_fade: float = 2.6,
                 x_offset: float = 0.0):
    """Return (lum_piece, lum_board, coverage) arrays of shape (rows, cols)."""
    W, H = cols * ss, rows * ss
    eye = np.array(eye, float)
    fwd = _norm(np.array(target, float) - eye)
    right = _norm(np.cross(fwd, [0, 1, 0]))
    up = np.cross(right, fwd)

    # Each sub-pixel is 1/ss of a cell; cells are taller than wide.
    half_w = np.tan(np.radians(fov) / 2)
    half_h = half_w * (rows / cell_aspect) / cols
    u = ((np.arange(W) + 0.5) / W * 2 - 1) * half_w + x_offset
    v = (1 - (np.arange(H) + 0.5) / H * 2) * half_h
    U, V = np.meshgrid(u, v)
    rd = _norm(fwd + U[..., None] * right + V[..., None] * up)
    ro = np.broadcast_to(eye, rd.shape)

    # Sphere-trace the piece.
    t = np.zeros((H, W))
    hit = np.zeros((H, W), bool)
    alive = np.ones((H, W), bool)
    for _ in range(180):
        idx = alive & ~hit
        if not idx.any():
            break
        p = ro[idx] + rd[idx] * t[idx][:, None]
        d = scene(p, theta)
        t_i = t[idx] + d * 0.7
        h_i = d < 0.0015
        dead = t_i > 14
        t[idx] = t_i
        hh = hit[idx]; hh |= h_i; hit[idx] = hh
        aa = alive[idx]; aa &= ~dead; alive[idx] = aa

    key = _norm(np.array([0.55, 0.75, 0.75]))
    rim_dir = _norm(np.array([-0.8, 0.3, -0.6]))

    lum_piece = np.zeros((H, W))
    if hit.any():
        p = ro[hit] + rd[hit] * t[hit][:, None]
        n = normals(p, theta)
        diff = np.clip(n @ key, 0, 1)
        half = _norm(key - rd[hit])
        spec = np.clip(np.sum(n * half, axis=-1), 0, 1) ** 28
        rim = np.clip(n @ rim_dir, 0, 1) ** 2
        # Ambient occlusion: how open is the space just above the surface?
        ao = np.ones(len(p))
        for i in range(1, 5):
            h = 0.06 * i
            ao -= (h - scene(p + n * h, theta)) * (0.9 / i)
        ao = np.clip(ao, 0.25, 1)
        lum_piece[hit] = np.clip(0.22 + (0.70 * diff) * ao + 0.45 * spec + 0.40 * rim, 0, 1)

    # The board: an analytic plane at y = 0 with a checkerboard. The knight
    # stands in the middle of one square, and a pool of light fades the
    # board out around it.
    lum_board = np.zeros((H, W))
    down = rd[..., 1] < -1e-4
    tf = np.where(down, -ro[..., 1] / np.where(down, rd[..., 1], -1), np.inf)
    on_board = down & (~hit | (tf < t))
    if on_board.any():
        q = ro[on_board] + rd[on_board] * tf[on_board][:, None]
        sq = board_square
        light_sq = ((np.floor(q[:, 0] / sq + 0.5) + np.floor(q[:, 2] / sq + 0.5)) % 2) == 0
        base = np.where(light_sq, 0.40, 0.03)
        # Soft shadow: march from the board towards the key light.
        shade = np.ones(len(q))
        ts = np.full(len(q), 0.02)
        for _ in range(48):
            d = scene(q + key * ts[:, None], theta)
            shade = np.minimum(shade, 8 * d / ts)
            ts += np.clip(d, 0.02, 0.25)
        shade = np.clip(shade, 0, 1)
        pool = np.clip(1.0 - (np.hypot(q[:, 0], q[:, 2]) - pool_inner) / pool_fade, 0, 1)
        lum_board[on_board] = base * (0.2 + 0.8 * shade) * pool

    # Downsample sub-pixels to cells.
    def cells(a):
        return a.reshape(rows, ss, cols, ss).mean(axis=(1, 3))

    cov = cells(hit.astype(float))
    lp = cells(lum_piece) / np.maximum(cov, 1e-6)
    lb = cells(lum_board)
    return lp, lb, cov


def to_glyphs(lp, lb, cov, board_ramp: str = " .:", split: int = 5):
    """
    Map cell brightness to characters. Returns one (bright, dim, board) tuple
    of strings per row: ramp glyphs below index `split` go to the dim layer,
    so the SVG can colour the shadow side of the piece differently.
    """
    rows, cols = cov.shape
    gy, gx = np.gradient(cov)
    out = []
    for r in range(rows):
        hi, lo, bd = [" "] * cols, [" "] * cols, [" "] * cols
        for c in range(cols):
            a = cov[r, c]
            if a >= 0.34:
                lum = lp[r, c] * (0.55 + 0.45 * min(1.0, a / 0.75))
                i = min(len(RAMP) - 1, int(lum * len(RAMP)))
                if a < 0.62:
                    # Outline cell: a stroke running along the edge, which is
                    # perpendicular to the coverage gradient.
                    ang = np.degrees(np.arctan2(gy[r, c], gx[r, c] * 0.52)) % 180
                    hi[c] = "-" if 67.5 <= ang < 112.5 else "|" if ang < 22.5 or ang >= 157.5 \
                        else ("\\" if ang < 67.5 else "/")
                elif i < split:
                    lo[c] = RAMP[i]
                else:
                    hi[c] = RAMP[i]
            elif lb[r, c] > 0.02:
                bd[c] = board_ramp[min(len(board_ramp) - 1, int(lb[r, c] * len(board_ramp) / 0.45))]
        out.append(("".join(hi), "".join(lo), "".join(bd)))
    return out


def render(frames: int, cols: int, rows: int, start_deg: float = 0.0, **kw):
    out = []
    for f in range(frames):
        theta = np.radians(start_deg + 360.0 * f / frames)
        out.append(to_glyphs(*render_frame(theta, cols, rows, **kw)))
    return out


if __name__ == "__main__":
    import sys
    deg = float(sys.argv[1]) if len(sys.argv) > 1 else 30
    frame = to_glyphs(*render_frame(np.radians(deg), 76, 40))
    for row in frame:
        print("".join(next((ch for ch in cells if ch != " "), " ") for cells in zip(*row)))
