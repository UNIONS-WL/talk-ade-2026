# /// script
# requires-python = ">=3.10"
# dependencies = ["astropy", "matplotlib", "numpy"]
# ///
"""Full 40-CCD MegaCam mosaic of one UNIONS r-band exposure, with one CCD outlined.

Exposure: 2099927p (CFHT MegaCam, r.MP9602, 116 s, 2017-04-20, field Nr2939_1),
Elixir-processed, read from Martin Kilbinger's ShapePipe demo run:
/n17data/mkilbing/astro/Runs/shapepipe/CFIS/1.4_demo/output/
    run_sp_GitFeGie_2024-10-21_17-11-46/get_images_runner_run_2/output/2099927p.fits.fz

Each CCD's data section is binned 8x8, background-subtracted by its own median,
and placed on a common tangent plane from its linear WCS (CRPIX + CD; distortion
and the ~0.6 deg CCD rotation are ignored at this binning). North up, east left.
Grayscale asinh stretch on white; gaps between CCDs show as white. One CCD is
outlined in orange with its on-sky size; a 10 arcmin scale bar sits below.

    uv run figures/megacam_ccds.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from matplotlib.patches import Rectangle

EXP = Path(
    "/n17data/mkilbing/astro/Runs/shapepipe/CFIS/1.4_demo/output/"
    "run_sp_GitFeGie_2024-10-21_17-11-46/get_images_runner_run_2/output/2099927p.fits.fz"
)
OUT = Path(__file__).resolve().parents[1] / "images" / "megacam_ccds.png"
BIN = 8
HIGHLIGHT = "ccd04"  # top row, middle
INK, ACCENT = "#1a1a1a", "#c0582b"


def section(s):
    (x0, x1), (y0, y1) = [map(int, p.split(":")) for p in s.strip("[]").split(",")]
    return slice(y0 - 1, y1), slice(x0 - 1, x1)


def binned(a, b):
    ny, nx = (a.shape[0] // b) * b, (a.shape[1] // b) * b
    return a[:ny, :nx].reshape(ny // b, b, nx // b, b).mean(axis=(1, 3))


ccds = []  # (name, image oriented north-up/east-left, extent in arcmin)
with fits.open(EXP) as hdul:
    for hdu in hdul[1:]:
        h = hdu.header
        sy, sx = section(h["DATASEC"])
        img = binned(hdu.data[sy, sx].astype(np.float32), BIN)
        img -= np.median(img)
        # tangent-plane offsets (arcmin) of the data-section corners
        cd = np.array([[h["CD1_1"], h.get("CD1_2", 0.0)], [h.get("CD2_1", 0.0), h["CD2_2"]]]) * 60
        px = np.array([sx.start + 1, sx.stop]) - h["CRPIX1"]
        py = np.array([sy.start + 1, sy.stop]) - h["CRPIX2"]
        xi = cd[0, 0] * px
        eta = cd[1, 1] * py
        # orient so that array column 0 is east (large xi) and row 0 is south
        if xi[0] < xi[1]:
            img = img[:, ::-1]
        if eta[0] > eta[1]:
            img = img[::-1, :]
        ext = (-xi.max(), -xi.min(), eta.min(), eta.max())  # x = -xi: east left
        ccds.append((h["EXTNAME"], img, ext))

allpix = np.concatenate([c[1].ravel() for c in ccds])
noise = 1.4826 * np.median(np.abs(allpix))
stretch = lambda a: np.arcsinh(np.clip(a, -3 * noise, None) / (2 * noise))
vmax = np.percentile(stretch(allpix), 99.7)

fig, ax = plt.subplots(figsize=(12, 11.4), dpi=100)
fig.patch.set_alpha(0)
for name, img, ext in ccds:
    ax.imshow(stretch(img), extent=ext, origin="lower", cmap="gray_r",
              vmin=-0.5, vmax=vmax, interpolation="antialiased")

x0s, x1s, y0s, y1s = np.array([c[2] for c in ccds]).T
xc, yc = (x0s.min() + x1s.max()) / 2, (y0s.min() + y1s.max()) / 2
xmin, xmax = x0s.min() - xc, x1s.max() - xc
ymin, ymax = y0s.min() - yc, y1s.max() - yc
for im in ax.images:
    e = im.get_extent()
    im.set_extent((e[0] - xc, e[1] - xc, e[2] - yc, e[3] - yc))

name, img, (a, b, c, d) = next(cc for cc in ccds if cc[0] == HIGHLIGHT)
a, b, c, d = a - xc, b - xc, c - yc, d - yc
ax.add_patch(Rectangle((a, c), b - a, d - c, fill=False, ec=ACCENT, lw=4.5, zorder=5))
ax.text((a + b) / 2, d + 1.0, f"one CCD: {b - a:.1f}′ × {d - c:.1f}′",
        ha="center", va="bottom", fontsize=32, color=ACCENT, weight="bold")

bar = 10
bx, by = xmax - bar, ymin - 2.6
ax.plot([bx, bx + bar], [by, by], color=INK, lw=6, solid_capstyle="butt")
ax.text(bx + bar / 2, by - 0.9, f"{bar}′", ha="center", va="top", fontsize=32, color=INK)

ax.set_xlim(xmin - 0.3, xmax + 0.3)
ax.set_ylim(ymin - 7.0, ymax + 5.5)
ax.set_aspect("equal")
ax.axis("off")
fig.subplots_adjust(0, 0, 1, 1)
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT, transparent=True)
print(OUT, f"noise={noise:.1f} ADU", f"mosaic {xmax - xmin:.1f}′ × {ymax - ymin:.1f}′")
