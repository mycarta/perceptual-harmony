import json
import math
import random
import xml.etree.ElementTree as ET

import pytest

from perceptual_harmony import (SPACES, TEMPLATES, check, contrast_ratio, fit_template,
                                get_space, lightness_difference, margin, parse_hex, render_svg, to_hex)
from perceptual_harmony.cli import main
from perceptual_harmony.harmony import _evaluate, angle_diff

ORIGINAL_SPACES = ('oklch', 'cielch', 'cam02ucs')   # the spaces the worked examples describe
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


def test_cam16ucs_and_ipt_reference_values():
    # reference values from colour-science 0.4.4 (sRGB, D65, its default viewing conditions)
    assert SPACES['cam16ucs'].to_lab((1, 0, 0)) == pytest.approx((59.1742, 40.8297, 21.1556), abs=0.02)
    assert SPACES['cam16ucs'].to_lab((0.2, 0.5, 0.8)) == pytest.approx((54.5312, -6.5933, -25.9991), abs=0.02)
    assert SPACES['ipt'].to_lab((1, 0, 0)) == pytest.approx((0.45611, 0.6211, 0.44291), abs=5e-4)
    assert SPACES['ipt'].to_lab((0.2, 0.5, 0.8)) == pytest.approx((0.55489, -0.143, -0.33058), abs=5e-4)


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
@pytest.mark.parametrize('space', ORIGINAL_SPACES)
def test_windmill_palette_fits_x(space):
    report = check(WINDMILL, space=space)
    assert report.chosen.template.name == 'X' and report.chosen.fits


LUNENBURG = ['#4e7fcc', '#6b9be8', '#85bd5a', '#639326', '#6d366d', '#b998dd']


@pytest.mark.parametrize('space', ORIGINAL_SPACES)
def test_lunenburg_palette_is_harmonious(space):
    report = check(LUNENBURG, space=space)
    assert report.chosen.fits
    assert next(f for f in report.fits if f.template.name == 'X').fits


def test_harmony_depends_on_colour_space():
    """Periwinkle is inside Windmill's X template in OKLCH and CAM02-UCS, just outside in CIELCh."""
    margins = {sp: check(WINDMILL, ['#94a0f0'], space=sp).candidates[0].margin
               for sp in ORIGINAL_SPACES}
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


def test_robustness_flags_periwinkle_as_borderline():
    report = check(WINDMILL, ['periwinkle=#94a0f0', 'sea green=#61d1ac', 'amber=#f0ac4c'])
    assert [r.space.name for r in report.robustness] == ['oklch', 'cielch', 'cam16ucs', 'ipt']
    assert report.fits_in == 4
    peri, sea, amber = report.candidates
    assert peri.robustness == 'borderline' and peri.inside_count == 3
    assert sea.robustness == 'outside' and amber.robustness == 'inside'
    assert peri.margins_by_space['oklch'] == pytest.approx(peri.margin)
    assert 'Borderline' in report.to_text()


def test_robustness_can_be_skipped_and_primary_comes_first():
    assert check(WINDMILL, robustness_spaces=()).robustness == []
    report = check(WINDMILL, space='cam02ucs', robustness_spaces=['oklch'])
    assert [r.space.name for r in report.robustness] == ['cam02ucs', 'oklch']


def test_background_contrast_and_nearest():
    report = check(WINDMILL, ['#94a0f0'], background='#1a2e3d')
    c = report.candidates[0]
    assert c.contrast == pytest.approx(contrast_ratio(parse_hex('#94a0f0'), parse_hex('#1a2e3d')))
    assert c.nearest in {p.label for p in report.palette}



def test_lightness_difference_is_signed_cie_lstar():
    # reference L* values from colour-science (sRGB, D65)
    light, dark = parse_hex('#94a0f0'), parse_hex('#1a2e3d')
    assert lightness_difference(light, dark) == pytest.approx(67.8202 - 17.9661, abs=0.01)
    assert lightness_difference(dark, light) == pytest.approx(-lightness_difference(light, dark))
    assert lightness_difference(parse_hex('#777777'), (1, 1, 1)) == pytest.approx(50.034 - 100, abs=0.01)
    report = check(WINDMILL, ['#94a0f0'], background='#1a2e3d', robustness_spaces=())
    c = report.candidates[0]
    assert c.lightness_diff == pytest.approx(lightness_difference(light, dark))
    assert report.to_dict()['candidates'][0]['lightness_diff'] == pytest.approx(49.85, abs=0.01)
    assert 'dL*' in report.to_text()
    # without a background, neither measure is reported
    assert check(WINDMILL, robustness_spaces=()).palette[0].lightness_diff is None

# ---- CSS --------------------------------------------------------------------------------------
@pytest.mark.parametrize('value', ['#4e7fcc', '#4E7FCC80', 'rgb(78 127 204)', 'rgb(78, 127, 204, .5)',
                                   'rgba(78,127,204,0.2)', 'oklch(59.8% 0.1302 259.1)',
                                   'oklch(0.598 0.1302 259.1 / 40%)', 'oklab(0.598 -0.0247 -0.1278)'])
def test_css_colour_syntaxes(value):
    from perceptual_harmony import parse_colour
    r, g, b = parse_hex(parse_colour(value))
    assert (r, g, b) == pytest.approx(parse_hex('#4e7fcc'), abs=1.5 / 255)


def test_css_named_hsl_hwb_lab():
    from perceptual_harmony import parse_colour
    assert parse_colour('RebeccaPurple') == '#663399'
    assert parse_colour('hsl(120 100% 25%)') == '#008000'
    assert parse_colour('hsl(0.5turn, 100%, 50%)') == '#00ffff'
    assert parse_colour('hwb(0 0% 0%)') == '#ff0000'
    assert parse_colour('lab(100 0 0)') == '#ffffff'
    with pytest.raises(ValueError):
        parse_colour('color-mix(in oklch, red, blue)')


CSS = '''
:root {
  /* palette */
  --sky: #4E7FCC; --leaf: rgb(133 189 90);
  --accent: var(--sky);
  --missing: var(--nope, oklch(70% 0.1 30));
  --ink: #1b2024;
  --font: "Lora", serif; --radius: 10px;
  --shadow: 0 1px 2px rgba(0, 0, 0, .1);
}
@media (prefers-color-scheme: dark) { :root { --sky: #000080; } }
'''


def test_css_custom_properties():
    from perceptual_harmony import css_colours
    found, notes = css_colours(CSS)
    names = [n for n, _ in found]
    assert names == ['sky', 'leaf', 'accent', 'missing', 'ink']    # fonts, lengths, shadows skipped
    assert dict(found)['sky'] == '#4e7fcc' == dict(found)['accent']  # first definition wins; var() resolved
    assert [n for n, _ in css_colours(CSS, exclude=['ink', '--miss*'])[0]] == ['sky', 'leaf', 'accent']
    assert [n for n, _ in css_colours(CSS, only=['s*', 'leaf'])[0]] == ['sky', 'leaf']
    assert 'clipped' in css_colours(':root { --x: oklch(70% 0.4 150); }')[1][0]


def test_cli_css(tmp_path, capsys):
    f = tmp_path / 'style.css'
    f.write_text(CSS)
    assert main(['check', '--css', str(f), '--exclude', 'ink,accent,missing', '-b', 'ink',
                 '-c', 'leaf', '-c', 'x=tomato', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert [c['label'] for c in data['palette']] == ['sky', 'leaf']
    assert [c['label'] for c in data['candidates']] == ['leaf', 'x']
    assert data['background'] == '#1b2024'
    with pytest.raises(SystemExit):
        main(['check'])                     # no colours at all


# ---- colour-vision deficiency ---------------------------------------------------------------
def test_cvd_simulation_matches_colorspacious():
    cs = pytest.importorskip('colorspacious')
    np = pytest.importorskip('numpy')
    from perceptual_harmony.colour import srgb_to_linear
    from perceptual_harmony.cvd import MACHADO_2009
    names = {'protanopia': 'protanomaly', 'deuteranopia': 'deuteranomaly', 'tritanopia': 'tritanomaly'}
    rng = random.Random(5)
    for kind, m in MACHADO_2009.items():
        for _ in range(50):
            rgb = tuple(rng.random() for _ in range(3))
            lin = srgb_to_linear(rgb)
            ours = [sum(m[i][j] * lin[j] for j in range(3)) for i in range(3)]
            ref = cs.cspace_convert(np.array(rgb), {'name': 'sRGB1+CVD', 'cvd_type': names[kind],
                                                    'severity': 100}, 'sRGB1-linear')
            assert ours == pytest.approx(list(ref), abs=1e-9)


def test_cvd_close_pairs():
    lun = check(LUNENBURG, robustness_spaces=())
    prot = lun.cvd['protanopia'][0]
    assert {prot.a, prot.b} == {'#6b9be8', '#b998dd'} and prot.delta_e < lun.cvd_threshold < prot.normal
    oi = check(OKABE_ITO[1:8], robustness_spaces=())          # the seven hues
    assert all(pairs[0].delta_e > oi.cvd_threshold for pairs in oi.cvd.values())
    assert 'Colour-vision deficiency' in lun.to_text()
    assert check(LUNENBURG, robustness_spaces=(), cvd=False).cvd == {}


def test_cvd_svg_and_cli(tmp_path, capsys):
    from perceptual_harmony import render_cvd_svg
    ET.fromstring(render_cvd_svg(check(WINDMILL + ['a & b=#000000'], ['#94a0f0'])))
    out = tmp_path / 'cvd.svg'
    assert main(['check', *WINDMILL, '--cvd-svg', str(out), '--robustness', 'none']) == 0
    assert out.read_text().startswith('<svg')
    capsys.readouterr()
    assert main(['check', *WINDMILL, '--no-cvd', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['cvd'] == {}


def test_cvd_safe_suggestions():
    from perceptual_harmony import simulate, suggest, SPACES as SP
    report, found = suggest(LUNENBURG, n=1, cvd_safe=True)
    new = parse_hex(found[0].hex)
    for kind in ('protanopia', 'deuteranopia', 'tritanopia'):
        for c in report.palette:
            assert SP['oklch'].delta_e(simulate(new, kind), simulate(c.rgb, kind)) >= 0.06


# ---- suggestions ------------------------------------------------------------------------------
def test_suggestions_are_inside_distinct_and_meet_contrast():
    from perceptual_harmony import suggest
    report, found = suggest(WINDMILL, n=2, background='#1a2e3d', min_contrast=4.5)
    assert len(found) == 2 and len(report.candidates) == 2
    for c, s in zip(report.candidates, found):
        assert c.hex == s.hex and c.robustness == 'inside' and c.margin >= 5
        assert c.contrast >= 4.5
        assert s.css.startswith('oklch(') and parse_colour_ok(s.css) == s.hex
    assert found[0].distance >= found[1].distance > 0.05    # greedy: farthest first


def parse_colour_ok(css):
    from perceptual_harmony import parse_colour
    return parse_colour(css)


def test_suggest_reports_when_nothing_fits():
    from perceptual_harmony import suggest
    report, found = suggest(WINDMILL, n=1, background='#ffffff', min_contrast=21)
    assert found == [] and any('no other colour' in n for n in report.notes)


def test_cli_suggest(capsys):
    assert main(['suggest', *WINDMILL, '-n', '1', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data['suggestions']) == 1 and data['suggestions'][0]['css'].startswith('oklch(')
    assert main(['suggest', *WINDMILL, '-n', '1', '--lightness', '60,80']) == 0
    assert '--new-1: oklch(' in capsys.readouterr().out


# ---- web page ---------------------------------------------------------------------------------
def test_web_bundle_is_current():
    """docs/perceptual_harmony.json must match the source; run python docs/build_bundle.py."""
    import runpy
    from pathlib import Path
    root = Path(__file__).parent.parent
    build = runpy.run_path(str(root / 'docs' / 'build_bundle.py'))
    assert (root / 'docs' / 'perceptual_harmony.json').read_text(encoding='utf-8') == build['bundle']()


# ---- outputs ----------------------------------------------------------------------------------
def test_svg_is_well_formed():
    report = check(WINDMILL + ['a & b=#000000'], ['#94a0f0'], background='#1a2e3d')
    ET.fromstring(render_svg(report))


def test_narrow_layout():
    report = check(WINDMILL, ['#94a0f0'], background='#1a2e3d')
    root = ET.fromstring(render_svg(report, layout='narrow'))
    assert root.get('width') == '640'
    with pytest.raises(ValueError):
        render_svg(report, layout='tall')


DANDELIONS = ['#5a9e30', '#246e24', '#9fcc6a', '#f5e642', '#4a2c00']


def test_dandelions_board_fits_v_in_every_space():
    report = check(DANDELIONS, ['#ef9a9a'])
    assert report.chosen.template.name == 'V' and report.fits_in == 4
    assert report.candidates[0].robustness == 'outside'


OKABE_ITO = ['#000000', '#e69f00', '#56b4e9', '#009e73', '#f0e442', '#0072b2', '#d55e00', '#cc79a7',
             '#999999']


def test_okabe_ito_fits_no_template_but_its_koppen_subset_does():
    full = check(OKABE_ITO)
    assert full.fits_in == 0 and not any(f.fits for f in full.fits[:1])
    koppen = check(['#d55e00', '#e69f00', '#009e73'], ['#0072b2'])
    assert koppen.chosen.template.name == 'T' and koppen.fits_in == 4
    assert koppen.candidates[0].robustness == 'outside'


def test_cli_json(capsys):
    assert main(['check', *WINDMILL, '-c', 'periwinkle=#94a0f0', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['chosen']['template'] == 'X'
    assert data['candidates'][0]['label'] == 'periwinkle'


def test_cli_robustness_option(capsys):
    assert main(['check', *WINDMILL, '--robustness', 'none', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['robustness'] == []
    assert main(['check', *WINDMILL, '--robustness', 'cielch,ipt', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert [r['space'] for r in data['robustness']] == ['oklch', 'cielch', 'ipt']
    with pytest.raises(SystemExit):
        main(['check', *WINDMILL, '--robustness', 'hsl'])


def test_cli_text_and_svg(tmp_path, capsys):
    out = tmp_path / 'w.svg'
    assert main(['check', *WINDMILL, '-s', 'cam02ucs', '--svg', str(out)]) == 0
    assert 'CAM02-UCS' in capsys.readouterr().out
    assert out.read_text().startswith('<svg')


# ---- colormaps --------------------------------------------------------------------------------
def _cubeyf(name='cubeyf'):
    from pathlib import Path
    path = Path(__file__).parent.parent / 'examples' / 'data' / f'{name}.csv'
    rows = [l for l in path.read_text().splitlines() if l and not l.startswith('#')][1:]
    return [tuple(float(v) for v in r.split(',')) for r in rows]


def test_cubeyf_is_close_to_a_t_template():
    """Niccoli (2013): cubeYF 'looks very close to a T template', 'exceeding a bit 180 degrees'."""
    from perceptual_harmony import check_colormap
    for space in ('oklch', 'cam02ucs'):
        r = check_colormap(_cubeyf(), 'cubeYF', space, robustness_spaces=())
        assert r.chosen.template.name == 'T' and r.chosen.cost < 2
        assert 180 < r.hue_span < 215
        assert r.lightness_reversal < r.space.jnd       # monotonic to within a fraction of a JND


def test_cube1_trades_lightness_for_hue_range():
    """Niccoli (2013): cube1 adds a red-like colour at the high-lightness end, at the cost of a
    modest deviation from perceptual: wider hues than cubeYF, lightness falling after a peak."""
    from perceptual_harmony import check_colormap
    r = check_colormap(_cubeyf('cube1'), 'cube1', 'cielch', robustness_spaces=())
    assert r.chosen.template.name == 'X'
    assert 250 < r.hue_span < 290
    assert 10 < r.lightness_reversal < 25
    assert 'peak' in r.lightness_range_text()


def test_colormap_robustness():
    from perceptual_harmony import check_colormap
    r = check_colormap(_cubeyf(), 'cubeYF', template='T')
    assert [x.space.name for x in r.robustness] == ['cielch', 'cam16ucs', 'ipt']
    assert all(x.chosen.template.name == 'T' and 195 < x.hue_span < 215 for x in r.robustness)
    assert check_colormap(_cubeyf(), robustness_spaces=()).robustness == []


def test_jet_lightness_is_not_monotonic():
    from perceptual_harmony import check_colormap
    jet = [(0, 0, 0.5), (0, 0, 1), (0, 1, 1), (1, 1, 0), (1, 0, 0), (0.5, 0, 0)]
    r = check_colormap(jet, 'jet-ish', 'oklch', robustness_spaces=())
    assert r.lightness_reversal > 0.3


def test_colormap_svg_is_well_formed():
    from perceptual_harmony import check_colormap, render_colormap_svg
    r = check_colormap(_cubeyf(), 'cubeYF', template='T')
    ET.fromstring(render_colormap_svg(r))
    assert ET.fromstring(render_colormap_svg(r, layout='narrow')).get('width') == '640'
