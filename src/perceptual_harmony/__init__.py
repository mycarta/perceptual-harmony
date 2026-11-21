"""Hue harmony in perceptual colour spaces.

Fits the harmonic hue templates of Cohen-Or et al. (2006) to a palette, with hue, lightness and
chroma measured in OKLCH, CIELCh or CAM02-UCS, and reports distinctness and contrast.
"""
__version__ = '0.1.0.dev0'

from .check import ColourInfo, Report, check, contrast_ratio
from .colour import SPACES, Space, get_space, parse_hex, to_hex
from .harmony import TEMPLATES, Fit, Template, fit_all, fit_template, get_template, margin
from .svg import render_svg

__all__ = ['check', 'contrast_ratio', 'render_svg', 'fit_all', 'fit_template', 'margin',
           'get_space', 'get_template', 'parse_hex', 'to_hex', 'SPACES', 'TEMPLATES',
           'ColourInfo', 'Report', 'Fit', 'Space', 'Template', '__version__']
