import json
import math
import random
import xml.etree.ElementTree as ET

import pytest

from perceptual_harmony import (SPACES, TEMPLATES, check, contrast_ratio, fit_template,
                                get_space, margin, parse_hex, render_svg, to_hex)
from perceptual_harmony.cli import main
from perceptual_harmony.harmony import _evaluate, angle_diff

WINDMILL = ['board blue=#30859e', 'pale label=#c5d9e8', 'gold=#f5e642', 'hit red=#ef9a9a']


# ---- colour conversions ------------------------------------------------------------------------
def test_parse_hex():
    assert parse_hex('#ffffff') == (1.0, 1.0, 1.0)
    assert parse_hex('38a') == parse_hex('#3388aa')
    assert to_hex(parse_hex('#30859E')) == '#30859e'
    with pytest.raises(ValueError):
        parse_hex('#12345')


def test_oklab_reference_values():
    L, a, b = SPACES['oklch'].to_lab(parse_hex('#ffffff'))
    assert L == pytest.approx(1.0, abs=1e-6) and abs(a) < 1e-6 and abs(b) < 1e-6
    # Ottosson's published value for sRGB red
    assert SPACES['oklch'].to_lab((1, 0, 0)) == pytest.approx((0.62796, 0.22486, 0.12585), abs=2e-4)


def test_cielab_reference_values():
    assert SPACES['cielch'].to_lab((1, 0, 0)) == pytest.approx((53.24, 80.09, 67.20), abs=0.02)


@pytest.mark.parametrize('name', list(SPACES))
def test_round_trip(name):
    sp = SPACES[name]
    rng = random.Random(0)
    for _ in range(300):
        rgb = tuple(rng.random() for _ in range(3))
        assert sp.from_lab(sp.to_lab(rgb)) == pytest.approx(rgb, abs=1e-6)


def test_cam02ucs_matches_colorspacious():
    cs = pytest.importorskip('colorspacious')
    np = pytest.importorskip('numpy')
    rng = random.Random(1)
    for _ in range(300):
        rgb = tuple(rng.random() for _ in range(3))
        ref = cs.cspace_convert(np.array(rgb), 'sRGB1', 'CAM02-UCS')
        # small residual from slightly different sRGB matrices
        assert SPACES['cam02ucs'].to_lab(rgb) == pytest.approx(tuple(ref), abs=0.02)


def test_contrast_ratio():
    assert contrast_ratio((0, 0, 0), (1, 1, 1)) == pytest.approx(21.0)
    assert contrast_ratio((1, 1, 1), (1, 1, 1)) == pytest.approx(1.0)
    assert contrast_ratio(parse_hex('#777777'), (1, 1, 1)) == pytest.approx(4.48, abs=0.01)


# ---- templates and fitting --------------------------------------------------------------------
def test_angle_diff():
    assert angle_diff(10, 350) == pytest.approx(20)
    assert angle_diff(350, 10) == pytest.approx(-20)


def test_margin():
    X = TEMPLATES['X']
    m, sector = margin(200, X, 200)
    assert m == pytest.approx(46.8) and sector == 0
    m, sector = margin(20, X, 200)
    assert m == pytest.approx(46.8) and sector == 1
    m, _ = margin(290, X, 200)          # 90 degrees from both centres: outside by 43.2
    assert m == pytest.approx(-43.2)


def test_narrow_cluster_fits_i_and_is_centred():
    fit = fit_template([100, 105, 110], [1, 1, 1], 'i')
    assert fit.fits
    assert fit.rotation == pytest.approx(105, abs=0.25)


@pytest.mark.parametrize('tname', list(TEMPLATES))
def test_fit_is_global_minimum(tname):
    """The breakpoint search must never be beaten by a fine brute-force scan."""
    rng = random.Random(hash(tname) % 1000)
    for _ in range(20):
        n = rng.randint(2, 7)
        hues = [rng.uniform(0, 360) for _ in range(n)]
        weights = [rng.uniform(0.1, 1) for _ in range(n)]
        fit = fit_template(hues, weights, tname)
        brute = min(_evaluate(hues, weights, TEMPLATES[tname], r / 20)[0] for r in range(7200))
        assert fit.cost <= brute + 1e-9


# ---- check ------------------------------------------------------------------------------------
@pytest.mark.parametrize('space', list(SPACES))
def test_windmill_palette_fits_x(space):
    report = check(WINDMILL, space=space)
    assert report.chosen.template.name == 'X' and report.chosen.fits


LUNENBURG = ['#4e7fcc', '#6b9be8', '#85bd5a', '#639326', '#6d366d', '#b998dd']


@pytest.mark.parametrize('space', list(SPACES))
def test_lunenburg_palette_is_harmonious(space):
    report = check(LUNENBURG, space=space)
    assert report.chosen.fits
    assert next(f for f in report.fits if f.template.name == 'X').fits


def test_harmony_depends_on_colour_space():
    """Periwinkle is inside Windmill's X template in OKLCH and CAM02-UCS, just outside in CIELCh."""
    margins = {sp: check(WINDMILL, ['#94a0f0'], space=sp).candidates[0].margin for sp in SPACES}
    assert margins['oklch'] > 5 and margins['cam02ucs'] > 5
    assert -5 < margins['cielch'] < 0


def test_neutrals_are_ignored_by_the_fit():
    report = check(['#ff0000', '#808080', '#ffffff'])
    assert [c.neutral for c in report.palette] == [False, True, True]
    assert all(f.fits for f in report.fits)        # one chromatic colour fits anything
    assert any('Neutral' in n for n in report.notes)


def test_fixed_template_and_rotation():
    report = check(WINDMILL, template='I', rotation=0)
    assert report.chosen.template.name == 'I' and report.chosen.rotation == 0
    assert not report.chosen.fits


def test_unknown_space_and_template():
    with pytest.raises(ValueError):
        get_space('hsl')
    with pytest.raises(ValueError):
        check(WINDMILL, template='Z')


def test_background_contrast_and_nearest():
    report = check(WINDMILL, ['#94a0f0'], background='#1a2e3d')
    c = report.candidates[0]
    assert c.contrast == pytest.approx(contrast_ratio(parse_hex('#94a0f0'), parse_hex('#1a2e3d')))
    assert c.nearest in {p.label for p in report.palette}


# ---- outputs ----------------------------------------------------------------------------------
def test_svg_is_well_formed():
    report = check(WINDMILL + ['a & b=#000000'], ['#94a0f0'], background='#1a2e3d')
    ET.fromstring(render_svg(report))


def test_cli_json(capsys):
    assert main(['check', *WINDMILL, '-c', 'periwinkle=#94a0f0', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['chosen']['template'] == 'X'
    assert data['candidates'][0]['label'] == 'periwinkle'


def test_cli_text_and_svg(tmp_path, capsys):
    out = tmp_path / 'w.svg'
    assert main(['check', *WINDMILL, '-s', 'cam02ucs', '--svg', str(out)]) == 0
    assert 'CAM02-UCS' in capsys.readouterr().out
    assert out.read_text().startswith('<svg')
