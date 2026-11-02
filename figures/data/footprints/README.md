# Survey footprints for the ADE talk

These products describe sky coverage for a presentation, not likelihood masks.
Run `uv run figures/footprints.py --dr1 figures/.cache/euclid_dr1_observed_wide_moc.fits` and `uv run figures/s8_landscape.py` from the deck root to rebuild the deck figures.
Run the footprint script without `--dr1` to rebuild the two `_nodr1.png` maps from public data alone, then `uv run figures/s8_landscape.py --no-dr1` to select them in the composites.

| Layer | Product and source | Definition and limitations |
| --- | --- | --- |
| DES | `des.fits`: [Survey Footprint Explorer](https://github.com/RuslanBrilenkov/skymap.github.io/tree/e77380d10de43985263c22e0f6fb4716d1ce7d1e/surveys), commit `e77380d10de43985263c22e0f6fb4716d1ce7d1e` | Public MOC from the NASA LAMBDA DES boundary polygon; 5,155 deg². Wide survey envelope, not the Y3/Y6 cosmology selection. |
| KiDS | `kids.fits`: same pinned repository | Public KiDS-N/S science-quality binary-mask MOC, 891 deg²; the released mask coverage rather than the nominal tile area. The [Explorer paper](https://arxiv.org/abs/2605.11099) documents the conversion. |
| HSC Y3 | `hsc_y3.npz`: [Li et al. 2023, Fig. 1](https://arxiv.org/html/2304.00702v3/neffMap.png), with source PNG and `hsc_y3_digitize.py` | Color-occupancy raster of six actual Y3 density-map fields, including the GAMA09H exclusion and broad disconnected patches. Approximate 0.25° boundaries lose small star holes; HECTOMAP's curved panel uses approximate coordinate calibration. Gross raster area is 572 deg² versus the selected science area of 416.96 deg²; this is a visual field-coverage approximation, not a science mask. |
| LSST WFD | `lsst.fits`: same pinned Explorer repository | Rubin scheduler low-dust + Virgo selection, 17,719 deg². Approximate final-survey region, not a forecast for an intermediate year. |
| Euclid Wide | `euclid_wide.npz`, accompanying source metadata and digitization recipe | Scaramella et al. 2022 RSD_2021A full six-year reference survey, digitized from Fig. 46. Approximate proxy for the final footprint; not an as-built mask. Smoothing and filling the outer envelope give 15,257 deg² versus the reference's 14,514 deg². |
| Euclid DR1 | EASIDR TAP, DR1_R1/R2 VIS, internal release; source data in gitignored `figures/.cache/` | Union of 9,504 unique wide VIS mosaic tile polygons, not an agreed shear analysis mask. Order-13 MOC area 2,346.1 deg². Cail authorized displaying the footprint; only rendered PNGs are committed. |
| UNIONS DR6 | `unions_dr6_status.json`: [public production status](https://unions-wl.github.io/production/status.json), generated 2026-10-30 | Full tile universe: 23,114 half-degree tiles, including 213 held tiles. ShapePipe convention: Dec=b/2−90°, RA=a/(2cos Dec) for tile a.b; RA half-width=0.25°/cos Dec. Summed nominal tile area is 5,778.5 deg² before star masks and selection. This is DR6 tile coverage, not the effective v2 shear area. |

The background shades |Galactic latitude| < 10°.
Right ascension increases to the left, with RA=180° at the centre.
Solid fills mark Stage III and UNIONS; dashed lines mark Stage IV, including the observed DR1 subset.
The two variants use identical geometry and layout.
The purple UNIONS colour is reserved for that layer.
