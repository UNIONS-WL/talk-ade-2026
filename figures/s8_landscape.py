# /// script
# dependencies = ["matplotlib", "numpy", "pillow", "fonttools", "brotli"]
# ///
"""S8 landscape frames, all on one canvas.

images/s8_consensus.png  Stage III S8 whisker beside the DES Y6 footprint map (no UNIONS)
images/s8_north.png      the same with the UNIONS outline on the map
images/s8_unions.png     the whisker alone, wide, with the two published UNIONS results

Stage III and CMB values as in Cail's Moriond 2026 deck; UNIONS values are the
published ones: Goh+2026 xi_pm 0.831 +0.067 -0.078, Guerrini+2026 C_ell 0.891 +0.057 -0.084.
"""
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from _style import *

setup()
STAGE3 = [("KiDS-1000", 0.759, 0.021, 0.024), ("DES Y3", 0.759, 0.023, 0.025), ("HSC Y3", 0.769, 0.034, 0.031),
          ("KiDS-Legacy", 0.815, 0.021, 0.016), ("DES Y6", 0.798, 0.015, 0.014)]
UNIONS = [(r"UNIONS $\xi_\pm$", 0.831, 0.078, 0.067), (r"UNIONS $C_\ell$", 0.891, 0.084, 0.057)]
CMB = (0.836, 0.013, 0.012)
TALKS = "/n17data/cdaley/unions/docs/talks/images/"


def whisker(ax, rows, xlim, ms=22):
    c, lo, hi = CMB
    ax.axvspan(c - lo, c + hi, color="#E7D7C8", zorder=0, lw=0)
    ax.axvline(c, color=ORANGE, lw=3, alpha=0.6, zorder=0)
    for i, (name, v, l, h, col) in enumerate(rows):
        ax.errorbar(v, i, xerr=[[l], [h]], fmt="s" if "UNIONS" in name else "o", ms=ms, lw=6, capsize=0,
                    color=col, zorder=3)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    for t, r in zip(ax.get_yticklabels(), rows):
        t.set_color(r[4])
    ax.tick_params(axis="y", length=0, pad=24)
    ax.text(c, -0.95, "CMB", ha="center", va="center", fontsize=60, color=ORANGE)
    ax.set_ylim(len(rows) - 0.5, -1.35)
    ax.set_xlim(*xlim)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(r"$S_8$", labelpad=10)


def landscape(map_png, out):
    fig = plt.figure(figsize=BODY, dpi=DPI)
    ax = fig.add_axes([0.15, 0.17, 0.15, 0.80])
    whisker(ax, [(n, v, l, h, INK) for n, v, l, h in STAGE3], (0.715, 0.87))
    ax.set_xticks([0.75, 0.85])
    im = np.asarray(Image.open(map_png).convert("RGB"))
    im = im[6:-6, 90:-6]  # trim the frame line
    axm = fig.add_axes([0.31, 0.02, 0.69, 0.96])
    axm.imshow(im, interpolation="lanczos"); axm.axis("off")
    fig.savefig(IMAGES / out, dpi=DPI)
    plt.close(fig)


def unions_whisker(out):
    fig = plt.figure(figsize=(BODY[0] * 0.58, BODY[1]), dpi=DPI)
    ax = fig.add_axes([0.25, 0.17, 0.72, 0.80])
    rows = [(n, v, l, h, INK) for n, v, l, h in STAGE3] + \
           [(n, v, l, h, col) for (n, v, l, h), col in zip(UNIONS, [ORANGE, TEAL])]
    whisker(ax, rows, (0.70, 0.98), ms=26)
    ax.axhline(len(STAGE3) - 0.5, color=RULE, lw=3, ls=":")
    ax.set_xticks([0.75, 0.85, 0.95])
    fig.savefig(IMAGES / out, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    landscape(TALKS + "des_y6_footprints.png", "s8_consensus.png")
    landscape(TALKS + "des_y6_footprints_unions.png", "s8_north.png")
    unions_whisker("s8_unions.png")
