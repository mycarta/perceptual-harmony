"""Worked example: the event palette of lunenburg.fingerpost.ca.

The site's colours were picked from a watercolour of a Lunenburg house, which is the page
banner: two blues from the sky, two greens from the clapboard and a magenta and a lavender from
the tower. This script checks that the picked palette is harmonious and writes a figure next to
this file. The colours are the CSS custom properties of the site's style sheet.

    python examples/lunenburg.py
"""
from pathlib import Path

from perceptual_harmony import check, render_svg

PALETTE = [
    'sky-blue=#4e7fcc',     # music badges, links, header
    'sky-light=#6b9be8',    # header gradient
    'green=#85bd5a',        # festival badges, card edge
    'green-dark=#639326',   # social and community badges
    'magenta=#6d366d',      # theatre and dance badges
    'lavender=#b998dd',     # arts badges
]
BACKGROUND = '#faf8f5'      # warm watercolour paper

here = Path(__file__).parent
report = check(PALETTE, space='oklch', background=BACKGROUND)
print(report.to_text())
out = here / 'lunenburg_oklch.svg'
out.write_text(render_svg(report, title=f'Lunenburg event palette: {report.chosen.template.name} '
                                        f'template in {report.space.label}'))
print('\nwrote', out)
