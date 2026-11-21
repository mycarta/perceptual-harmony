"""Draw a check report as an SVG: a chroma-hue wheel with the fitted template, plus swatches.

The wheel is the a-b plane of the chosen space seen from above: +a to the right, +b up, hue
angles counter-clockwise from +a. Each colour sits at radius proportional to its chroma, so
neutrals are near the centre. The outer ring is drawn at one lightness and one chroma for
every hue (the largest chroma that stays in the sRGB gamut at all hues), so it is perceptually
even rather than a saturated HSL rainbow.
"""
from __future__ import annotations

import math
from html import escape
from typing import Tuple

from .check import ColourInfo, ColormapReport, Report
from .colour import SRGB_MAX_CHROMA, Space, to_hex

INK, MUTED, GRID, SECTOR = '#1f2328', '#57606a', '#d0d7de', '#8c959f'


def _even_ring(space: Space, steps: int = 72) -> Tuple[float, float]:
    """(lightness, chroma) giving the most colourful ring that is in gamut at every hue."""
    hi = 2 * SRGB_MAX_CHROMA[space.name]
    best = (0.0, 0.0)
    for i in range(30, 91, 5):
        L = i / space.l_scale
        c = min(space.max_chroma(L, h * 360 / steps, hi) for h in range(steps))
        if c > best[1]:
            best = (L, c)
    return best


def _pt(r: float, hue: float) -> Tuple[float, float]:
    a = math.radians(hue)
    return r * math.cos(a), -r * math.sin(a)          # SVG y grows downwards


def _arc_path(r0: float, r1: float, h0: float, h1: float) -> str:
    """Annular sector from hue h0 to h1 (counter-clockwise), radii r0 (inner) to r1."""
    span = (h1 - h0) % 360 or 360
    large = 1 if span > 180 else 0
    x0, y0 = _pt(r1, h0)
    x1, y1 = _pt(r1, h0 + span)
    if r0 <= 0:
        return (f'M 0 0 L {x0:.2f} {y0:.2f} A {r1} {r1} 0 {large} 0 {x1:.2f} {y1:.2f} Z')
    x2, y2 = _pt(r0, h0 + span)
    x3, y3 = _pt(r0, h0)
    return (f'M {x0:.2f} {y0:.2f} A {r1} {r1} 0 {large} 0 {x1:.2f} {y1:.2f} '
            f'L {x2:.2f} {y2:.2f} A {r0} {r0} 0 {large} 1 {x3:.2f} {y3:.2f} Z')


def _fmt_c(space: Space, v: float) -> str:
    return f'{v:.3f}' if space.l_scale != 1 else f'{v:.1f}'


def _fmt_l(space: Space, v: float) -> str:
    return f'{v * space.l_scale:.0f}'


def _wheel_base(g: list, sp: Space, fit, R: float, ring_in: float, plot_r: float):
    """Append the even hue ring, chroma grid, hue ticks and template sectors; return the ring's L, C."""
    L_ring, C_ring = _even_ring(sp)
    for i in range(120):
        h0 = i * 3
        col = to_hex(sp.lch_to_srgb(L_ring, C_ring, h0 + 1.5))
        g.append(f'<path d="{_arc_path(ring_in, R, h0, h0 + 3.3)}" fill="{col}"/>')
    for f in (0.25, 0.5, 0.75, 1.0):
        g.append(f'<circle r="{plot_r * f:.1f}" fill="none" stroke="{GRID}" stroke-width="1"/>')
    for h in range(0, 360, 30):
        x0, y0 = _pt(ring_in - 4, h)
        x1, y1 = _pt(R + 10, h)
        g.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{MUTED}" stroke-width="1"/>')
        tx, ty = _pt(R + 26, h)
        g.append(f'<text x="{tx:.1f}" y="{ty:.1f}" fill="{MUTED}" font-size="12" text-anchor="middle" '
                 f'dominant-baseline="central">{h}°</text>')
    for a, b in fit.sector_ranges():
        g.append(f'<path d="{_arc_path(0, ring_in, a, b)}" fill="{SECTOR}" fill-opacity="0.16" '
                 f'stroke="{SECTOR}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    return L_ring, C_ring


def _narrow(layout: str) -> bool:
    if layout not in ('wide', 'narrow'):
        raise ValueError(f"layout must be 'wide' or 'narrow', not {layout!r}")
    return layout == 'narrow'


def render_svg(report: Report, title: str = '', layout: str = 'wide') -> str:
    """Hue wheel of a palette check. layout='wide' (1180 px, panel beside the wheel) or 'narrow'
    (640 px wide, panel below the wheel, for a blog or document column)."""
    narrow = _narrow(layout)
    sp = report.space
    fit = report.chosen
    W, H = 1180, 640
    cx, cy, R = 320, 330, 230            # wheel centre and ring outer radius
    rows = [('Palette', report.palette), ('Candidates', report.candidates)]
    n_rows = sum(len(r) for _, r in rows) + sum(1 for _, r in rows if r)
    if narrow:
        W, cy = 640, 380
        step = 52
        panel_y = cy + 322
        H = int(panel_y + sum(step * 0.8 + len(r) * step for _, r in rows if r)
                + (34 if report.background else 0) + 16)
    ring_in = R * 0.9
    plot_r = R * 0.84                    # radius available for colours
    cmax = max([c.chroma for c in report.colours] + [sp.neutral_chroma * 2]) / 0.9

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="-apple-system, \'Segoe UI\', Helvetica, Arial, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    heading = title or f'{fit.template.name} template in {sp.label}'
    out.append(f'<text x="28" y="40" fill="{INK}" font-size="22" font-weight="600">{escape(heading)}</text>')

    g = [f'<g transform="translate({cx},{cy})">']
    L_ring, C_ring = _wheel_base(g, sp, fit, R, ring_in, plot_r)
    # colours: markers first, then labels placed greedily to avoid markers and each other
    colours = report.palette + report.candidates
    pos = []
    for c in colours:
        r = plot_r * min(c.chroma / cmax, 1.0)
        pos.append((r, c.hue, *_pt(r, c.hue)))
    for c, (r, h, x, y) in zip(colours, pos):
        if c.role == 'candidate':
            s = 10
            g.append(f'<rect x="{x - s:.1f}" y="{y - s:.1f}" width="{2 * s}" height="{2 * s}" '
                     f'transform="rotate(45 {x:.1f} {y:.1f})" fill="{c.hex}" stroke="{INK}" stroke-width="1.5"/>')
        else:
            g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{c.hex}" stroke="{INK}" stroke-width="1.5"/>')
    taken = [(x - 11, y - 11, x + 11, y + 11) for _, _, x, y in pos]

    def overlaps(box):
        return sum(max(0, min(box[2], b[2]) - max(box[0], b[0])) *
                   max(0, min(box[3], b[3]) - max(box[1], b[1])) for b in taken)

    for c, (r, h, x, y) in zip(colours, pos):
        weight = 600 if c.role == 'candidate' else 400
        w, hgt = len(c.label) * (7.6 if weight == 600 else 7.0), 16
        best = None
        for dist in (16, 26, 38):
            for dh in (0, 25, -25, 50, -50, 90, -90, 135, -135, 180):
                a = math.radians(h + dh)
                lx, ly = x + dist * math.cos(a), y - dist * math.sin(a)
                dx = lx - x
                anchor = 'start' if dx > 3 else ('end' if dx < -3 else 'middle')
                x0 = lx if anchor == 'start' else (lx - w if anchor == 'end' else lx - w / 2)
                box = (x0, ly - hgt / 2, x0 + w, ly + hgt / 2)
                score = overlaps(box) + dist * 0.5 + abs(dh) * 0.2
                if best is None or score < best[0]:
                    best = (score, lx, ly, anchor, box)
            if best[0] < 60:
                break
        _, lx, ly, anchor, box = best
        taken.append(box)
        g.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{INK}" font-size="13" font-weight="{weight}" '
                 f'text-anchor="{anchor}" dominant-baseline="central" paint-order="stroke" '
                 f'stroke="#ffffff" stroke-width="3">{escape(c.label)}</text>')
    g.append('</g>')
    out += g

    Ln, Cn, hn = sp.axis_names
    out.append(f'<text x="{cx}" y="{cy + 288}" fill="{MUTED}" font-size="12" text-anchor="middle">'
               f'Radius: chroma {Cn} (outer grid circle = {_fmt_c(sp, cmax)}). '
               f'Ring: {Ln} {_fmt_l(sp, L_ring)}, {Cn} {_fmt_c(sp, C_ring)}.</text>')

    # side panel (below the wheel in the narrow layout, with the status under the title)
    x0, y = (28, 70) if narrow else (640, 92)
    secs = ', '.join(f'{a:.0f}°–{b:.0f}°' for a, b in fit.sector_ranges())
    status = 'fits' if fit.fits else f'misses by {fit.cost:.1f}° on average'
    out.append(f'<text x="{x0}" y="{y}" fill="{MUTED}" font-size="14">Palette {status}. '
               f'Sectors {escape(secs)}.</text>')
    nrob = len(report.robustness)
    if nrob > 1:
        y += 20
        nb = sum(c.robustness == 'borderline' for c in report.colours)
        out.append(f'<text x="{x0}" y="{y}" fill="{MUTED}" font-size="14">Fits in {report.fits_in} of '
                   f'{nrob} colour spaces; '
                   + (f'{nb} borderline colour{"s" if nb > 1 else ""} (marked).' if nb else
                      'every colour keeps its verdict in all of them.') + '</text>')
    y += 34
    if narrow:
        y = panel_y
    else:
        step = min(58, (H - y - 40) / max(n_rows, 1))
    sw = min(40, step - 8)
    for name, items in rows:
        if not items:
            continue
        out.append(f'<text x="{x0}" y="{y + 14}" fill="{INK}" font-size="15" font-weight="600">{name}</text>')
        y += step * 0.6
        for c in items:
            out.append(f'<rect x="{x0}" y="{y:.1f}" width="{sw}" height="{sw}" rx="6" fill="{c.hex}" '
                       f'stroke="{GRID}"/>')
            where = 'neutral' if c.neutral else (f'{"inside" if c.margin >= 0 else "outside"} by '
                                                 f'{abs(c.margin):.1f}°')
            detail = (f'{c.hex}  {Ln} {_fmt_l(sp, c.lightness)}  {Cn} {_fmt_c(sp, c.chroma)}  '
                      f'{hn} {c.hue:.0f}°  ·  {where}')
            if c.contrast is not None:
                detail += f'  ·  {c.contrast:.1f}:1'
            name = c.label
            if c.robustness == 'borderline':
                name += f'  (borderline: inside in {c.inside_count} of {nrob} spaces)'
            out.append(f'<text x="{x0 + sw + 14}" y="{y + sw * 0.38:.1f}" fill="{INK}" font-size="14" '
                       f'font-weight="600">{escape(name)}</text>')
            out.append(f'<text x="{x0 + sw + 14}" y="{y + sw * 0.38 + 18:.1f}" fill="{MUTED}" '
                       f'font-size="12.5">{escape(detail)}</text>')
            y += step
        y += step * 0.2
    if report.background:
        out.append(f'<text x="{x0}" y="{H - 22}" fill="{MUTED}" font-size="12">Contrast: WCAG 2 ratio '
                   f'against {report.background}.</text>')
    out.append('</svg>')
    return '\n'.join(out)


def render_colormap_svg(report: ColormapReport, title: str = '', layout: str = 'wide') -> str:
    """A colormap's samples as a path on the chroma-hue wheel, beside its lightness profile
    (layout='wide', 1180 px) or above it (layout='narrow', 640 px wide)."""
    narrow = _narrow(layout)
    sp = report.space
    fit = report.chosen
    W, H = 1180, 640
    cx, cy, R = 320, 330, 230
    if narrow:
        W, H, cy = 640, 1122, 332
    ring_in, plot_r = R * 0.9, R * 0.84
    cmax = max(C for _, C, _ in report.lch) / 0.9
    scale = sp.l_scale
    Ln, Cn, _ = sp.axis_names

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="-apple-system, \'Segoe UI\', Helvetica, Arial, sans-serif">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    heading = title or f'{report.name or "Colormap"}: {fit.template.name} template in {sp.label}'
    out.append(f'<text x="28" y="40" fill="{INK}" font-size="22" font-weight="600">{escape(heading)}</text>')

    # wheel with the colormap path
    g = [f'<g transform="translate({cx},{cy})">']
    L_ring, C_ring = _wheel_base(g, sp, fit, R, ring_in, plot_r)
    pts = [_pt(plot_r * min(C / cmax, 1.0), h) for _, C, h in report.lch]
    g.append('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in pts) +
             f'" fill="none" stroke="{MUTED}" stroke-width="1" stroke-opacity="0.6"/>')
    for (x, y), hx in zip(pts, report.hexes):
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{hx}"/>')
    for (x, y), hx, label in ((pts[0], report.hexes[0], 'start'), (pts[-1], report.hexes[-1], 'end')):
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{hx}" stroke="{INK}" stroke-width="1.5"/>')
        g.append(f'<text x="{x + 11:.1f}" y="{y:.1f}" fill="{INK}" font-size="13" dominant-baseline="central" '
                 f'paint-order="stroke" stroke="#ffffff" stroke-width="3">{label}</text>')
    g.append('</g>')
    out += g
    out.append(f'<text x="{cx}" y="{cy + 288}" fill="{MUTED}" font-size="12" text-anchor="middle">'
               f'Radius: chroma {Cn} (outer grid circle = {_fmt_c(sp, cmax)}). '
               f'Ring: {Ln} {_fmt_l(sp, L_ring)}, {Cn} {_fmt_c(sp, C_ring)}.</text>')

    # lightness profile
    if narrow:
        px0, px1, py0, py1 = 78, 600, cy + 368, cy + 568
    else:
        px0, px1, py0, py1 = 690, 1130, 110, 380      # plot box
    out.append(f'<text x="{px0 - 50}" y="{py0 - 22}" fill="{INK}" font-size="15" font-weight="600">'
               f'Lightness {Ln} along the colormap</text>')
    for v in range(0, 101, 20):
        y = py1 - (py1 - py0) * v / 100
        out.append(f'<line x1="{px0}" y1="{y:.1f}" x2="{px1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{px0 - 8}" y="{y:.1f}" fill="{MUTED}" font-size="12" text-anchor="end" '
                   f'dominant-baseline="central">{v}</text>')
    n = len(report.lch)
    lp = [(px0 + (px1 - px0) * i / (n - 1), py1 - (py1 - py0) * min(max(L * scale, 0), 100) / 100)
          for i, (L, _, _) in enumerate(report.lch)]
    for (x, y), hx in zip(lp, report.hexes):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{hx}"/>')
    # colour bar
    bw = (px1 - px0) / n
    for i, hx in enumerate(report.hexes):
        out.append(f'<rect x="{px0 + i * bw:.2f}" y="{py1 + 14}" width="{bw + 0.6:.2f}" height="22" fill="{hx}"/>')
    out.append(f'<text x="{px0}" y="{py1 + 54}" fill="{MUTED}" font-size="12">start</text>')
    out.append(f'<text x="{px1}" y="{py1 + 54}" fill="{MUTED}" font-size="12" text-anchor="end">end</text>')

    # summary
    rev = report.lightness_reversal * scale
    wm = report.worst_margin
    lines = [
        (f'Best template: {fit.template.name}' if fit.template is report.fits[0].template else
         f'Template: {fit.template.name} (best fit: {report.fits[0].template.name})')
        + f'. Mean miss {fit.cost:.1f}°. Sectors '
        + ', '.join(f'{a:.0f}°–{b:.0f}°' for a, b in fit.sector_ranges()) + '.',
        f'Hue span {report.hue_span:.0f}°; worst sample {abs(wm):.1f}° '
        f'{"inside" if wm >= 0 else "outside"} the template.',
        f'{Ln} {report.lightness_range_text(0)}; largest reversal {rev:.2f} '
        f'({"none" if rev == 0 else ("below" if rev < sp.jnd * scale else "above") + " a just-noticeable difference"}).',
    ]
    if report.robustness:
        allr = [report] + report.robustness
        spans = [r.hue_span for r in allr]
        costs = [r.chosen.cost for r in allr]
        lines.append(f'Across {len(allr)} colour spaces: hue span {min(spans):.0f}°–{max(spans):.0f}°, '
                     f'{fit.template.name} mean miss {min(costs):.1f}°–{max(costs):.1f}°.')
    for i, line in enumerate(lines):
        out.append(f'<text x="{px0 - 50}" y="{py1 + 100 + i * 24}" fill="{INK}" font-size="14">{escape(line)}</text>')
    out.append('</svg>')
    return '\n'.join(out)
