# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy"]
# ///
"""Add the sky overlay's reflection in the car roof to the 24 h Eiffel frames.

The overlay (Gaia + mass map) is recovered per frame as D = frame − photo.
The roof is a curved mirror: a sky point at height d above the mirror line
H(x) reflects at H(x) + K·d, spread outward horizontally by (1 + C·depth).
H, K, C are fitted from the photo's own reflections (tower tip 83→3183, arch
lights 1824→2100, lamp heads, and the hedge-top silhouette column by column). Reflectance R is the photo's
reflected/direct luminance ratio, so the overlay dims and fades with the roof
exactly as the real sky does. Output = photo + S·R·D(source), roof only, where the
source is open sky (its own blue brightness).

    uv run render_roof_reflection.py [--strength 1.0] [--test N]
"""
import argparse
import pathlib
import subprocess

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
PHOTO = pathlib.Path.home() / "Downloads" / "eiffel_tower_night.jpg"
SEQ = ROOT / "24h_jan10_north_gaia_masked_replace" / "start_frame078" / "frames_seq"
OUT = ROOT / "24h_reflect"
K = 0.62          # vertical compression of the reflection
C = 4.3e-5        # outward horizontal spread per pixel of depth
CX = 2500.0


# mirror line H(x), from hedge-top ↔ reflected-hedge pairs per column at K = 0.62
H_KNOTS = ([0, 500, 1500, 2500, 3500, 3900, 4300, 4500, 4700, 5000],
           [1995, 1986, 1976, 1990, 1981, 1985, 2000, 2019, 2027, 2040])


def mirror_line(x):
    return np.interp(x, *H_KNOTS)


def geometry(h, w):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    H = mirror_line(x)
    depth = y - H
    roof = depth > 2
    src_y = H - depth / K
    src_x = CX + (x - CX) / (1 + C * np.clip(depth, 0, None))
    roof &= src_y >= 0
    return roof, src_y, src_x


def sample(img, sy, sx):
    return np.stack([ndimage.map_coordinates(img[..., c], [sy, sx], order=1, mode="nearest")
                     for c in range(3)], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--test", type=int, default=None, help="render only this frame index")
    a = ap.parse_args()
    photo = np.asarray(Image.open(PHOTO).convert("RGB"), dtype=np.float32) / 255
    h, w, _ = photo.shape
    roof, sy, sx = geometry(h, w)
    ys, xs = sy[roof], sx[roof]
    L = ndimage.gaussian_filter(photo.mean(2), 6)
    Lsrc = ndimage.map_coordinates(L, [ys, xs], order=1)
    R = np.clip(L[roof] / np.maximum(Lsrc, 0.02), 0, 1)
    # only open sky reflects the overlay; the blurred sky mask also tints the hedge tops
    blue = ndimage.gaussian_filter(photo[..., 2], 4)
    bsrc = ndimage.map_coordinates(blue, [ys, xs], order=1)
    R = (R * np.clip((bsrc - 0.10) / 0.10, 0, 1))[:, None]
    OUT.mkdir(exist_ok=True)
    frames = sorted(SEQ.glob("seq_*.jpg"))
    if a.test is not None:
        frames = [frames[a.test]]
    for f in frames:
        img = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32) / 255
        D = img - photo
        D[np.abs(D).max(2) < 0.012] = 0  # JPEG noise outside the overlay
        D = ndimage.gaussian_filter(D, (1.5, 1.5, 0))  # a roof is not a perfect mirror
        out = img.copy()
        out[roof] = np.clip(img[roof] + a.strength * R * sample(D, ys, xs), 0, 1)
        Image.fromarray((255 * out).astype(np.uint8)).save(OUT / f.name, quality=94)
        print(f.name)
    if a.test is None:
        mp4 = OUT / "eiffel_unions_24h_roof_reflection_hq.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "12", "-i", str(OUT / "seq_%03d.jpg"),
                        "-vf", "scale=2500:-2:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-crf", "16",
                        str(mp4)], check=True)
        print(mp4)


if __name__ == "__main__":
    main()
