# /// script
# dependencies = ["matplotlib", "numpy", "fonttools", "brotli"]
# ///
"""images/nz_v2.png: the working four-bin n(z) of the v2 bound-9 catalogue.

Each bin is drawn as its share of the retained shear weight, so the four
curves stack to the full tomographic sample's n(z) (ink outline). Source:
analyses/shear_tomographic/nz_v2_full/products/nz_v2_bound9_full_tomo.txt
(full area, both z filters; columns integrate to retained weight fractions).
"""
import numpy as np
import matplotlib.pyplot as plt
from _style import *

setup()
SRC = "/n17data/cdaley/unions/analyses/shear_tomographic/nz_v2_full/products/nz_v2_bound9_full_tomo.txt"
a = np.loadtxt(SRC)
z, nz = a[:, 0], a[:, 1:]
k = np.exp(-0.5 * (np.arange(-3, 4) / 1.2) ** 2); k /= k.sum()   # light smoothing (dz = 0.01)
nz = np.array([np.convolve(c, k, mode="same") for c in nz.T]).T
means = (z[:, None] * nz).sum(0) / nz.sum(0)

fig = plt.figure(figsize=(BODY[0] * 0.62, BODY[1]), dpi=DPI)
ax = fig.add_axes([0.07, 0.19, 0.91, 0.78])
for i in range(4):
    ax.fill_between(z, nz[:, i], color=BINS[i], alpha=0.22, lw=0)
    ax.plot(z, nz[:, i], color=BINS[i], lw=6)
    j = np.argmax(nz[:, i])
    ax.text(z[j], nz.sum(1)[max(j - 3, 0):j + 4].max() + 0.04 * nz.sum(1).max(), f"{i + 1}", color=BINS[i], ha="center", va="bottom", fontsize=72)
ax.plot(z, nz.sum(1), color=INK, lw=4, ls=(0, (4, 2)))
ax.set_xlim(0, 1.5)
ax.set_ylim(0, nz.sum(1).max() * 1.18)
ax.set_xticks([0, 0.4, 0.8, 1.2])
ax.set_yticks([])
ax.spines["left"].set_visible(False)
ax.set_xlabel(r"redshift $z$", labelpad=10)
fig.savefig(IMAGES / "nz_v2.png", dpi=DPI)
print("means", means.round(3))
