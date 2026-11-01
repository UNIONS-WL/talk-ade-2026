# Eiffel + UNIONS kappa map composite method

This note documents how `eiffel_unions_exact_kappa_northern_v2.jpg` was produced, what is faithful to the FITS map, and what is an outreach/artistic placement choice.

## Inputs

- Eiffel image: `/Users/cd280747/Downloads/eiffel_tower_night.jpg`
- Kappa map: `/Users/cd280747/Downloads/unions_mcalens_nside2048_theory_pixwin_nsigma3p5_e.fits`
- Rendering script: `/Users/cd280747/Downloads/unions-eiffel-composites/render_exact_kappa_v2.py`
- Main output: `/Users/cd280747/Downloads/unions-eiffel-composites/eiffel_unions_exact_kappa_northern_v2.jpg`
- Transparent map layer: `/Users/cd280747/Downloads/unions-eiffel-composites/eiffel_unions_exact_kappa_northern_v2_overlay.png`
- Projection sidecar: `/Users/cd280747/Downloads/unions-eiffel-composites/eiffel_unions_exact_kappa_northern_v2_projection.json`

The FITS file is an implicit HEALPix RING map with `NSIDE=2048`. The script reads it directly with `healpy.read_map(..., dtype=np.float32)` and samples it with `healpy.get_interp_val`.

## Projection

This image uses a northern-sky art projection, not the literal Trocadero camera geometry.

For every output pixel `(x, y)` in the Eiffel image, the script assigns a sky coordinate:

```text
ysky = clip(y / (0.64 * image_height), 0, 1)

dec = 62 deg - (62 deg - 30 deg) * ysky
ra  = 188 deg + (x - image_width / 2) / image_width * 82 deg
      + 4 deg * sin(pi * ysky)
```

Pixels are considered sky-map candidates only for `y < 0.64 * image_height`; a separate sky mask then limits the overlay to the blue sky/reflection regions of the photograph.

Interpretation:

- The top of the visible map is assigned roughly `Dec = +62 deg`.
- The lower mapped sky is assigned roughly `Dec = +30 deg`.
- The center of the image is assigned roughly `RA = 188 deg`.
- The horizontal span is roughly 82 degrees in RA, plus a small sinusoidal bend to avoid a mechanically flat rectangular strip.

If the `RA_center = 188 deg` were interpreted as crossing the Paris meridian, the corresponding approximate time is:

```text
2026-05-28 21:57 CEST
2026-05-28 19:57 UTC
```

That timestamp only describes the chosen central RA. It does not make the composite a physically literal sky view from the Trocadero photo.

## Why this is not literal sky geometry

The original Eiffel photograph appears to be a Trocadero-facing view toward the southeast. For a fixed camera location and direction, changing the observation time changes which right ascension is visible, but it does not change the declination assigned to each altitude/azimuth pixel. A literal Trocadero sky projection mainly samples low and negative declinations in the visible sky behind the tower. That is not the northern UNIONS-like sky placement we wanted visually.

So this composite deliberately chooses a northern declination band and maps it into the photograph's sky area. It is faithful to a selected patch of the FITS kappa map, but it is not claiming that this exact sky patch would appear behind the Eiffel Tower from that viewpoint at that time.

## Sky mask

The map is blended only where the photo looks like blue sky/reflection:

```text
blue_sky = (B > R + 0.030) and (B > 0.70 * G) and (y < 0.66)
```

That binary mask is blurred with a Gaussian radius of `max(image_width // 180, 12)`, then multiplied by a vertical fade:

```text
vertical_fade = clip((0.66 - y_norm) / 0.10, 0, 1) * clip(y_norm / 0.04, 0, 1)
```

The script samples the FITS map only where:

```text
projection_valid and sky_alpha > 0.002
```

This is why the tower, most trees, and most foreground remain photographic.

## Kappa sampling fidelity

For each sampled pixel, the script computes HEALPix angular coordinates:

```text
theta = pi / 2 - dec
phi = ra
kappa = hp.get_interp_val(map, theta, phi)
```

The positions of hot/cold spots and footprint/mask features in the rendered map are therefore tied to the FITS map under the projection above. The sampling is bilinear interpolation on the HEALPix sphere through `healpy.get_interp_val`, not nearest-neighbor pixel drawing.

Faithful:

- The displayed texture comes from the actual FITS values.
- The relative positions of features are fixed by the RA/Dec mapping above.
- Positive and negative values are encoded with opposite colors.
- The source map is sampled at its native `NSIDE=2048` resolution.

Not faithful / display choices:

- The projection into the Eiffel image is chosen for composition, not a literal camera sky.
- The FITS header does not declare `COORDSYS`; the script treats the map coordinates as RA/Dec-like longitude/latitude.
- The map is color-stretched nonlinearly for visibility.
- Weak low-amplitude regions are partially transparent, so absence of visible color does not mean zero kappa.
- JPEG compression affects the final `jpg`; use the `overlay.png` or rerender if exact display pixels matter.

## Color and opacity

The display normalization is symmetric around zero:

```text
scale = 99.2 percentile of |kappa| over sampled visible pixels
signed = clip(kappa / scale, -1, 1)
power = |signed| ** 0.72
```

Colors:

```text
negative kappa -> cyan-blue RGB = [0.10, 0.50, 1.00]
positive kappa -> amber-gold RGB = [1.00, 0.54, 0.12]
color = (0.20 + 0.80 * power) * sign_color
```

Map opacity:

```text
map_alpha = clip((power - 0.10) / 0.90, 0, 1) ** 0.8
total_alpha = 0.48 * sky_alpha * map_alpha
```

The final image uses a screen-style blend:

```text
screened = 1 - (1 - photo_rgb) * (1 - map_color)
composite = photo_rgb * (1 - total_alpha) + screened * total_alpha
```

This means the output is a visualization of the FITS kappa field, not a quantitatively calibrated colorbar image. A colorbar would need a separate companion figure using the same normalization.

## Recommended caption language

Safe wording:

> Artistically placed visualization of a UNIONS weak-lensing mass map behind the Eiffel Tower. The sky texture is sampled from the UNIONS kappa map; its placement in the photograph is illustrative.

Avoid wording that implies literal observational geometry:

> The dark matter map as it appeared in the Paris sky.

or

> A true sky projection behind the Eiffel Tower at this time.
