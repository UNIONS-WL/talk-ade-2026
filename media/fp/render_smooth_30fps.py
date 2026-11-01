# /// script
# requires-python = ">=3.11"
# dependencies = ["healpy", "astropy", "numpy", "scipy", "pillow"]
# ///
"""Render the 4-minute sky sequence and its roof reflection without touching the original outputs.

`--cmap` picks the mass-map colouring (see COLORMAPS); each colormap renders into its own
directories and mp4, so the variants sit side by side.

    uv run render_smooth_30fps.py [--cmap original|gold] [--workers N] [--test]
"""
import argparse
import csv
import json
import multiprocessing as mp
import subprocess
import time
from datetime import timedelta, timezone
from pathlib import Path

import healpy as hp
import numpy as np
from astropy.utils import iers
from PIL import Image
from scipy import ndimage

import render_literal_paris_north_24h_gaia_masked_replace as sky
import render_roof_reflection as roof

ROOT = Path(__file__).parent.resolve()
sky.N_FRAMES = 360
sky.STEP_MINUTES = 4
sky.LOOP_START_ORIGINAL_FRAME = 292
iers.conf.auto_download = False

# OKLab endpoints sampled from eiffel_tower_night.jpg: GOLD_NEG is the open sky a quarter of
# the way down the frame (median over x = 10-35 % of the width); GOLD_POS is the tower's
# mid-brightness warm lights (median of warm tower pixels with mean level 0.5-0.65), which
# is amber rather than the near-white yellow of the brightest bulbs.
GOLD_NEG = '#102d6d'
GOLD_POS = '#df9f39'


def _srgb_to_oklab(rgb):
    rgb = np.asarray(rgb, dtype=np.float64)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lms = np.cbrt(lin @ _M1.T)
    return lms @ _M2.T


def _oklab_to_srgb(lab):
    lin = np.clip((lab @ np.linalg.inv(_M2).T) ** 3 @ np.linalg.inv(_M1).T, 0, 1)
    return np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def oklab_ramp(neg_hex, pos_hex, n=256):
    """sRGB lookup table (n, 3) along the straight OKLab line from neg_hex to pos_hex."""
    ends = [_srgb_to_oklab([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]) for h in (neg_hex, pos_hex)]
    lab = ends[0] + (ends[1] - ends[0]) * np.linspace(0, 1, n)[:, None]
    assert np.all(np.diff(lab[:, 0]) > 0), 'lightness must rise monotonically from negative to positive'
    return _oklab_to_srgb(lab).astype(np.float32)


GOLD_LUT = oklab_ramp(GOLD_NEG, GOLD_POS)


def kappa_to_color_gold(kappa, valid, scale):
    """Colour kappa from the photo's own palette: evening-sky blue (negative) to tower gold (positive).

    kappa/scale is clipped to [-1, 1] and mapped through GOLD_LUT, a perceptually uniform OKLab
    ramp whose lightness rises monotonically from GOLD_NEG to GOLD_POS. Opacity follows |kappa|
    exactly as the original map does, so kappa near zero leaves the photo's sky untouched.
    """
    signed = np.clip(np.nan_to_num(kappa) / scale, -1, 1)
    power = np.abs(signed) ** 0.72
    color = GOLD_LUT[np.rint((signed + 1) * 0.5 * (len(GOLD_LUT) - 1)).astype(np.int32)]
    map_alpha = np.where(valid, np.clip((power - 0.10) / 0.90, 0, 1) ** 0.8, 0)
    return color, map_alpha.astype('f4')


# name -> (sky frames dir, reflection frames dir, mp4, render_frame options)
COLORMAPS = {
    'original': ('24h_jan10_north_gaia_masked_replace_4min', '24h_reflect_4min',
                 '24h_reflect_4min/eiffel_unions_24h_roof_reflection_4min_30fps.mp4', {}),
    # Over-blend so the dark blue can darken the bright lower sky (a screen can only brighten);
    # opacity 0.8 keeps the gold reading as glow once it is no longer screened.
    'gold': ('24h_jan10_north_gaia_masked_replace_4min_gold', '24h_reflect_4min_gold',
             '24h_reflect_4min/eiffel_unions_24h_roof_reflection_4min_30fps_gold.mp4',
             dict(kappa_to_color=kappa_to_color_gold, blend='over', kappa_opacity=0.8)),
}


def render(i):
    dt = sky.START_LOCAL + timedelta(minutes=4 * i)
    record = sky.render_frame(masked, gaia_renderer, base_renderer, mass_map, mask_map,
                              gaia, rgb, geom, dt, scale, i, **RENDER_OPTS)
    print(f'sky {i:03d}', flush=True)
    return record


def reflect(i):
    f = seq / f'seq_{i:03d}.jpg'
    img = np.asarray(Image.open(f).convert('RGB'), dtype=np.float32) / 255
    delta = img - photo
    delta[np.abs(delta).max(2) < 0.012] = 0
    delta = ndimage.gaussian_filter(delta, (1.5, 1.5, 0))
    out = img.copy()
    out[roof_mask] = np.clip(img[roof_mask] + R * roof.sample(delta, ys, xs), 0, 1)
    Image.fromarray((255 * out).astype(np.uint8)).save(REFLECT / f.name, quality=94)
    print(f'reflection {i:03d}', flush=True)


def main():
    global masked, gaia_renderer, base_renderer, mass_map, mask_map, gaia, rgb, geom, scale
    global seq, photo, roof_mask, ys, xs, R, OUT, REFLECT, RENDER_OPTS
    p = argparse.ArgumentParser()
    p.add_argument('--test', action='store_true')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--cmap', choices=COLORMAPS, default='original')
    args = p.parse_args()
    out, reflect_dir, mp4, RENDER_OPTS = COLORMAPS[args.cmap]
    OUT, REFLECT, mp4 = ROOT / out, ROOT / reflect_dir, ROOT / mp4
    sky.OUT = OUT
    sky.FRAMES = OUT / 'frames'
    start = time.monotonic()
    sky.FRAMES.mkdir(parents=True, exist_ok=True)
    masked = sky.load_masked_renderer()
    gaia_renderer = masked.load_gaia_renderer()
    base_renderer = gaia_renderer.load_base_renderer()
    rgb = np.asarray(Image.open(base_renderer.BASE).convert('RGB'), dtype=np.float32) / 255
    gaia = np.asarray(Image.open(gaia_renderer.GAIA).convert('RGB'), dtype=np.float32) / 255
    geom = gaia_renderer.camera_geometry(base_renderer, rgb.shape[1], rgb.shape[0])
    mass_map = hp.read_map(base_renderer.MAP, dtype=np.float32)
    mask_map = hp.read_map(masked.MASK, dtype=np.float32)
    # The original 96-time sampling fixes the same normalization as the original clip.
    times = [(sky.START_LOCAL + timedelta(minutes=15*i)).astimezone(timezone.utc) for i in range(96)]
    scale = masked.fixed_color_scale_masked(masked, base_renderer, mass_map, mask_map, geom, times)
    print(f'scale {scale}', flush=True)
    if args.test:
        record = render(15)
        original = next((ROOT / '24h_jan10_north_gaia_masked_replace/frames').glob('frame_004_*.jpg'))
        a = np.asarray(Image.open(original).convert('RGB'), dtype=np.int16)
        b = np.asarray(Image.open(record['path']).convert('RGB'), dtype=np.int16)
        diff = np.abs(a-b)
        print(f'comparison max={diff.max()} mean={diff.mean():.8f}', flush=True)
        Image.open(original).thumbnail((1000, 1000))
        for src, name in [(original, 'original'), (record['path'], 'new')]:
            im = Image.open(src); im.thumbnail((1250, 1250)); im.save(OUT / f'comparison_{name}.jpg', quality=95)
        print(f'wall_seconds {time.monotonic()-start:.1f}', flush=True)
        return
    with mp.get_context('fork').Pool(args.workers) as pool:
        records = list(pool.imap(render, range(360)))
    with (OUT / 'frames_index.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=records[0].keys()); w.writeheader(); w.writerows(records)
    (OUT / 'frames_index.json').write_text(json.dumps({'fixed_kappa_abs_p99p2_masked': scale, 'loop_start_frame': 292, 'frames': records}, indent=2)+'\n')
    _, seq, _ = sky.write_reordered_links(records)
    # Release sky arrays before constructing the reflection geometry.
    del mass_map, mask_map, gaia, rgb, geom
    photo = np.asarray(Image.open(roof.PHOTO).convert('RGB'), dtype=np.float32) / 255
    roof_mask, sy, sx = roof.geometry(*photo.shape[:2])
    ys, xs = sy[roof_mask], sx[roof_mask]
    del sy, sx
    L = ndimage.gaussian_filter(photo.mean(2), 6)
    Lsrc = ndimage.map_coordinates(L, [ys, xs], order=1)
    R = np.clip(L[roof_mask] / np.maximum(Lsrc, 0.02), 0, 1)
    blue = ndimage.gaussian_filter(photo[..., 2], 4)
    bsrc = ndimage.map_coordinates(blue, [ys, xs], order=1)
    R = (R * np.clip((bsrc - 0.10) / 0.10, 0, 1))[:, None]
    del L, Lsrc, blue, bsrc
    REFLECT.mkdir(exist_ok=True)
    with mp.get_context('fork').Pool(args.workers) as pool:
        list(pool.imap_unordered(reflect, range(360)))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '30', '-i', str(REFLECT/'seq_%03d.jpg'),
                    '-vf', 'scale=2500:-2:flags=lanczos,format=yuv420p', '-c:v', 'libx264', '-crf', '16', str(mp4)], check=True)
    print(f'mp4 {mp4}\nwall_seconds {time.monotonic()-start:.1f}', flush=True)

if __name__ == '__main__':
    main()
