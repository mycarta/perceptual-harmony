"""Worked example: the board colours of the game Dandelions.

Dandelions (https://github.com/mycarta/Dandelions) is a meadow game: the board cells are three
greens (empty, flower, seed) and the symbols on them are a gold flower and a brown seed. The
colours are taken from the game's style sheet. The pink of the "Wind wins" message is judged as
a candidate: an alert colour that is meant to stand apart.

This script writes a wide figure next to this file and a narrow one in blog/.

    python examples/dandelions.py
"""
from pathlib import Path

from perceptual_harmony import check, render_svg

PALETTE = [
    'empty cell=#5a9e30',
    'flower cell=#246e24',
    'seed cell=#9fcc6a',
    'flower=#f5e642',       # flower symbol, on the flower cell
    'seed=#4a2c00',         # seed symbol, on the seed cell
]
CANDIDATES = ['Wind wins=#ef9a9a']   # status message when the Wind wins

here = Path(__file__).parent
report = check(PALETTE, CANDIDATES, space='oklch')
print(report.to_text())
title = f'Dandelions board: {report.chosen.template.name} template in {report.space.label}'
for out, layout in ((here / 'dandelions_oklch.svg', 'wide'), (here / 'blog' / 'dandelions.svg', 'narrow')):
    out.write_text(render_svg(report, title=title, layout=layout))
    print('wrote', out)
