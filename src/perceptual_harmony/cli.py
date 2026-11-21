"""Command-line interface: `perceptual-harmony check ...` and `perceptual-harmony templates`."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .check import check
from .css import css_colours, custom_properties, lookup
from .colour import ROBUSTNESS_SPACES, SPACES
from .harmony import TEMPLATES


def _robustness_spaces(text: str):
    if text.strip().lower() == 'none':
        return ()
    names = [t.strip() for t in text.split(',') if t.strip()]
    for n in names:
        if n.lower().replace('-', '') not in SPACES:
            raise ValueError(f'unknown colour space {n!r} in --robustness; choose from {", ".join(SPACES)}')
    return names


def _patterns(text):
    return [t.strip() for t in (text or '').split(',') if t.strip()]


def _spec(text: str, props) -> str:
    """'label=colour', 'colour' or a custom-property name -> 'label=#rrggbb'."""
    label, value = text.split('=', 1) if '=' in text else ('', text)
    hx = lookup(value, props)
    name = value.strip().lstrip('-')
    if not label and props and name in props:
        label = name
    return f'{label.strip() or hx}={hx}'


def _palette(args):
    """Palette specs from --css and positional colours; returns (palette, props, notes)."""
    props, palette, notes = {}, [], []
    if args.css:
        with open(args.css, encoding='utf-8') as f:
            text = f.read()
        props = custom_properties(text)
        found, notes = css_colours(text, _patterns(args.only), _patterns(args.exclude))
        palette = [f'{n}={hx}' for n, hx in found]
    palette += [_spec(c, props) for c in args.colours]
    if not palette:
        raise ValueError('no palette colours: give colours, or --css with colour custom properties')
    return palette, props, notes


def _write_svg(args, report):
    if args.svg:
        from .svg import render_svg
        with open(args.svg, 'w', encoding='utf-8') as f:
            f.write(render_svg(report, title=args.title or '', layout=args.layout))
        if not args.json:
            print(f'\nwrote {args.svg}')
    if args.cvd_svg:
        from .svg import render_cvd_svg
        with open(args.cvd_svg, 'w', encoding='utf-8') as f:
            f.write(render_cvd_svg(report))
        if not args.json:
            print(f'wrote {args.cvd_svg}')


def _pair(text):
    if not text:
        return None
    a, b = (float(t) for t in text.split(','))
    return a, b


def _cmd_suggest(args) -> int:
    from .suggest import css_block, suggest
    palette, props, notes = _palette(args)
    light = _pair(args.lightness)
    if light and max(light) > 1:
        light = (light[0] / 100, light[1] / 100)        # given in percent
    report, found = suggest(palette, n=args.n, space=args.space, template=args.template,
                            rotation=args.rotation,
                            background=lookup(args.background, props) if args.background else None,
                            min_contrast=args.min_contrast, min_margin=args.min_margin,
                            lightness=light, chroma=_pair(args.chroma),
                            robustness_spaces=_robustness_spaces(args.robustness),
                            neutral_chroma=args.neutral_chroma, prefix=args.prefix,
                            cvd_safe=args.cvd_safe, cvd=not args.no_cvd,
                            cvd_threshold=args.cvd_threshold)
    report.notes += notes
    if args.json:
        import json
        d = report.to_dict()
        d['suggestions'] = [s.to_dict() for s in found]
        print(json.dumps(d, indent=2, ensure_ascii=False))
    else:
        print(report.to_text())
        if found:
            print('\nSuggested colours, as CSS custom properties:\n' + css_block(found))
    _write_svg(args, report)
    return 0


def _cmd_check(args) -> int:
    palette, props, notes = _palette(args)
    report = check(palette, [_spec(c, props) for c in args.candidate], space=args.space,
                   template=args.template, rotation=args.rotation,
                   background=lookup(args.background, props) if args.background else None,
                   neutral_chroma=args.neutral_chroma,
                   robustness_spaces=_robustness_spaces(args.robustness),
                   cvd=not args.no_cvd, cvd_threshold=args.cvd_threshold)
    report.notes += notes
    print(report.to_json() if args.json else report.to_text())
    _write_svg(args, report)
    return 0


def _cmd_templates(args) -> int:
    for t in TEMPLATES.values():
        secs = ', '.join(f'{w:g}° at +{off:g}°' for off, w in t.sectors)
        print(f'{t.name}  {t.description:45}  {secs}')
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog='perceptual-harmony',
        description='Hue harmony (Cohen-Or et al. 2006 templates) in perceptual colour spaces.')
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    sub = p.add_subparsers(dest='command', required=True)

    def common(c):
        c.add_argument('colours', nargs='*', help='palette colours (added after any read with --css)')
        c.add_argument('--css', metavar='FILE',
                       help='read the palette from the colour custom properties (--name: colour) of '
                            'a style sheet; -b and -c then also accept property names')
        c.add_argument('--only', metavar='NAMES',
                       help='with --css: keep only these properties (comma-separated, wildcards allowed)')
        c.add_argument('--exclude', metavar='NAMES',
                       help='with --css: leave out these properties, e.g. "ink*,paper*"')
        c.add_argument('-s', '--space', default='oklch', choices=list(SPACES),
                       help='colour space for lightness, chroma and hue (default: oklch)')
        c.add_argument('-t', '--template', choices=list(TEMPLATES),
                       help='use this template instead of the best-fitting one')
        c.add_argument('-r', '--rotation', type=float,
                       help='fix the template rotation (centre of its first sector, degrees)')
        c.add_argument('-b', '--background',
                       help='background colour for WCAG 2 contrast ratios (a colour or, with --css, '
                            'a property name)')
        c.add_argument('--neutral-chroma', type=float,
                       help='chroma below which a colour counts as neutral (default depends on space)')
        c.add_argument('--robustness', metavar='SPACES', default=','.join(ROBUSTNESS_SPACES),
                       help='comma-separated colour spaces in which to refit the template and '
                            f'compare each verdict, or "none" (default: {",".join(ROBUSTNESS_SPACES)})')
        c.add_argument('--no-cvd', action='store_true',
                       help='skip the colour-vision-deficiency check')
        c.add_argument('--cvd-threshold', type=float,
                       help='colour difference below which a pair counts as close under simulated '
                            'dichromacy (default: 3 x the space\'s rough just-noticeable difference)')
        c.add_argument('--cvd-svg', metavar='PATH',
                       help='also write swatches under simulated dichromacy as SVG')
        c.add_argument('--svg', metavar='PATH', help='also write a hue-wheel figure as SVG')
        c.add_argument('--layout', default='wide', choices=('wide', 'narrow'),
                       help='SVG layout: wide (1180 px) or narrow (640 px, for a blog column)')
        c.add_argument('--title', help='title for the SVG figure')
        c.add_argument('--json', action='store_true', help='print the report as JSON')

    c = sub.add_parser('check', help='fit the hue templates to a palette and judge candidate colours',
                       description='Colours are CSS colours (hex, rgb(), hsl(), oklch(), names ...), '
                                   'optionally labelled: "gold=#f5e642".')
    common(c)
    c.add_argument('-c', '--candidate', action='append', default=[],
                   help='a candidate colour to judge against the palette (repeatable)')
    c.set_defaults(func=_cmd_check)

    g = sub.add_parser('suggest', help='suggest new colours inside the palette\'s template',
                       description='Suggest colours that sit inside the palette\'s harmonic template, '
                                   'in every space of the robustness check, and are as distinct as '
                                   'possible from the palette and from each other. Output includes '
                                   'CSS oklch() custom properties.')
    common(g)
    g.add_argument('-n', type=int, default=3, help='how many colours to suggest (default: 3)')
    g.add_argument('--min-contrast', type=float,
                   help='WCAG 2 contrast each suggestion must reach against --background')
    g.add_argument('--min-margin', type=float, default=5.0,
                   help='degrees inside the template, in the primary space (default: 5)')
    g.add_argument('--lightness', metavar='LO,HI',
                   help='OKLCH lightness range to search, 0-1 or percent (default: the palette\'s, widened)')
    g.add_argument('--chroma', metavar='LO,HI',
                   help='OKLCH chroma range to search (default: the palette\'s, widened)')
    g.add_argument('--prefix', default='new', help='name prefix of the suggestions (default: new)')
    g.add_argument('--cvd-safe', action='store_true',
                   help='keep each suggestion distinct from the palette under simulated dichromacy')
    g.set_defaults(func=_cmd_suggest)

    t = sub.add_parser('templates', help='list the hue templates')
    t.set_defaults(func=_cmd_templates)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as e:
        p.error(str(e))
        return 2


if __name__ == '__main__':
    sys.exit(main())
