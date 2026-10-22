# UNIONS at Colloque national Dark Energy

Scaffold for the joint 30-minute talk by Calum Murray (~15 min) and Cail Daley (~10 min), Paris, Tuesday 3 November 2026 at 14:30. Calum owns the survey and astrophysics slides; Cail owns cosmic shear and outlook. One handover separates the sections. Replace the two plot placeholders during preparation.

## Build and check

Requires Node.js. From the repository root:

```bash
npm install
node house/build.mjs .
node house/check.mjs .
```

The build writes a self-contained deck to `_site/talk-ade-2026/index.html` and a reader report alongside it. Check screenshots and `_check/check.txt` before changes are considered ready. `house/` is the copied house slide system; `slides/` contains hand-authored HTML and `deck.json` orders them. `images/` contains only the UNIONS logo, used in slide furniture.

## Previous talks

- [Cail Daley · Moriond 2026 UNIONS source](https://github.com/cailmdaley/talks/tree/main/26_Moriond_UNIONS) — source directory confirmed; no matching deck found on the configured Pages site.
- [Sacha Guerrini · Moriond 2026 UNIONS deck](https://sachaguer.github.io/talks/26_Moriond_UNIONS/26_Moriond_UNIONS.html) — confirmed in the `gh-pages` branch and live.

Cail's configured Pages URL for the directory returned 404; use the source link. Sacha's deck file is present on `gh-pages` and the direct URL is the published HTML file.

## Abstract (draft 2)

The Ultraviolet Near-Infrared Optical Northern Survey (UNIONS) is the largest deep weak lensing survey of the northern sky, combining multi-band data from telescopes on Mauna Kea over more than 5500 deg² at a depth comparable to LSST Year 1. UNIONS weak lensing measurements include the characterization of intrinsic alignments with spectroscopic samples, the tidal stripping of satellite halos in clusters, and new insights into the “lensing is low” tension. Earlier this year we released the first cosmological weak lensing results from UNIONS, constraining S₈ to about 8% using 2400 deg² of effective area in a joint non-tomographic configuration- and harmonic-space analysis. We close with an update on the status of the first UNIONS tomographic 3×2pt analysis over a footprint covering about 4800 deg².
