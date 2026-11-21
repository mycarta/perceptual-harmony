"""Worked example: the event palette of lunenburg.fingerpost.ca.

The site's colours were picked from a watercolour of a Lunenburg house, which is the page
banner: two blues from the sky, two greens from the clapboard and a magenta and a lavender from
the tower. This script checks that the picked palette is harmonious and writes a figure next to
this file (and a narrow one in blog/). The colours are read from the CSS custom properties of the
site's style sheet, as the command line does with --css.

    python examples/lunenburg.py
"""
from pathlib import Path

from perceptual_harmony import (check, css_colours, custom_properties, parse_colour, render_cvd_svg,
                                render_svg)

# data/lunenburg.css is the :root block of the site's style sheet. The colour roles:
#   sky-blue    music badges, links, header      sky-light  header gradient
#   green       festival badges, card edge       green-dark social and community badges
#   magenta     theatre and dance badges         lavender   arts badges
# ink* and paper* are the neutrals of text and background, left out of the palette.
here = Path(__file__).parent
css = (here / 'data' / 'lunenburg.css').read_text()
palette, notes = css_colours(css, exclude=['ink*', 'paper*'])
background = parse_colour(custom_properties(css)['paper'])     # warm watercolour paper

report = check([f'{name}={hx}' for name, hx in palette], space='oklch', background=background)
print(report.to_text())
title = f'Lunenburg event palette: {report.chosen.template.name} template in {report.space.label}'
for out, layout in ((here / 'lunenburg_oklch.svg', 'wide'), (here / 'blog' / 'lunenburg.svg', 'narrow')):
    out.write_text(render_svg(report, title=title, layout=layout))
    print('wrote', out)
out = here / 'lunenburg_cvd.svg'
out.write_text(render_cvd_svg(report, title='Lunenburg event palette, simulated dichromacy'))
print('wrote', out)
