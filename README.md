# UNIONS at Colloque national Dark Energy

Joint 30-minute talk by Calum Murray (~15 min: the survey and its astrophysics) and Cail Daley (~15 min: cosmic
shear and outlook), Paris, Tuesday 3 November 2026 at 14:30. Live at https://unions-wl.github.io/talk-ade-2026/.

## One deck: `index.html`

Since 2 November the talk is a single [Lectern](https://github.com/calumhrmurray/lectern) deck: `index.html`
(one `<section>` per slide, speaker notes in `<aside class="notes">`) with `theme.css`, `reveal/` and `fonts/`.
Open it in any browser (arrow keys; `S` for the speaker view), or edit it on a canvas with
`npx lectern-editor index.html`; plain HTML edits work too. Pushing to `main` publishes it as it is
(`.github/workflows/publish.yml`); there is no build step.

- Calum's half: slides 1–21 (figures in `fig/`, videos in `media/`). Cail's half starts at the teal
  "Cosmology from UNIONS" divider (slide 22; figures in `images/`, videos in `media/`), with backup slides at the end (3×2pt first, then the error-bar blink on one slide).
- Look: Cail's house theme (EB Garamond, the orange headline rule, the small-caps footer, the logo bottom right,
  the teal · orange · yellow strip along the foot) on a white ground.
- Cail's slides were ported on 2 November from his house-system sources (removed the same day; they are in the
  git history before that). His PDF figures are rasterised next to them in `images/` as PNG; `figures/` holds
  the scripts that make his plots.

## Abstract (draft 2)

The Ultraviolet Near-Infrared Optical Northern Survey (UNIONS) is the largest deep weak lensing survey of the northern sky, combining multi-band data from telescopes on Mauna Kea over more than 5500 deg² at a depth comparable to LSST Year 1. UNIONS weak lensing measurements include the characterization of intrinsic alignments with spectroscopic samples, the tidal stripping of satellite halos in clusters, and new insights into the “lensing is low” tension. Earlier this year we released the first cosmological weak lensing results from UNIONS, constraining S₈ to about 8% using 2400 deg² of effective area in a joint non-tomographic configuration- and harmonic-space analysis. We close with an update on the status of the first UNIONS tomographic 3×2pt analysis over a footprint covering about 4800 deg².
