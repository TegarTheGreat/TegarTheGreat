#!/usr/bin/env python3
"""Build the animated SVGs in ../assets that the profile README shows.

GitHub serves README images under a Content-Security-Policy that blocks web
fonts, so every piece of text here is converted to outlines. That keeps the
brand typefaces from tegarprayuda.com (Bricolage Grotesque, Plus Jakarta Sans)
and JetBrains Mono pixel-identical on every device. Each glyph is defined once
in <defs> and placed with <use>, which keeps the files small.

Animations are SMIL. Every animated element keeps a sensible static value, so
a renderer that ignores SMIL still shows a complete, readable image.

    pip install fonttools uharfbuzz brotli
    python scripts/build_assets.py

Edit the copy in the CONTENT section below, then re-run.

Fonts in scripts/fonts/ are SIL OFL 1.1 (licences alongside). Brand icon paths
in scripts/icons.json come from Simple Icons v16 (CC0).
"""
import io
import json
import math
import os
import re
from xml.sax.saxutils import escape

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "scripts", "fonts")
OUT_DIR = os.path.join(ROOT, "assets")

# --------------------------------------------------------------------------
# CONTENT
# --------------------------------------------------------------------------

ROLES = ["Solopreneur", "SaaS Builder", "AI-Native Engineer", "Indie Hacker", "Vibe Coder", "Dreamer"]
TAGLINE = "I build anything on the internet: solo, AI-native, and actually shipped."
BADGE_WORDS = ["SOLOPRENEUR", "SAAS BUILDER", "INDIE HACKER"]

TERMINAL = [
    ("cmd", "whoami"),
    ("out", "solopreneur · SaaS builder · AI-native engineer · dreamer"),
    ("cmd", "cat principles.txt"),
    ("ok", "effective beats busy"),
    ("ok", "done beats perfect"),
    ("ok", "tools are leverage, not shame"),
    ("cmd", "echo $MOTTO"),
    ("out", "“You don’t need to be an expert to start building —"),
    ("out", " you need to start building to become one.”"),
    ("cmd", ""),
]

PROJECTS = [
    dict(
        slug="supermd", name="SuperMD", color="violet", icon="markdown",
        sticker="npx supermd",
        tagline="A universal anti-slop system prompt that makes AI answer instead of perform. Composable for any profession.",
        chips=["103 field modules", "34/34 blind wins", "EN + ID"],
        tech="Markdown · Node CLI · npm",
    ),
    dict(
        slug="dalangai", name="DalangAI", color="yellow", icon="gunungan",
        sticker="Cursor for video",
        tagline="An agent-piloted video editor. AI writes the script, picks visuals, builds the timeline and renders. You direct.",
        chips=["1,200+ tests", "MCP server", "runs keyless"],
        tech="TypeScript · Remotion · React",
    ),
    dict(
        slug="sotongassistant", name="SotongAssistant", color="mint", icon="squid",
        sticker="lives in Telegram",
        tagline="An all-in-one Telegram assistant for moderation, onboarding, Business chats and AI. Set up entirely in chat.",
        chips=["30+ AI actions", "10 languages", "any model"],
        tech="TypeScript · grammY · SQLite",
    ),
    dict(
        slug="quidchat", name="QuidChat", color="pink", icon="bubble",
        sticker="no source, no answer",
        tagline="A support assistant for businesses that never makes things up: every claim cites your documents, or it declines.",
        chips=["cites every claim", "14 AI providers", "6 channels"],
        tech="TypeScript · Postgres · pgvector",
    ),
]

STACK = [
    ("LANGUAGES", ["TypeScript", "JavaScript", "Python", "PHP"]),
    ("WEB", ["Node.js", "React", "Vite", "Hono", "Laravel", "Tailwind CSS"]),
    ("DATA", ["PostgreSQL", "SQLite", "Zod"]),
    ("AI & BOTS", ["Claude Code", "MCP", "Telegram", "Markdown"]),
    ("SHIP", ["Git", "GitHub Actions", "Docker", "pnpm", "npm", "Biome", "Linux"]),
]

BUTTONS = [
    # (file slug, label, icon, style)  style: "violet" = filled brand button
    ("website", "tegarprayuda.com", "globe", "violet"),
    ("linkedin", "LinkedIn", "linkedin", "card"),
    ("youtube", "YouTube", "youtube", "card"),
    ("tiktok", "TikTok", "tiktok", "card"),
    ("contact", "Send me a message", "mail", "violet"),
    ("guestbook", "Sign my guestbook", "pen", "yellow"),
]

NOTE = ["no fancy degree.", "no wall of certs.", "just a dreamer", "who ships."]

TICKER = ["SHIP SMALL", "SHIP OFTEN", "DONE BEATS PERFECT", "AI, BUT HONEST", "BUILT SOLO IN BOGOR", "ALWAYS BE BUILDING"]

# --------------------------------------------------------------------------
# THEMES  (brand: tegarprayuda.com)
# --------------------------------------------------------------------------

THEMES = {
    "light": dict(
        bg="#FAF7F2", card="#FFFFFF", fg="#1C1B2E", muted="#57536E", line="#1C1B2E",
        shadow="#1C1B2E", violet="#7C3AED", on_violet="#FFFFFF", soft="#EDE4FF",
        yellow="#FFD23F", pink="#FFA3C4", mint="#8BE3B6", ok="#15803D",
        dot="#1C1B2E", dot_op="0.10",
    ),
    "dark": dict(
        bg="#1C1B2E", card="#262539", fg="#FAF7F2", muted="#BDB9D3", line="#FAF7F2",
        shadow="#7C3AED", violet="#A78BFA", on_violet="#1C1B2E", soft="#3A2C66",
        yellow="#FFD23F", pink="#FFA3C4", mint="#8BE3B6", ok="#8BE3B6",
        dot="#FAF7F2", dot_op="0.07",
    ),
}
INK = "#1C1B2E"

# --------------------------------------------------------------------------
# TEXT ENGINE: HarfBuzz shaping + fontTools outlines
# --------------------------------------------------------------------------


class Font:
    def __init__(self, key, filename):
        self.key = key
        src = TTFont(os.path.join(FONT_DIR, filename))
        src.flavor = None
        buf = io.BytesIO()
        src.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.cmap = self.tt.getBestCmap()
        self.upem = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(data))

    def shape(self, text):
        missing = [c for c in text if ord(c) not in self.cmap]
        if missing:
            raise ValueError(f"{self.key}: no glyph for {missing!r} in {text!r}")
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": False, "calt": False})
        return [(self.order[i.codepoint], p.x_advance, p.x_offset, p.y_offset)
                for i, p in zip(buf.glyph_infos, buf.glyph_positions)]

    def outline(self, name):
        pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
        self.glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
        return pen.getCommands()

    def width(self, text, size, ls=0.0):
        run = self.shape(text)
        return sum(g[1] for g in run) * size / self.upem + ls * max(len(run) - 1, 0)


FONTS = {}


def font(key):
    files = {
        "display": "bricolage-grotesque-latin-800-normal.woff",
        "body5": "plus-jakarta-sans-latin-500-normal.woff",
        "body6": "plus-jakarta-sans-latin-600-normal.woff",
        "body7": "plus-jakarta-sans-latin-700-normal.woff",
        "body8": "plus-jakarta-sans-latin-800-normal.woff",
        "mono": "jetbrains-mono-latin-400-normal.woff",
        "mono7": "jetbrains-mono-latin-700-normal.woff",
    }
    if key not in FONTS:
        FONTS[key] = Font(key, files[key])
    return FONTS[key]


def f1(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.glyph_defs = {}
        self.defs = []
        self.body = []

    def add(self, *parts):
        self.body.extend(parts)

    def glyph(self, fnt, name):
        gid = re.sub(r"[^A-Za-z0-9_-]", "_", f"{fnt.key}-{name}")
        if gid not in self.glyph_defs:
            self.glyph_defs[gid] = fnt.outline(name)
        return gid

    def text(self, key, s, x, y, size, fill, anchor="start", ls=0.0, glyph_anim=None, attrs=""):
        """Place a line of text as outlines.

        Returns (svg, width, stops) where stops[i] is the x after glyph i,
        useful for cursors. glyph_anim(i, n) may return SMIL for glyph i.
        """
        fnt = font(key)
        run = fnt.shape(s)
        scale = size / fnt.upem
        ls_fu = ls / scale
        total_fu = sum(g[1] for g in run) + ls_fu * max(len(run) - 1, 0)
        width = total_fu * scale
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        uses, stops, pen = [], [], 0.0
        n = len(run)
        for i, (name, adv, xo, yo) in enumerate(run):
            if fnt.outline(name):
                anim = glyph_anim(i, n) if glyph_anim else ""
                gx, gy = pen + xo, -yo
                pos = (f' x="{round(gx)}"' if round(gx) else "") + (f' y="{round(gy)}"' if round(gy) else "")
                ref = self.glyph(fnt, name)
                uses.append(f'<use href="#{ref}"{pos}>{anim}</use>' if anim else f'<use href="#{ref}"{pos}/>')
            pen += adv + (ls_fu if i < n - 1 else 0)
            stops.append(x + pen * scale)
        g = (f'<g fill="{fill}" transform="translate({f1(x)} {f1(y)}) scale({scale:.5f})"{attrs}>'
             + "".join(uses) + "</g>")
        return g, width, stops

    def render(self):
        glyphs = "".join(f'<path id="{k}" d="{v}"/>' for k, v in self.glyph_defs.items())
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="title">'
            f'<title id="title">{escape(self.title)}</title>'
            f"<defs>{glyphs}{''.join(self.defs)}</defs>{''.join(self.body)}</svg>"
        )


def wrap(key, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and font(key).width(trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


# --------------------------------------------------------------------------
# SHAPES
# --------------------------------------------------------------------------


def box(x, y, w, h, r, fill, t, stroke=3, shadow=8, attrs=""):
    """Neo-brutalist box: solid offset shadow, ink outline."""
    out = []
    if shadow:
        out.append(f'<rect x="{f1(x + shadow)}" y="{f1(y + shadow)}" width="{f1(w)}" height="{f1(h)}" rx="{r}" fill="{t["shadow"]}"/>')
    out.append(f'<rect x="{f1(x)}" y="{f1(y)}" width="{f1(w)}" height="{f1(h)}" rx="{r}" fill="{fill}" '
               f'stroke="{t["line"]}" stroke-width="{stroke}"{attrs}/>')
    return "".join(out)


def sparkle(cx, cy, s, fill):
    k = 0.18 * s
    return (f'<path transform="translate({f1(cx)} {f1(cy)})" fill="{fill}" d="M0 {-s}C{k} {-k} {k} {-k} {s} 0'
            f'C{k} {k} {k} {k} 0 {s}C{-k} {k} {-k} {k} {-s} 0C{-k} {-k} {-k} {-k} 0 {-s}Z"/>')


def twinkle(dur, begin):
    return (f'<animateTransform attributeName="transform" type="scale" additive="sum" values="1;0.55;1" '
            f'keyTimes="0;0.5;1" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1" dur="{dur}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>')


def float_anim(dy, dur, begin=0):
    return (f'<animateTransform attributeName="transform" type="translate" additive="sum" values="0 0;0 {-dy};0 0" '
            f'keyTimes="0;0.5;1" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1" dur="{dur}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>')


def wiggle(deg, dur, begin=0):
    return (f'<animateTransform attributeName="transform" type="rotate" additive="sum" '
            f'values="0;{deg};0;{-deg};0" keyTimes="0;0.25;0.5;0.75;1" calcMode="spline" '
            f'keySplines=".45 0 .55 1;.45 0 .55 1;.45 0 .55 1;.45 0 .55 1" dur="{dur}s" begin="{begin}s" '
            f'repeatCount="indefinite"/>')


def dots_pattern(pid, t):
    return (f'<pattern id="{pid}" width="22" height="22" patternUnits="userSpaceOnUse">'
            f'<circle cx="2" cy="2" r="1.6" fill="{t["dot"]}" fill-opacity="{t["dot_op"]}"/></pattern>')


def pin_icon(x, y, color):
    return (f'<g transform="translate({f1(x)} {f1(y)})"><path fill="{color}" d="M0-9C-5-9-8-5.5-8-1.6-8 3.6 0 11 0 11S8 3.6 8-1.6C8-5.5 5-9 0-9Z"/>'
            f'<circle cy="-1.8" r="3" fill="#FFFFFF"/></g>')


def link_icon(x, y, color):
    return (f'<g transform="translate({f1(x)} {f1(y)})" fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round">'
            f'<circle r="8.5"/><path d="M-8.5 0H8.5M0-8.5C4-4 4 4 0 8.5M0-8.5C-4-4-4 4 0 8.5"/></g>')


def live_dot(x, y, color):
    return (f'<g transform="translate({f1(x)} {f1(y)})"><circle r="9" fill="{color}" fill-opacity="0.35">'
            f'<animate attributeName="r" values="5;10;5" dur="2s" repeatCount="indefinite"/>'
            f'<animate attributeName="fill-opacity" values="0.45;0;0.45" dur="2s" repeatCount="indefinite"/></circle>'
            f'<circle r="5" fill="{color}"/></g>')


def bolt(cx, cy, s, fill, t):
    return (f'<path transform="translate({f1(cx)} {f1(cy)}) scale({s})" fill="{fill}" stroke="{t["line"]}" '
            f'stroke-width="{2.4 / s:.2f}" stroke-linejoin="round" d="M4-26-14 4H-1L-5 26 14-6H1Z"/>')


def check(x, y, color, w=2.8):
    return (f'<path transform="translate({f1(x)} {f1(y)})" d="M-6 0-1.5 4.5 7-5" fill="none" stroke="{color}" '
            f'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')


def arrow(x, y, color):
    return (f'<path transform="translate({f1(x)} {f1(y)})" d="M-8 0H8M2-6 8 0 2 6" fill="none" stroke="{color}" '
            f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')


def project_icon(kind, cx, cy, t, icons):
    if kind == "markdown":
        p = icons["Markdown"]["path"]
        return f'<path transform="translate({cx - 17} {cy - 17}) scale(1.4167)" fill="#FFFFFF" d="{p}"/>' \
            if t["on_violet"] == "#FFFFFF" else \
            f'<path transform="translate({cx - 17} {cy - 17}) scale(1.4167)" fill="{INK}" d="{p}"/>'
    if kind == "gunungan":
        return (f'<g transform="translate({cx} {cy})"><path fill="{INK}" d="M0-22C9-13 16-2 14 9 13 14 9 17 0 17-9 17-13 14-14 9-16-2-9-13 0-22Z"/>'
                f'<path d="M0-12V12M0 0 7-6M0 0-7-6M0 7 6 2M0 7-6 2" stroke="#FFD23F" stroke-width="2" stroke-linecap="round" fill="none"/>'
                f'<rect x="-10" y="16" width="20" height="5" rx="2" fill="{INK}"/></g>')
    if kind == "squid":
        return (f'<g transform="translate({cx} {cy - 3})"><path fill="{INK}" d="M0-21C9-14 13-4 12 5L8 8H-8L-12 5C-13-4-9-14 0-21Z"/>'
                f'<circle cx="-4.5" cy="0" r="2.6" fill="#FFFFFF"/><circle cx="4.5" cy="0" r="2.6" fill="#FFFFFF"/>'
                f'<path d="M-7 8C-9 13-5 15-8 20M-2.5 8C-3.5 13 0 15-2 21M2.5 8C3.5 13 0 15 2 21M7 8C9 13 5 15 8 20" '
                f'stroke="{INK}" stroke-width="2.8" stroke-linecap="round" fill="none"/></g>')
    if kind == "bubble":
        return (f'<g transform="translate({cx} {cy})"><path fill="{INK}" d="M-15-15H15A5 5 0 0 1 20-10V6A5 5 0 0 1 15 11H-3L-12 19V11H-15A5 5 0 0 1-20 6V-10A5 5 0 0 1-15-15Z"/>'
                f'<path d="M-8-2-2 4 9-7" fill="none" stroke="#FFA3C4" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></g>')
    raise ValueError(kind)


def luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


# --------------------------------------------------------------------------
# ASSETS
# --------------------------------------------------------------------------


def build_banner(theme):
    t = THEMES[theme]
    W, H = 1200, 450
    s = Svg(W, H, "Tegar Prayuda: solopreneur, SaaS builder and AI-native engineer from Bogor, Indonesia")
    s.defs.append(dots_pattern("dots", t))
    s.add(box(12, 12, 1164, 414, 24, t["bg"], t, shadow=10))
    s.add('<rect x="14" y="14" width="1160" height="410" rx="22" fill="url(#dots)"/>')
    x0 = 66

    # "HALO! I'M" pill, slightly tilted
    label, lw, _ = s.text("body8", "HALO! I’M", 0, 0, 17, t["on_violet"], ls=2.6)
    pw = lw + 40
    s.add(f'<g transform="translate({x0} 58) rotate(-3)">'
          + box(0, 0, pw, 40, 20, t["violet"], t, stroke=2.5, shadow=4)
          + s.text("body8", "HALO! I’M", 20, 26.5, 17, t["on_violet"], ls=2.6)[0]
          + "</g>")

    # Name
    name_size = 104
    while font("display").width("Tegar Prayuda", name_size, -2.5) > 690:
        name_size -= 2
    g, nw, stops = s.text("display", "Tegar Prayuda", x0 - 4, 200, name_size, t["fg"], ls=-2.5)
    s.add(g)
    # hand-drawn underline beneath "Prayuda"
    sx, ex = stops[5] + 4, stops[-1] - 4
    wave, x, up = [f"M{f1(sx)} 222"], sx, True
    step = (ex - sx) / 8
    while x < ex - 1:
        wave.append(f"Q{f1(x + step / 2)} {214 if up else 230} {f1(x + step)} 222")
        x += step
        up = not up
    s.add(f'<path d="{" ".join(wave)}" fill="none" stroke="{t["violet"]}" stroke-width="7" stroke-linecap="round" '
          f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="0">'
          f'<animate attributeName="stroke-dashoffset" values="1;1;0" keyTimes="0;0.35;1" dur="1.4s" '
          f'calcMode="spline" keySplines="0 0 1 1;.3 .7 .4 1" fill="freeze"/></path>')

    # Typing role line: a yellow sticker block grows with the typed text, so
    # the ink lettering always sits on yellow (legible in both themes).
    size, base, pad = 46, 290, 12
    per_char, hold, gap = 0.075, 1.7, 0.35
    runs, tcur = [], 0.4
    for role in ROLES:
        t_typed = tcur + len(role) * per_char
        t_del = t_typed + hold
        runs.append((role, tcur, t_del))
        tcur = t_del + len(role) * per_char * 0.45 + gap
    DUR = tcur
    kt = lambda v: f"{max(0.0, min(1.0, v / DUR)):.4f}"
    anim = f'calcMode="discrete" dur="{DUR:.2f}s" repeatCount="indefinite"'
    block_at = len(s.body)
    cursor_pts = []
    for idx, (role, t0, t2) in enumerate(runs):
        n_chars = len(role)

        def ganim(i, n, t0=t0, t2=t2, n_chars=n_chars):
            on = t0 + (i + 1) * per_char
            off = t2 + (n_chars - 1 - i) * per_char * 0.45
            return f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{kt(on)};{kt(off)}" {anim}/>'

        g, _, rstops = s.text("display", role, x0, base, size, INK, ls=-1, glyph_anim=ganim)
        # Only the first role shows where SMIL does not run; the <set>
        # reveals the others as soon as the animation clock starts.
        s.add(g if idx == 0 else f'<g opacity="0"><set attributeName="opacity" to="1" begin="0s"/>{g}</g>')
        cursor_pts.append((t0, x0))
        for i in range(n_chars):
            cursor_pts.append((t0 + (i + 1) * per_char, rstops[i]))
        for i in range(n_chars):
            j = n_chars - 2 - i
            cursor_pts.append((t2 + i * per_char * 0.45, rstops[j] if j >= 0 else x0))
    cursor_pts.sort()
    kts = ";".join(["0"] + [kt(p[0]) for p in cursor_pts[1:]])
    widths = ";".join(f1(p[1] - x0 + 2 * pad) if p[1] > x0 else "0" for p in cursor_pts)
    first_end = s.text("display", ROLES[0], x0, base, size, INK, ls=-1)[2][-1]
    static_w = f1(first_end - x0 + 2 * pad)
    bx0, by0, bh = x0 - pad, base - 41, 54
    block = (f'<g transform="rotate(-1.5 {x0} {base})">'
             f'<rect x="{bx0 + 5}" y="{by0 + 5}" width="{static_w}" height="{bh}" rx="10" fill="{t["shadow"]}">'
             f'<animate attributeName="width" values="{widths}" keyTimes="{kts}" {anim}/></rect>'
             f'<rect x="{bx0}" y="{by0}" width="{static_w}" height="{bh}" rx="10" fill="{t["yellow"]}" stroke="{t["line"]}" stroke-width="2.6">'
             f'<animate attributeName="width" values="{widths}" keyTimes="{kts}" {anim}/></rect></g>')
    s.body.insert(block_at, block)
    xs = ";".join(f1(p[1] + 16) for p in cursor_pts)
    s.add(f'<rect x="{f1(first_end + 16)}" y="{by0 + 3}" width="5" height="{bh - 6}" rx="2" fill="{t["violet"]}">'
          f'<animate attributeName="x" values="{xs}" keyTimes="{kts}" {anim}/>'
          f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" calcMode="discrete" dur="1.05s" repeatCount="indefinite"/></rect>')

    # Tagline
    s.add(s.text("body5", TAGLINE, x0, 344, 21, t["muted"])[0])

    # Info pills
    px = x0
    for icon, text in (("pin", "Bogor, Indonesia"), ("link", "tegarprayuda.com"), ("live", "Open to collabs")):
        _, tw, _ = s.text("body7", text, 0, 0, 16, t["fg"])
        w = tw + 62
        s.add(box(px, 370, w, 38, 19, t["card"], t, stroke=2.2, shadow=3.5))
        cx = px + 24
        if icon == "pin":
            s.add(pin_icon(cx, 388.5, t["violet"]))
        elif icon == "link":
            s.add(link_icon(cx, 389, t["violet"]))
        else:
            s.add(live_dot(cx, 389, "#22C55E"))
        s.add(s.text("body7", text, px + 42, 394.5, 16, t["fg"])[0])
        px += w + 16

    # Right collage ------------------------------------------------------
    # spinning badge
    bx, by, R = 1032, 150, 104
    s.add(f'<circle cx="{bx + 7}" cy="{by + 7}" r="{R}" fill="{t["shadow"]}"/>')
    s.add(f'<circle cx="{bx}" cy="{by}" r="{R}" fill="{t["violet"]}" stroke="{t["line"]}" stroke-width="3"/>')
    ring_r, rsize = 80, 17
    words = [(w, font("body8").width(w, rsize, 2.2)) for w in BADGE_WORDS]
    circ = 2 * math.pi * ring_r
    gap = (circ - sum(w for _, w in words)) / len(words)
    ring = []
    pos = 0.0
    for word, ww in words:
        fnt = font("body8")
        run = fnt.shape(word)
        sc = rsize / fnt.upem
        pen = pos
        for gname, adv, _, _ in run:
            gw = adv * sc
            mid = pen + gw / 2
            ang = mid / ring_r - math.pi / 2
            gx = bx + ring_r * math.cos(ang)
            gy = by + ring_r * math.sin(ang)
            rot = math.degrees(ang) + 90
            if fnt.outline(gname):
                ring.append(f'<use href="#{s.glyph(fnt, gname)}" transform="translate({f1(gx)} {f1(gy)}) rotate({f1(rot)}) '
                            f'translate({f1(-gw / 2)} {f1(rsize * 0.36)}) scale({sc:.5f})"/>')
            pen += gw + 2.2
        star_at = pos + ww + gap / 2
        ang = star_at / ring_r - math.pi / 2
        ring.append(sparkle(bx + ring_r * math.cos(ang), by + ring_r * math.sin(ang), 7, t["on_violet"]))
        pos += ww + gap
    s.add(f'<g fill="{t["on_violet"]}">{"".join(ring)}'
          f'<animateTransform attributeName="transform" type="rotate" from="0 {bx} {by}" to="360 {bx} {by}" dur="26s" repeatCount="indefinite"/></g>')
    s.add(f'<circle cx="{bx}" cy="{by}" r="52" fill="{t["yellow"]}" stroke="{t["line"]}" stroke-width="3"/>')
    s.add(f'<g transform="translate({bx} {by})"><g>{bolt(0, 0, 1.05, INK, dict(line=INK))}{wiggle(6, 3.2)}</g></g>')

    # code-window sticker
    s.add(f'<g transform="translate(812 262) rotate(-6)"><g>'
          + box(0, 0, 214, 128, 14, t["card"], t, stroke=3, shadow=7)
          + f'<path d="M1.5 32H212.5" stroke="{t["line"]}" stroke-width="3"/>'
          + "".join(f'<circle cx="{20 + i * 18}" cy="16.5" r="5.5" fill="{c}" stroke="{t["line"]}" stroke-width="2"/>'
                    for i, c in enumerate((t["pink"], t["yellow"], t["mint"])))
          + s.text("display", "</>", 22, 98, 52, t["violet"])[0]
          + s.text("body8", "ship it.", 108, 90, 21, t["fg"])[0]
          + float_anim(7, 4.2) + "</g></g>")

    # "done > perfect" sticker
    _, dw, _ = s.text("body8", "done > perfect", 0, 0, 19, INK)
    s.add(f'<g transform="translate({1150 - dw - 40} 352) rotate(5)"><g>'
          + box(0, 0, dw + 40, 46, 23, t["pink"], t, stroke=2.6, shadow=5)
          + s.text("body8", "done > perfect", 20, 30.5, 19, INK)[0]
          + float_anim(6, 3.6, 0.8) + "</g></g>")

    for cx, cy, sz, col, d, b in ((820, 92, 13, t["violet"], 2.6, 0), (1160, 262, 11, t["yellow"], 3.1, 0.5),
                                   (760, 330, 9, t["pink"], 2.2, 1.1), (1164, 42, 8, t["mint"], 2.8, 0.3)):
        s.add(f'<g transform="translate({cx} {cy})"><g>{sparkle(0, 0, sz, col)}{twinkle(d, b)}</g></g>')
    return s


def build_terminal(theme):
    t = THEMES[theme]
    size, lh, top, x0 = 21, 36, 104, 58
    H = top + lh * len(TERMINAL) + 34
    s = Svg(1200, H, "whoami: solopreneur, SaaS builder, AI-native engineer. Principles: effective beats busy, done beats perfect, tools are leverage.")
    s.add(box(12, 12, 1164, H - 32, 22, t["card"], t, shadow=10))
    s.add(f'<path d="M13.5 62H1174.5" stroke="{t["line"]}" stroke-width="3"/>')
    for i, c in enumerate((t["pink"], t["yellow"], t["mint"])):
        s.add(f'<circle cx="{44 + i * 26}" cy="37" r="8" fill="{c}" stroke="{t["line"]}" stroke-width="2.4"/>')
    s.add(s.text("body7", "tegar@bogor: ~", 600, 43, 16, t["muted"], anchor="middle")[0])

    per_char = 0.055
    events, tcur = [], 0.8
    line_times = []
    for kind, text in TERMINAL:
        if kind == "cmd":
            start = tcur
            end = start + len(text) * per_char
            line_times.append((start, end))
            tcur = end + (0.45 if text else 0)
        else:
            line_times.append((tcur, tcur))
            tcur += 0.22
    DUR = tcur + 4.5
    kt = lambda v: f"{max(0.0, min(1.0, v / DUR)):.4f}"
    show = lambda at: (f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{kt(at)};{kt(DUR - 0.25)}" '
                       f'calcMode="discrete" dur="{DUR:.2f}s" repeatCount="indefinite"/>')
    prompt_w = font("mono7").width("tegar@bogor", size) + font("mono").width(":~$ ", size)
    cursor_pts = []
    for li, ((kind, text), (start, end)) in enumerate(zip(TERMINAL, line_times)):
        y = top + li * lh
        if kind == "cmd":
            g1, w1, _ = s.text("mono7", "tegar@bogor", x0, y, size, t["violet"])
            g2, w2, _ = s.text("mono", ":~$ ", x0 + w1, y, size, t["muted"])
            s.add(f'<g>{g1}{g2}{show(start)}</g>')
            cx = x0 + prompt_w
            cursor_pts.append((start, cx, y))
            if text:
                g, _, stops = s.text("mono", text, cx, y, size, t["fg"],
                                     glyph_anim=lambda i, n, st=start: show(st + (i + 1) * per_char))
                s.add(g)
                for i, st in enumerate(stops):
                    cursor_pts.append((start + (i + 1) * per_char, st, y))
        elif kind == "ok":
            s.add(f'<g>{check(x0 + 10, y - 7, t["ok"])}'
                  + s.text("mono", text, x0 + 34, y, size, t["fg"])[0] + show(start) + "</g>")
        else:
            s.add(f'<g>{s.text("mono", text, x0, y, size, t["muted"] if not text.startswith((" ", "“")) else t["fg"])[0]}{show(start)}</g>')
    # sticky note (paraphrased from tegarprayuda.com/tentang)
    note = [f'<g transform="translate(872 104) rotate(4)"><g>',
            box(0, 0, 252, 186, 10, t["yellow"], t, stroke=2.6, shadow=7),
            f'<rect x="92" y="-14" width="72" height="26" rx="3" fill="{t["pink"]}" fill-opacity="0.9" '
            f'stroke="{t["line"]}" stroke-width="2" transform="rotate(-6 128 -1)"/>']
    for i, line in enumerate(NOTE):
        note.append(s.text("body8", line, 24, 52 + i * 34, 20, INK)[0])
    note.append(f'<g transform="translate(222 158)"><g>{sparkle(0, 0, 11, INK)}{twinkle(2.4, 0)}</g></g>')
    note.append(float_anim(6, 4.6) + "</g></g>")
    s.add("".join(note))
    last_x, last_y = cursor_pts[-1][1], cursor_pts[-1][2]
    xs = ";".join(f1(p[1] + 2) for p in cursor_pts)
    ys = ";".join(f1(p[2] - 18) for p in cursor_pts)
    kts = ";".join(["0"] + [kt(p[0]) for p in cursor_pts[1:]])
    s.add(f'<rect x="{f1(last_x + 2)}" y="{f1(last_y - 18)}" width="12" height="23" fill="{t["violet"]}">'
          f'<animate attributeName="x" values="{xs}" keyTimes="{kts}" calcMode="discrete" dur="{DUR:.2f}s" repeatCount="indefinite"/>'
          f'<animate attributeName="y" values="{ys}" keyTimes="{kts}" calcMode="discrete" dur="{DUR:.2f}s" repeatCount="indefinite"/>'
          f'<animate attributeName="opacity" values="1;0" keyTimes="0;0.5" calcMode="discrete" dur="1.05s" repeatCount="indefinite"/></rect>')
    return s


def build_project(theme, p, icons, lines_needed):
    t = THEMES[theme]
    color = t[p["color"]]
    on_color = t["on_violet"] if p["color"] == "violet" else INK
    W = 600
    tag_top = 146
    chips_y = tag_top + 27 * lines_needed + 6
    foot_y = chips_y + 72
    H = foot_y + 44
    s = Svg(W, H, f'{p["name"]}: {p["tagline"]}')
    s.add(box(10, 10, W - 32, H - 30, 22, t["card"], t, shadow=9))
    s.add(box(38, 38, 66, 66, 16, color, t, stroke=2.6, shadow=4))
    s.add(project_icon(p["icon"], 71, 71, t, icons))
    name_size = 36
    while font("display").width(p["name"], name_size, -0.8) > 260:
        name_size -= 1
    s.add(s.text("display", p["name"], 124, 84, name_size, t["fg"], ls=-0.8)[0])

    _, sw, _ = s.text("body8", p["sticker"], 0, 0, 14.5, on_color)
    stx = W - 38 - sw - 30
    s.add(f'<g transform="translate({f1(stx)} 30) rotate(4)"><g>'
          + box(0, 0, sw + 30, 34, 17, t["soft"] if p["color"] == "violet" else color, t, stroke=2.2, shadow=3.5)
          + s.text("body8", p["sticker"], 15, 22.5, 14.5, t["fg"] if p["color"] == "violet" else INK)[0]
          + wiggle(2.2, 4.4, 0.3) + "</g></g>")

    for i, line in enumerate(wrap("body6", p["tagline"], 18.5, W - 84)):
        s.add(s.text("body6", line, 40, tag_top + i * 27, 18.5, t["muted"])[0])

    cx = 40
    for chip in p["chips"]:
        _, cw, _ = s.text("body7", chip, 0, 0, 15, t["fg"])
        s.add(box(cx, chips_y, cw + 28, 34, 17, t["bg"], t, stroke=2, shadow=3))
        s.add(s.text("body7", chip, cx + 14, chips_y + 22.5, 15, t["fg"])[0])
        cx += cw + 40
    s.add(f'<path d="M40 {foot_y - 16}H{W - 62}" stroke="{t["line"]}" stroke-opacity="0.18" stroke-width="2" stroke-dasharray="2 7" stroke-linecap="round"/>')
    s.add(s.text("body7", p["tech"], 40, foot_y + 12, 15, t["muted"])[0])
    s.add(f'<circle cx="{W - 76}" cy="{foot_y + 6}" r="19" fill="{color}" stroke="{t["line"]}" stroke-width="2.4"/>')
    s.add(f'<g>{arrow(W - 76, foot_y + 6, on_color)}'
          f'<animateTransform attributeName="transform" type="translate" values="0 0;4 0;0 0" dur="1.6s" repeatCount="indefinite"/></g>')
    return s


def build_stack(theme, icons):
    t = THEMES[theme]
    s = Svg(1200, 10, "Toolbox: " + "; ".join(f"{c}: {', '.join(items)}" for c, items in STACK))
    rows, y, idx = [], 58, 0
    body = []
    label_x, chip_x0, max_x = 56, 236, 1150
    for cat, items in STACK:
        body.append(s.text("display", cat, label_x, y + 30, 21, t["violet"], ls=0.6)[0])
        x = chip_x0
        for item in items:
            ic = icons[item]
            _, tw, _ = s.text("body7", item, 0, 0, 16.5, t["fg"])
            w = 58 + tw + 18
            if x + w > max_x:
                x = chip_x0
                y += 62
            brand = "#" + ic["hex"]
            badge_fill = brand
            glyph = "#FFFFFF" if luminance(brand) < 0.45 else INK
            chip = (box(0, 0, w, 44, 22, t["card"], t, stroke=2.2, shadow=4)
                    + f'<circle cx="23" cy="22" r="15" fill="{badge_fill}" stroke="{t["line"]}" stroke-width="2"/>'
                    + f'<path transform="translate(14.6 13.6) scale(0.7)" fill="{glyph}" d="{ic["path"]}"/>'
                    + s.text("body7", item, 48, 28, 16.5, t["fg"])[0])
            begin = 0.25 + idx * 0.045
            dur = begin + 0.4
            body.append(
                f'<g transform="translate({f1(x + w / 2)} {y + 22})"><g>'
                f'<g transform="translate({f1(-w / 2)} -22)">{chip}</g>'
                f'<animateTransform attributeName="transform" type="scale" values="0.4;0.4;1.08;1" '
                f'keyTimes="0;{begin / dur:.3f};{(begin + 0.28) / dur:.3f};1" dur="{dur:.2f}s" fill="freeze"/>'
                f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;{begin / dur:.3f};{(begin + 0.12) / dur:.3f}" '
                f'dur="{dur:.2f}s" fill="freeze"/></g></g>')
            x += w + 14
            idx += 1
        y += 72
    H = y + 18
    s.h = H
    s.add(box(12, 12, 1164, H - 34, 24, t["bg"], t, shadow=10))
    s.defs.append(dots_pattern("dots", t))
    s.add(f'<rect x="14" y="14" width="1160" height="{H - 38}" rx="22" fill="url(#dots)"/>')
    s.add(*body)
    return s


def build_ticker(theme):
    t = THEMES[theme]
    W, H = 1200, 118
    s = Svg(W, H, "Ship small. Ship often. Done beats perfect. AI, but honest. Built solo in Bogor.")
    s.add(box(12, 16, 1164, 76, 38, t["violet"], t, shadow=9))
    s.defs.append('<clipPath id="band"><rect x="16" y="19" width="1156" height="70" rx="35"/></clipPath>')
    size = 30
    seq, pen = [], 0.0
    for word in TICKER:
        g, w, _ = s.text("display", word, pen, 66, size, t["on_violet"], ls=1.2)
        seq.append(g)
        pen += w + 26
        seq.append(sparkle(pen, 55, 10, t["yellow"]))
        pen += 36
    seq_w = pen
    copies = math.ceil(W / seq_w) + 1
    tiles = "".join(f'<g transform="translate({f1(i * seq_w)} 0)">{"".join(seq)}</g>' for i in range(copies))
    s.add(f'<g clip-path="url(#band)"><g transform="translate(40 0)"><g>{tiles}'
          f'<animateTransform attributeName="transform" type="translate" from="0 0" to="{f1(-seq_w)} 0" '
          f'dur="{seq_w / 55:.1f}s" repeatCount="indefinite"/></g></g></g>')
    return s


def button_icon(kind, cx, cy, t, icons, fg):
    if kind == "globe":
        return link_icon(cx, cy, fg)
    if kind == "linkedin":
        return (f'<rect x="{cx - 12}" y="{cy - 12}" width="24" height="24" rx="5" fill="#0A66C2"/>'
                f'<rect x="{cx - 7.5}" y="{cy - 2}" width="3.6" height="9.5" fill="#FFFFFF"/>'
                f'<circle cx="{cx - 5.7}" cy="{cy - 6}" r="2.1" fill="#FFFFFF"/>'
                f'<path d="M{cx - 1} {cy + 7.5}V{cy - 2}H{cx + 2.4}V{cy - 0.5}C{cx + 3.4} {cy - 2.4} {cx + 8.5} {cy - 2.8} {cx + 8.5} {cy + 1.8}V{cy + 7.5}H{cx + 5}V{cy + 2.5}C{cx + 5} {cy} {cx + 2.4} {cy} {cx + 2.4} {cy + 2.5}V{cy + 7.5}Z" fill="#FFFFFF"/>')
    if kind in ("youtube", "tiktok"):
        ic = icons["YouTube" if kind == "youtube" else "TikTok"]
        color = "#FF0000" if kind == "youtube" else fg
        return f'<path transform="translate({cx - 12} {cy - 12})" fill="{color}" d="{ic["path"]}"/>'
    if kind == "mail":
        return (f'<g transform="translate({cx} {cy})" fill="none" stroke="{fg}" stroke-width="2.6" stroke-linejoin="round">'
                f'<rect x="-12" y="-8.5" width="24" height="17" rx="3"/><path d="M-11-7 0 1.5 11-7"/></g>')
    if kind == "pen":
        return (f'<g transform="translate({cx} {cy}) rotate(45)" fill="{fg}">'
                f'<rect x="-3.5" y="-13" width="7" height="19" rx="1.5"/><path d="M-3.5 7H3.5L0 13Z"/></g>')
    raise ValueError(kind)


def build_button(theme, label, icon, style, icons):
    t = THEMES[theme]
    fill = {"violet": t["violet"], "yellow": t["yellow"], "card": t["card"]}[style]
    fg = t["on_violet"] if style == "violet" else (INK if style == "yellow" else t["fg"])
    tw = font("body8").width(label, 19)
    w = 24 + 26 + 12 + tw + 26
    s = Svg(round(w + 10), 62, label)
    s.add(box(3, 3, w, 50, 25, fill, t, stroke=2.8, shadow=5))
    s.add(button_icon(icon, 3 + 24 + 13, 28, t, icons, fg))
    s.add(s.text("body8", label, 3 + 24 + 26 + 12, 35, 19, fg)[0])
    return s


def main():
    with open(os.path.join(ROOT, "scripts", "icons.json")) as fh:
        icons = json.load(fh)
    os.makedirs(OUT_DIR, exist_ok=True)
    lines_needed = max(len(wrap("body6", p["tagline"], 18.5, 600 - 84)) for p in PROJECTS)
    written = []
    for theme in THEMES:
        docs = {
            f"banner-{theme}.svg": build_banner(theme),
            f"about-{theme}.svg": build_terminal(theme),
            f"stack-{theme}.svg": build_stack(theme, icons),
            f"ticker-{theme}.svg": build_ticker(theme),
        }
        for p in PROJECTS:
            docs[f'project-{p["slug"]}-{theme}.svg'] = build_project(theme, p, icons, lines_needed)
        for slug, label, icon, style in BUTTONS:
            docs[f"btn-{slug}-{theme}.svg"] = build_button(theme, label, icon, style, icons)
        for name, doc in docs.items():
            path = os.path.join(OUT_DIR, name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(doc.render())
            written.append((name, os.path.getsize(path)))
    for name, size in written:
        print(f"{size / 1024:7.1f} KB  assets/{name}")


if __name__ == "__main__":
    main()
