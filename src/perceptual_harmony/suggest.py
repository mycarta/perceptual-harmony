"""Suggest new colours for a palette: inside its harmonic template and distinct from its colours.

The search runs over a grid of OKLCH colours (lightness steps of 0.5%, chroma steps of 0.005, hue
steps of 1 degree), so every suggestion can be written exactly as a CSS oklch() colour. A colour
is eligible when it is inside the sRGB gamut, within the palette's range of lightness and chroma
(slightly widened, or as given), inside the template by at least `min_margin` degrees in the
primary space and inside it in every space of the robustness check, and, if asked, above a
contrast ratio against the background. Among eligible colours the one farthest (OKLab colour
difference) from every palette colour and every earlier suggestion is taken, one at a time.

Suggestions are options to look at, not answers: the designer decides.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .check import ColourSpec, Report, check, contrast_ratio
from .colour import ROBUSTNESS_SPACES, SPACES, get_space, in_gamut, oklab_to_srgb, parse_hex, srgb_to_oklab, to_hex
from .css import parse_colour
from .cvd import CVD_TYPES, simulate
from .harmony import fit_template, margin


@dataclass
class Suggestion:
    label: str
    hex: str
    L: float                        # OKLCH lightness, 0-1
    C: float                        # OKLCH chroma
    h: float                        # OKLCH hue, degrees
    distance: float                 # OKLab colour difference to the nearest palette or earlier colour

    @property
    def css(self) -> str:
        return f'oklch({self.L * 100:.1f}% {self.C:.3f} {self.h:.0f})'

    def to_dict(self) -> dict:
        return {'label': self.label, 'hex': self.hex, 'css': self.css,
                'distance': round(self.distance, 4)}


def _range(given, values, pad, lo, hi) -> Tuple[float, float]:
    if given is not None:
        a, b = given
        return min(a, b), max(a, b)
    return max(lo, min(values) - pad), min(hi, max(values) + pad)


def suggest(palette: Iterable[ColourSpec], n: int = 3, space='oklch', template=None,
            rotation: Optional[float] = None, background: Optional[str] = None,
            min_contrast: Optional[float] = None, min_margin: float = 5.0,
            lightness: Optional[Tuple[float, float]] = None,
            chroma: Optional[Tuple[float, float]] = None,
            robustness_spaces: Sequence = ROBUSTNESS_SPACES,
            neutral_chroma: Optional[float] = None,
            prefix: str = 'new', cvd_safe: bool = False, cvd: bool = True,
            cvd_threshold: Optional[float] = None) -> Tuple[Report, List[Suggestion]]:
    """Suggest up to `n` colours for `palette`; returns (report, suggestions).

    The report is a `check` of the palette with the suggestions as candidates, so it carries
    their margins, robustness, nearest colour and contrast. Arguments as for `check`, plus:
    min_contrast: WCAG 2 ratio each suggestion must reach against `background`.
    min_margin: degrees a suggestion must sit inside the template in the primary space.
    lightness, chroma: OKLCH ranges to search, e.g. (0.6, 0.8) and (0.05, 0.15); by default the
        palette's own range, widened by 0.05 in lightness and 0.02 in chroma.
    cvd_safe: also require each suggestion to stay at least `cvd_threshold` (in the primary
        space; default three times its rough JND) from every palette colour and earlier
        suggestion under simulated protanopia, deuteranopia and tritanopia.
    """
    palette = list(palette)
    base = check(palette, space=space, template=template, rotation=rotation, background=background,
                 neutral_chroma=neutral_chroma, robustness_spaces=robustness_spaces)
    sp = base.space
    ok = SPACES['oklch']
    chromatic = [c for c in base.palette if not c.neutral] or base.palette
    pal_lch = [ok.lch(c.rgb) for c in chromatic]

    # where the template lies in OKLCH, to restrict the grid (exact membership is checked below)
    fits = {r.space.name: r.fit for r in base.robustness}
    ok_fit = fits.get('oklch') or fit_template([h for _, _, h in pal_lch], [C for _, C, _ in pal_lch],
                                               base.chosen.template)
    checks = [(r.space, r.fit, 0.0) for r in base.robustness if r.space is not sp]
    checks.insert(0, (sp, base.chosen, min_margin))

    L_lo, L_hi = _range(lightness, [L for L, _, _ in pal_lch], 0.05, 0.2, 0.97)
    C_lo, C_hi = _range(chroma, [C for _, C, _ in pal_lch], 0.02, 0.03, 0.37)
    bg = parse_hex(parse_colour(background)) if background else None

    grid = []                       # (L, C, h, lab, rgb)
    hues = [h for h in range(360) if margin(h, ok_fit.template, ok_fit.rotation)[0] >= -10]
    for li in range(int(math.ceil(L_lo * 200)), int(L_hi * 200) + 1):
        L = li / 200
        for ci in range(int(math.ceil(C_lo * 200)), int(C_hi * 200) + 1):
            C = ci / 200
            for h in hues:
                a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
                rgb = oklab_to_srgb((L, a, b))
                if not in_gamut(rgb, 1e-9):
                    continue
                if bg is not None and min_contrast and contrast_ratio(rgb, bg) < min_contrast:
                    continue
                grid.append((L, C, float(h), (L, a, b), rgb))

    threshold = 3 * sp.jnd if cvd_threshold is None else cvd_threshold
    sim_taken = {k: [simulate(c.rgb, k) for c in base.palette] for k in CVD_TYPES}

    def eligible(rgb) -> bool:
        for s, fit, need in checks:
            if margin(s.lch(rgb)[2], fit.template, fit.rotation)[0] < need:
                return False
        if cvd_safe:
            for k in CVD_TYPES:
                srgb = simulate(rgb, k)
                if any(sp.delta_e(srgb, t) < threshold for t in sim_taken[k]):
                    return False
        return True

    taken = [srgb_to_oklab(c.rgb) for c in base.palette]
    nearest = [min(math.dist(g[3], t) for t in taken) for g in grid]   # updated as colours are added
    out: List[Suggestion] = []
    notes = []
    for k in range(n):
        pick = None
        for i in sorted(range(len(grid)), key=nearest.__getitem__, reverse=True):
            if eligible(grid[i][4]):
                pick = grid[i]
                break
        if pick is None:
            notes.append(f'Found {len(out)} of {n} suggestions: no other colour met every constraint. '
                         'Try a smaller --min-margin, wider --lightness or --chroma, or a lower '
                         '--min-contrast.')
            break
        L, C, h, lab, rgb = pick
        d = min(math.dist(lab, t) for t in taken)
        out.append(Suggestion(f'{prefix}-{k + 1}', to_hex(rgb), L, C, h, d))
        taken.append(lab)
        for k in CVD_TYPES:
            sim_taken[k].append(simulate(rgb, k))
        nearest = [min(d0, math.dist(g[3], lab)) for d0, g in zip(nearest, grid)]

    report = check(palette, [f'{s.label}={s.hex}' for s in out], space=space, template=template,
                   rotation=rotation, background=background, neutral_chroma=neutral_chroma,
                   robustness_spaces=robustness_spaces, cvd=cvd, cvd_threshold=cvd_threshold)
    report.notes += [f'Suggestions searched in OKLCH: lightness {L_lo * 100:.0f}-{L_hi * 100:.0f}%, '
                     f'chroma {C_lo:.3f}-{C_hi:.3f}, at least {min_margin:g} deg inside the template'
                     + (', distinct under simulated dichromacy.' if cvd_safe else '.')]
    report.notes += notes
    return report, out


def css_block(suggestions: Sequence[Suggestion]) -> str:
    """The suggestions as CSS custom properties, ready to paste into a style sheet."""
    return '\n'.join(f'  --{s.label}: {s.css};  /* {s.hex} */' for s in suggestions)
