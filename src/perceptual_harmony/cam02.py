"""CIECAM02 and CAM02-UCS (Luo, Cui & Li 2006), forward and inverse, standard library only.

Viewing conditions match the defaults of the `colorspacious` package so results can be
checked against it: D65 white (XYZ 95.047, 100, 108.883), adapting luminance L_A = 64/pi/5 cd/m2,
background Y_b = 20, average surround.
"""
from __future__ import annotations

import math

_M_CAT02 = ((0.7328, 0.4296, -0.1624),
            (-0.7036, 1.6975, 0.0061),
            (0.0030, 0.0136, 0.9834))
_M_HPE = ((0.38971, 0.68898, -0.07868),
          (-0.22981, 1.18340, 0.04641),
          (0.0, 0.0, 1.0))


def _mul(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _inv(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return ((( e * i - f * h) / det, -(b * i - c * h) / det, ( b * f - c * e) / det),
            (-(d * i - f * g) / det, ( a * i - c * g) / det, -(a * f - c * d) / det),
            (( d * h - e * g) / det, -(a * h - b * g) / det, ( a * e - b * d) / det))


_M_CAT02_INV = _inv(_M_CAT02)
_M_TO_HPE = _matmul(_M_HPE, _M_CAT02_INV)
_M_FROM_HPE = _matmul(_M_CAT02, _inv(_M_HPE))

# ---- viewing conditions -----------------------------------------------------------------------
_XYZ_W = (95.047, 100.0, 108.883)
_L_A = 64 / math.pi / 5
_Y_B = 20.0
_F, _C, _N_C = 1.0, 0.69, 1.0          # average surround

_Y_W = _XYZ_W[1]
_RGB_W = _mul(_M_CAT02, _XYZ_W)
_D = min(1.0, max(0.0, _F * (1 - (1 / 3.6) * math.exp((-_L_A - 42) / 92))))
_D_RGB = tuple(_Y_W * _D / w + 1 - _D for w in _RGB_W)
_k = 1 / (5 * _L_A + 1)
_F_L = 0.2 * _k ** 4 * (5 * _L_A) + 0.1 * (1 - _k ** 4) ** 2 * (5 * _L_A) ** (1 / 3)
_n = _Y_B / _Y_W
_z = 1.48 + math.sqrt(_n)
_N_BB = _N_CB = 0.725 * _n ** -0.2


def _adapt(x):
    """Post-adaptation non-linear response compression."""
    p = (_F_L * abs(x) / 100) ** 0.42
    return math.copysign(400 * p / (p + 27.13), x) + 0.1


def _unadapt(ra):
    x = ra - 0.1
    ax = min(abs(x), 399.999999)     # guard against out-of-range inputs
    return math.copysign(100 / _F_L * (27.13 * ax / (400 - ax)) ** (1 / 0.42), x)


_RGB_AW = tuple(_adapt(v) for v in _mul(_M_TO_HPE, tuple(w * d for w, d in zip(_RGB_W, _D_RGB))))
_A_W = (2 * _RGB_AW[0] + _RGB_AW[1] + _RGB_AW[2] / 20 - 0.305) * _N_BB


def xyz100_to_jmh(xyz):
    """CIECAM02 lightness J, colourfulness M and hue angle h (degrees) from XYZ scaled 0-100."""
    rgb_c = tuple(v * d for v, d in zip(_mul(_M_CAT02, xyz), _D_RGB))
    ra, ga, ba = (_adapt(v) for v in _mul(_M_TO_HPE, rgb_c))
    a = ra - 12 * ga / 11 + ba / 11
    b = (ra + ga - 2 * ba) / 9
    h = math.degrees(math.atan2(b, a)) % 360
    e_t = 0.25 * (math.cos(math.radians(h) + 2) + 3.8)
    A = (2 * ra + ga + ba / 20 - 0.305) * _N_BB
    J = 100 * (max(A, 0.0) / _A_W) ** (_C * _z)
    t = (50000 / 13 * _N_C * _N_CB * e_t * math.hypot(a, b)) / (ra + ga + 21 / 20 * ba)
    C = max(t, 0.0) ** 0.9 * math.sqrt(J / 100) * (1.64 - 0.29 ** _n) ** 0.73
    return J, C * _F_L ** 0.25, h


def jmh_to_xyz100(J, M, h):
    """Inverse of xyz100_to_jmh."""
    if J <= 0:
        return (0.0, 0.0, 0.0)
    C = M / _F_L ** 0.25
    t = (C / (math.sqrt(J / 100) * (1.64 - 0.29 ** _n) ** 0.73)) ** (1 / 0.9)
    hr = math.radians(h)
    e_t = 0.25 * (math.cos(hr + 2) + 3.8)
    A = _A_W * (J / 100) ** (1 / (_C * _z))
    p2 = A / _N_BB + 0.305
    p3 = 21 / 20
    if t == 0:
        a = b = 0.0
    else:
        p1 = (50000 / 13 * _N_C * _N_CB) * e_t / t
        sh, ch = math.sin(hr), math.cos(hr)
        if abs(sh) >= abs(ch):
            p4 = p1 / sh
            b = p2 * (2 + p3) * (460 / 1403) / (
                p4 + (2 + p3) * (220 / 1403) * (ch / sh) - 27 / 1403 + p3 * (6300 / 1403))
            a = b * ch / sh
        else:
            p5 = p1 / ch
            a = p2 * (2 + p3) * (460 / 1403) / (
                p5 + (2 + p3) * (220 / 1403) - (27 / 1403 - p3 * (6300 / 1403)) * (sh / ch))
            b = a * sh / ch
    ra = (460 * p2 + 451 * a + 288 * b) / 1403
    ga = (460 * p2 - 891 * a - 261 * b) / 1403
    ba = (460 * p2 - 220 * a - 6300 * b) / 1403
    rgb_c = _mul(_M_FROM_HPE, tuple(_unadapt(v) for v in (ra, ga, ba)))
    return _mul(_M_CAT02_INV, tuple(v / d for v, d in zip(rgb_c, _D_RGB)))


def xyz100_to_ucs(xyz):
    """CAM02-UCS J', a', b'."""
    J, M, h = xyz100_to_jmh(xyz)
    Jp = 1.7 * J / (1 + 0.007 * J)
    Mp = math.log1p(0.0228 * M) / 0.0228
    return Jp, Mp * math.cos(math.radians(h)), Mp * math.sin(math.radians(h))


def ucs_to_xyz100(Jp, ap, bp):
    J = Jp / (1.7 - 0.007 * Jp)
    Mp = math.hypot(ap, bp)
    M = math.expm1(0.0228 * Mp) / 0.0228
    h = math.degrees(math.atan2(bp, ap)) % 360
    return jmh_to_xyz100(J, M, h)
