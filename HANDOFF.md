# perceptual-harmony: handoff brief

Started 2026-11-19 as a spin-off of Matteo's Windmill game
(`~/Documents/GitHub/windmill`). Nothing here is decided beyond the name.
The first session should read this, then **ask Matteo** about every open
question below before writing any code.

## Where the idea came from

While choosing Windmill's palette, one compass colour (the 8 extra wind
directions shown in a replay) needed to be clearly different from the existing
ocean blues and still sit well with them. Claude checked candidates against the
hue templates in:

> Daniel Cohen-Or, Olga Sorkine, Ran Gal, Tommer Leyvand, Ying-Qing Xu.
> *Color Harmonization.* ACM SIGGRAPH 2006.
> https://igl.ethz.ch/projects/color-harmonization/harmonization.pdf

The paper, building on Matsuda's harmonic templates, treats a set of colours
as harmonious when their hues fall inside the sectors of one template on the
hue wheel. The templates are: i (one narrow sector), V (one wide sector),
L (narrow plus wide at 90°), I (two narrow opposite sectors), T (half the
wheel), Y (wide plus narrow opposite) and X (two wide opposite sectors). A
template can be rotated to any angle.

Windmill's palette (ocean blues around 195–206°, gold at 55°, a soft red at 0°)
fits the X template: the blues sit in one sector, and gold and red in the
opposite one. Cyan, the first candidate, sat in the middle of the blues and
looked too similar. Periwinkle (`#94a0f0`, hue 232°) sits in the same sector at
its far edge, so it is still harmonious but clearly different. Matteo chose it
and asked for the method to become a shareable tool, because colour is his
field: years of writing on perceptual colour on his blog, for example
https://mycartablog.com/2013/03/06/perceptual-rainbow-palette-the-goodies/

## What exists

- `prototype/windmill_harmony_wheel.py`: a standalone script (Python standard
  library only). It places Windmill's palette and four candidates on a hue
  wheel, draws the X template, and writes an SVG. `windmill_harmony_wheel.png`
  is its output, rendered with headless Chrome.

## What the prototype does not do

1. **Hue is HSL hue, which is not perceptual.** Equal steps of HSL hue are not
   equal steps of perceived hue. Matteo's work argues for perceptual spaces:
   CIELAB / CIELCh, CAM02-UCS or OKLCH are the obvious candidates.
2. **One template, placed by eye.** The paper fits every template and finds the
   best rotation by minimising the hue distance of the palette to the
   template's sectors (with saturation as a weight). The prototype just draws X
   at hand-picked centres.
3. **No lightness or contrast checks.** For Windmill these were done by hand
   (WCAG contrast ratios of label colours against the compass background). A
   palette tool should probably report lightness, chroma and contrast together
   with harmony.
4. **No suggestion step.** It checks candidates someone already picked. It does
   not propose colours for a new role ("give me a colour that fits this
   palette, distinct from these").
5. **Tied to Windmill's data**, hard-coded at the top of the script.

## Open questions for Matteo (none decided)

- **Form:** a Python library, a command-line tool, a web page, a notebook, or
  more than one of these?
- **Colour space** for hue, lightness and chroma, and whether it is selectable.
- **Scope:** check a palette, fit templates, suggest new colours, or all three?
  Is contrast (WCAG, APCA) in scope?
- **Audience:** designers, scientists making figures, both?
- **Licence**, and whether to publish on PyPI. The name `perceptual-harmony`
  was free on PyPI and GitHub on 2026-11-19. Near neighbours to be aware of:
  Evil Martians' *Harmonizer* (UI palettes, OKLCH and APCA) and the
  `harmonize()` function in Google's Material colour utilities.
- **Relationship to Windmill:** should Windmill's README credit or link this
  tool once it exists?

## Working notes

- Matteo pushes himself unless he asks otherwise. There is no GitHub remote
  yet.
- To render SVG to PNG on this Mac, use headless Chrome, not `qlmanage`.
- Matteo prefers questions asked in chat as numbered text, not polls.
