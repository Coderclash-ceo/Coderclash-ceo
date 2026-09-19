#!/usr/bin/env python3
"""Generate banner (VISUAL.MAP + SYSTEM.INFO) and radar SVGs from config/profile.json.

Usage:
    pip install pillow
    python scripts/generate-assets.py

Photo dot-map: put a photo at assets/portrait.jpg (face/bust, plain background works best)
and re-run. Without a photo, a dot-matrix monogram (config "monogram") is used.
"""
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
CFG = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))

THEMES = {
    "dark": dict(bg="#0B1220", panel="#0F1A2B", border="#1E2A3D", text="#D6E2F0", muted="#7D8DA6",
                 cyan="#2DD4D4", dot="#8B7FE8", green="#3DDC97", red="#FF5C7A", card="#0D1117", grid="#30363D"),
    "light": dict(bg="#F3F6FA", panel="#FFFFFF", border="#D0D7DE", text="#1F2937", muted="#6B7280",
                  cyan="#0E7490", dot="#6D5BD0", green="#15803D", red="#DC2626", card="#FFFFFF", grid="#D0D7DE"),
}
PURPLE = "#AA9BEF"

COLS, ROWS, STEP = 113, 156, 3  # dot grid -> 339 x 468 px area

CSS = """
.m{font-family:'JetBrains Mono','SFMono-Regular',Consolas,'Liberation Mono',monospace}
.l{animation:fade .5s ease backwards}
@keyframes fade{from{opacity:0}}
.pulse{animation:pulse 1.6s ease-in-out infinite}
@keyframes pulse{50%{opacity:.2}}
"""


# ---------- dot matrix ----------
def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _monogram(text):
    s = 6
    w, h = COLS * s, ROWS * s
    img = Image.new("L", (w, h), 0)
    px = img.load()
    cx, cy = w / 2, h / 2
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - cx) / (w * .5), (y - cy) / (h * .5))
            px[x, y] = int(max(0, 1 - d) ** 1.6 * 120)
    ImageDraw.Draw(img).text((cx, cy), text, font=_font(int(w * .55)), fill=255, anchor="mm")
    return img.resize((COLS, ROWS), Image.LANCZOS)


def _photo(path):
    """Photo -> tone-mapped grayscale sized to the dot grid.
    Optional config block "photo": {zoom, center_x, center_y, invert (auto/true/false), gamma}
    """
    o = CFG.get("photo", {})
    zoom = max(1.0, float(o.get("zoom", 1.0)))
    fx, fy = float(o.get("center_x", 0.5)), float(o.get("center_y", 0.42))
    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    w, h = im.size
    ar = COLS / ROWS
    if w / h > ar:
        ch = h / zoom
        cw = ch * ar
    else:
        cw = w / zoom
        ch = cw / ar
    cx = min(max(w * fx, cw / 2), w - cw / 2)
    cy = min(max(h * fy, ch / 2), h - ch / 2)
    im = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2)))
    im = im.resize((COLS, ROWS), Image.LANCZOS)
    # bright background -> invert so the background stays empty
    edge = [im.getpixel((x, y)) for x in range(COLS) for y in (0, 1, 2, ROWS - 1)]
    edge += [im.getpixel((x, y)) for y in range(ROWS) for x in (0, 1, COLS - 1)]
    inv = o.get("invert", "auto")
    if inv == "auto":
        inv = sum(edge) / len(edge) > 130
    im = ImageOps.autocontrast(im, cutoff=1)
    im = Image.blend(im, ImageOps.equalize(im), 0.45)
    g = float(o.get("gamma", 1.0))
    if g != 1.0:
        im = im.point(lambda v: int(255 * (v / 255) ** g))
    im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=170, threshold=2))
    # flatten everything close to the background tone so the background stays clean
    edge2 = sorted(im.getpixel((x, y)) for x in range(COLS) for y in (0, 1, 2, ROWS - 1))
    bgv = edge2[len(edge2) // 2]
    tol = int(o.get("bg_tolerance", 28))
    im = im.point(lambda v: bgv if abs(v - bgv) < tol else v)
    if inv:
        im = ImageOps.invert(im)
    floor = int(o.get("floor", 45))  # crush near-black -> clean, empty background
    bg_after = 255 - bgv if inv else bgv
    if bg_after < 128:
        floor = max(floor, bg_after + 4)
    im = im.point(lambda v: 0 if v < floor else min(255, int((v - floor) * 255 / (255 - floor))))
    return im


MODE = "1-BIT"


def dot_path():
    global COLS, ROWS, STEP, MODE
    photo = None
    for ext in ("jpg", "jpeg", "png", "webp", "jpg.jpg", "jpeg.jpg", "png.png", "jpg.png"):
        cand = ASSETS / f"portrait.{ext}"
        if cand.exists():
            photo = cand
            break
    if photo:
        print("Using photo:", photo)
        style = CFG.get("photo", {}).get("style", "halftone")
        if style == "halftone":
            COLS, ROWS, STEP, MODE = 68, 94, 5, "HALFTONE"
        base = _photo(photo)
        if style == "halftone":
            # variable-size dots: tone is kept, so the face stays readable when GitHub scales the banner down
            d, n = [], 0
            for y in range(ROWS):
                for x in range(COLS):
                    v = base.getpixel((x, y)) / 255
                    if v < 0.07:
                        continue
                    r = round((0.55 + 1.85 * v) * 5) / 5
                    cx, cy = x * STEP + STEP / 2, y * STEP + STEP / 2
                    d.append("M%.1f %.1fa%.1f %.1f 0 1 0 %.1f 0a%.1f %.1f 0 1 0 -%.1f 0" % (cx - r, cy, r, r, 2 * r, r, r, 2 * r))
                    n += 1
            return "".join(d), n
    else:
        print("No photo found in", ASSETS, "-> using monogram. Files there:", sorted(x.name for x in ASSETS.iterdir()))
        base = _monogram(CFG.get("monogram", "KM"))
    bits = base.convert("1")  # Floyd-Steinberg dither -> 1-bit
    d, n = [], 0
    for y in range(ROWS):
        for x in range(COLS):
            if bits.getpixel((x, y)):
                d.append("M%d %dh2v2h-2z" % (x * STEP, y * STEP))
                n += 1
    return "".join(d), n


# ---------- banner ----------
def banner(theme, dots, count):
    t = THEMES[theme]
    ox, oy = 44, 120  # origin of dot area
    rows_svg, y = "", 146
    for i, (label, value) in enumerate(CFG["info"]):
        raw_l, raw_v = label, value
        label, value = html.escape(label), html.escape(value)
        delay = 0.4 + i * 0.14
        x1 = 444 + len(raw_l) * 9 + 12
        x2 = 1156 - len(raw_v) * 9 - 12
        leader = ""
        if x2 > x1:
            leader = (f'<line x1="{x1}" y1="{y - 5}" x2="{x2}" y2="{y - 5}" stroke="{t["muted"]}" '
                      f'stroke-opacity=".45" stroke-width="1.6" stroke-dasharray="1 6" stroke-linecap="round"/>')
        rows_svg += (
            f'<g class="l" style="animation-delay:{delay:.2f}s">'
            f'<text x="444" y="{y}" class="m" font-size="15" fill="{t["muted"]}">{label}</text>{leader}'
            f'<text x="1156" y="{y}" class="m" font-size="15" text-anchor="end" fill="{t["text"]}">{value}</text></g>\n'
        )
        y += 32
    br = 14  # corner bracket size
    x0, y0, x1b, y1b = ox - 4, oy - 4, ox + COLS * STEP + 2, oy + ROWS * STEP + 2
    brackets = "".join(
        f'<path d="M{a} {b + dy * br}V{b}H{a + dx * br}" fill="none" stroke="{t["cyan"]}" stroke-opacity=".6"/>'
        for a, b, dx, dy in ((x0, y0, 1, 1), (x1b, y0, -1, 1), (x0, y1b, 1, -1), (x1b, y1b, -1, -1))
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="660" viewBox="0 0 1200 660">
<defs><style>{CSS}</style>
<clipPath id="dotclip"><rect x="{ox}" y="{oy}" width="{COLS * STEP}" height="{ROWS * STEP}"/></clipPath></defs>
<rect width="1200" height="660" rx="18" fill="{t['bg']}"/>
<rect x="1" y="1" width="1198" height="658" rx="18" fill="none" stroke="{t['border']}" stroke-width="2"/>
<circle cx="34" cy="34" r="6" fill="#FF5F56"/><circle cx="56" cy="34" r="6" fill="#FFBD2E"/><circle cx="78" cy="34" r="6" fill="#27C93F"/>
<text x="600" y="39" text-anchor="middle" class="m" font-size="13" fill="{t['muted']}">profile.sh --live</text>

<rect x="24" y="64" width="380" height="560" rx="8" fill="{t['panel']}" stroke="{t['border']}"/>
<text x="44" y="92" class="m" font-size="13" font-weight="700" fill="{t['cyan']}">VISUAL.MAP</text>
<text x="384" y="92" text-anchor="end" class="m" font-size="11" fill="{t['muted']}">{COLS * STEP}×{ROWS * STEP} / {MODE}</text>
<line x1="24" y1="104" x2="404" y2="104" stroke="{t['border']}"/>
<g transform="translate({ox} {oy})"><path d="{dots}" fill="{t['dot']}" fill-opacity=".9"/></g>
{brackets}
<g clip-path="url(#dotclip)"><rect x="{ox}" y="{oy}" width="{COLS * STEP}" height="2" fill="{t['cyan']}" fill-opacity=".55">
<animate attributeName="y" values="{oy};{oy + ROWS * STEP};{oy}" dur="6s" repeatCount="indefinite"/></rect></g>
<text x="44" y="612" class="m" font-size="10" fill="{t['muted']}">PTS {count} · {'HALFTONE' if MODE == 'HALFTONE' else 'FS/SERPENTINE'}</text>

<rect x="420" y="64" width="756" height="560" rx="8" fill="{t['panel']}" stroke="{t['border']}"/>
<text x="444" y="92" class="m" font-size="13" font-weight="700" fill="{t['cyan']}">SYSTEM.INFO</text>
<circle cx="826" cy="88" r="4" fill="{t['red']}" class="pulse"/><text x="838" y="92" class="m" font-size="12" fill="{t['red']}">LIVE</text>
<rect x="896" y="74" width="260" height="28" rx="14" fill="{t['cyan']}" fill-opacity=".08" stroke="{t['cyan']}" stroke-opacity=".5"/>
<text x="1026" y="93" text-anchor="middle" class="m" font-size="13" fill="{t['cyan']}">@{CFG['github']}</text>
<line x1="420" y1="112" x2="1176" y2="112" stroke="{t['border']}"/>
{rows_svg}<line x1="420" y1="580" x2="1176" y2="580" stroke="{t['border']}"/>
<circle cx="450" cy="600" r="3.5" fill="{t['green']}" class="pulse"/><text x="462" y="604" class="m" font-size="11" fill="{t['green']}">ALL SYSTEMS NOMINAL</text>
<text x="1156" y="604" text-anchor="end" class="m" font-size="11" fill="{t['muted']}">{CFG['timezone_label']}</text>
</svg>'''


# ---------- radar ----------
def radar(title, labels, vals, theme):
    t = THEMES[theme]
    title = html.escape(title)
    labels = [html.escape(x) for x in labels]
    cx, cy, R, n = 260, 255, 140, len(labels)

    def pt(i, frac):
        a = -math.pi / 2 + 2 * math.pi * i / n
        return cx + R * frac * math.cos(a), cy + R * frac * math.sin(a), a

    rings = "".join(
        '<polygon points="%s" fill="none" stroke="%s" stroke-width="1"/>' % (
            " ".join("%.1f,%.1f" % pt(i, s / 100)[:2] for i in range(n)), t["grid"])
        for s in (25, 50, 75, 100))
    axes, texts, shape, dots = [], [], [], []
    for i, label in enumerate(labels):
        x, y, a = pt(i, 1)
        axes.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{t["grid"]}"/>')
        sx, sy, _ = pt(i, vals[i] / 100)
        shape.append("%.1f,%.1f" % (sx, sy))
        dots.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4" fill="{t["green"]}"/>')
        tx, ty = cx + (R + 34) * math.cos(a), cy + (R + 34) * math.sin(a)
        anchor = "middle" if abs(math.cos(a)) < .35 else ("start" if math.cos(a) > 0 else "end")
        texts.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}" dominant-baseline="middle" '
                     f'font-family="Arial,sans-serif" font-size="13" fill="{t["muted"]}">{label}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="500" viewBox="0 0 520 500">
<style>.f{{animation:f 1.2s .3s ease backwards}}@keyframes f{{from{{opacity:0}}}}</style>
<rect width="520" height="500" fill="{t['card']}"/>
<text x="260" y="40" text-anchor="middle" font-family="Arial,sans-serif" font-size="20" font-weight="700" fill="{t['text']}">{title}</text>
{rings}{"".join(axes)}
<g class="f"><polygon points="{' '.join(shape)}" fill="{t['green']}" fill-opacity=".18" stroke="{t['green']}" stroke-width="2.5"/>{"".join(dots)}</g>
{"".join(texts)}
</svg>'''


def main():
    dots, count = dot_path()
    for theme in THEMES:
        (ASSETS / f"banner-{theme}.svg").write_text(banner(theme, dots, count), encoding="utf-8")
        d, l = CFG["dev_signals"], CFG["lang_signals"]
        (ASSETS / f"radar-{theme}.svg").write_text(radar(d["title"], d["labels"], d["values"], theme), encoding="utf-8")
        (ASSETS / f"radar-langs-{theme}.svg").write_text(radar(l["title"], l["labels"], l["values"], theme), encoding="utf-8")
    print(f"Generated banner ({count} dots) + radars in {ASSETS}")


if __name__ == "__main__":
    main()
