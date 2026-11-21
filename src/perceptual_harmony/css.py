"""Read colours written in CSS: hex, rgb(), hsl(), hwb(), oklch(), oklab(), lab(), lch(), named
colours, and the custom properties (``--name: value``) of a style sheet.

Only what is needed to read a palette: alpha is accepted and ignored, ``var()`` references are
resolved, and colours outside the sRGB gamut are clipped (and reported by ``css_colours``).
"""
from __future__ import annotations

import fnmatch
import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

from . import cam02
from .colour import (Triple, cielab_to_srgb, in_gamut, linear_to_srgb, oklab_to_srgb, parse_hex,
                     srgb_to_linear, to_hex)

# CSS named colours (CSS Color Module Level 4)
_NAMED_TABLE = """
aliceblue:f0f8ff antiquewhite:faebd7 aqua:00ffff aquamarine:7fffd4 azure:f0ffff
beige:f5f5dc bisque:ffe4c4 black:000000 blanchedalmond:ffebcd blue:0000ff blueviolet:8a2be2
brown:a52a2a burlywood:deb887 cadetblue:5f9ea0 chartreuse:7fff00 chocolate:d2691e
coral:ff7f50 cornflowerblue:6495ed cornsilk:fff8dc crimson:dc143c cyan:00ffff
darkblue:00008b darkcyan:008b8b darkgoldenrod:b8860b darkgray:a9a9a9 darkgreen:006400
darkgrey:a9a9a9 darkkhaki:bdb76b darkmagenta:8b008b darkolivegreen:556b2f darkorange:ff8c00
darkorchid:9932cc darkred:8b0000 darksalmon:e9967a darkseagreen:8fbc8f darkslateblue:483d8b
darkslategray:2f4f4f darkslategrey:2f4f4f darkturquoise:00ced1 darkviolet:9400d3
deeppink:ff1493 deepskyblue:00bfff dimgray:696969 dimgrey:696969 dodgerblue:1e90ff
firebrick:b22222 floralwhite:fffaf0 forestgreen:228b22 fuchsia:ff00ff gainsboro:dcdcdc
ghostwhite:f8f8ff gold:ffd700 goldenrod:daa520 gray:808080 green:008000 greenyellow:adff2f
grey:808080 honeydew:f0fff0 hotpink:ff69b4 indianred:cd5c5c indigo:4b0082 ivory:fffff0
khaki:f0e68c lavender:e6e6fa lavenderblush:fff0f5 lawngreen:7cfc00 lemonchiffon:fffacd
lightblue:add8e6 lightcoral:f08080 lightcyan:e0ffff lightgoldenrodyellow:fafad2
lightgray:d3d3d3 lightgreen:90ee90 lightgrey:d3d3d3 lightpink:ffb6c1 lightsalmon:ffa07a
lightseagreen:20b2aa lightskyblue:87cefa lightslategray:778899 lightslategrey:778899
lightsteelblue:b0c4de lightyellow:ffffe0 lime:00ff00 limegreen:32cd32 linen:faf0e6
magenta:ff00ff maroon:800000 mediumaquamarine:66cdaa mediumblue:0000cd mediumorchid:ba55d3
mediumpurple:9370db mediumseagreen:3cb371 mediumslateblue:7b68ee mediumspringgreen:00fa9a
mediumturquoise:48d1cc mediumvioletred:c71585 midnightblue:191970 mintcream:f5fffa
mistyrose:ffe4e1 moccasin:ffe4b5 navajowhite:ffdead navy:000080 oldlace:fdf5e6 olive:808000
olivedrab:6b8e23 orange:ffa500 orangered:ff4500 orchid:da70d6 palegoldenrod:eee8aa
palegreen:98fb98 paleturquoise:afeeee palevioletred:db7093 papayawhip:ffefd5
peachpuff:ffdab9 peru:cd853f pink:ffc0cb plum:dda0dd powderblue:b0e0e6 purple:800080
rebeccapurple:663399 red:ff0000 rosybrown:bc8f8f royalblue:4169e1 saddlebrown:8b4513
salmon:fa8072 sandybrown:f4a460 seagreen:2e8b57 seashell:fff5ee sienna:a0522d silver:c0c0c0
skyblue:87ceeb slateblue:6a5acd slategray:708090 slategrey:708090 snow:fffafa
springgreen:00ff7f steelblue:4682b4 tan:d2b48c teal:008080 thistle:d8bfd8 tomato:ff6347
turquoise:40e0d0 violet:ee82ee wheat:f5deb3 white:ffffff whitesmoke:f5f5f5 yellow:ffff00
yellowgreen:9acd32
"""
NAMED: Dict[str, str] = dict(tok.split(':') for tok in _NAMED_TABLE.split())

_FUNC = re.compile(r'^(rgba?|hsla?|hwb|oklch|oklab|lab|lch)\(\s*(.*?)\s*\)$', re.I | re.S)
_HEX4 = re.compile(r'^#([0-9a-fA-F]{4}|[0-9a-fA-F]{8})$')


def _num(tok: str, pct_scale: float = 1.0) -> float:
    """A CSS number or percentage; a percentage is scaled so that 100% = pct_scale."""
    tok = tok.strip()
    if tok.lower() == 'none':
        return 0.0
    if tok.endswith('%'):
        return float(tok[:-1]) / 100 * pct_scale
    return float(tok)


def _angle(tok: str) -> float:
    tok = tok.strip().lower()
    for unit, f in (('deg', 1.0), ('grad', 0.9), ('rad', 180 / math.pi), ('turn', 360.0)):
        if tok.endswith(unit):
            return float(tok[:-len(unit)]) * f
    return 0.0 if tok == 'none' else float(tok)


def _args(body: str) -> List[str]:
    """Split 'a b c / alpha' or 'a, b, c, alpha' into the three colour components."""
    body = body.split('/')[0]
    parts = [p for p in re.split(r'[\s,]+', body.strip()) if p]
    if len(parts) < 3:
        raise ValueError
    return parts[:3]


def _hsl_to_rgb(h: float, s: float, l: float) -> Triple:
    def f(n):
        k = (n + h / 30) % 12
        a = s * min(l, 1 - l)
        return l - a * max(-1.0, min(k - 3, 9 - k, 1.0))
    return f(0), f(8), f(4)


# CSS lab() and lch() are CIELAB relative to D50; adapt to D65 (Bradford, as in CSS Color 4)
_D50 = (0.3457 / 0.3585, 1.0, (1 - 0.3457 - 0.3585) / 0.3585)
_D50_TO_D65 = ((0.955473421488075, -0.02309845494876471, 0.06325924320057072),
               (-0.0283697093338637, 1.0099953980813041, 0.021041441191917323),
               (0.012314014864481998, -0.020507649298898964, 1.330365926242124))


def _lab_d50_to_srgb(L: float, a: float, b: float) -> Triple:
    from .colour import xyz_to_srgb
    eps, kappa = 216 / 24389, 24389 / 27
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    xr = fx ** 3 if fx ** 3 > eps else (116 * fx - 16) / kappa
    yr = fy ** 3 if L > kappa * eps else L / kappa
    zr = fz ** 3 if fz ** 3 > eps else (116 * fz - 16) / kappa
    xyz50 = (xr * _D50[0], yr * _D50[1], zr * _D50[2])
    return xyz_to_srgb(cam02._mul(_D50_TO_D65, xyz50))


def parse_colour_rgb(value: str) -> Triple:
    """Any supported CSS colour -> sRGB triple in 0-1, possibly outside the gamut (not clipped)."""
    v = value.strip()
    low = v.lower()
    if low in NAMED:
        return parse_hex(NAMED[low])
    if low == 'transparent':
        return (0.0, 0.0, 0.0)
    m4 = _HEX4.match(v)
    if m4:                                   # #rgba / #rrggbbaa: drop the alpha
        h = m4.group(1)
        return parse_hex(h[:3] if len(h) == 4 else h[:6])
    if v.startswith('#') or re.fullmatch(r'[0-9a-fA-F]{3}|[0-9a-fA-F]{6}', v):
        return parse_hex(v)
    m = _FUNC.match(v)
    if not m:
        raise ValueError(f'not a CSS colour: {value!r}')
    fn, body = m.group(1).lower(), m.group(2)
    try:
        p = _args(body)
        if fn in ('rgb', 'rgba'):
            return tuple(_num(t, 255) / 255 for t in p)
        if fn in ('hsl', 'hsla'):
            return _hsl_to_rgb(_angle(p[0]) % 360, _num(p[1].rstrip('%')) / 100, _num(p[2].rstrip('%')) / 100)
        if fn == 'hwb':
            h, w, bk = _angle(p[0]) % 360, _num(p[1], 1), _num(p[2], 1)
            if w + bk >= 1:
                g = w / (w + bk)
                return (g, g, g)
            return tuple(c * (1 - w - bk) + w for c in _hsl_to_rgb(h, 1.0, 0.5))
        if fn == 'oklab':
            return oklab_to_srgb((_num(p[0], 1), _num(p[1], 0.4), _num(p[2], 0.4)))
        if fn == 'oklch':
            L, C, h = _num(p[0], 1), _num(p[1], 0.4), math.radians(_angle(p[2]))
            return oklab_to_srgb((L, C * math.cos(h), C * math.sin(h)))
        if fn == 'lab':
            return _lab_d50_to_srgb(_num(p[0], 100), _num(p[1], 125), _num(p[2], 125))
        if fn == 'lch':
            L, C, h = _num(p[0], 100), _num(p[1], 150), math.radians(_angle(p[2]))
            return _lab_d50_to_srgb(L, C * math.cos(h), C * math.sin(h))
    except (ValueError, IndexError):
        pass
    raise ValueError(f'not a CSS colour: {value!r}')


def parse_colour(value: str) -> str:
    """Any supported CSS colour -> '#rrggbb' (clipped to the sRGB gamut)."""
    return to_hex(parse_colour_rgb(value))


# ---- style sheets ----------------------------------------------------------------------------
_COMMENT = re.compile(r'/\*.*?\*/', re.S)
_DECL = re.compile(r'(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]+?)\s*(?:;|(?=}))')
_VAR = re.compile(r'^var\(\s*(--[A-Za-z0-9_-]+)\s*(?:,\s*(.+))?\)$', re.S)


def custom_properties(css: str) -> Dict[str, str]:
    """Custom properties of a style sheet, name (without '--') -> raw value. The first definition
    of each name wins, so redefinitions in later blocks (a dark theme, say) are ignored."""
    props: Dict[str, str] = {}
    for name, value in _DECL.findall(_COMMENT.sub('', css)):
        props.setdefault(name[2:], value.strip())
    return props


def _resolve(value: str, props: Dict[str, str], depth: int = 0) -> Optional[str]:
    m = _VAR.match(value.strip())
    if not m:
        return value
    if depth > 20:
        return None
    name, fallback = m.group(1)[2:], m.group(2)
    if name in props:
        return _resolve(props[name], props, depth + 1)
    return _resolve(fallback, props, depth + 1) if fallback else None


def css_colours(css: str, only: Sequence[str] = (), exclude: Sequence[str] = ()
                ) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Colour custom properties of a style sheet, in order of first definition.

    Returns ([(name, '#rrggbb'), ...], notes). Properties whose value is not a single colour (a
    font, a shadow, a length) are skipped silently. `only` and `exclude` are name patterns
    (fnmatch, with or without the leading '--'), e.g. exclude=['ink*', 'paper*'].
    """
    only = [p.lstrip('-') for p in only]
    exclude = [p.lstrip('-') for p in exclude]
    props = custom_properties(css)
    out, notes, clipped = [], [], []
    for name, raw in props.items():
        if only and not any(fnmatch.fnmatchcase(name, p) for p in only):
            continue
        if any(fnmatch.fnmatchcase(name, p) for p in exclude):
            continue
        value = _resolve(raw, props)
        if value is None:
            continue
        try:
            rgb = parse_colour_rgb(value)
        except ValueError:
            continue
        if not in_gamut(rgb, 1e-4):
            clipped.append(name)
        out.append((name, to_hex(rgb)))
    if clipped:
        notes.append(f'Outside the sRGB gamut, clipped: {", ".join(clipped)}.')
    return out, notes


def lookup(value: str, css_props: Optional[Dict[str, str]] = None) -> str:
    """A colour given as CSS, or as the name of a custom property ('paper', '--paper' or
    'var(--paper)') when the properties of a style sheet are supplied -> '#rrggbb'."""
    if css_props:
        key = value.strip()
        m = _VAR.match(key)
        key = (m.group(1) if m else key).lstrip('-')
        if key in css_props:
            resolved = _resolve(css_props[key], css_props)
            if resolved is not None:
                return parse_colour(resolved)
    return parse_colour(value)
