"""Colour parsing and conversion between sRGB and the perceptual spaces used for harmony.

Every space is exposed as a `Space` with the same interface: lightness, chroma and hue in that
space's own units, plus the Euclidean colour difference in its rectangular form.

  oklch     OKLab / OKLCH (Ottosson 2020). L 0-1, C roughly 0-0.37.
  cielch    CIELAB / CIELCh, D65 white. L* 0-100, C* roughly 0-134. Delta E is CIE76.
  cam02ucs  CAM02-UCS (Luo et al. 2006) on CIECAM02. J' 0-100, M' roughly 0-50.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from . import cam02

Triple = Tuple[float, float, float]

# ---- sRGB ------------------------------------------------------------------------------------
_HEX = re.compile(r'^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$')


def parse_hex(s: str) -> Triple:
    """'#30859e', '30859e' or '#38a' -> sRGB in 0-1."""
    m = _HEX.match(s.strip())
    if not m:
        raise ValueError(f'not a hex colour: {s!r}')
    h = m.group(1)
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def to_hex(rgb: Triple) -> str:
    return '#' + ''.join('%02x' % round(min(1.0, max(0.0, v)) * 255) for v in rgb)


def in_gamut(rgb: Triple, eps: float = 1e-6) -> bool:
    return all(-eps <= v <= 1 + eps for v in rgb)


def _to_linear(v: float) -> float:
    return v / 12.92 if abs(v) <= 0.04045 else math.copysign(((abs(v) + 0.055) / 1.055) ** 2.4, v)


def _from_linear(v: float) -> float:
    return v * 12.92 if abs(v) <= 0.0031308 else math.copysign(1.055 * abs(v) ** (1 / 2.4) - 0.055, v)


def srgb_to_linear(rgb: Triple) -> Triple:
    return tuple(_to_linear(v) for v in rgb)


def linear_to_srgb(lin: Triple) -> Triple:
    return tuple(_from_linear(v) for v in lin)


def _mul(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


_RGB_TO_XYZ = ((0.4124564, 0.3575761, 0.1804375),
               (0.2126729, 0.7151522, 0.0721750),
               (0.0193339, 0.1191920, 0.9503041))
_XYZ_TO_RGB = cam02._inv(_RGB_TO_XYZ)


def srgb_to_xyz(rgb: Triple) -> Triple:
    """XYZ with Y = 1 for sRGB white (D65)."""
    return _mul(_RGB_TO_XYZ, srgb_to_linear(rgb))


def xyz_to_srgb(xyz: Triple) -> Triple:
    return linear_to_srgb(_mul(_XYZ_TO_RGB, xyz))


def relative_luminance(rgb: Triple) -> float:
    """WCAG 2 relative luminance."""
    r, g, b = srgb_to_linear(rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---- OKLab -----------------------------------------------------------------------------------
_LIN_TO_LMS = ((0.4122214708, 0.5363325363, 0.0514459929),
               (0.2119034982, 0.6806995451, 0.1073969566),
               (0.0883024619, 0.2817188376, 0.6299787005))
_LMS_TO_OK = ((0.2104542553, 0.7936177850, -0.0040720468),
              (1.9779984951, -2.4285922050, 0.4505937099),
              (0.0259040371, 0.7827717662, -0.8086757660))
# exact inverses, so conversions round-trip to machine precision
_OK_TO_LMS = cam02._inv(_LMS_TO_OK)
_LMS_TO_LIN = cam02._inv(_LIN_TO_LMS)


def srgb_to_oklab(rgb: Triple) -> Triple:
    lms = _mul(_LIN_TO_LMS, srgb_to_linear(rgb))
    return _mul(_LMS_TO_OK, tuple(math.copysign(abs(v) ** (1 / 3), v) for v in lms))


def oklab_to_srgb(lab: Triple) -> Triple:
    lms = tuple(v ** 3 for v in _mul(_OK_TO_LMS, lab))
    return linear_to_srgb(_mul(_LMS_TO_LIN, lms))


# ---- CIELAB (D65) ------------------------------------------------------------------------------
_WHITE_D65 = (0.95047, 1.0, 1.08883)
_EPS, _KAPPA = 216 / 24389, 24389 / 27


def srgb_to_cielab(rgb: Triple) -> Triple:
    def f(t):
        return t ** (1 / 3) if t > _EPS else (_KAPPA * t + 16) / 116
    fx, fy, fz = (f(v / w) for v, w in zip(srgb_to_xyz(rgb), _WHITE_D65))
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def cielab_to_srgb(lab: Triple) -> Triple:
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def finv(t):
        return t ** 3 if t ** 3 > _EPS else (116 * t - 16) / _KAPPA
    return xyz_to_srgb(tuple(finv(t) * w for t, w in zip((fx, fy, fz), _WHITE_D65)))


# ---- CAM02-UCS -------------------------------------------------------------------------------
def srgb_to_cam02ucs(rgb: Triple) -> Triple:
    return cam02.xyz100_to_ucs(tuple(100 * v for v in srgb_to_xyz(rgb)))


def cam02ucs_to_srgb(jab: Triple) -> Triple:
    return xyz_to_srgb(tuple(v / 100 for v in cam02.ucs_to_xyz100(*jab)))


# ---- CAM16-UCS -------------------------------------------------------------------------------
def srgb_to_cam16ucs(rgb: Triple) -> Triple:
    return cam02.CAM16.xyz100_to_ucs(tuple(100 * v for v in srgb_to_xyz(rgb)))


def cam16ucs_to_srgb(jab: Triple) -> Triple:
    return xyz_to_srgb(tuple(v / 100 for v in cam02.CAM16.ucs_to_xyz100(*jab)))


# ---- IPT (Ebner & Fairchild 1998) -------------------------------------------------------------
_XYZ_TO_LMS_IPT = ((0.4002, 0.7075, -0.0807),
                   (-0.2280, 1.1500, 0.0612),
                   (0.0, 0.0, 0.9184))
_LMS_TO_IPT = ((0.4000, 0.4000, 0.2000),
               (4.4550, -4.8510, 0.3960),
               (0.8056, 0.3572, -1.1628))
_LMS_IPT_TO_XYZ = cam02._inv(_XYZ_TO_LMS_IPT)
_IPT_TO_LMS = cam02._inv(_LMS_TO_IPT)


def srgb_to_ipt(rgb: Triple) -> Triple:
    lms = _mul(_XYZ_TO_LMS_IPT, srgb_to_xyz(rgb))
    return _mul(_LMS_TO_IPT, tuple(math.copysign(abs(v) ** 0.43, v) for v in lms))


def ipt_to_srgb(ipt: Triple) -> Triple:
    lms = tuple(math.copysign(abs(v) ** (1 / 0.43), v) for v in _mul(_IPT_TO_LMS, ipt))
    return xyz_to_srgb(_mul(_LMS_IPT_TO_XYZ, lms))


# ---- the Space interface -----------------------------------------------------------------------
@dataclass(frozen=True)
class Space:
    """A perceptual colour space with a lightness axis and two opponent axes."""
    name: str
    label: str                 # human-readable name
    axis_names: Tuple[str, str, str]   # lightness, chroma, hue symbols
    to_lab: Callable[[Triple], Triple]
    from_lab: Callable[[Triple], Triple]
    neutral_chroma: float      # below this chroma, hue is treated as undefined
    jnd: float                 # rough just-noticeable colour difference, for reporting
    l_scale: float = 1.0       # multiply lightness by this to report it on a 0-100 scale

    def lch(self, rgb: Triple) -> Triple:
        L, a, b = self.to_lab(rgb)
        return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360

    def lch_to_srgb(self, L: float, C: float, h: float) -> Triple:
        hr = math.radians(h)
        return self.from_lab((L, C * math.cos(hr), C * math.sin(hr)))

    def delta_e(self, rgb1: Triple, rgb2: Triple) -> float:
        return math.dist(self.to_lab(rgb1), self.to_lab(rgb2))

    def max_chroma(self, L: float, h: float, hi: float) -> float:
        """Largest chroma inside the sRGB gamut at lightness L and hue h (bisection)."""
        lo = 0.0
        if not in_gamut(self.lch_to_srgb(L, 0.0, h)):
            return 0.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if in_gamut(self.lch_to_srgb(L, mid, h)):
                lo = mid
            else:
                hi = mid
        return lo


SPACES: Dict[str, Space] = {
    'oklch': Space('oklch', 'OKLCH', ('L', 'C', 'h'), srgb_to_oklab, oklab_to_srgb,
                   neutral_chroma=0.015, jnd=0.02, l_scale=100.0),
    'cielch': Space('cielch', 'CIELCh (D65)', ('L*', 'C*', 'h'), srgb_to_cielab, cielab_to_srgb,
                    neutral_chroma=4.0, jnd=2.3),
    'cam02ucs': Space('cam02ucs', 'CAM02-UCS', ("J'", "M'", 'h'), srgb_to_cam02ucs, cam02ucs_to_srgb,
                      neutral_chroma=2.5, jnd=1.0),
    'cam16ucs': Space('cam16ucs', 'CAM16-UCS', ("J'", "M'", 'h'), srgb_to_cam16ucs, cam16ucs_to_srgb,
                      neutral_chroma=2.5, jnd=1.0),
    # IPT has no published JND; both thresholds are OKLCH's scaled by the median IPT/OKLab ratio
    # of chroma (2.3) and of small colour differences (1.9) over random sRGB colours.
    'ipt': Space('ipt', 'IPT', ('I', 'C', 'h'), srgb_to_ipt, ipt_to_srgb,
                 neutral_chroma=0.035, jnd=0.04, l_scale=100.0),
}

# Spaces compared by default in the robustness check: one per design family, chosen for that
# reason and not for the results they give. CAM16-UCS stands in for CAM02-UCS, which it supersedes.
ROBUSTNESS_SPACES = ('oklch', 'cielch', 'cam16ucs', 'ipt')

# chroma scale used to size plots: the largest chroma of any sRGB colour in each space
SRGB_MAX_CHROMA = {'oklch': 0.323, 'cielch': 133.8, 'cam02ucs': 45.7, 'cam16ucs': 46.0, 'ipt': 0.786}


def get_space(name) -> Space:
    if isinstance(name, Space):
        return name
    try:
        return SPACES[name.lower().replace('-', '').replace('_', '')]
    except KeyError:
        raise ValueError(f'unknown colour space {name!r}; choose from {", ".join(SPACES)}') from None
