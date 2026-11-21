"""Command-line interface: `perceptual-harmony check ...` and `perceptual-harmony templates`."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .check import check
from .colour import SPACES
from .harmony import TEMPLATES


def _cmd_check(args) -> int:
    report = check(args.colours, args.candidate, space=args.space, template=args.template,
                   rotation=args.rotation, background=args.background,
                   neutral_chroma=args.neutral_chroma)
    print(report.to_json() if args.json else report.to_text())
    if args.svg:
        from .svg import render_svg
        with open(args.svg, 'w', encoding='utf-8') as f:
            f.write(render_svg(report, title=args.title or ''))
        if not args.json:
            print(f'\nwrote {args.svg}')
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

    c = sub.add_parser('check', help='fit the hue templates to a palette and judge candidate colours',
                       description='Colours are hex codes, optionally labelled: "gold=#f5e642".')
    c.add_argument('colours', nargs='+', help='palette colours')
    c.add_argument('-c', '--candidate', action='append', default=[],
                   help='a candidate colour to judge against the palette (repeatable)')
    c.add_argument('-s', '--space', default='oklch', choices=list(SPACES),
                   help='colour space for lightness, chroma and hue (default: oklch)')
    c.add_argument('-t', '--template', choices=list(TEMPLATES),
                   help='judge against this template instead of the best-fitting one')
    c.add_argument('-r', '--rotation', type=float,
                   help='fix the template rotation (centre of its first sector, degrees)')
    c.add_argument('-b', '--background', help='background colour for WCAG 2 contrast ratios')
    c.add_argument('--neutral-chroma', type=float,
                   help='chroma below which a colour counts as neutral (default depends on space)')
    c.add_argument('--svg', metavar='PATH', help='also write a hue-wheel figure as SVG')
    c.add_argument('--title', help='title for the SVG figure')
    c.add_argument('--json', action='store_true', help='print the report as JSON')
    c.set_defaults(func=_cmd_check)

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
