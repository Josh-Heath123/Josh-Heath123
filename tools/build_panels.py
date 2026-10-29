"""
build_panels.py - writes every README panel except the hero.

    python tools/build_panels.py

Each panel comes in two layouts: <name>.svg (960 wide, desktop) and
<name>-m.svg (480 wide, picked by the README's <picture> on narrow screens so
the text stays readable on a phone). Numbers come from tools/stats.json, made
by gitstats.py.

All panels share the hero's look: ink background, bone text, one jacaranda
accent, JetBrains Mono embedded as WOFF2 subsets. The EquityLens panels hold
a screenshot, so the README shows them as 2x WebP exports (equitylens.svg is
the source, kept in tools/); every other panel is pure vector SVG.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from svg_ascii import font_face

TOOLS = Path(__file__).resolve().parent
ASSETS = TOOLS.parent / "assets"
STATS = json.loads((TOOLS / "stats.json").read_text())
PRIVATE = {"Josh-Heath123/Culprit", "Josh-Heath123/COS341_SPL"}

INK, CARD, LINE = "#0c0b10", "#121019", "#2a2537"
BONE, BODY, DUST, MUTED, JAC = "#efe8da", "#cfc8bb", "#8a83a3", "#8f889c", "#a08ae8"
HEAT = ["#2e2940", "#5d5287", "#8a74d6", "#b9a6f5", BONE]          # commit calendar, dim -> bright
LANG = ["#efe8da", "#c9b8f7", "#a08ae8", "#7d69c4", "#62539c", "#4b4078", "#332c4a"]

BASE_CSS = (
    "text{white-space:pre;font-family:'JBM',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
    f".lab{{font-weight:700;fill:{JAC};letter-spacing:2px}}"
    f".h{{font-weight:700;fill:{BONE}}}.b{{fill:{BONE}}}.t{{fill:{BODY}}}.m{{fill:{MUTED}}}"
    f".a{{fill:{JAC}}}.d{{fill:{DUST}}}"
)


class Svg:
    """A panel: collects elements, and the characters it needs from the font."""

    def __init__(self, w, title, panel=True, gutter=0):
        # gutter > 0 pads the right side, < 0 the left: two cards set at 50% each
        # then meet with a gap between them and flush outer edges.
        self.w, self.h, self.title, self.panel, self.gutter = w, 100, title, panel, gutter
        self.els, self.css = [], []
        self.reg, self.bold = set(" \u00a0"), set(" \u00a0")

    def text(self, x, y, s, cls, size, anchor=None, style=""):
        bold = {"h", "lab"} & set(cls.split())
        (self.bold if bold else self.reg).update(s)
        a = f' text-anchor="{anchor}"' if anchor else ""
        st = f' style="{style}"' if style else ""
        body = escape(s).replace(" ", "\u00a0")
        self.els.append(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}"{a}{st}>{body}</text>')

    def spans(self, x, y, parts, size):
        """One line made of (text, class) runs, laid out on the monospace grid."""
        for s, cls in parts:
            self.text(x, y, s, cls, size)
            x += len(s) * size * 0.6

    def para(self, x, y, s, cls, size, width, leading):
        """Wrap s to `width` characters; returns the baseline after the last line."""
        for line in textwrap.wrap(s, width):
            self.text(x, y, line, cls, size)
            y += leading
        return y

    def raw(self, s):
        self.els.append(s)

    def render(self):
        css = font_face("JBM", "jetbrains-mono-latin-400-normal.woff2", "".join(self.reg))
        if len(self.bold) > 2:
            css += font_face("JBM", "jetbrains-mono-latin-700-normal.woff2", "".join(self.bold), 700)
        greek = "".join(c for c in self.reg | self.bold if "\u0370" <= c <= "\u03ff")
        if greek:  # λ, σ, β come from the Greek subset, chosen per character by unicode-range
            css += font_face("JBM", "jetbrains-mono-greek-400-normal.woff2", greek, 400, "U+0370-03FF")
        css += BASE_CSS + "".join(self.css)
        w, h = self.w, int(self.h)
        defs = body = ""
        if self.panel:
            defs = (f'<radialGradient id="g" cx="78%" cy="18%" r="85%"><stop offset="0" stop-color="#17141f"/>'
                    f'<stop offset="1" stop-color="{INK}"/></radialGradient>'
                    f'<pattern id="s" width="4" height="3" patternUnits="userSpaceOnUse">'
                    f'<rect width="4" height="1" fill="#fff" opacity=".02"/></pattern>'
                    f'<clipPath id="c"><rect width="{w}" height="{h}" rx="14"/></clipPath>')
            body = (f'<g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="url(#g)"/>{"".join(self.els)}'
                    f'<rect width="{w}" height="{h}" fill="url(#s)"/></g>'
                    f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="13.5" fill="none" stroke="{LINE}"/>')
        else:
            body = "".join(self.els)
        ow = w + abs(self.gutter)
        if self.gutter:
            body = f'<g transform="translate({max(-self.gutter, 0)} 0)">{body}</g>'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ow} {h}" width="{ow}" height="{h}" '
                f'xml:space="preserve" role="img" aria-labelledby="t"><title id="t">{escape(self.title)}</title>'
                f'<defs><style>{css}</style>{defs}</defs>{body}</svg>\n')

    def save(self, name, folder=ASSETS):
        svg = self.render()
        (folder / name).write_text(svg, encoding="utf-8")
        print(f"{name}: {len(svg.encode()) / 1024:.0f} KiB")


def chip(svg, x, y, label, size=13):
    w = len(label) * size * 0.6 + 22
    svg.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{size + 13}" rx="{(size + 13) / 2:.1f}" '
            f'fill="{CARD}" stroke="{LINE}"/>')
    svg.text(x + 11, y + size + 3.5, label, "b", size)
    return w


def chips(svg, x0, y, labels, size, right):
    """Lay chips out left to right, wrapping at `right`; returns the y below the last row."""
    x = x0
    for label in labels:
        w = len(label) * size * 0.6 + 22
        if x + w > right and x > x0:
            x, y = x0, y + size + 22
        x += chip(svg, x, y, label, size) + 10
    return y + size + 13


def arrow(x, y, color=JAC, s=7):
    """A small north-east arrow, drawn as a path (the font subset has no arrow glyph)."""
    return (f'<path d="M{x:.1f} {y + s:.1f} L{x + s:.1f} {y:.1f} M{x + 2:.1f} {y:.1f} H{x + s:.1f} V{y + s - 2:.1f}" '
            f'fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>')


def name(base, narrow):
    return f"{base}-m.svg" if narrow else f"{base}.svg"


# ------------------------------------------------------------------- about

ABOUT = [
    "Final-year BSc Computer Science student at the University of Pretoria, graduating at the end of "
    "2026. I work across the full stack with a focus on data: I build the pipeline, the API and the "
    "interface for a feature, then take it to production and look after it once real people use it.",
    "Comfortable from low-level systems and networking up to production web apps. I care about the "
    "unglamorous parts too: tests worked out by hand, migrations that round-trip, deploys that stay up.",
    "Away from the keyboard: gym and gaming. I like a challenge, physical, recreational or mental.",
]


def about(narrow=False):
    s = Svg(480 if narrow else 960,
            "NAME: josh, builds a feature end to end, then stays to keep it running. " + " ".join(ABOUT)
            + " Open to internships and graduate roles.")
    if narrow:
        x, size, wrap = 24, 15, 47
        s.text(x, 44, "NAME", "lab", 11)
        s.spans(x, 70, [("josh", "h"), (" \u2014 builds a feature end to", "t")], size)
        s.text(x, 92, "end, then stays to keep it running", "t", size)
        s.text(x, 132, "SYNOPSIS", "lab", 11)
        s.spans(x, 158, [("josh ", "h"), ("[--pipeline] [--api] [--interface]", "a")], size * 0.92)
        s.spans(x, 180, [("     --to production ", "b"), ("problem", "m")], size * 0.92)
        s.text(x, 220, "DESCRIPTION", "lab", 11)
        y = 246
    else:
        x, size, wrap = 214, 14.5, 76
        s.text(52, 62, "NAME", "lab", 12)
        s.spans(x, 62, [("josh", "h"), (" \u2014 builds a feature end to end, then stays to keep it running", "t")], 15)
        s.text(52, 106, "SYNOPSIS", "lab", 12)
        s.spans(x, 106, [("josh ", "h"), ("[--pipeline] [--api] [--interface] ", "a"), ("--to production ", "b"),
                         ("problem", "m")], 15)
        s.text(52, 150, "DESCRIPTION", "lab", 12)
        y = 150
    for p in ABOUT:
        y = s.para(x, y, p, "t", size, wrap, size * 1.5) + 12
    s.raw(f'<circle cx="{x + 5}" cy="{y - 5}" r="4.5" fill="{JAC}"><animate attributeName="opacity" '
          f'values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    s.text(x + 18, y, "Open to internships and graduate roles.", "b", size * (0.95 if narrow else 1))
    s.h = y + 40
    s.save(name("about", narrow))


# ----------------------------------------------------------------- history

def heat_level(n):
    return 0 if n == 0 else 1 if n <= 2 else 2 if n <= 5 else 3 if n <= 9 else 4


def history(narrow=False):
    t = STATS["totals"]
    days = {dt.date.fromisoformat(k): v for k, v in STATS["days"].items()}
    end = dt.date.fromisoformat(STATS["generated"])
    weeks = 26 if narrow else 53
    start = end - dt.timedelta(days=(end.weekday() + 1) % 7) - dt.timedelta(weeks=weeks - 1)
    window = sum(v for d, v in days.items() if start <= d <= end)
    first = min(days)
    public = sum(1 for r in STATS["repos"] if r["repo"] not in PRIVATE)

    s = Svg(480 if narrow else 960,
            f"HISTORY: {t['commits']} commits and {t['added']:,} lines of code added across {t['repos']} "
            f"repositories ({public} public, {t['repos'] - public} private) since {first:%B %Y}, counted from git "
            f"history on {end:%d %B %Y}. {window} commits in the last {weeks - 1 if weeks == 53 else weeks} weeks.")
    stats = [(f"{t['commits']:,}", "commits", f"every branch, since {first:%b %Y}"),
             (f"{t['added']:,}", "lines of code added", "code files only, no lockfiles"),
             (f"{t['repos']}", "repositories", f"{public} public, {t['repos'] - public} private")]
    if narrow:
        x, right = 24, 456
        s.text(x, 44, "HISTORY", "lab", 11)
        s.spans(x, 70, [("$ ", "m"), ("git log ", "b"), ("--author=josh --all", "a")], 13)
        y = 124
        for big, label, sub in stats:
            s.text(x - 2, y, big, "h", 40)
            s.text(x + 196, y - 18, label, "b", 14)
            s.text(x + 196, y, sub, "m", 11.5)
            y += 58
        gx, gy, cw = x + 34, y + 30, 15.2
    else:
        x, right = 214, 908
        s.text(52, 62, "HISTORY", "lab", 12)
        s.spans(x, 62, [("$ ", "m"), ("git log ", "b"), ("--author=josh --all ", "a"), ("--since=", "m"),
                        (f"{first:%Y-%m}", "m")], 14)
        for i, (big, label, sub) in enumerate(stats):
            cx = x + (0, 240, 520)[i]
            s.text(cx - 3, 140, big, "h", 54)
            s.text(cx, 168, label, "b", 14)
            s.text(cx, 188, sub, "m", 11.5)
        gx, gy, cw = x + 26, 246, 12.3
    ch = 15

    # Commit calendar: one glyph per day, Sunday-first columns as on GitHub.
    glyphs = "\u00b7:=#@"
    s.reg.update(glyphs)
    s.css.append("".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(HEAT)))
    # Fade in week by week. The resting state is visible, so a renderer that skips
    # CSS animation still shows every day.
    s.css.append(".wk{animation:in .5s ease-out backwards}@keyframes in{from{opacity:0}}")
    prev = None
    for w in range(weeks):
        week0 = start + dt.timedelta(weeks=w)
        nxt = week0 + dt.timedelta(weeks=1)
        if week0.month != prev and w < weeks - 2 and not (w == 0 and nxt.month != week0.month):
            s.text(gx + w * cw - 3, gy - 12, f"{week0:%b}", "m", 10.5)
            prev = week0.month
        cells = []
        for r in range(7):
            day = week0 + dt.timedelta(days=r)
            if day <= end:
                lvl = heat_level(days.get(day, 0))
                cells.append(f'<text class="l{lvl}" x="{gx + w * cw + cw / 2:.1f}" y="{gy + r * ch + 11:.1f}" '
                             f'font-size="{13 if narrow else 12}" text-anchor="middle">{glyphs[lvl]}</text>')
        s.raw(f'<g class="wk" style="animation-delay:{0.25 + w * 0.018:.3f}s">{"".join(cells)}</g>')
    for r, day_name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        s.text(gx - 32, gy + r * ch + 11, day_name, "m", 10)
    ly = gy + 7 * ch + 22
    s.text(gx - 32 if narrow else gx, ly, f"{window} commits, last {weeks - 1 if weeks == 53 else weeks} weeks", "m", 11)
    gr = gx + weeks * cw
    s.text(gr - 5 * 15 - 40, ly, "less", "m", 11, anchor="end")
    for i, g in enumerate(glyphs):
        s.text(gr - (5 - i) * 15 - 28, ly, g, f"l{i}", 13, anchor="middle")
    s.text(gr, ly, "more", "m", 11, anchor="end")

    # Lines of code by language.
    langs = STATS["languages"]
    total = sum(langs.values())
    top = list(langs.items())[:6]
    top.append(("Other", total - sum(v for _, v in top)))
    by = ly + 44
    if narrow:
        s.text(x, by, "LANGUAGES", "lab", 11)
        by += 16
    else:
        s.text(52, by + 9, "LANGUAGES", "lab", 12)
    bx = x
    for i, (lang, v) in enumerate(top):
        wseg = (right - x) * v / total
        s.raw(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{max(wseg - 2, 1):.1f}" height="10" rx="2" fill="{LANG[i]}"/>')
        bx += wseg
    lx, y = x, by + 36
    for i, (lang, v) in enumerate(top):
        label = f"{lang} {100 * v / total:.1f}%"
        if lx + len(label) * 7.2 + 15 > right:
            lx, y = x, y + 22
        s.raw(f'<rect x="{lx:.1f}" y="{y - 9:.1f}" width="9" height="9" rx="2" fill="{LANG[i]}"/>')
        s.text(lx + 15, y, label, "t", 12)
        lx += len(label) * 7.2 + 36
    note = (f"Counted from git history on {end:%d %b %Y}: commits by me on every branch; lines added in "
            "non-merge commits, code files only, without lockfiles, virtualenvs, build output or test data.")
    y = s.para(x, y + 34, note, "m", 10.5, 64 if narrow else 108, 16)
    s.h = y + 10
    s.save(name("stats", narrow))


# -------------------------------------------------------------- EquityLens

def equitylens(narrow=False):
    repo = next(r for r in STATS["repos"] if r["repo"] == "COS301-SE-2026/Equity-Lens")
    W = 480 if narrow else 960
    s = Svg(W, "EquityLens, our COS 301 capstone with Amazon Web Services as industry client: portfolio "
               "analytics for South African retail investors. Screenshot of the dashboard's performance against "
               "the benchmark, where each dot is a day a holding moved unusually far.")
    m = 24 if narrow else 52
    labels = ("COS 301 capstone", "client: Amazon Web Services", "team of 4, The Big Five", "live at equitylens.co.za")
    if narrow:
        s.text(m, 44, "EXAMPLES", "lab", 11)
        s.text(m - 2, 90, "EquityLens", "h", 34)
        y = s.para(m, 120, "See why your portfolio moved, not just that it did.", "t", 15, 46, 22)
        s.spans(m, y + 4, [(f"{repo['commits']} commits", "a"), (f"  {repo['added']:,} lines", "m")], 13)
        fy = chips(s, m, y + 22, labels, 12, W - m) + 18
    else:
        s.text(m, 58, "EXAMPLES", "lab", 12)
        s.text(m - 2, 108, "EquityLens", "h", 40)
        s.text(m, 140, "See why your portfolio moved, not just that it did.", "t", 16)
        s.text(W - m, 108, f"{repo['commits']} commits", "a", 14, anchor="end")
        s.text(W - m, 130, f"{repo['added']:,} lines", "m", 12, anchor="end")
        fy = chips(s, m, 160, labels, 12.5, W - m) + 24

    shot = (ASSETS / "equitylens-dashboard.webp").read_bytes()
    fw = W - 2 * m
    ih = fw * 738 / 1360
    bar = 26 if narrow else 34
    s.raw(f'<rect x="{m}" y="{fy}" width="{fw}" height="{ih + bar:.0f}" rx="10" fill="#08070b" stroke="{LINE}"/>')
    pill = 170 if narrow else 220
    s.raw(f'<rect x="{m + fw / 2 - pill / 2}" y="{fy + bar / 2 - 9}" width="{pill}" height="18" rx="9" '
          f'fill="{CARD}" stroke="{LINE}"/>')
    s.text(m + fw / 2, fy + bar / 2 + 4, "equitylens.co.za" if narrow else "equitylens.co.za/dashboard",
           "m", 11, anchor="middle")
    s.raw(f'<clipPath id="shot"><rect x="{m + 1}" y="{fy + bar}" width="{fw - 2}" height="{ih - 1:.0f}" rx="9"/>'
          f'</clipPath><image clip-path="url(#shot)" x="{m}" y="{fy + bar}" width="{fw}" height="{ih:.1f}" '
          f'href="data:image/webp;base64,{base64.b64encode(shot).decode()}"/>')
    cap = ("Each dot is a day one holding moved unusually far for itself. Click it for the event study and "
           "the news around it.")
    y = s.para(m, fy + bar + ih + 32, cap, "m", 12, 62 if narrow else 120, 18)
    s.h = y + 6
    s.save(name("equitylens", narrow), TOOLS)


# ---------------------------------------------------------------- my part

PARTS = [
    ("Dashboard", "TWR   XIRR via Newton's method",
     "The flagship page: returns against a blended benchmark, a 0\u201310 health score and what-if rebalancing."),
    ("Unusual moves", "\u03bb = 0.94   |z| >= 3",
     "EWMA volatility scores each day's log return against the holding's own recent volatility."),
    ("Event study", "OLS \u03b2   CAR \u00b1 1.96\u03c3",
     "A market model splits each move into a market part and a company part, with a cumulative abnormal "
     "return band."),
    ("News pipeline", "BM25 0.5  date 0.3  entity 0.2",
     "Stored once in Postgres, ranked by a hand-written BM25 index, date proximity and entity match; "
     "refreshed nightly."),
    ("Guest mode", "no sign-up   data wiped on exit",
     "Visitors try the whole product without an account, plus the landing page that sells it."),
]
CODE = [
    [("variance ", "b"), ("= ", "m"), ("LAMBDA ", "a"), ("* ", "m"), ("variance", "b")],
    [("  + ", "m"), ("(", "m"), ("1 ", "d"), ("- ", "m"), ("LAMBDA", "a"), (") * ", "m"), ("r_prev", "b"),
     ("**", "m"), ("2", "d")],
    [("sigma ", "b"), ("= ", "m"), ("math.sqrt", "a"), ("(variance)", "b")],
    [("z ", "b"), ("= ", "m"), ("r ", "b"), ("/ ", "m"), ("sigma", "b")],
    [("# unusual when |z| >= 3", "m")],
]
STACK = "React  FastAPI  PostgreSQL 16  Docker  GitHub Actions  Terraform  AWS"


def part_card(s, x, y, w, title, tag, desc, wrap, size, h=None):
    lines = textwrap.wrap(desc, wrap)
    h = h or 74 + len(lines) * size * 1.5
    s.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h:.0f}" rx="10" fill="{CARD}" stroke="{LINE}"/>')
    s.raw(f'<rect x="{x}" y="{y + 18}" width="3" height="22" rx="1.5" fill="{JAC}"/>')
    s.text(x + 18, y + 35, title, "h", 17)
    s.text(x + 18, y + 58, tag, "a", 11.5)
    for k, line in enumerate(lines):
        s.text(x + 18, y + 86 + k * size * 1.5, line, "t", size)
    return h


def code_card(s, x, y, w, h):
    s.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#08070b" stroke="{LINE}"/>')
    s.text(x + 18, y + 30, "event_detection.py", "b", 12.5)
    s.text(x + w - 16, y + 30, "simplified", "m", 10.5, anchor="end")
    for k, parts in enumerate(CODE):
        s.spans(x + 18, y + 62 + k * 20, parts, 12)


def owned(narrow=False):
    W = 480 if narrow else 960
    s = Svg(W, "The parts of EquityLens I own: " + "; ".join(f"{t} ({g}): {d}" for t, g, d in PARTS))
    if narrow:
        m = 24
        s.text(m, 44, "MY PART", "lab", 11)
        s.text(m, 68, STACK.replace("  ", " \u00b7 ", 3).replace("  ", " "), "m", 10.5)
        y = 88
        for title, tag, desc in PARTS:
            y += part_card(s, m, y, W - 2 * m, title, tag, desc, 44, 14) + 14
        code_card(s, m, y, W - 2 * m, 166)
        s.h = y + 166 + 24
    else:
        m, cw, gap, card_h = 52, 272, 20, 168
        s.text(m, 58, "MY PART", "lab", 12)
        s.text(W - m, 58, STACK, "m", 11.5, anchor="end")
        for i, (title, tag, desc) in enumerate(PARTS):
            x, y = m + (i % 3) * (cw + gap), 82 + (i // 3) * (card_h + gap)
            part_card(s, x, y, cw, title, tag, desc, 32, 12.5, card_h)
        code_card(s, m + 2 * (cw + gap), 82 + card_h + gap, cw, card_h)
        s.h = 82 + 2 * card_h + gap + 34
    s.save(name("owned", narrow))


# ---------------------------------------------------------- project cards

PROJECTS = [
    ("card-spl", "SPL compiler", "COS 341 \u00b7 Java \u00b7 group of four",
     "A compiler for SPL, the course's teaching language, built stage by stage. I worked on the parser and "
     "the semantic analysis.", "Josh-Heath123/COS341_SPL", "{;}"),
    ("card-culprit", "Culprit", "personal \u00b7 Python, Go \u00b7 in progress",
     "A multimeter for software: probes the links between components to find what is wrong, where and why, "
     "with the evidence attached.", "Josh-Heath123/Culprit", "-o-"),
    ("card-nursery", "Plant nursery simulator", "COS 214 \u00b7 C++ \u00b7 team project",
     "A nursery simulation built to show object-oriented design patterns. I built the GUI and the Iterator "
     "pattern.", "Abdulrahman-Sabah/COS214_Final_Project", "\\|/"),
    ("card-market", "Stationery marketplace", "COS 221 \u00b7 PHP, JavaScript \u00b7 team",
     "Pulls product data from several retailers' APIs into one store. I wrote the PHP API layer and the "
     "products page.", "Josua-Louw/COS221-Assignment5", "[$]"),
]


def project_card(file, title, meta, desc, repo, motif, narrow=False, lines=0, meta_lines=1, side=1):
    commits = next(r["commits"] for r in STATS["repos"] if r["repo"] == repo)
    private = repo in PRIVATE
    if narrow:
        W, m, wrap, size = 240, 16, 25, 13
    else:
        W, m, wrap, size = 470, 28, 45, 14.5
    s = Svg(W, f"{title}. {meta}. {desc} {commits} commits.", gutter=side * (6 if narrow else 9))
    if narrow:
        y = s.para(m, 36, title, "h", 14.5, 24, 20)
        y0 = y + 2
        y = max(s.para(m, y0, meta, "a", 11, 32, 16), y0 + meta_lines * 16) + 14
    else:
        s.text(W - m, 66, motif, "d", 40, anchor="end", style="opacity:.35")
        s.text(m, 50, title, "h", 22)
        s.text(m, 76, meta, "a", 13)
        y = 112
    y0 = y
    y = s.para(m, y, desc, "t", size, wrap, size * 1.5)
    y = max(y, y0 + lines * size * 1.5)   # pad so cards in a row line up
    rule = y + 4
    s.raw(f'<line x1="{m}" y1="{rule:.0f}" x2="{W - m}" y2="{rule:.0f}" stroke="{LINE}"/>')
    fs = 11.5 if narrow else 12.5
    s.text(m, rule + 24, f"{commits} commits", "m", fs)
    if private:
        s.text(W - m, rule + 24, "private" if narrow else "private repo", "m", fs, anchor="end")
    else:
        s.text(W - m - 14, rule + 24, "source", "b", fs, anchor="end")
        s.raw(arrow(W - m - 8, rule + 15))
    s.h = rule + 42
    s.save(name(file, narrow))


def projects(narrow=False):
    # Every card gets the same number of description lines, so rows line up.
    wrap = 25 if narrow else 45
    lines = max(len(textwrap.wrap(p[3], wrap)) for p in PROJECTS)
    meta_lines = max(len(textwrap.wrap(p[2], 32)) for p in PROJECTS)
    for i, (f, title, meta, desc, repo, motif) in enumerate(PROJECTS):
        side = 1 if i % 2 == 0 else -1          # left column pads right, right column pads left
        project_card(f, title, meta, desc, repo, motif, narrow, lines, meta_lines, side)


# ------------------------------------------------------------ environment

ENV = [("languages", ["Java", "Python", "TypeScript", "C++", "SQL", "Prolog"]),
       ("frontend", ["React", "Next.js", "Angular", "Vite", "Tailwind CSS"]),
       ("backend", ["FastAPI", "Node.js", "Express", "NestJS", "SQLAlchemy", "Alembic"]),
       ("data", ["PostgreSQL", "Supabase", "pandas", "NumPy"]),
       ("cloud", ["AWS", "Azure", "Docker", "GitHub Actions"])]


def environment(narrow=False):
    W = 480 if narrow else 960
    s = Svg(W, "ENVIRONMENT. " + ". ".join(f"{k.title()}: {', '.join(v)}" for k, v in ENV) + ".")
    if narrow:
        m = 24
        s.text(m, 44, "ENVIRONMENT", "lab", 11)
        y = 64
        for key, items in ENV:
            s.text(m, y + 14, key, "m", 12)
            y = chips(s, m, y + 24, items, 13, W - m) + 18
        s.h = y + 6
    else:
        s.text(52, 58, "ENVIRONMENT", "lab", 12)
        y = 84
        for key, items in ENV:
            s.text(52, y + 18, key, "m", 12.5)
            chips(s, 214, y, items, 13, W - 52)
            y += 42
        s.h = y + 18
    s.save(name("stack", narrow))


# ------------------------------------------------------- footer, buttons

def footer(narrow=False):
    W = 480 if narrow else 960
    s = Svg(W, "Josh-Heath123, University of Pretoria, October 2026, JOSH(1)")
    s.h = 56
    s.text(24 if narrow else 32, 34, "Josh-Heath123", "m", 12)
    if not narrow:
        s.text(W / 2, 34, "University of Pretoria \u00b7 October 2026", "m", 12, anchor="middle")
    s.text(W - (24 if narrow else 32), 34, "JOSH(1)", "m", 12, anchor="end")
    s.save(name("footer", narrow))


def button(file, label, glyph, external=True):
    size = 14
    w = int(len(glyph + "  " + label) * size * 0.6 + 32 + (22 if external else 0))
    s = Svg(w, label, panel=False)
    s.h = 40
    s.raw(f'<rect x=".5" y=".5" width="{w - 1}" height="39" rx="9" fill="{INK}" stroke="#3b3452"/>')
    s.raw(f'<rect x="1.5" y="36" width="{w - 3}" height="3" rx="1.5" fill="#1b1826"/>')
    s.spans(16, 25, [(glyph + "  ", "a"), (label, "b")], size)
    if external:
        s.raw(arrow(w - 25, 16, MUTED))
    s.save(file)


if __name__ == "__main__":
    for narrow in (False, True):
        about(narrow)
        history(narrow)
        equitylens(narrow)
        owned(narrow)
        projects(narrow)
        environment(narrow)
        footer(narrow)
    button("btn-linkedin.svg", "LinkedIn", "in")
    button("btn-email.svg", "joshuaheath004@gmail.com", "@", external=False)
    button("btn-equitylens.svg", "equitylens.co.za", "~>")
    button("btn-source.svg", "source on GitHub", "</>")
