# /// script
# dependencies = ["matplotlib", "numpy", "pillow", "fonttools", "brotli"]
# ///
"""S8 landscape frames, all on one canvas.

images/s8_consensus.png  Stage III S8 whisker beside the survey footprint map (no UNIONS)
images/s8_north.png      the same with the UNIONS DR6 footprint on the map
images/s8_unions.png     the whisker alone, wide, with the two published UNIONS results

Stage III and CMB values as in Cail's Moriond 2026 deck; UNIONS values are the
published ones: Goh+2026 xi_pm 0.831 +0.067 -0.078, Guerrini+2026 C_ell 0.891 +0.057 -0.084.
"""
import matplotlib.pyplot as plt
import argparse
import numpy as np
from PIL import Image
from _style import *

setup()
STAGE3 = [("KiDS-1000", 0.759, 0.021, 0.024), ("DES Y3", 0.759, 0.023, 0.025), ("HSC Y3", 0.769, 0.034, 0.031),
          ("KiDS-Legacy", 0.815, 0.021, 0.016), ("DES Y6", 0.798, 0.015, 0.014)]
UNIONS = [(r"UNIONS $\xi_\pm$", 0.831, 0.078, 0.067), (r"UNIONS $C_\ell$", 0.891, 0.084, 0.057)]
CMB = (0.836, 0.013, 0.012)


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
    ax.text(c - lo - 0.004, -0.95, "CMB", ha="right", va="center", fontsize=60, color=ORANGE)
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


def stage3_whisker():
    """Portrait comparison for the rotating survey globe, at slide text size."""
    with plt.rc_context({'font.size':72}):
        fig = plt.figure(figsize=(11.5, 16.4), dpi=DPI)
        ax = fig.add_axes([0.51, 0.22, 0.46, 0.72])
        whisker(ax, [(n,v,l,h,INK) for n,v,l,h in STAGE3], (0.715,0.87))
        ax.texts[0].set_fontsize(72)
        ax.set_xticks([0.75,0.85])
        fig.canvas.draw()
        for text in [*ax.get_yticklabels(), *ax.get_xticklabels(), ax.xaxis.label, *ax.texts]:
            box = text.get_window_extent(fig.canvas.get_renderer())
            assert 0 <= box.x0 and box.x1 <= fig.bbox.width and 0 <= box.y0 and box.y1 <= fig.bbox.height, (text.get_text(), box)
        fig.savefig(IMAGES/'s8_stage3.png', dpi=DPI)
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-dr1", action="store_true", help="Use the public-only footprint variants")
    args = parser.parse_args()
    stage3_whisker()
    suffix = "_nodr1" if args.no_dr1 else ""
    landscape(IMAGES / f"footprints{suffix}.png", "s8_consensus.png")
    landscape(IMAGES / f"footprints_unions{suffix}.png", "s8_north.png")
    unions_whisker("s8_unions.png")
