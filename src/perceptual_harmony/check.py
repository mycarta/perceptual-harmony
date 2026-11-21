"""Check a palette (and optional candidate colours) for hue harmony, distinctness and contrast."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .colour import Space, Triple, get_space, parse_hex, relative_luminance, to_hex
from .harmony import Fit, Template, fit_all, fit_template, get_template, margin

ColourSpec = Union[str, Tuple[str, str]]


def contrast_ratio(rgb1: Triple, rgb2: Triple) -> float:
    """WCAG 2 contrast ratio, 1 to 21."""
    a, b = sorted((relative_luminance(rgb1), relative_luminance(rgb2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def parse_spec(spec: ColourSpec) -> Tuple[str, str]:
    """'#30859e', 'blue=#30859e' or ('blue', '#30859e') -> (label, normalised hex)."""
    if isinstance(spec, tuple):
        label, hx = spec
    elif '=' in spec:
        label, hx = spec.split('=', 1)
    else:
        label, hx = '', spec
    hx = to_hex(parse_hex(hx))
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

    @property
    def rgb(self) -> Triple:
        return parse_hex(self.hex)


@dataclass
class Report:
    space: Space
    palette: List[ColourInfo]
    candidates: List[ColourInfo]
    fits: List[Fit]                 # every template, best first, fitted to the palette
    chosen: Fit                     # the fit used for margins (best, or the one asked for)
    background: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    @property
    def colours(self) -> List[ColourInfo]:
        return self.palette + self.candidates

    # ---- output ----------------------------------------------------------------------------
    def to_dict(self) -> dict:
        def col(c: ColourInfo) -> dict:
            d = {k: getattr(c, k) for k in ('label', 'hex', 'role', 'lightness', 'chroma', 'hue',
                                           'neutral', 'margin', 'sector', 'nearest', 'delta_e',
                                           'contrast')}
            return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}

        def fit(f: Fit) -> dict:
            return {'template': f.template.name, 'rotation': round(f.rotation, 2),
                    'cost': round(f.cost, 3), 'fits': f.fits,
                    'sectors': [[round(a, 2), round(b, 2)] for a, b in f.sector_ranges()]}
        return {'space': self.space.name, 'background': self.background,
                'chosen': fit(self.chosen), 'fits': [fit(f) for f in self.fits],
                'palette': [col(c) for c in self.palette],
                'candidates': [col(c) for c in self.candidates], 'notes': self.notes}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_text(self) -> str:
        sp = self.space
        Ln, Cn, hn = sp.axis_names
        cfmt = '{:.3f}' if sp.name == 'oklch' else '{:.1f}'
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
        out.append('')
        head = f'  {"":22} {"hex":8} {Ln:>6} {Cn:>7} {hn:>6}  {"in template":>12}  {"nearest (dE)":<24}'
        if self.background:
            head += ' contrast'
        for title, rows in (('Palette', self.palette), ('Candidates', self.candidates)):
            if not rows:
                continue
            out += [f'{title}:', head]
            for c in rows:
                L = f'{c.lightness * 100:.1f}' if sp.name == 'oklch' else f'{c.lightness:.1f}'
                if c.neutral:
                    where = 'neutral'
                else:
                    where = f'{"in" if c.margin >= 0 else "out"} {abs(c.margin):5.1f}'
                near = f'{c.nearest} ({cfmt.format(c.delta_e)})' if c.nearest else ''
                line = (f'  {c.label[:22]:22} {c.hex:8} {L:>6} {cfmt.format(c.chroma):>7} '
                        f'{c.hue:6.1f}  {where:>12}  {near[:24]:<24}')
                if c.contrast is not None:
                    line += f' {c.contrast:5.2f}:1'
                out.append(line)
            out.append('')
        out.append(f'"in"/"out": degrees inside or outside the nearest sector edge of the '
                   f'{self.chosen.template.name} template. Rough just-noticeable dE in {sp.label}: '
                   f'{sp.jnd:g}.')
        out += self.notes
        return '\n'.join(out)


def _info(label, hx, role, space: Space) -> ColourInfo:
    L, C, h = space.lch(parse_hex(hx))
    return ColourInfo(label, hx, role, L, C, h, neutral=C < space.neutral_chroma)


def check(palette: Iterable[ColourSpec], candidates: Iterable[ColourSpec] = (),
          space='oklch', template: Union[None, str, Template] = None,
          rotation: Optional[float] = None, background: Optional[str] = None,
          neutral_chroma: Optional[float] = None) -> Report:
    """Fit the hue templates to `palette` and judge each colour, and each candidate, against it.

    palette, candidates: hex strings, 'label=#hex' strings or (label, hex) pairs.
    space: 'oklch' (default), 'cielch' or 'cam02ucs'.
    template: use this template instead of the best-fitting one; `rotation` fixes its angle.
    background: hex colour; adds WCAG 2 contrast ratios against it.
    neutral_chroma: chroma below which a colour's hue is ignored (default depends on the space).
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
            c.contrast = contrast_ratio(c.rgb, parse_hex(background))

    notes = []
    if len(chromatic) < 2:
        notes.append('Fewer than two chromatic palette colours: every template fits trivially.')
    neutrals = [c.label for c in pal if c.neutral]
    if neutrals:
        notes.append(f'Neutral (ignored by the hue fit): {", ".join(neutrals)}.')
    return Report(sp, pal, cands, fits, chosen, to_hex(parse_hex(background)) if background else None,
                  notes)
