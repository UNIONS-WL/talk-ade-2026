# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "Pillow"]
# ///
"""Rasterize the published HSC Y3 effective-density map onto a 0.25-deg sky grid.

Source: Li et al. (2023), Fig. 1, arXiv:2304.00702v3:
https://arxiv.org/html/2304.00702v3/neffMap.png

The source figure is a density map, not a survey mask. This recipe thresholds
its colored map pixels, aggregates them by sky-grid cell, and retains cells with
at least 30% source-pixel occupancy. The six panel calibrations use labeled
RA/Dec ticks. HECTOMAP has a curved graticule; its linear calibration is less
accurate. The result preserves image-scale gaps but is still a visual mask
approximation and must not replace the released HSC Y3 catalog mask.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE_IMAGE = HERE / "hsc_y3_neffMap.png"
OUTPUT_NPZ = HERE / "hsc_y3.npz"

# Bounds are the source image's six black plotting frames, with axes interior
# coordinates calibrated against the labeled ticks in the source figure.
PANELS = {
    "XMM": dict(box=(225, 90, 598, 282), ra=(32, 332, 34, 403), dec=(-2, 123, -6, 262), area=33.17),
    "VVDS": dict(box=(753, 90, 1655, 282), ra=(340, 1022, 350, 1288), dec=(4, 141, 0, 245), area=96.18),
    "GAMA09H": dict(box=(225, 394, 731, 529), ra=(135, 366, 140, 465), dec=(4, 409, 0, 487), area=82.36),
    "GAMA15H": dict(box=(886, 400, 1655, 525), ra=(210, 1041, 215, 1203), dec=(1, 410, 0, 450), area=40.87),
    "WIDE12H": dict(box=(225, 648, 1524, 826), ra=(160, 411, 170, 693), dec=(4, 661, 0, 771), area=121.32),
    "HECTOMAP": dict(box=(225, 932, 1392, 1095), ra=(220, 444, 230, 760), dec=(44, 941, 41, 1061), area=43.06),
}
GRID_STEP_DEG = 0.25
OCCUPANCY_THRESHOLD = 0.30

image = np.asarray(Image.open(SOURCE_IMAGE).convert("RGB"))
ra_grid = np.linspace(360.0, 0.0, 1441)
dec_grid = np.linspace(-90.0, 90.0, 721)
cell_count = len(dec_grid) * len(ra_grid)
field_masks = []
field_areas = []
field_fractions = []

for name, panel in PANELS.items():
    x0, y0, x1, y1 = panel["box"]
    # Exclude the black axes frame itself. Only plot pixels enter occupancy.
    crop = image[y0 + 2:y1 - 1, x0 + 2:x1 - 1]
    red, green = crop[..., 0], crop[..., 1]
    observed = (red > 38) & (green > 45)

    yy, xx = np.indices(observed.shape)
    xx = xx + x0 + 2
    yy = yy + y0 + 2
    ra0, xra0, ra1, xra1 = panel["ra"]
    dec0, ydec0, dec1, ydec1 = panel["dec"]
    ra = ra0 + (xx - xra0) * (ra1 - ra0) / (xra1 - xra0)
    dec = dec0 + (yy - ydec0) * (dec1 - dec0) / (ydec1 - ydec0)
    ra %= 360.0
    ix = np.rint((360.0 - ra) / GRID_STEP_DEG).astype(np.int64)
    ix %= len(ra_grid)
    iy = np.rint((dec + 90.0) / GRID_STEP_DEG).astype(np.int64)
    iy = np.clip(iy, 0, len(dec_grid) - 1)
    flat = iy * len(ra_grid) + ix

    total = np.bincount(flat.ravel(), minlength=cell_count)
    filled = np.bincount(flat[observed], minlength=cell_count)
    fraction = np.divide(filled, total, out=np.zeros(cell_count, dtype=float), where=total > 0)
    fraction_map = fraction.reshape(len(dec_grid), len(ra_grid))
    mask = fraction_map >= OCCUPANCY_THRESHOLD
    field_masks.append(mask)
    field_fractions.append(fraction_map)
    cell_area = GRID_STEP_DEG**2 * np.cos(np.deg2rad(dec_grid))
    field_areas.append(float(mask.sum(axis=1) @ cell_area))

masks = np.stack(field_masks)
fractions = np.stack(field_fractions)
cell_area = GRID_STEP_DEG**2 * np.cos(np.deg2rad(dec_grid))
area_sensitivity = {}
for cut in (0.30, 0.40, 0.50, 0.60, 0.70):
    per_field = [(f >= cut).sum(axis=1) @ cell_area for f in fractions]
    trial_union_area = float(np.any(fractions >= cut, axis=0).sum(axis=1) @ cell_area)
    area_sensitivity[f"{cut:.2f}"] = {"per_field_deg2": [float(x) for x in per_field], "union_deg2": trial_union_area}
    print(f"occupancy {cut:.2f}: per-field={[round(float(x), 1) for x in per_field]}, union={trial_union_area:.1f} deg2")
union = np.any(masks, axis=0)
cell_area = GRID_STEP_DEG**2 * np.cos(np.deg2rad(dec_grid))
union_area = float(union.sum(axis=1) @ cell_area)
reference_areas = np.array([p["area"] for p in PANELS.values()], dtype=np.float64)
metadata = {
    "source": "Li et al. (2023), HSC Y3 cosmic shear, Fig. 1 effective number density map",
    "source_version": "arXiv:2304.00702v3",
    "source_url": "https://arxiv.org/html/2304.00702v3/neffMap.png",
    "source_image": SOURCE_IMAGE.name,
    "threshold_rgb": "red > 38 and green > 45",
    "occupancy_threshold": OCCUPANCY_THRESHOLD,
    "grid": "RA descending from 360 to 0 deg; Dec ascending from -90 to +90 deg; 0.25 deg spacing",
    "field_names": list(PANELS),
    "reference_areas_deg2": reference_areas.tolist(),
    "raster_areas_deg2": field_areas,
    "union_raster_area_deg2": union_area,
    "area_sensitivity_by_occupancy": area_sensitivity,
    "method_limitations": [
        "The source is a published effective-density map, not an official mask; color occupancy is a visual approximation.",
        "RA/Dec are linearly calibrated from labeled ticks in each panel.",
        "HECTOMAP has a curved graticule; its linear calibration is less accurate.",
        "The 0.25-degree grid and occupancy threshold remove subpixel gaps and some low-occupancy boundary cells.",
    ],
}
np.savez_compressed(
    OUTPUT_NPZ,
    mask=union,
    field_masks=masks,
    occupancy_fraction_by_field=fractions.astype(np.float16),
    ra=ra_grid,
    dec=dec_grid,
    field_names=np.asarray(list(PANELS), dtype="U16"),
    reference_areas_deg2=reference_areas,
    raster_areas_deg2=np.asarray(field_areas),
    metadata_json=np.asarray(json.dumps(metadata)),
)
print(f"saved {OUTPUT_NPZ}")
for name, measured, ref in zip(PANELS, field_areas, reference_areas):
    print(f"{name:10s} raster={measured:7.2f} deg2; paper={ref:6.2f} deg2")
print(f"union      raster={union_area:.2f} deg2; paper sum={reference_areas.sum():.2f} deg2")
