"""Check a palette (and optional candidate colours) for hue harmony, distinctness and contrast."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .colour import (ROBUSTNESS_SPACES, Space, Triple, get_space, parse_hex, relative_luminance,
                     to_hex)
from .css import parse_colour
from .harmony import Fit, Template, fit_all, fit_template, get_template, margin

ColourSpec = Union[str, Tuple[str, str]]


def contrast_ratio(rgb1: Triple, rgb2: Triple) -> float:
    """WCAG 2 contrast ratio, 1 to 21."""
    a, b = sorted((relative_luminance(rgb1), relative_luminance(rgb2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def parse_spec(spec: ColourSpec) -> Tuple[str, str]:
    """'#30859e', 'blue=#30859e' or ('blue', '#30859e') -> (label, normalised hex). The colour may
    be any CSS colour: 'accent=oklch(70% 0.12 250)', 'rgb(78 127 204)', 'tomato'."""
    if isinstance(spec, tuple):
        label, hx = spec
    elif '=' in spec:
        label, hx = spec.split('=', 1)
    else:
        label, hx = '', spec
    hx = parse_colour(hx)
    return (label.strip() or hx), hx


@dataclass
class ColourInfo:
    label: str
    hex: str
    role: str                       # 'palette' or 'candidate'
    lightness: float
    chroma: float
    hue: float
    neutral: bool                   # chroma too low for hue to matter; ignored by the fit
    margin: Optional[float] = None  # degrees inside (+) or outside (-) the chosen template
    sector: Optional[int] = None
    nearest: Optional[str] = None   # label of the closest palette colour
    delta_e: Optional[float] = None # colour difference to it, in the space's units
    contrast: Optional[float] = None  # WCAG 2 ratio against the background, if one was given
    # margin in each space of the robustness check (template refitted there), by space name
    margins_by_space: Dict[str, float] = field(default_factory=dict)

    @property
    def rgb(self) -> Triple:
        return parse_hex(self.hex)

    @property
    def margin_range(self) -> Optional[Tuple[float, float]]:
        """Smallest and largest margin across the spaces of the robustness check."""
        m = list(self.margins_by_space.values())
        return (min(m), max(m)) if m else None

    @property
    def inside_count(self) -> int:
        """In how many spaces of the robustness check the colour is inside the template."""
        return sum(m >= 0 for m in self.margins_by_space.values())

    @property
    def robustness(self) -> Optional[str]:
        """'inside' or 'outside' in every space compared, else 'borderline'; None if not checked."""
        if len(self.margins_by_space) < 2:
            return None
        n = self.inside_count
        return 'inside' if n == len(self.margins_by_space) else ('outside' if n == 0 else 'borderline')


@dataclass
class SpaceFit:
    """The chosen template refitted to the same colours in another colour space."""
    space: Space
    fit: Fit                        # the chosen template, best rotation in this space
    best: Fit                       # the best-fitting template in this space


@dataclass
class Report:
    space: Space
    palette: List[ColourInfo]
    candidates: List[ColourInfo]
    fits: List[Fit]                 # every template, best first, fitted to the palette
    chosen: Fit                     # the fit used for margins (best, or the one asked for)
    background: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    robustness: List[SpaceFit] = field(default_factory=list)   # primary space first
    cvd: Dict[str, list] = field(default_factory=dict)         # dichromacy -> close CVDPairs
    cvd_threshold: Optional[float] = None

    @property
    def colours(self) -> List[ColourInfo]:
        return self.palette + self.candidates

    @property
    def fits_in(self) -> int:
        """In how many spaces of the robustness check the chosen template fits the palette."""
        return sum(r.fit.fits for r in self.robustness)

    # ---- output ----------------------------------------------------------------------------
    def to_dict(self) -> dict:
        def col(c: ColourInfo) -> dict:
            d = {k: getattr(c, k) for k in ('label', 'hex', 'role', 'lightness', 'chroma', 'hue',
                                           'neutral', 'margin', 'sector', 'nearest', 'delta_e',
                                           'contrast', 'robustness')}
            d['margins_by_space'] = {k: round(v, 3) for k, v in c.margins_by_space.items()}
            return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}

        def fit(f: Fit) -> dict:
            return {'template': f.template.name, 'rotation': round(f.rotation, 2),
                    'cost': round(f.cost, 3), 'fits': f.fits,
                    'sectors': [[round(a, 2), round(b, 2)] for a, b in f.sector_ranges()]}
        return {'space': self.space.name, 'background': self.background,
                'chosen': fit(self.chosen), 'fits': [fit(f) for f in self.fits],
                'palette': [col(c) for c in self.palette],
                'candidates': [col(c) for c in self.candidates], 'notes': self.notes,
                'robustness': [{'space': r.space.name, **fit(r.fit), 'best': r.best.template.name}
                               for r in self.robustness],
                'cvd': {k: [p.to_dict() for p in v] for k, v in self.cvd.items()},
                'cvd_threshold': self.cvd_threshold}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_text(self) -> str:
        sp = self.space
        Ln, Cn, hn = sp.axis_names
        cfmt = '{:.3f}' if sp.l_scale != 1 else '{:.1f}'
        out = [f'Colour space: {sp.label}']
        if self.background:
            out.append(f'Background:   {self.background}')
        out += ['', 'Template fits to the palette (cost = chroma-weighted mean hue deviation):']
        for f in self.fits:
            mark = '*' if f is self.chosen else ' '
            secs = ', '.join(f'{a:.0f}-{b:.0f}' for a, b in f.sector_ranges())
            out.append(f' {mark} {f.template.name}  rotation {f.rotation:6.1f}  cost {f.cost:6.2f} deg'
                       f'  {"fits " if f.fits else "     "} sectors {secs}')
        if self.chosen not in self.fits:
            f = self.chosen
            out.append(f' * {f.template.name}  rotation {f.rotation:6.1f}  cost {f.cost:6.2f} deg  (as requested)')
        nrob = len(self.robustness)
        if nrob > 1:
            out += ['', f'Robustness: the {self.chosen.template.name} template refitted in each colour space '
                        f'(fits in {self.fits_in} of {nrob}):']
            for r in self.robustness:
                out.append(f'   {r.space.label:13} rotation {r.fit.rotation:6.1f}  cost {r.fit.cost:6.2f} deg'
                           f'  {"fits " if r.fit.fits else "     "} best: {r.best.template.name}')
        out.append('')
        head = f'  {"":22} {"hex":8} {Ln:>6} {Cn:>7} {hn:>6}  {"in template":>12}  {"nearest (dE)":<24}'
        if nrob > 1:
            head += f' {f"in {nrob} spaces":<22}'
        if self.background:
            head += ' contrast'
        for title, rows in (('Palette', self.palette), ('Candidates', self.candidates)):
            if not rows:
                continue
            out += [f'{title}:', head]
            for c in rows:
                L = f'{c.lightness * sp.l_scale:.1f}'
                if c.neutral:
                    where = 'neutral'
                else:
                    where = f'{"in" if c.margin >= 0 else "out"} {abs(c.margin):5.1f}'
                near = f'{c.nearest} ({cfmt.format(c.delta_e)})' if c.nearest else ''
                line = (f'  {c.label[:22]:22} {c.hex:8} {L:>6} {cfmt.format(c.chroma):>7} '
                        f'{c.hue:6.1f}  {where:>12}  {near[:24]:<24}')
                if nrob > 1:
                    if c.robustness is None:
                        rob = ''
                    else:
                        lo, hi = c.margin_range
                        rob = f'{c.inside_count}/{nrob} ({lo:+.0f} to {hi:+.0f})'
                    line += f' {rob:<22}'
                if c.contrast is not None:
                    line += f' {c.contrast:5.2f}:1'
                out.append(line)
            out.append('')
        out.append(f'"in"/"out": degrees inside or outside the nearest sector edge of the '
                   f'{self.chosen.template.name} template. Rough just-noticeable dE in {sp.label}: '
                   f'{sp.jnd:g}.')
        if nrob > 1:
            out.append(f'"in {nrob} spaces": in how many spaces the colour is inside the template, '
                       f'and its range of margins ({", ".join(r.space.label for r in self.robustness)}).')
            border = [c.label for c in self.colours if c.robustness == 'borderline']
            if border:
                out.append(f'Borderline (inside in some spaces, outside in others): {", ".join(border)}.')
        if self.cvd:
            fmt = cfmt.format
            out += ['', 'Colour-vision deficiency (simulated dichromacy, Machado et al. 2009), '
                        'closest pairs:']
            for kind, pairs in self.cvd.items():
                for i, pr in enumerate(pairs[:4]):
                    flag = '  close' if pr.delta_e < self.cvd_threshold else ''
                    out.append(f'   {kind if i == 0 else "":13} {(pr.a + " / " + pr.b)[:40]:40} '
                               f'dE {fmt(pr.delta_e):>6} (normal vision {fmt(pr.normal)}){flag}')
                if len(pairs) > 4:
                    out.append(f'   {"":13} and {len(pairs) - 4} more close pairs')
            out.append(f'"close": colour difference below {fmt(self.cvd_threshold)} (3 x the rough '
                       f'just-noticeable dE); such pairs may be hard to tell apart.')
        out += self.notes
        return '\n'.join(out)


def _info(label, hx, role, space: Space) -> ColourInfo:
    L, C, h = space.lch(parse_hex(hx))
    return ColourInfo(label, hx, role, L, C, h, neutral=C < space.neutral_chroma)


def check(palette: Iterable[ColourSpec], candidates: Iterable[ColourSpec] = (),
          space='oklch', template: Union[None, str, Template] = None,
          rotation: Optional[float] = None, background: Optional[str] = None,
          neutral_chroma: Optional[float] = None,
          robustness_spaces: Sequence = ROBUSTNESS_SPACES,
          cvd: bool = True, cvd_threshold: Optional[float] = None) -> Report:
    """Fit the hue templates to `palette` and judge each colour, and each candidate, against it.

    palette, candidates: hex strings, 'label=#hex' strings or (label, hex) pairs.
    space: 'oklch' (default), 'cielch', 'cam02ucs', 'cam16ucs' or 'ipt'.
    template: use this template instead of the best-fitting one; `rotation` fixes its angle.
    background: hex colour; adds WCAG 2 contrast ratios against it.
    neutral_chroma: chroma below which a colour's hue is ignored (default depends on the space).
    robustness_spaces: also refit the chosen template in these spaces (the primary space is always
        included, first) and report each colour's margin in every one. A verdict that changes sign
        between spaces is borderline. Colours neutral in the primary space stay out of every fit.
        Pass () to skip.
    cvd: simulate protanopia, deuteranopia and tritanopia and report the pairs of colours
        (palette and candidates) that come closest; pairs below `cvd_threshold` (default three
        times the space's rough JND) are flagged as close.
    """
    sp = get_space(space)
    thresh = sp.neutral_chroma if neutral_chroma is None else neutral_chroma
    pal = [_info(*parse_spec(s), 'palette', sp) for s in palette]
    cands = [_info(*parse_spec(s), 'candidate', sp) for s in candidates]
    if not pal:
        raise ValueError('the palette is empty')
    for c in pal + cands:
        c.neutral = c.chroma < thresh

    chromatic = [c for c in pal if not c.neutral]
    hues = [c.hue for c in chromatic]
    weights = [c.chroma for c in chromatic]
    fits = fit_all(hues, weights)
    if template is None and rotation is None:
        chosen = fits[0]
    else:
        t = get_template(template or fits[0].template)
        chosen = (fit_template(hues, weights, t, rotation) if rotation is not None
                  else next(f for f in fits if f.template is t))

    for c in pal + cands:
        if not c.neutral:
            c.margin, c.sector = margin(c.hue, chosen.template, chosen.rotation)
        others = [p for p in pal if p is not c]
        if others:
            near = min(others, key=lambda p: sp.delta_e(c.rgb, p.rgb))
            c.nearest, c.delta_e = near.label, sp.delta_e(c.rgb, near.rgb)
        if background:
            c.contrast = contrast_ratio(c.rgb, parse_hex(parse_colour(background)))

    robustness = []
    if robustness_spaces:
        names = [sp.name] + [n for n in (get_space(x).name for x in robustness_spaces) if n != sp.name]
        for name in names:
            s = get_space(name)
            if s is sp:
                rfit, rbest, hue_of = chosen, fits[0], {id(c): c.hue for c in pal + cands}
            else:
                hue_of, w = {}, {}
                for c in pal + cands:
                    _, C, h = s.lch(c.rgb)
                    hue_of[id(c)], w[id(c)] = h, C
                rfits = fit_all([hue_of[id(c)] for c in chromatic], [w[id(c)] for c in chromatic])
                rfit, rbest = next(f for f in rfits if f.template is chosen.template), rfits[0]
            robustness.append(SpaceFit(s, rfit, rbest))
            for c in pal + cands:
                if not c.neutral:
                    c.margins_by_space[s.name] = margin(hue_of[id(c)], rfit.template, rfit.rotation)[0]

    notes = []
    if rotation is not None and len(robustness) > 1:
        notes.append('The fixed rotation applies to the primary space; other spaces are refitted.')
    if len(chromatic) < 2:
        notes.append('Fewer than two chromatic palette colours: every template fits trivially.')
    neutrals = [c.label for c in pal if c.neutral]
    if neutrals:
        notes.append(f'Neutral (ignored by the hue fit): {", ".join(neutrals)}.')
    report = Report(sp, pal, cands, fits, chosen, parse_colour(background) if background else None,
                    notes, robustness)
    if cvd and len(pal) + len(cands) >= 2:
        from .cvd import close_pairs
        report.cvd_threshold = 3 * sp.jnd if cvd_threshold is None else cvd_threshold
        report.cvd = close_pairs([(c.label, c.rgb) for c in pal + cands], sp, report.cvd_threshold)
    return report


# ---- colormaps --------------------------------------------------------------------------------
@dataclass
class ColormapReport:
    """Harmony and lightness of a continuous colormap, given as an ordered list of samples."""
    name: str
    space: Space
    hexes: List[str]
    lch: List[Triple]               # lightness, chroma, hue of each sample in `space`
    neutral: List[bool]
    fits: List[Fit]                 # every template, best first
    chosen: Fit
    margins: List[Optional[float]]  # per sample, degrees inside (+) / outside (-); None if neutral
    # the same colormap in the other spaces of the robustness check, same template refitted
    robustness: List['ColormapReport'] = field(default_factory=list)

    @property
    def inside_fraction(self) -> float:
        """Share of chromatic samples inside the template, 0 to 1."""
        m = [v for v in self.margins if v is not None]
        return sum(v >= 0 for v in m) / len(m) if m else 1.0

    @property
    def hue_span(self) -> float:
        """Smallest arc of the hue wheel, in degrees, that holds every chromatic sample."""
        hues = sorted(h for (_, _, h), n in zip(self.lch, self.neutral) if not n)
        if len(hues) < 2:
            return 0.0
        gaps = [(hues[(i + 1) % len(hues)] - hues[i]) % 360 for i in range(len(hues))]
        return 360 - max(gaps)

    @property
    def lightness_reversal(self) -> float:
        """Largest total fall in lightness from an earlier peak (0 if lightness never decreases).

        Measured against the overall direction, so a map running from light to dark is judged on
        its rises. Unlike the largest single step, this catches a slow rise and fall such as
        jet's."""
        L = [l for l, _, _ in self.lch]
        if L[-1] < L[0]:
            L = [-v for v in L]
        peak, worst = L[0], 0.0
        for v in L:
            peak = max(peak, v)
            worst = max(worst, peak - v)
        return worst

    @property
    def worst_margin(self) -> float:
        return min(m for m in self.margins if m is not None)

    def lightness_range_text(self, digits: int = 1) -> str:
        """'from A to B', plus any interior peak or low beyond the ends by more than a JND."""
        scale = self.space.l_scale
        L = [l * scale for l, _, _ in self.lch]
        jnd = self.space.jnd * scale
        text = f'from {L[0]:.{digits}f} to {L[-1]:.{digits}f}'
        if max(L) > max(L[0], L[-1]) + jnd:
            text += f', peak {max(L):.{digits}f}'
        if min(L) < min(L[0], L[-1]) - jnd:
            text += f', low {min(L):.{digits}f}'
        return text

    def to_text(self) -> str:
        sp = self.space
        scale = sp.l_scale
        Ln = sp.axis_names[0]
        out = [f'{self.name or "Colormap"}: {len(self.hexes)} samples, {sp.label}', '',
               'Template fits (cost = chroma-weighted mean hue deviation):']
        for f in self.fits:
            mark = '*' if f.template is self.chosen.template else ' '
            secs = ', '.join(f'{a:.0f}-{b:.0f}' for a, b in f.sector_ranges())
            out.append(f' {mark} {f.template.name}  rotation {f.rotation:6.1f}  cost {f.cost:6.2f} deg'
                       f'  {"fits " if f.fits else "     "} sectors {secs}')
        out += ['',
                f'Hue span: {self.hue_span:.0f} degrees.',
                f'Worst sample: {abs(self.worst_margin):.1f} degrees '
                f'{"inside" if self.worst_margin >= 0 else "outside"} the {self.chosen.template.name} template.',
                f'Lightness {Ln} {self.lightness_range_text()}; largest reversal '
                f'{self.lightness_reversal * scale:.2f} (rough just-noticeable dE: {sp.jnd * scale:g}).']
        if self.robustness:
            t = self.chosen.template.name
            out += ['', f'Robustness: the {t} template refitted in each colour space:']
            for r in [self] + self.robustness:
                wm = r.worst_margin
                out.append(f'   {r.space.label:13} hue span {r.hue_span:4.0f} deg  cost {r.chosen.cost:6.2f} deg  '
                           f'worst {abs(wm):5.1f} deg {"in " if wm >= 0 else "out"}  '
                           f'samples inside {100 * r.inside_fraction:3.0f}%  best: {r.fits[0].template.name}')
        return '\n'.join(out)


def check_colormap(colours: Sequence, name: str = '', space='oklch',
                   template: Union[None, str, Template] = None,
                   neutral_chroma: Optional[float] = None, bin_width: float = 0.5,
                   robustness_spaces: Sequence = ROBUSTNESS_SPACES) -> ColormapReport:
    """Fit the hue templates to a colormap and measure its hue span and lightness profile.

    colours: ordered samples, as CSS colour strings (e.g. hex) or sRGB triples in 0-1.
    Hues are pooled into bins of `bin_width` degrees (weights summed) before fitting, which keeps
    the fit fast for long colormaps; the result is within half a bin of the unbinned fit.
    robustness_spaces: also refit the chosen template in these spaces, with their default neutral
    thresholds (see `check`). Pass () to skip.
    """
    sp = get_space(space)
    thresh = sp.neutral_chroma if neutral_chroma is None else neutral_chroma
    rgbs = [parse_hex(parse_colour(c)) if isinstance(c, str) else tuple(c) for c in colours]
    if len(rgbs) < 2:
        raise ValueError('a colormap needs at least two samples')
    lch = [sp.lch(c) for c in rgbs]
    neutral = [C < thresh for _, C, _ in lch]
    bins = {}
    for (_, C, h), n in zip(lch, neutral):
        if not n:
            k = int(h // bin_width)
            bins[k] = bins.get(k, 0.0) + C
    hues = [(k + 0.5) * bin_width for k in sorted(bins)]
    weights = [bins[k] for k in sorted(bins)]
    fits = fit_all(hues, weights)
    chosen = fits[0] if template is None else next(f for f in fits if f.template is get_template(template))
    margins = [None if n else margin(h, chosen.template, chosen.rotation)[0]
               for (_, _, h), n in zip(lch, neutral)]
    others = [get_space(x) for x in robustness_spaces]
    robustness = [check_colormap(rgbs, name, s, chosen.template, bin_width=bin_width, robustness_spaces=())
                  for s in dict.fromkeys(others) if s is not sp]
    return ColormapReport(name, sp, [to_hex(c) for c in rgbs], lch, neutral, fits, chosen, margins,
                          robustness)
