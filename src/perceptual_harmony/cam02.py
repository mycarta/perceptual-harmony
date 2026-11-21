"""CIECAM02 and CAM16 with their uniform colour spaces CAM02-UCS and CAM16-UCS (Luo, Cui & Li
2006; Li et al. 2017), forward and inverse, standard library only.

Viewing conditions match the defaults of the `colorspacious` package so results can be
checked against it: D65 white (XYZ 95.047, 100, 108.883), adapting luminance L_A = 64/pi/5 cd/m2,
background Y_b = 20, average surround. CAM16 uses the same conditions (and matches the
`colour-science` defaults).
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


# CAM16 (Li et al. 2017) replaces CAT02 and the Hunt-Pointer-Estevez step with one matrix, M16.
_M16 = ((0.401288, 0.650173, -0.051461),
        (-0.250268, 1.204414, 0.045854),
        (-0.002079, 0.048952, 0.953127))
_IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

# ---- viewing conditions -----------------------------------------------------------------------
_XYZ_W = (95.047, 100.0, 108.883)
_L_A = 64 / math.pi / 5
_Y_B = 20.0
_F, _C, _N_C = 1.0, 0.69, 1.0          # average surround


class _Model:
    """CIECAM02 or CAM16 under the viewing conditions above.

    m_cat: matrix to the space of chromatic adaptation (CAT02 or M16).
    m_post: matrix from there to the space of response compression (HPE for CIECAM02, identity
    for CAM16, which compresses in the M16 space).
    """

    def __init__(self, m_cat, m_post):
        self.m_cat, self.m_cat_inv = m_cat, _inv(m_cat)
        self.m_post, self.m_post_inv = m_post, _inv(m_post)
        self.y_w = _XYZ_W[1]
        rgb_w = _mul(m_cat, _XYZ_W)
        D = min(1.0, max(0.0, _F * (1 - (1 / 3.6) * math.exp((-_L_A - 42) / 92))))
        self.d_rgb = tuple(self.y_w * D / w + 1 - D for w in rgb_w)
        k = 1 / (5 * _L_A + 1)
        self.f_l = 0.2 * k ** 4 * (5 * _L_A) + 0.1 * (1 - k ** 4) ** 2 * (5 * _L_A) ** (1 / 3)
        self.n = _Y_B / self.y_w
        self.z = 1.48 + math.sqrt(self.n)
        self.n_bb = self.n_cb = 0.725 * self.n ** -0.2
        rgb_aw = tuple(self._adapt(v) for v in
                       _mul(m_post, tuple(w * d for w, d in zip(rgb_w, self.d_rgb))))
        self.a_w = (2 * rgb_aw[0] + rgb_aw[1] + rgb_aw[2] / 20 - 0.305) * self.n_bb

    def _adapt(self, x):
        """Post-adaptation non-linear response compression."""
        p = (self.f_l * abs(x) / 100) ** 0.42
        return math.copysign(400 * p / (p + 27.13), x) + 0.1

    def _unadapt(self, ra):
        x = ra - 0.1
        ax = min(abs(x), 399.999999)     # guard against out-of-range inputs
        return math.copysign(100 / self.f_l * (27.13 * ax / (400 - ax)) ** (1 / 0.42), x)

    def xyz100_to_jmh(self, xyz):
        """Lightness J, colourfulness M and hue angle h (degrees) from XYZ scaled 0-100."""
        rgb_c = tuple(v * d for v, d in zip(_mul(self.m_cat, xyz), self.d_rgb))
        ra, ga, ba = (self._adapt(v) for v in _mul(self.m_post, rgb_c))
        a = ra - 12 * ga / 11 + ba / 11
        b = (ra + ga - 2 * ba) / 9
        h = math.degrees(math.atan2(b, a)) % 360
        e_t = 0.25 * (math.cos(math.radians(h) + 2) + 3.8)
        A = (2 * ra + ga + ba / 20 - 0.305) * self.n_bb
        J = 100 * (max(A, 0.0) / self.a_w) ** (_C * self.z)
        t = (50000 / 13 * _N_C * self.n_cb * e_t * math.hypot(a, b)) / (ra + ga + 21 / 20 * ba)
        C = max(t, 0.0) ** 0.9 * math.sqrt(J / 100) * (1.64 - 0.29 ** self.n) ** 0.73
        return J, C * self.f_l ** 0.25, h

    def jmh_to_xyz100(self, J, M, h):
        """Inverse of xyz100_to_jmh."""
        if J <= 0:
            return (0.0, 0.0, 0.0)
        C = M / self.f_l ** 0.25
        t = (C / (math.sqrt(J / 100) * (1.64 - 0.29 ** self.n) ** 0.73)) ** (1 / 0.9)
        hr = math.radians(h)
        e_t = 0.25 * (math.cos(hr + 2) + 3.8)
        A = self.a_w * (J / 100) ** (1 / (_C * self.z))
        p2 = A / self.n_bb + 0.305
        p3 = 21 / 20
        if t == 0:
            a = b = 0.0
        else:
            p1 = (50000 / 13 * _N_C * self.n_cb) * e_t / t
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
        rgb_c = _mul(self.m_post_inv, tuple(self._unadapt(v) for v in (ra, ga, ba)))
        return _mul(self.m_cat_inv, tuple(v / d for v, d in zip(rgb_c, self.d_rgb)))

    def xyz100_to_ucs(self, xyz):
        """UCS J', a', b' (Luo, Cui & Li 2006 coefficients, used by both CAM02-UCS and CAM16-UCS)."""
        J, M, h = self.xyz100_to_jmh(xyz)
        Jp = 1.7 * J / (1 + 0.007 * J)
        Mp = math.log1p(0.0228 * M) / 0.0228
        return Jp, Mp * math.cos(math.radians(h)), Mp * math.sin(math.radians(h))

    def ucs_to_xyz100(self, Jp, ap, bp):
        J = Jp / (1.7 - 0.007 * Jp)
        Mp = math.hypot(ap, bp)
        M = math.expm1(0.0228 * Mp) / 0.0228
        h = math.degrees(math.atan2(bp, ap)) % 360
        return self.jmh_to_xyz100(J, M, h)


CIECAM02 = _Model(_M_CAT02, _matmul(_M_HPE, _inv(_M_CAT02)))
CAM16 = _Model(_M16, _IDENTITY)

# CIECAM02 module-level API
xyz100_to_jmh = CIECAM02.xyz100_to_jmh
jmh_to_xyz100 = CIECAM02.jmh_to_xyz100
xyz100_to_ucs = CIECAM02.xyz100_to_ucs
ucs_to_xyz100 = CIECAM02.ucs_to_xyz100
