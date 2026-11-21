"""Colour-vision deficiency: simulate dichromacy and find colours that become hard to tell apart.

Simulation follows Machado, Oliveira & Fernandes (2009) at full severity (protanopia,
deuteranopia, tritanopia): a 3x3 matrix applied in linear sRGB, as in the `colorspacious`
package, whose matrices these are. Results outside the gamut are clipped.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Sequence, Tuple

from .colour import Space, Triple, linear_to_srgb, srgb_to_linear

# Machado et al. (2009), severity 1.0
MACHADO_2009 = {
    'protanopia': ((0.152286, 1.052583, -0.204868),
                   (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    'deuteranopia': ((0.367322, 0.860646, -0.227968),
                     (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    'tritanopia': ((1.255528, -0.076749, -0.178779),
                   (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}
CVD_TYPES = tuple(MACHADO_2009)


def simulate(rgb: Triple, kind: str) -> Triple:
    """sRGB (0-1) as seen with the given dichromacy."""
    m = MACHADO_2009[kind]
    lin = srgb_to_linear(rgb)
    out = tuple(min(1.0, max(0.0, m[i][0] * lin[0] + m[i][1] * lin[1] + m[i][2] * lin[2]))
                for i in range(3))
    return linear_to_srgb(out)


@dataclass
class CVDPair:
    kind: str
    a: str
    b: str
    delta_e: float                  # colour difference under the simulation, in the report's space
    normal: float                   # the same pair in normal vision

    def to_dict(self) -> dict:
        return {'kind': self.kind, 'a': self.a, 'b': self.b, 'delta_e': round(self.delta_e, 4),
                'normal': round(self.normal, 4)}


def close_pairs(colours: Sequence[Tuple[str, Triple]], space: Space, threshold: float
                ) -> Dict[str, List[CVDPair]]:
    """For each dichromacy, the pairs closer than `threshold` (closest first); if none are, the
    single closest pair, so the report always shows how close the palette comes."""
    out: Dict[str, List[CVDPair]] = {}
    for kind in CVD_TYPES:
        sim = [(label, simulate(rgb, kind), rgb) for label, rgb in colours]
        pairs = sorted((CVDPair(kind, la, lb, space.delta_e(sa, sb), space.delta_e(ra, rb))
                        for (la, sa, ra), (lb, sb, rb) in combinations(sim, 2)),
                       key=lambda p: p.delta_e)
        close = [p for p in pairs if p.delta_e < threshold]
        out[kind] = close or pairs[:1]
    return out
