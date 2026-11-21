"""Harmonic hue templates (Matsuda; Cohen-Or et al. 2006) and fitting them to a set of hues.

A template is a set of sectors on the hue wheel, each given as (offset, width) in degrees. The
offset is relative to the template's rotation, which is the centre of its first sector. Widths
follow Cohen-Or et al. (2006): narrow sectors are 18 degrees (5% of the wheel), wide ones 93.6
degrees (26%), the wide sector of L is 79.2 degrees (22%) and T is half the wheel.

Fitting follows the paper's harmony function: each colour's distance to the template is the
angle from its hue to the nearest sector edge (zero when inside a sector), weighted by its
chroma (the paper uses saturation). Here the weighted sum is divided by the total weight, so the
cost reads as a chroma-weighted mean hue deviation in degrees.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

NARROW, WIDE, L_WIDE, HALF = 18.0, 93.6, 79.2, 180.0


@dataclass(frozen=True)
class Template:
    name: str
    sectors: Tuple[Tuple[float, float], ...]   # (offset from rotation, width), degrees
    description: str

    @property
    def coverage(self) -> float:
        """Total angular width of the sectors, degrees."""
        return sum(w for _, w in self.sectors)


TEMPLATES: Dict[str, Template] = {t.name: t for t in (
    Template('i', ((0, NARROW),), 'one narrow sector'),
    Template('V', ((0, WIDE),), 'one wide sector'),
    Template('L', ((0, NARROW), (90, L_WIDE)), 'narrow sector, wide sector 90 degrees away'),
    Template('I', ((0, NARROW), (180, NARROW)), 'two opposite narrow sectors'),
    Template('T', ((0, HALF),), 'half the wheel'),
    Template('Y', ((0, WIDE), (180, NARROW)), 'wide sector, opposite narrow sector'),
    Template('X', ((0, WIDE), (180, WIDE)), 'two opposite wide sectors'),
)}


def get_template(name) -> Template:
    if isinstance(name, Template):
        return name
    try:
        return TEMPLATES[name]
    except KeyError:
        raise ValueError(f'unknown template {name!r}; choose from {", ".join(TEMPLATES)}') from None


def angle_diff(a: float, b: float) -> float:
    """Signed smallest difference a - b, in (-180, 180]."""
    d = (a - b) % 360
    return d - 360 if d > 180 else d


def margin(hue: float, template: Template, rotation: float) -> Tuple[float, int]:
    """Signed angular margin of a hue in a rotated template, and the sector it belongs to.

    Positive: inside a sector, by that many degrees from its nearest edge.
    Negative: outside every sector, by that many degrees from the nearest edge.
    """
    best, idx = -999.0, 0
    for i, (off, w) in enumerate(template.sectors):
        m = w / 2 - abs(angle_diff(hue, rotation + off))
        if m > best:
            best, idx = m, i
    return best, idx


@dataclass
class Fit:
    template: Template
    rotation: float                 # centre of the first sector, degrees
    cost: float                     # chroma-weighted mean deviation outside the sectors, degrees
    margins: List[float] = field(default_factory=list)   # per hue, as in `margin`

    @property
    def fits(self) -> bool:
        return self.cost < 1e-9

    def sector_ranges(self) -> List[Tuple[float, float]]:
        """(start, end) hue angles of each sector, going counter-clockwise from start to end."""
        return [((self.rotation + off - w / 2) % 360, (self.rotation + off + w / 2) % 360)
                for off, w in self.template.sectors]


def _evaluate(hues, weights, template, rotation):
    margins = [margin(h, template, rotation)[0] for h in hues]
    total = sum(weights)
    cost = sum(w * max(0.0, -m) for w, m in zip(weights, margins)) / total if total else 0.0
    return cost, margins


def fit_template(hues: Sequence[float], weights: Sequence[float], template,
                 rotation: Optional[float] = None) -> Fit:
    """Best rotation of one template for the given hues (or evaluate a fixed rotation).

    The cost is piecewise linear in the rotation, with its minima where some hue sits exactly on
    a sector edge, so trying every such rotation finds the global minimum. Among rotations of
    equal cost (typically several that fit perfectly) the one whose worst-placed hue sits
    furthest inside its sector is chosen; that tie-break is searched on a 0.25 degree grid plus
    the exact edge rotations.
    """
    template = get_template(template)
    if not hues:
        return Fit(template, 0.0 if rotation is None else rotation % 360, 0.0, [])
    if rotation is not None:
        cost, margins = _evaluate(hues, weights, template, rotation % 360)
        return Fit(template, rotation % 360, cost, margins)
    candidates = {round((h - off + s * w / 2) % 360, 9)
                  for h in hues for off, w in template.sectors for s in (-1, 1)}
    candidates.update(i * 0.25 for i in range(1440))
    best = None
    for rot in sorted(candidates):
        cost, margins = _evaluate(hues, weights, template, rot)
        key = (round(cost, 9), -min(margins))
        if best is None or key < best[0]:
            best = (key, rot, cost, margins)
    _, rot, cost, margins = best
    return Fit(template, rot, cost, margins)


def fit_all(hues: Sequence[float], weights: Sequence[float]) -> List[Fit]:
    """Fit every template; best first (lowest cost, then the narrowest template)."""
    fits = [fit_template(hues, weights, t) for t in TEMPLATES.values()]
    return sorted(fits, key=lambda f: (round(f.cost, 6), f.template.coverage))
