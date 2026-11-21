"""Worked example: the hue spread of the cubeYF and cube1 colormaps, and of jet.

cubeYF is a perceptual rainbow colormap by Matteo Niccoli (MyCarta, 2013), built in CIELAB with a
monotonic lightness profile. In the 2013 post that presented it, the hue spread was judged by eye
against the Cohen-Or templates: it "looks very close to a T template rotated by 180 degrees",
"also exceeding a bit 180 degrees". This script measures that, in three colour spaces, and
compares cube1, offered in the same post as an alternative with a red-like colour added at the
high-lightness end, and jet, which the post also placed in a T template. The post also showed an
industry spectrum colormap; matplotlib's nipy_spectral, a similar spectrum, stands in for it. It
is also the spectral colormap analysed in Niccoli (2014), The Leading Edge 33(8), 910-912.

Harmony is a secondary property of a colormap; lightness is the first. So each figure shows the
lightness profile next to the hue wheel.

    python examples/cubeyf.py

The cubeYF and cube1 samples in data/cubeyf.csv and data/cube1.csv are reused with permission;
credit Matteo Niccoli and mycartablog.com.
"""
from pathlib import Path

from perceptual_harmony import check_colormap, render_colormap_svg

here = Path(__file__).parent


def load_csv(path):
    rows = [line for line in path.read_text().splitlines() if line and not line.startswith('#')]
    return [tuple(float(v) for v in row.split(',')) for row in rows[1:]]


# matplotlib's jet, from its segment data (no matplotlib needed)
JET = {'red': ((0., 0, 0), (0.35, 0, 0), (0.66, 1, 1), (0.89, 1, 1), (1, 0.5, 0.5)),
       'green': ((0., 0, 0), (0.125, 0, 0), (0.375, 1, 1), (0.64, 1, 1), (0.91, 0, 0), (1, 0, 0)),
       'blue': ((0., 0.5, 0.5), (0.11, 1, 1), (0.34, 1, 1), (0.65, 0, 0), (1, 0, 0))}


# matplotlib's nipy_spectral (called "spectral" before matplotlib 2.0), from its segment data:
# 21 evenly spaced knots, values listed per channel
_KNOTS = [i / 20 for i in range(21)]
_NS = {'red': (0, .4667, .5333, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, .7333, .9333, 1, 1, 1, .8667, .8, .8),
       'green': (0, 0, 0, 0, 0, .4667, .6, .6667, .6667, .6, .7333, .8667, 1, 1, .9333, .8, .6, 0, 0, 0,
                 .8),
       'blue': (0, .5333, .6, .6667, .8667, .8667, .8667, .6667, .5333, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                .8)}
NIPY_SPECTRAL = {c: tuple((x, v, v) for x, v in zip(_KNOTS, vals)) for c, vals in _NS.items()}


def from_segments(data, n=256):
    """Sample a matplotlib-style segment-data colormap at n points (no matplotlib needed)."""
    def interp(seg, x):
        for (x0, _, y0), (x1, y1, _) in zip(seg, seg[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return [tuple(interp(data[c], i / (n - 1)) for c in ('red', 'green', 'blue')) for i in range(n)]


def jet(n=256):
    return from_segments(JET, n)


cubeyf = load_csv(here / 'data' / 'cubeyf.csv')
cube1 = load_csv(here / 'data' / 'cube1.csv')
spectral = from_segments(NIPY_SPECTRAL)

for space in ('oklch', 'cielch', 'cam02ucs'):
    print(check_colormap(cubeyf, 'cubeYF', space).to_text(), end='\n\n')
for space in ('oklch', 'cielch'):
    print(check_colormap(cube1, 'cube1', space).to_text(), end='\n\n')
print(check_colormap(jet(), 'jet', 'oklch').to_text(), end='\n\n')
print(check_colormap(spectral, 'nipy_spectral', 'oklch').to_text(), end='\n\n')

for name, samples in (('cubeYF', cubeyf), ('cube1', cube1), ('nipy_spectral', spectral)):
    report = check_colormap(samples, name, 'oklch', template='T')
    out = here / f'{name.lower()}_oklch.svg'
    out.write_text(render_colormap_svg(report, title=f'{name}: T template in OKLCH'))
    print('wrote', out)

report = check_colormap(cubeyf, 'cubeYF', 'oklch', template='T')
out = here / 'blog' / 'cubeyf.svg'
out.write_text(render_colormap_svg(report, title='cubeYF: T template in OKLCH', layout='narrow'))
print('wrote', out)
