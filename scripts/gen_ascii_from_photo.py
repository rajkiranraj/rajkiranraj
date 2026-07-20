#!/usr/bin/env python3
"""
Generate a clean, professional ASCII-art SVG portrait — Andrew6rant style.

THE KEY INSIGHT: a professional ASCII portrait is LIGHT and AIRY.
  • The darkest area (black shirt) should render as MEDIUM density (#, s, c)
  • The face should render as SPARSE characters (. : - =)
  • Background is pure blank (spaces)
  • No heavy block characters anywhere — cap the max density

This is achieved by remapping the image tonal range so black->medium gray,
rather than black->black. The portrait "floats" on the dark terminal bg.
"""
import html
import math
import os
import sys

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "avi-ascii.svg")

# ── ASCII settings ───────────────────────────────────────────────────────────
COLS = 80
ROWS = 44
CELL_W = 8
CELL_H = 14

# Sparse ramp — no ultra-heavy characters at all
RAMP = " .`:-~=+*cs#%"

# The max density cap: 0.0 = everything blank, 1.0 = full range.
# 0.55 means even pure black only reaches ~halfway through the ramp (around 'c')
MAX_DENSITY = 0.55

WHITE_FLOOR = 0.92       # very generous — most light pixels become blank

# ── SVG layout ───────────────────────────────────────────────────────────────
PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
ART_W = COLS * CELL_W
ART_H = ROWS * CELL_H
CANVAS_W = ART_W + PAD * 2
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD

BG_COL = "#0d1117"
BG2 = "#111722"
FRAME = "#30363d"
TITLE_TEXT = "#7d8590"
INK = "#c9d1d9"
CURSOR = "#c9d1d9"

ROW_DUR = 0.11
STAGGER = 0.11
STATIC = bool(os.environ.get("STATIC"))


def remove_background(im_rgba):
    """Remove circular gray bg and gradient glow."""
    width, height = im_rgba.size
    cx, cy = width / 2, height / 2
    radius = min(width, height) / 2

    im_rgb = im_rgba.convert("RGB")
    im_gray = im_rgba.convert("L")
    px_rgb = im_rgb.load()
    px_gray = im_gray.load()
    px_rgba = im_rgba.load()

    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            r, g, b = px_rgb[x, y]
            a = px_rgba[x, y][3]
            lum = px_gray[x, y]
            sat = max(r, g, b) - min(r, g, b)

            if dist > radius * 0.96 or a < 128:
                px_gray[x, y] = 255
            elif lum > 185 and sat < 35:
                px_gray[x, y] = 255
            elif sat > 55 and lum > 130:
                px_gray[x, y] = 255
            elif dist > radius * 0.84:
                fade = (dist - radius * 0.84) / (radius * 0.12)
                fade = min(1.0, max(0.0, fade))
                px_gray[x, y] = int(lum + (255 - lum) * fade)

    return im_gray


def remap_tonal_range(im_gray):
    """Remap pixel values so the darkest pixel maps to a medium gray,
    not to black. This is the key to a light, professional ASCII look.
    
    After this, the image range is [floor..255] where floor ~= 128,
    so even the darkest areas render as mid-density ASCII characters."""
    px = im_gray.load()
    w, h = im_gray.size

    # Find the actual darkest non-background pixel
    darkest = 255
    for y in range(h):
        for x in range(w):
            v = px[x, y]
            if v < darkest and v < 250:  # ignore bg
                darkest = v

    # Remap: darkest -> floor, 255 -> 255
    # floor is controlled by MAX_DENSITY: higher = lighter portrait
    floor = int(255 * (1.0 - MAX_DENSITY))  # MAX_DENSITY=0.55 -> floor=~114

    for y in range(h):
        for x in range(w):
            v = px[x, y]
            if v >= 250:
                px[x, y] = 255
                continue
            # Linear remap from [darkest..250] to [floor..255]
            if darkest < 250:
                t = (v - darkest) / (250 - darkest)
            else:
                t = 1.0
            px[x, y] = int(floor + t * (255 - floor))

    return im_gray


def clean_noise(rows_txt):
    """Remove isolated stray characters."""
    cleaned = []
    for y, row in enumerate(rows_txt):
        chars = list(row)
        for x, ch in enumerate(chars):
            if ch == ' ':
                continue
            neighbors = 0
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < len(rows_txt) and 0 <= nx < len(rows_txt[ny]):
                        if rows_txt[ny][nx] != ' ':
                            neighbors += 1
            if neighbors < 2:
                chars[x] = ' '
        cleaned.append("".join(chars))
    return cleaned


# ── 1. Process image ────────────────────────────────────────────────────────
im_rgba = Image.open(SRC).convert("RGBA")
im_gray = remove_background(im_rgba)

# Mild contrast boost BEFORE tonal remap (enhances face features)
im_gray = ImageEnhance.Contrast(im_gray).enhance(1.2)

# Gentle sharpen for edge clarity on face
im_gray = im_gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=100, threshold=3))

# THE KEY STEP: remap the tonal range so black shirt -> medium gray
im_gray = remap_tonal_range(im_gray)

# ── 2. Sample to ASCII ──────────────────────────────────────────────────────
im_small = im_gray.resize((COLS, ROWS), Image.LANCZOS)
px = im_small.load()

rows_txt = []
for y in range(ROWS):
    chars = []
    for x in range(COLS):
        lum = px[x, y] / 255.0
        if lum >= WHITE_FLOOR:
            chars.append(" ")
            continue
        # Map [0..WHITE_FLOOR] -> ramp index
        t = 1.0 - (lum / WHITE_FLOOR)  # 0=lightest, 1=darkest
        idx = int(t * (len(RAMP) - 1) + 0.5)
        idx = max(0, min(len(RAMP) - 1, idx))
        chars.append(RAMP[idx])
    rows_txt.append("".join(chars))

rows_txt = clean_noise(rows_txt)

# Trim blank rows
first = next((i for i, r in enumerate(rows_txt) if r.strip()), 0)
last = next((i for i in range(len(rows_txt)-1, -1, -1) if rows_txt[i].strip()), len(rows_txt)-1)
rows_txt = rows_txt[max(0, first-1):last+2]
while len(rows_txt) < ROWS:
    rows_txt.append(" " * COLS)
rows_txt = rows_txt[:ROWS]

# Recalculate canvas
ART_H = len(rows_txt) * CELL_H
CANVAS_H = TITLEBAR_H + ART_H + STATUS_H + PAD
art_top = TITLEBAR_H + PAD * 0.35

# ── 3. Build SVG ────────────────────────────────────────────────────────────
parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
    f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="ui-monospace, SFMono-Regular, '
    f'Menlo, Consolas, monospace">'
)
parts.append('<defs>'
             f'<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG_COL}"/>'
             f'</linearGradient></defs>')
parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" rx="12" fill="url(#bg)"/>')
parts.append(f'<rect x="0.5" y="0.5" width="{CANVAS_W-1}" height="{CANVAS_H-1}" rx="12" '
             f'fill="none" stroke="{FRAME}" stroke-width="1"/>')
parts.append(f'<line x1="0" y1="{TITLEBAR_H}" x2="{CANVAS_W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>')
for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
    parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
parts.append(f'<text x="{CANVAS_W/2}" y="{TITLEBAR_H/2 + 4}" fill="{TITLE_TEXT}" font-size="12" '
             f'text-anchor="middle">raj@github: ~$ ./portrait.sh</text>')

font_size = CELL_H * 0.86
for ry, line in enumerate(rows_txt):
    y_pos = art_top + ry * CELL_H + CELL_H * 0.74
    row_y = art_top + ry * CELL_H
    delay = ry * STAGGER
    safe = html.escape(line)
    text = (f'<text xml:space="preserve" x="{PAD}" y="{y_pos:.1f}" fill="{INK}" '
            f'font-size="{font_size:.1f}" textLength="{ART_W}" lengthAdjust="spacing">{safe}</text>')

    if STATIC:
        parts.append(text)
        continue

    parts.append(
        f'<clipPath id="r{ry}"><rect x="{PAD}" y="{row_y:.1f}" height="{CELL_H}" width="0">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/></rect></clipPath>'
    )
    parts.append(f'<g clip-path="url(#r{ry})">{text}</g>')
    parts.append(
        f'<rect y="{row_y+1:.1f}" width="{CELL_W}" height="{CELL_H-2}" fill="{CURSOR}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD+ART_W}" begin="{delay:.3f}s" '
        f'dur="{ROW_DUR:.2f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{delay:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{delay+ROW_DUR:.3f}s"/></rect>'
    )

status_line_y = TITLEBAR_H + ART_H + PAD * 0.35
status_y = status_line_y + 19
parts.append(f'<line x1="0" y1="{status_line_y:.1f}" x2="{CANVAS_W}" y2="{status_line_y:.1f}" stroke="{FRAME}"/>')
parts.append(f'<text x="{PAD}" y="{status_y:.1f}" fill="{TITLE_TEXT}" font-size="13">'
             f'raj@github:~$ whoami <tspan fill="{INK}">Rajkiran</tspan></text>')
parts.append(f'<rect x="{PAD+204}" y="{status_y-12:.1f}" width="8" height="14" fill="{INK}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" '
             f'dur="1s" repeatCount="indefinite"/></rect>')

parts.append("</svg>")
svg = "".join(parts)
with open(OUT, "w") as f:
    f.write(svg)
print(f"wrote {OUT} ({len(svg)} bytes; {CANVAS_W} x {CANVAS_H})")

print("\n--- ASCII Preview ---")
for row in rows_txt:
    print(row)
