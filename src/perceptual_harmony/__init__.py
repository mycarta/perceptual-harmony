"""Hue harmony in perceptual colour spaces.

Fits the harmonic hue templates of Cohen-Or et al. (2006) to a palette, with hue, lightness and
chroma measured in OKLCH, CIELCh or CAM02-UCS, and reports distinctness and contrast.
"""
__version__ = '0.1.0.dev0'

from .check import (ColormapReport, ColourInfo, Report, SpaceFit, check, check_colormap,
                    contrast_ratio)
from .css import css_colours, custom_properties, parse_colour
from .colour import ROBUSTNESS_SPACES, SPACES, Space, get_space, parse_hex, to_hex
from .harmony import TEMPLATES, Fit, Template, fit_all, fit_template, get_template, margin
from .suggest import Suggestion, css_block, suggest
from .svg import render_colormap_svg, render_svg

__all__ = ['check', 'check_colormap', 'suggest', 'css_block', 'Suggestion', 'contrast_ratio', 'render_svg', 'render_colormap_svg', 'fit_all', 'fit_template', 'margin',
           'get_space', 'get_template', 'parse_hex', 'parse_colour', 'css_colours', 'custom_properties',
           'to_hex', 'SPACES', 'TEMPLATES',
           'ROBUSTNESS_SPACES', 'ColourInfo', 'ColormapReport', 'Report', 'SpaceFit', 'Fit', 'Space',
           'Template', '__version__']
