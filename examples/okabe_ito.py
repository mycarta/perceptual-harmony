"""Worked example: the Okabe-Ito palette, built for distinction rather than harmony.

Okabe and Ito (2008) designed the palette so that categories stay distinct for readers with
colour-vision deficiencies. Wilke's Fundamentals of Data Visualization (2019) uses it throughout,
and it is the default of R's palette.colors() since R 4.0. The colours below are that default,
in R's order.

The second check is a real use of three of its colours: the map of Koppen-Geiger climate classes
in Sink and Brikowski (2025), Hydrol. Earth Syst. Sci. 29, 4015-4054, Fig. 2, with the blue of a
small tropical area as a candidate.

    python examples/okabe_ito.py

It writes two figures next to this file and a narrow one of the climate-map colours in blog/.
"""
from pathlib import Path

from perceptual_harmony import check, render_svg

OKABE_ITO = [            # R: palette.colors()
    'black=#000000', 'orange=#e69f00', 'sky blue=#56b4e9', 'bluish green=#009e73',
    'yellow=#f0e442', 'blue=#0072b2', 'vermillion=#d55e00', 'reddish purple=#cc79a7',
    'grey=#999999',
]
KOPPEN = ['arid=#d55e00', 'continental=#e69f00', 'temperate=#009e73']
TROPICAL = ['tropical=#0072b2']

here = Path(__file__).parent
full = check(OKABE_ITO, space='oklch', background='#ffffff')
print(full.to_text(), end='\n\n')
(here / 'okabe_ito_oklch.svg').write_text(
    render_svg(full, title=f'Okabe–Ito palette: closest is {full.chosen.template.name}, in OKLCH'))

koppen = check(KOPPEN, TROPICAL, space='oklch', background='#ffffff')
print(koppen.to_text())
(here / 'okabe_ito_koppen_oklch.svg').write_text(
    render_svg(koppen, title=f'Three Okabe–Ito colours on a climate map: '
                             f'{koppen.chosen.template.name} template in OKLCH'))
(here / 'blog' / 'koppen.svg').write_text(
    render_svg(koppen, title=f'Köppen–Geiger map colours: {koppen.chosen.template.name} template in OKLCH',
               layout='narrow'))
print('\nwrote okabe_ito_oklch.svg, okabe_ito_koppen_oklch.svg, blog/koppen.svg')
