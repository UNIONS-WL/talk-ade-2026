#!/usr/bin/env python3.13
from __future__ import annotations

import json
from pathlib import Path

import healpy as hp
import numpy as np
from PIL import Image, ImageFilter


ROOT = Path("/Users/cd280747/Downloads")
BASE = ROOT / "eiffel_tower_night.jpg"
MAP = ROOT / "unions_mcalens_nside2048_theory_pixwin_nsigma3p5_e.fits"
OUT = ROOT / "unions-eiffel-composites"


PARAMS = {
    "description": "Exact nside=2048 HEALPix kappa values sampled into a northern-sky art projection behind the Eiffel Tower.",
    "ra_center_deg": 188.0,
    "ra_span_deg": 82.0,
    "dec_top_deg": 62.0,
    "dec_bottom_deg": 30.0,
    "sky_fraction_height": 0.64,
    "colormap": "custom diverging: negative cyan-blue, positive amber-gold",
    "normalization": "symmetric about zero using 99.2 percentile of |kappa| in visible sampled sky",
    "datetime_if_interpreted_as_meridian_ra_center": {
        "paris_local_cest": "2026-05-28T21:57:00",
        "utc": "2026-05-28T19:57:00",
        "note": "This is the time when local sidereal time at Paris is approximately 188 deg. The art projection itself is not the true Trocadero camera geometry.",
    },
}


def sky_alpha(rgb: np.ndarray) -> np.ndarray:
    h, w, _ = rgb.shape
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    blue_sky = (b > r + 0.030) & (b > 0.70 * g) & (y < 0.66)
    sky = Image.fromarray((255 * blue_sky).astype(np.uint8), mode="L")
    sky = sky.filter(ImageFilter.GaussianBlur(radius=max(w // 180, 12)))
    vertical_fade = np.clip((0.66 - y) / 0.10, 0, 1) * np.clip(y / 0.04, 0, 1)
    return (np.asarray(sky, dtype=np.float32) / 255.0) * vertical_fade


def projection(width: int, height: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:height, 0:width].astype("f4")
    ysky = np.clip(yy / (PARAMS["sky_fraction_height"] * height), 0, 1)
    dec = np.deg2rad(PARAMS["dec_top_deg"] - (PARAMS["dec_top_deg"] - PARAMS["dec_bottom_deg"]) * ysky)
    ra = (
        PARAMS["ra_center_deg"]
        + (xx - width / 2) / width * PARAMS["ra_span_deg"]
        + 4.0 * np.sin(np.pi * ysky)
    ) % 360
    valid = yy < PARAMS["sky_fraction_height"] * height
    return (np.pi / 2 - dec).astype("f4"), np.deg2rad(ra).astype("f4"), valid


def kappa_to_color(kappa: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scale = np.nanpercentile(np.abs(kappa[valid]), 99.2)
    signed = np.clip(kappa / scale, -1, 1)
    power = np.abs(signed) ** 0.72
    negative = np.array([0.10, 0.50, 1.00], dtype=np.float32)
    positive = np.array([1.00, 0.54, 0.12], dtype=np.float32)
    color = np.where(signed[..., None] >= 0, positive, negative)
    color = (0.20 + 0.80 * power[..., None]) * color
    map_alpha = np.clip((power - 0.10) / 0.90, 0, 1) ** 0.8
    return np.nan_to_num(color).astype("f4"), np.nan_to_num(map_alpha).astype("f4")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    image = Image.open(BASE).convert("RGB")
    rgb = np.asarray(image, dtype=np.float32) / 255.0
    h, w, _ = rgb.shape

    theta, phi, valid = projection(w, h)
    alpha = sky_alpha(rgb)
    sample = valid & (alpha > 0.002)

    mass_map = hp.read_map(MAP, dtype=np.float32, verbose=False)
    kappa = np.full((h, w), np.nan, dtype=np.float32)
    kappa[sample] = hp.get_interp_val(mass_map, theta[sample], phi[sample]).astype("f4")

    color, map_alpha = kappa_to_color(kappa, sample)
    total_alpha = 0.48 * alpha * map_alpha * sample
    screened = 1 - (1 - rgb) * (1 - color)
    composite = np.clip(rgb * (1 - total_alpha[..., None]) + screened * total_alpha[..., None], 0, 1)

    out = OUT / "eiffel_unions_exact_kappa_northern_v2.jpg"
    overlay = OUT / "eiffel_unions_exact_kappa_northern_v2_overlay.png"
    sidecar = OUT / "eiffel_unions_exact_kappa_northern_v2_projection.json"
    Image.fromarray((255 * composite).astype(np.uint8)).save(out, quality=95)
    Image.fromarray((255 * np.dstack([color, total_alpha])).astype(np.uint8), mode="RGBA").save(overlay)
    sidecar.write_text(json.dumps(PARAMS, indent=2) + "\n")
    print(out)
    print(overlay)
    print(sidecar)


if __name__ == "__main__":
    main()
