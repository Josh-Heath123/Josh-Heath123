"""
build_panels.py - writes every README panel except the hero.

    python tools/build_panels.py

Each panel comes in two layouts: <name>.svg (960 wide) and <name>-m.svg (480
wide), which the README's <picture> picks on narrow screens so the text stays
readable on a phone. Numbers come from tools/stats.json, made by gitstats.py.

The design language, shared with the hero:
  - black cards, 16 px corners, one hairline border; they read as screens on
    GitHub's dark theme and as solid black tiles on the light one
  - white headings, grey body text, one grey for labels; no accent colour
    except the green "open to work" dot (the jellyfish is the only colour)
  - Geist for text, Geist Mono for labels, numbers and code, embedded as
    WOFF2 subsets so every browser draws the same thing
  - every card starts with the same mono overline (ABOUT, PROJECT, ...)
"""

from __future__ import annotations

import base64
import datetime as dt
import json
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.ttLib import TTFont

from svg_ascii import font_face

TOOLS = Path(__file__).resolve().parent
ASSETS = TOOLS.parent / "assets"
FONTS = TOOLS / "fonts"
STATS = json.loads((TOOLS / "stats.json").read_text())
PRIVATE = {"Josh-Heath123/Culprit", "Josh-Heath123/COS341_SPL"}

BG, TILE, LINE, LINE2 = "#000000", "#0a0a0a", "#232323", "#2e2e2e"
WHITE, SOFT, BODY, LABEL, MUTED = "#fafafa", "#d4d4d4", "#a1a1a1", "#8a8a8a", "#7a7a7a"
GO = "#3ddc84"
HEAT = ["#141414", "#3a3a3a", "#6b6b6b", "#a8a8a8", "#fafafa"]           # commit calendar, none -> most
LANG = ["#fafafa", "#c4c4c4", "#949494", "#6e6e6e", "#4f4f4f", "#3a3a3a", "#262626"]

FACES = {  # (family, file, weight)
    "sans": ("G", "Geist-Regular.woff2", 400),
    "medium": ("G", "Geist-Medium.woff2", 500),
    "semi": ("G", "Geist-SemiBold.woff2", 600),
    "mono": ("GM", "GeistMono-Regular.woff2", 400),
    "monom": ("GM", "GeistMono-Medium.woff2", 500),
}


@lru_cache(None)
def _metrics(file):
    f = TTFont(FONTS / file)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return {cp: hmtx[g][0] / upm for cp, g in cmap.items()}


def width(s, face, size, ls=0.0):
    m = _metrics(FACES[face][1])
    return sum(m.get(ord(c), 0.6) for c in s) * size + ls * len(s)


def wrap(s, face, size, max_w, ls=0.0):
    lines, cur = [], ""
    for word in s.split(" "):
        trial = (cur + " " + word).strip()
        if cur and width(trial, face, size, ls) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class Panel:
    """One card: collects elements, and the characters each font face must carry."""

    def __init__(self, w, alt, card=True, gutter=0):
        # gutter > 0 pads the right side, < 0 the left, so two cards set at 50%
        # meet with a gap between them and outer edges flush with full-width cards.
        self.w, self.h, self.alt, self.card, self.gutter = w, 100, alt, card, gutter
        self.els = []
        self.used = {k: set(" ") for k in FACES}
        self.css = []

    def text(self, x, y, s, face="sans", size=15, fill=BODY, anchor=None, ls=0.0, upper=False):
        if upper:
            s = s.upper()
        self.used[face].update(s)
        fam, _, wt = FACES[face]
        a = f' text-anchor="{anchor}"' if anchor else ""
        l = f' letter-spacing="{ls}"' if ls else ""
        cls = "m" if fam == "GM" else "s"
        body = escape(s).replace("  ", "  ")
        self.els.append(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{wt}" '
                        f'fill="{fill}"{a}{l}>{body}</text>')
        return width(s, face, size, ls)

    def para(self, x, y, s, max_w, face="sans", size=15, fill=BODY, lead=1.6):
        for line in wrap(s, face, size, max_w):
            self.text(x, y, line, face, size, fill)
            y += size * lead
        return y

    def overline(self, x, y, s, fill=LABEL, anchor=None):
        return self.text(x, y, s, "mono", 11, fill, anchor, ls=1.8, upper=True)

    def raw(self, s):
        self.els.append(s)

    def rule(self, x1, x2, y, color=LINE):
        self.raw(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{color}"/>')

    def tile(self, x, y, w, h, r=12, fill=TILE, stroke=LINE):
        self.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')

    def arrow(self, x, y, color=WHITE, s=7):
        """A small north-east arrow, drawn as a path (no arrow glyph in the subsets)."""
        self.raw(f'<path d="M{x:.1f} {y + s:.1f} L{x + s:.1f} {y:.1f} M{x + 1.5:.1f} {y:.1f} H{x + s:.1f} '
                 f'V{y + s - 1.5:.1f}" fill="none" stroke="{color}" stroke-width="1.4" stroke-linecap="round" '
                 f'stroke-linejoin="round"/>')

    def render(self):
        css = []
        for key, (fam, file, wt) in FACES.items():
            chars = "".join(sorted(self.used[key]))
            if len(chars.strip()) > 0:
                css.append(font_face(fam, file, chars, wt))
        greek = "".join(sorted(c for c in self.used["mono"] if "\u0370" <= c <= "\u03ff"))
        if greek:  # Geist Mono has no beta or sigma: Greek comes from JetBrains Mono, by unicode-range
            css.append(font_face("GM", "jetbrains-mono-greek-400-normal.woff2", greek, 400, "U+0370-03FF"))
        css.append("text{white-space:pre}.s{font-family:'G',system-ui,-apple-system,'Segoe UI',sans-serif}"
                   ".m{font-family:'GM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}")
        css += self.css
        w, h = self.w, round(self.h)
        if self.card:
            body = (f'<clipPath id="c"><rect width="{w}" height="{h}" rx="16"/></clipPath>'
                    f'<g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="{BG}"/>{"".join(self.els)}</g>'
                    f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="15.5" fill="none" stroke="{LINE}"/>')
        else:
            body = "".join(self.els)
        ow = w + abs(self.gutter)
        if self.gutter:
            body = f'<g transform="translate({max(-self.gutter, 0)} 0)">{body}</g>'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ow} {h}" width="{ow}" height="{h}" '
                f'xml:space="preserve" role="img" aria-labelledby="t"><title id="t">{escape(self.alt)}</title>'
                f'<defs><style>{"".join(css)}</style></defs>{body}</svg>\n')

    def save(self, name, folder=ASSETS):
        svg = self.render()
        (folder / name).write_text(svg, encoding="utf-8")
        print(f"{name}: {len(svg.encode()) / 1024:.0f} KiB")


def fname(base, narrow):
    return f"{base}-m.svg" if narrow else f"{base}.svg"


def repo_stats(repo):
    return next(r for r in STATS["repos"] if r["repo"] == repo)


def chips(p, x0, y, labels, right, size=13):
    """Outline pills, left to right, wrapping at `right`; returns the y below the last row."""
    x, hh = x0, size + 15
    for label in labels:
        w = width(label, "sans", size) + 24
        if x + w > right and x > x0:
            x, y = x0, y + hh + 10
        p.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{hh}" rx="{hh / 2}" fill="{TILE}" stroke="{LINE2}"/>')
        p.text(x + 12, y + hh / 2 + size * 0.36, label, "sans", size, SOFT)
        x += w + 8
    return y + hh


# -------------------------------------------------------------------- about

ABOUT_HEAD = "I build a feature end to end, then stay to keep it running."
ABOUT = [
    "Final-year BSc Computer Science student at the University of Pretoria. I work across the full stack with "
    "a focus on data: I build the pipeline, the API and the interface for a feature, then take it to "
    "production and look after it once real people use it.",
    "Comfortable from low-level systems and networking up to production web apps. I care about the unglamorous "
    "parts too: tests worked out by hand, migrations that round-trip, deploys that stay up.",
    "Away from the keyboard: gym and gaming.",
]
FACTS = [("Studying", "BSc Computer Science", "University of Pretoria"),
         ("Graduating", "End of 2026", ""),
         ("Based in", "Gauteng", "South Africa"),
         ("Open to", "Internships and", "graduate roles")]


def about(narrow=False):
    W = 480 if narrow else 960
    p = Panel(W, "About. " + ABOUT_HEAD + " " + " ".join(ABOUT) + " "
              + " ".join(f"{k}: {a} {b}." for k, a, b in FACTS))
    m = 28 if narrow else 56
    p.overline(m, 52 if narrow else 60, "About")
    if narrow:
        y = 92
        for line in wrap(ABOUT_HEAD, "semi", 24, W - 2 * m, -0.4):
            p.text(m, y, line, "semi", 24, WHITE, ls=-0.4)
            y += 31
        y += 12
        for para in ABOUT:
            y = p.para(m, y, para, W - 2 * m, size=14.5) + 10
        y += 8
    else:
        y = 106
        for line in wrap(ABOUT_HEAD, "semi", 30, 360, -0.6):
            p.text(m, y, line, "semi", 30, WHITE, ls=-0.6)
            y += 38
        yb = 102
        for para in ABOUT:
            yb = p.para(456, yb, para, W - 456 - m, size=15) + 10
        y = max(y, yb) + 12
    p.rule(m, W - m, y)
    y += 34
    cols = 2 if narrow else 4
    cw = (W - 2 * m) / cols
    for i, (k, a, b) in enumerate(FACTS):
        x = m + (i % cols) * cw
        yy = y + (i // cols) * 86
        p.overline(x, yy, k)
        dot = 0
        if k == "Open to":
            p.raw(f'<circle cx="{x + 4}" cy="{yy + 22}" r="4" fill="{GO}"><animate attributeName="opacity" '
                  f'values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
            dot = 14
        p.text(x + dot, yy + 27, a, "medium", 15, WHITE)
        if b:
            p.text(x + dot, yy + 49, b, "sans", 14, BODY)
    p.h = y + (2 if narrow else 1) * 86 - 10
    p.save(fname("about", narrow))


# --------------------------------------------------------------- EquityLens

EQ_FACTS = [("Client", "Amazon Web Services"), ("Team", "Four, The Big Five"), ("Live", "equitylens.co.za")]


def equitylens(narrow=False):
    repo = repo_stats("COS301-SE-2026/Equity-Lens")
    W = 480 if narrow else 960
    m = 28 if narrow else 56
    p = Panel(W, "Featured: EquityLens, our COS 301 capstone, with Amazon Web Services as industry client. See why "
                 "your portfolio moved, not just that it did. Built by a team of four; "
                 f"{repo['commits']} of the commits are mine. Screenshot of the dashboard plotting a portfolio "
                 "against the Satrix 40 benchmark, with a dot on each day a holding moved unusually far.")
    p.overline(m, 52 if narrow else 60, "Featured  ·  COS 301 capstone")
    if narrow:
        p.text(m, 100, "EquityLens", "semi", 34, WHITE, ls=-0.8)
        y = p.para(m, 132, "See why your portfolio moved, not just that it did.", W - 2 * m, size=16, fill=SOFT)
        y += 4
        for k, v in EQ_FACTS:
            p.text(m, y, k, "mono", 11.5, LABEL, ls=1.2, upper=True)
            p.text(m + 82, y, v, "sans", 14, SOFT)
            y += 24
        p.text(m, y + 4, f"{repo['commits']} commits  ·  {repo['added']:,} lines", "mono", 12, LABEL)
        fy = y + 28
    else:
        p.text(m, 116, "EquityLens", "semi", 44, WHITE, ls=-1.2)
        p.text(m, 150, "See why your portfolio moved, not just that it did.", "sans", 18, SOFT)
        p.text(W - m, 98, f"{repo['commits']}", "semi", 30, WHITE, anchor="end", ls=-0.5)
        p.text(W - m, 120, "commits", "mono", 11.5, LABEL, anchor="end", ls=1.2, upper=True)
        x = m
        for k, v in EQ_FACTS:
            x += p.text(x, 190, k, "mono", 11.5, LABEL, ls=1.2, upper=True) + 10
            x += p.text(x, 190, v, "sans", 14, SOFT) + 30
        p.text(W - m, 190, f"{repo['added']:,} lines", "mono", 12, LABEL, anchor="end")
        fy = 216

    shot = (ASSETS / "equitylens-dashboard.webp").read_bytes()
    fw = W - 2 * m
    ih = fw * 738 / 1360
    bar = 28 if narrow else 36
    p.tile(m, fy, fw, ih + bar, r=12, fill="#070707")
    pill = 176 if narrow else 236
    p.raw(f'<rect x="{m + fw / 2 - pill / 2:.1f}" y="{fy + bar / 2 - 10:.1f}" width="{pill}" height="20" rx="10" '
          f'fill="{TILE}" stroke="{LINE}"/>')
    p.text(m + fw / 2, fy + bar / 2 + 4, "equitylens.co.za" if narrow else "equitylens.co.za/dashboard",
           "mono", 11, MUTED, anchor="middle")
    p.raw(f'<clipPath id="shot"><rect x="{m + 1}" y="{fy + bar}" width="{fw - 2}" height="{ih - 1:.0f}" rx="11"/>'
          f'</clipPath><image clip-path="url(#shot)" x="{m}" y="{fy + bar}" width="{fw}" height="{ih:.1f}" '
          f'href="data:image/webp;base64,{base64.b64encode(shot).decode()}"/>')
    cap = ("Each dot is a day one holding moved unusually far for itself. Click it for the event study and "
           "the news around it.")
    y = p.para(m, fy + bar + ih + 34, cap, W - 2 * m, size=13.5, fill=MUTED)
    p.h = y + 10
    p.save(fname("equitylens", narrow))


# ----------------------------------------------------------------- my part

PARTS = [
    ("Dashboard", "TWR  ·  XIRR via Newton's method",
     "The flagship page: returns against a blended benchmark, a 0–10 health score and what-if rebalancing."),
    ("Unusual moves", "λ = 0.94  ·  |z| ≥ 3",
     "EWMA volatility scores each day's log return against the holding's own recent volatility."),
    ("Event study", "OLS β  ·  CAR ± 1.96σ",
     "A market model splits each move into a market part and a company part, with a cumulative abnormal "
     "return band."),
    ("News pipeline", "BM25 0.5  ·  date 0.3  ·  entity 0.2",
     "Stored once in Postgres, ranked by a hand-written BM25 index, date proximity and entity match; "
     "refreshed nightly."),
    ("Guest mode", "no sign-up  ·  data wiped on exit",
     "Visitors try the whole product without an account, plus the landing page that sells it."),
]
CODE = [
    [("variance", WHITE), (" = ", MUTED), ("LAMBDA", SOFT), (" * ", MUTED), ("variance", WHITE)],
    [("  + (", MUTED), ("1", BODY), (" - ", MUTED), ("LAMBDA", SOFT), (") * ", MUTED), ("r_prev", WHITE),
     ("**", MUTED), ("2", BODY)],
    [("sigma", WHITE), (" = ", MUTED), ("math.sqrt", SOFT), ("(variance)", WHITE)],
    [("z", WHITE), (" = ", MUTED), ("r", WHITE), (" / ", MUTED), ("sigma", WHITE)],
    [("# unusual when |z| >= 3", MUTED)],
]
STACK_EQ = ["React", "FastAPI", "PostgreSQL 16", "Docker", "GitHub Actions", "Terraform", "AWS"]


def mono_line(p, x, y, parts, size):
    for s, color in parts:
        x += p.text(x, y, s, "mono", size, color)


def owned(narrow=False):
    W = 480 if narrow else 960
    m = 28 if narrow else 56
    p = Panel(W, "EquityLens, my part: " + "; ".join(f"{t} ({g}): {d}" for t, g, d in PARTS)
              + " Stack: " + ", ".join(STACK_EQ) + ".")
    p.overline(m, 52 if narrow else 60, "EquityLens  ·  My part")
    if narrow:
        p.text(m, 92, "The parts I own", "semi", 24, WHITE, ls=-0.4)
        y = 116
        x = m
        line = "  ·  ".join(STACK_EQ)
        y = p.para(m, y, line, W - 2 * m, face="mono", size=11, fill=LABEL, lead=1.7) + 6
        tw = W - 2 * m
        for title, tag, desc in PARTS:
            lines = wrap(desc, "sans", 13.5, tw - 40)
            h = 88 + len(lines) * 21
            p.tile(x, y, tw, h)
            p.text(x + 20, y + 34, title, "medium", 17, WHITE)
            p.text(x + 20, y + 56, tag, "mono", 11, LABEL)
            for k, l in enumerate(lines):
                p.text(x + 20, y + 84 + k * 21, l, "sans", 13.5, BODY)
            y += h + 12
        ch = 160
        p.tile(x, y, tw, ch, fill="#050505")
        p.text(x + 20, y + 32, "event_detection.py", "mono", 12, SOFT)
        p.text(x + tw - 18, y + 32, "simplified", "mono", 10.5, MUTED, anchor="end")
        for k, parts in enumerate(CODE):
            mono_line(p, x + 20, y + 64 + k * 19, parts, 11.5)
        p.h = y + ch + 28
    else:
        p.text(m, 106, "The parts I own", "semi", 30, WHITE, ls=-0.6)
        p.text(W - m, 106, "  ·  ".join(STACK_EQ), "mono", 11.5, LABEL, anchor="end")
        tw, gap, th = (W - 2 * m - 2 * 16) / 3, 16, 176
        for i, (title, tag, desc) in enumerate(PARTS):
            x, y = m + (i % 3) * (tw + gap), 138 + (i // 3) * (th + gap)
            p.tile(x, y, tw, th)
            p.text(x + 22, y + 38, title, "medium", 17, WHITE)
            p.text(x + 22, y + 61, tag, "mono", 11, LABEL)
            for k, l in enumerate(wrap(desc, "sans", 13.5, tw - 44)):
                p.text(x + 22, y + 94 + k * 21, l, "sans", 13.5, BODY)
        x, y = m + 2 * (tw + gap), 138 + th + gap
        p.tile(x, y, tw, th, fill="#050505")
        p.text(x + 22, y + 36, "event_detection.py", "mono", 12, SOFT)
        p.text(x + tw - 20, y + 36, "simplified", "mono", 10.5, MUTED, anchor="end")
        for k, parts in enumerate(CODE):
            mono_line(p, x + 22, y + 70 + k * 20, parts, 11.5)
        p.h = 138 + 2 * th + gap + 44
    p.save(fname("owned", narrow))


# ------------------------------------------------------------ project cards

PROJECTS = [
    ("card-stylecode", "StyleCode", "Josh-Heath123/StyleCode", "v0.5.0",
     "A local-first visual UI editor where the canvas is the prompt: draw an interface, ask an AI to change "
     "part of it, export real HTML/CSS or React. Now also a workspace for software consultants.",
     "TypeScript  ·  React  ·  Vite  ·  Playwright"),
    ("card-studysensei", "StudySensei", "Josh-Heath123/StudySensei", "Phase 2 of 9",
     "Turns your own course material into a topic map you control, finds the exact page for any question, "
     "and times study sessions that survive reloads and lost connections.",
     "React  ·  FastAPI  ·  Postgres + pgvector"),
    ("card-munisense", "MuniSense", "Josh-Heath123/MuniSense", "Phase 1 done",
     "Exact, source-cited South African municipal electricity bills, for software and AI agents. The "
     "calculation core is built: decimal money, cited tariff values and prepaid purchases.",
     "Python 3.13  ·  Pydantic  ·  100% branch coverage"),
    ("card-culprit", "Culprit", "Josh-Heath123/Culprit", "In progress",
     "A multimeter for software: probes the links between components to find what is wrong, where and why, "
     "with the evidence attached.",
     "Go  ·  Python  ·  TypeScript"),
]


def project_card(file, title, repo, status, desc, tech, narrow, lines, side, tlines=1):
    st = repo_stats(repo)
    private = repo in PRIVATE
    W = 240 if narrow else 470
    m = 18 if narrow else 30
    p = Panel(W, f"Project: {title} ({status}). {desc} {tech.replace(chr(183), ',').replace('  ', ' ')}. "
                 f"{st['commits']} commits" + (", private repository." if private else "."),
              gutter=side * (6 if narrow else 9))
    if narrow:
        p.overline(m, 34, "Project")
        p.text(m, 62, title, "semi", 18, WHITE, ls=-0.3)
        p.text(m, 82, status, "mono", 10.5, LABEL)
        y = 108
        size, lead = 12.5, 19
    else:
        p.overline(m, 46, "Project")
        sw = width(status, "mono", 11) + 20
        p.raw(f'<rect x="{W - m - sw:.1f}" y="{30}" width="{sw:.1f}" height="22" rx="11" fill="{TILE}" stroke="{LINE2}"/>')
        p.text(W - m - sw / 2, 45, status, "mono", 11, SOFT, anchor="middle")
        p.text(m, 88, title, "semi", 24, WHITE, ls=-0.5)
        y = 120
        size, lead = 14, 22
    dl = wrap(desc, "sans", size, W - 2 * m)
    for k, l in enumerate(dl):
        p.text(m, y + k * lead, l, "sans", size, BODY)
    y += max(len(dl), lines) * lead + (2 if narrow else 6)
    if narrow:
        tl = wrap(tech.replace("  ·  ", " · "), "mono", 10.5, W - 2 * m)
        for k, l in enumerate(tl):
            p.text(m, y + k * 16, l, "mono", 10.5, LABEL)
        y += max(len(tl), tlines) * 16 + 2
    else:
        p.text(m, y, tech, "mono", 11.5, LABEL)
        y += 8
    rule = y + 6
    p.rule(m, W - m, rule)
    fs = 11 if narrow else 12
    p.text(m, rule + 26, f"{st['commits']} commits", "mono", fs, MUTED)
    if private:
        p.text(W - m, rule + 26, "private", "mono", fs, MUTED, anchor="end")
    else:
        p.text(W - m - 13, rule + 26, "source", "mono", fs, SOFT, anchor="end")
        p.arrow(W - m - 7, rule + 17.5, SOFT)
    p.h = rule + 44
    p.save(fname(file, narrow))


def projects(narrow=False):
    # the two cards in a row get the same number of description lines, so they line up
    W, m = (240, 18) if narrow else (470, 30)
    size = 12.5 if narrow else 14
    for i, pr in enumerate(PROJECTS):
        pair = PROJECTS[i - i % 2: i - i % 2 + 2]
        lines = max(len(wrap(q[4], "sans", size, W - 2 * m)) for q in pair)
        tlines = max(len(wrap(q[5].replace("  ·  ", " · "), "mono", 10.5, W - 2 * m)) for q in pair)
        project_card(*pr, narrow=narrow, lines=lines, side=1 if i % 2 == 0 else -1, tlines=tlines)


# ---------------------------------------------------------------- coursework

COURSEWORK = [
    ("row-spl", "SPL compiler", "COS 341", "Java  ·  group of four", "Josh-Heath123/COS341_SPL",
     "A compiler for SPL, the course's teaching language, built stage by stage. I worked on the parser and the "
     "semantic analysis."),
    ("row-nursery", "Plant nursery simulator", "COS 214", "C++  ·  team project", "Josh-Heath123/COS214-Final_Project",
     "A nursery simulation built to show object-oriented design patterns. I built the GUI and the Iterator "
     "pattern."),
    ("row-market", "Stationery marketplace", "COS 221", "PHP, JavaScript  ·  team",
     "Josh-Heath123/COS221-Assignment5",
     "Pulls product data from several retailers' APIs into one store. I wrote the PHP API layer and the "
     "products page."),
]


def course_row(file, title, course, meta, repo, desc, narrow):
    st = repo_stats(repo)
    private = repo in PRIVATE
    W = 480 if narrow else 960
    m = 28 if narrow else 56
    p = Panel(W, f"Coursework, {course}: {title}. {meta.replace(chr(183), ',').replace('  ', ' ')}. {desc} "
                 f"{st['commits']} commits" + (", private repository." if private else "."))
    if narrow:
        p.overline(m, 40, f"Coursework  ·  {course}")
        p.text(m, 68, title, "semi", 18, WHITE, ls=-0.3)
        p.text(m, 90, meta.replace("  ·  ", " · "), "mono", 11, LABEL)
        y = p.para(m, 118, desc, W - 2 * m, size=13.5) - 4
        p.text(m, y + 10, f"{st['commits']} commits", "mono", 11, MUTED)
        if private:
            p.text(W - m, y + 10, "private", "mono", 11, MUTED, anchor="end")
        else:
            p.text(W - m - 13, y + 10, "source", "mono", 11, SOFT, anchor="end")
            p.arrow(W - m - 7, y + 1.5, SOFT)
        p.h = y + 34
    else:
        p.overline(m, 44, f"Coursework  ·  {course}")
        p.text(m, 76, title, "semi", 20, WHITE, ls=-0.3)
        p.text(m, 100, meta, "mono", 11.5, LABEL)
        lines = wrap(desc, "sans", 14, 410)
        y0 = 72 - (len(lines) - 2) * 11
        for k, l in enumerate(lines):
            p.text(364, y0 + k * 22, l, "sans", 14, BODY)
        p.text(W - m, 76, f"{st['commits']} commits", "mono", 12, MUTED, anchor="end")
        if private:
            p.text(W - m, 100, "private", "mono", 12, MUTED, anchor="end")
        else:
            p.text(W - m - 13, 100, "source", "mono", 12, SOFT, anchor="end")
            p.arrow(W - m - 7, 91.5, SOFT)
        p.h = 128
    p.save(fname(file, narrow))


def coursework(narrow=False):
    for row in COURSEWORK:
        course_row(*row, narrow=narrow)


# ------------------------------------------------------------------- numbers

def numbers(narrow=False):
    t = STATS["totals"]
    days = {dt.date.fromisoformat(k): v for k, v in STATS["days"].items()}
    end = dt.date.fromisoformat(STATS["generated"])
    weeks = 26 if narrow else 53
    start = end - dt.timedelta(days=(end.weekday() + 1) % 7) - dt.timedelta(weeks=weeks - 1)
    window = sum(v for d, v in days.items() if start <= d <= end)
    first = min(days)
    public = sum(1 for r in STATS["repos"] if r["repo"] not in PRIVATE)
    langs = STATS["languages"]
    total = sum(langs.values())
    top = list(langs.items())[:6]
    top.append(("Other", total - sum(v for _, v in top)))
    span = f"{weeks - 1 if weeks == 53 else weeks} weeks"

    W = 480 if narrow else 960
    m = 28 if narrow else 56
    p = Panel(W, f"By the numbers: {t['commits']:,} commits and {t['added']:,} lines of code added across "
                 f"{t['repos']} repositories ({public} public, {t['repos'] - public} private) since {first:%B %Y}, "
                 f"counted from git history on {end:%d %B %Y}. {window} commits in the last {span}. Lines by "
                 "language: " + ", ".join(f"{k} {100 * v / total:.1f}%" for k, v in top) + ".")
    p.overline(m, 52 if narrow else 60, "By the numbers")
    big = [(f"{t['commits']:,}", "Commits", f"Every branch, since {first:%b %Y}"),
           (f"{t['added']:,}", "Lines of code added", "Code files only"),
           (f"{t['repos']}", "Repositories", f"{public} public, {t['repos'] - public} private")]
    if narrow:
        y = 106
        for val, label, sub in big:
            p.text(m, y, val, "semi", 36, WHITE, ls=-1)
            p.text(m + 200, y - 16, label, "medium", 14, WHITE)
            p.text(m + 200, y + 2, sub, "sans", 12.5, MUTED)
            y += 58
        gy, cell, gap = y + 26, 12, 3
    else:
        cols = [m, m + 300, m + 640]
        for (val, label, sub), x in zip(big, cols):
            p.text(x, 140, val, "semi", 56, WHITE, ls=-2)
            p.text(x, 172, label, "medium", 15, WHITE)
            p.text(x, 194, sub, "sans", 13.5, MUTED)
        gy, cell, gap = 252, 12.2, 3.2

    # commit calendar: one square per day, Sunday-first columns as on GitHub
    gx = m + (0 if narrow else 30)
    step = cell + gap
    prev = None
    for w in range(weeks):
        week0 = start + dt.timedelta(weeks=w)
        nxt = week0 + dt.timedelta(weeks=1)
        if week0.month != prev and w < weeks - 2 and not (w == 0 and nxt.month != week0.month):
            p.text(gx + w * step, gy - 10, f"{week0:%b}", "mono", 10, MUTED)
            prev = week0.month
        cells = []
        for r in range(7):
            day = week0 + dt.timedelta(days=r)
            if day <= end:
                n = days.get(day, 0)
                lvl = 0 if n == 0 else 1 if n <= 2 else 2 if n <= 5 else 3 if n <= 10 else 4
                cells.append(f'<rect x="{gx + w * step:.1f}" y="{gy + r * step:.1f}" width="{cell}" height="{cell}" '
                             f'rx="2.5" fill="{HEAT[lvl]}"/>')
        p.raw("".join(cells))
    if not narrow:
        for r, d in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
            p.text(m, gy + r * step + cell - 2, d, "mono", 10, MUTED)
    ly = gy + 7 * step + 22
    p.text(m if narrow else gx, ly, f"{window:,} commits, last {span}" if narrow else f"{window:,} commits in the last {span}",
           "mono", 11, MUTED)
    gr = gx + weeks * step - gap
    lx = gr - 5 * (cell + 4) - width("more", "mono", 11) - 8
    p.text(lx - 8, ly, "less", "mono", 11, MUTED, anchor="end")
    for i, c in enumerate(HEAT):
        p.raw(f'<rect x="{lx + i * (cell + 4):.1f}" y="{ly - cell + 2:.1f}" width="{cell}" height="{cell}" rx="2.5" fill="{c}" stroke="{LINE if i == 0 else c}"/>')
    p.text(gr, ly, "more", "mono", 11, MUTED, anchor="end")

    # lines by language
    y = ly + 54
    p.overline(m, y, "Lines by language")
    y += 18
    bx, right = m, W - m
    for i, (lang, v) in enumerate(top):
        wseg = (right - m) * v / total
        p.raw(f'<rect x="{bx:.1f}" y="{y:.1f}" width="{max(wseg - 3, 1):.1f}" height="8" rx="2" fill="{LANG[i]}"/>')
        bx += wseg
    lx, y = m, y + 38
    for i, (lang, v) in enumerate(top):
        label = f"{lang}"
        pct = f"{100 * v / total:.1f}%"
        wl = 16 + width(label, "sans", 13) + 6 + width(pct, "mono", 12)
        if lx + wl > right:
            lx, y = m, y + 24
        p.raw(f'<rect x="{lx:.1f}" y="{y - 9:.1f}" width="9" height="9" rx="2" fill="{LANG[i]}" stroke="{LINE2 if i >= 5 else LANG[i]}"/>')
        p.text(lx + 16, y, label, "sans", 13, SOFT)
        p.text(lx + 16 + width(label, "sans", 13) + 6, y, pct, "mono", 12, MUTED)
        lx += wl + 26
    note = (f"Counted from git history on {end:%d %B %Y}: my commits on every branch, merges included; lines "
            "added in my non-merge commits, code files only, without lockfiles, virtual environments, build "
            "output, generated API types or test data.")
    y = p.para(m, y + 40, note, W - 2 * m, size=12, fill=MUTED, lead=1.55)
    p.h = y + 12
    p.save(fname("numbers", narrow))


# --------------------------------------------------------------------- stack

STACK = [("Languages", ["Python", "TypeScript", "Go", "Java", "C++", "SQL", "Prolog"]),
         ("Frontend", ["React", "Next.js", "Angular", "Vite", "Tailwind CSS"]),
         ("Backend", ["FastAPI", "Node.js", "Express", "NestJS", "SQLAlchemy", "Alembic", "Pydantic"]),
         ("Data", ["PostgreSQL", "pgvector", "Supabase", "pandas", "NumPy"]),
         ("Cloud", ["AWS", "Azure", "Docker", "Terraform", "GitHub Actions"]),
         ("Testing", ["pytest", "Vitest", "Playwright"])]


def stack(narrow=False):
    W = 480 if narrow else 960
    m = 28 if narrow else 56
    p = Panel(W, "Stack. " + ". ".join(f"{k}: {', '.join(v)}" for k, v in STACK) + ".")
    p.overline(m, 52 if narrow else 60, "Stack")
    if narrow:
        y = 74
        for key, items in STACK:
            p.text(m, y + 14, key, "medium", 13.5, WHITE)
            y = chips(p, m, y + 26, items, W - m, 12.5) + 18
        p.h = y + 8
    else:
        y = 88
        for key, items in STACK:
            p.text(m, y + 20, key, "medium", 14, WHITE)
            yb = chips(p, 216, y, items, W - m, 13)
            y = yb + 12
        p.h = y + 30
    p.save(fname("stack", narrow))


# -------------------------------------------------------------------- footer

def footer(narrow=False):
    W = 480 if narrow else 960
    end = dt.date.fromisoformat(STATS["generated"])
    p = Panel(W, f"Joshua Heath. Updated {end:%B %Y}.")
    m = 28 if narrow else 40
    p.h = 64
    p.text(m, 38, "Joshua Heath", "medium", 13, SOFT)
    p.text(W - m, 38, f"Updated {end:%B %Y}", "mono", 11.5, MUTED, anchor="end")
    if not narrow:
        p.text(W / 2, 38, "University of Pretoria  ·  Gauteng, South Africa", "mono", 11.5, MUTED, anchor="middle")
    p.save(fname("footer", narrow))


# ------------------------------------------------------------------- buttons

def button(file, label, mark=None, external=True):
    size = 14
    h = 44
    tw = width(label, "medium", size)
    mw = width(mark, "mono", 13) + 10 if mark else 0
    w = round(tw + mw + 40 + (18 if external else 0))
    p = Panel(w, label, card=False)
    p.h = h
    p.raw(f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{h / 2 - .5}" fill="{BG}" stroke="{LINE2}"/>')
    x = 20
    if mark:
        p.text(x, h / 2 + 4.5, mark, "mono", 13, LABEL)
        x += mw
    p.text(x, h / 2 + 5, label, "medium", size, WHITE)
    if external:
        p.arrow(x + tw + 9, h / 2 - 3.5, LABEL)
    p.save(file)


if __name__ == "__main__":
    for narrow in (False, True):
        about(narrow)
        equitylens(narrow)
        owned(narrow)
        projects(narrow)
        coursework(narrow)
        numbers(narrow)
        stack(narrow)
        footer(narrow)
    button("btn-linkedin.svg", "LinkedIn", "in")
    button("btn-email.svg", "joshuaheath004@gmail.com", "@", external=False)
    button("btn-equitylens.svg", "equitylens.co.za", "~>")
    button("btn-source.svg", "Source on GitHub", "</>")
