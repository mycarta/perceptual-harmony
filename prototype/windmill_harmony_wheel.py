"""Prototype from the Windmill project (2026-11-19): place a palette's hues on a hue wheel,
overlay the "X" hue template of Cohen-Or et al. (2006), and compare candidate colours for one
new role (the 8 added wind directions in Windmill's replay compass).

This is the rough tool that picked periwinkle #94a0f0 for Windmill. Known limits (see HANDOFF.md):
  - hue is HSL hue, which is not perceptual;
  - only the X template is drawn, placed by eye (centres 197 and 17 degrees), not fitted;
  - no lightness or contrast check beyond what was done separately by hand.

Usage:  python3 windmill_harmony_wheel.py   -> writes windmill_harmony_wheel.svg next to this file.
Render to PNG with headless Chrome, e.g.
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
     --screenshot=out.png --window-size=1300,900 file:///full/path/windmill_harmony_wheel.svg
"""
import colorsys
import math
import os

# ---- data: Windmill's palette and the candidates that were compared -------------------------
PALETTE = [  # (label, hex) -- the colours already on screen
    ('blues', '#30859e'),      # board cell
    ('', '#c5d9e8'),           # pale label text
    ('gold', '#f5e642'),       # current gust, turbine hub, title
    ('hit red', '#ef9a9a'),    # hit marker
]
CANDIDATES = [  # (label, colour before use, dimmed colour after use)
    ('Cyan (first draft)', '#60ccdb', '#1f4b51'),
    ('Periwinkle (chosen)', '#94a0f0', '#282f5d'),
    ('Sea green', '#61d1ac', '#224f40'),
    ('Amber', '#f0ac4c', '#564125'),
]
X_TEMPLATE = [(197, 93.6), (17, 93.6)]   # (centre, width) of each sector, degrees

# ---- helpers -----------------------------------------------------------------------------------
def hex_to_hls(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)

def hue_deg(h):
    return hex_to_hls(h)[0] * 360

def hsl_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return '#%02x%02x%02x' % tuple(round(v * 255) for v in (r, g, b))

def in_template(h, template):
    return any(abs((h - c + 180) % 360 - 180) <= w / 2 for c, w in template)

# ---- drawing -----------------------------------------------------------------------------------
def wheel(cx, cy, r):
    out = [f'<g transform="translate({cx},{cy})">']
    for i in range(72):
        a0, a1 = math.radians(i * 5 - 90), math.radians((i + 1) * 5 - 90 + 0.6)
        out.append(
            f'<path d="M {r*math.cos(a0):.1f} {r*math.sin(a0):.1f} A {r} {r} 0 0 1 {r*math.cos(a1):.1f} {r*math.sin(a1):.1f} '
            f'L {0.78*r*math.cos(a1):.1f} {0.78*r*math.sin(a1):.1f} A {0.78*r} {0.78*r} 0 0 0 {0.78*r*math.cos(a0):.1f} {0.78*r*math.sin(a0):.1f} Z" '
            f'fill="{hsl_hex(i*5+2.5, 60, 55)}" opacity="0.35"/>')
    for centre, width in X_TEMPLATE:
        a0, a1 = math.radians(centre - width / 2 - 90), math.radians(centre + width / 2 - 90)
        R2 = r * 1.08
        out.append(f'<path d="M 0 0 L {R2*math.cos(a0):.1f} {R2*math.sin(a0):.1f} A {R2} {R2} 0 0 1 '
                   f'{R2*math.cos(a1):.1f} {R2*math.sin(a1):.1f} Z" fill="#e8f0f5" opacity="0.10" '
                   f'stroke="#e8f0f5" stroke-opacity="0.5" stroke-dasharray="4 4"/>')

    def dot(h, col, label, ring, bold=False):
        a = math.radians(h - 90)
        x, y = ring * math.cos(a), ring * math.sin(a)
        lx, ly = (ring + 38) * math.cos(a), (ring + 38) * math.sin(a)
        s = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{col}" stroke="#10202b" stroke-width="2"/>'
        if label:
            s += (f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#d8e6f0" font-size="14" font-weight="{700 if bold else 400}" '
                  f'text-anchor="middle" dominant-baseline="central">{label}</text>')
        return s

    for label, col in PALETTE:
        out.append(dot(hue_deg(col), col, label, r * 0.89))
    for label, col, _ in CANDIDATES:
        out.append(dot(hue_deg(col), col, label.split(' (')[0], r * 0.62, True))
    out.append('</g>')
    return '\n'.join(out)

def swatches(x, y):
    out = []
    for i, (label, col, dim) in enumerate(CANDIDATES):
        yy = y + i * 90
        ok = 'inside' if in_template(hue_deg(col), X_TEMPLATE) else 'outside'
        out += [f'<rect x="{x}" y="{yy}" width="60" height="60" rx="10" fill="{col}"/>',
                f'<rect x="{x+70}" y="{yy}" width="60" height="60" rx="10" fill="{dim}"/>',
                f'<text x="{x+150}" y="{yy+24}" fill="#e8f0f5" font-size="17" font-weight="600">{label}</text>',
                f'<text x="{x+150}" y="{yy+48}" fill="#a8c4d8" font-size="14">{col} / dimmed {dim} · hue {hue_deg(col):.0f}°, {ok} the X template</text>']
    return '\n'.join(out)

def main():
    W, H = 1300, 600
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           'font-family="-apple-system, Helvetica, Arial, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="#1a2e3d"/>',
           wheel(330, 290, 170),
           '<text x="330" y="520" fill="#a8c4d8" font-size="15" text-anchor="middle">Dashed: the two opposite 93.6° sectors of the "X" template</text>',
           '<text x="330" y="542" fill="#a8c4d8" font-size="15" text-anchor="middle">Outer dots: palette.  Inner dots: candidates.  Hue = HSL hue (not perceptual).</text>',
           swatches(700, 120),
           '</svg>']
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'windmill_harmony_wheel.svg')
    with open(out, 'w') as f:
        f.write('\n'.join(svg))
    for label, col, _ in CANDIDATES:
        print(f'{label:22} {col}  hue {hue_deg(col):5.1f}  in X template: {in_template(hue_deg(col), X_TEMPLATE)}')
    print('wrote', out)

if __name__ == '__main__':
    main()
