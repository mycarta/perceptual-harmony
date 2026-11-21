"""Worked example: choosing one extra colour for the palette of the game Windmill.

Windmill's replay compass needed a colour for 8 added wind directions: clearly different from
the ocean blues already on screen, yet harmonious with them. This script fits the hue templates
to the palette and judges four candidates, in OKLCH and in CIELCh, and writes one figure per
space next to this file.

    python examples/windmill.py
"""
from pathlib import Path

from perceptual_harmony import check, render_svg

PALETTE = [
    'board blue=#30859e',   # board cell
    'pale label=#c5d9e8',   # pale label text
    'gold=#f5e642',         # current gust, turbine hub, title
    'hit red=#ef9a9a',      # hit marker
]
CANDIDATES = [
    'cyan=#60ccdb',         # first draft: too close to the blues
    'periwinkle=#94a0f0',   # the colour Windmill uses
    'sea green=#61d1ac',
    'amber=#f0ac4c',
]
BACKGROUND = '#1a2e3d'      # the compass background

here = Path(__file__).parent
for space in ('oklch', 'cielch'):
    report = check(PALETTE, CANDIDATES, space=space, background=BACKGROUND)
    print(report.to_text(), end='\n\n')
    out = here / f'windmill_{space}.svg'
    out.write_text(render_svg(report, title=f'Windmill palette: {report.chosen.template.name} '
                                            f'template in {report.space.label}'))
    print('wrote', out, end='\n\n')
