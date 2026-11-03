# /// script
# dependencies = ["matplotlib", "numpy", "pymupdf", "fonttools", "brotli"]
# ///
"""Paper III Figure 1 (Goh+2026 best-fit xi_pm) with Paper II pure B-modes (Daley+2026) overlaid.

images/paper3_xipm_bmodes.png

Paper III's arrays (data, diagonal errors, best fit, best-fit xi_sys) are read from the
vector content of its Figure 1 PDF: axes registered on the 12'/83' scale-cut edges (x, log)
and the zero line plus y tick-label spacing (y). Both papers use the same 20 log bins over
1-250 arcmin. The B-modes and their errors (diagonal of the MC pure-mode covariance) come
from the bmodes Lightcone baseline, the input of pure_eb.pure_eb_data_vector_figure.
"""
import matplotlib.pyplot as plt
import numpy as np
import pymupdf
from _style import *

P3 = "/n17data/cdaley/unions/analyses/shear_2d/unions_release/unions_2d_shear_xi/Figures/best_fit_xipm_SP_v1.4.6.3_B.pdf"
P2 = "/n17data/cdaley/unions/analyses/shear_2d/bmodes_2d/pure_eb/results/baseline/pure_eb/pure_eb_semianalytic_data.npz"
CUT = (12.0, 83.0)
B_COLOR = TEAL


def paper3_arrays():
    """Panel arrays in data units (theta [arcmin], theta*xi*1e4) from the Figure 1 PDF."""
    page = pymupdf.open(P3)[0]
    words = page.get_text("words")
    draws = page.get_drawings()
    legend = next(d["rect"] for d in draws if d["type"] == "fs" and d["color"] and 0.7 < d["color"][0] < 0.9)
    grey = [d["rect"] for d in draws if d["type"] == "f" and d["fill"] and 0.4 < d["fill"][0] < 0.6]
    panels = []
    for x0, x1 in [(0, 730), (730, 1430)]:
        inside = lambda x: x0 < x < x1
        g = sorted([r for r in grey if inside(r.x1)], key=lambda r: r.x1)
        px12, px83 = g[0].x1, g[1].x0                     # edges of the two shaded scale-cut regions
        b = (px83 - px12) / np.log10(CUT[1] / CUT[0])
        theta = lambda px: 10 ** ((np.asarray(px) - px12) / b + np.log10(CUT[0]))
        zero = next(d["items"][0][1].y for d in draws if d["type"] == "s" and d.get("dashes", "").startswith("[ 5")
                    and inside(d["rect"].x0 + 1))
        ticks = sorted((w[1] + w[3]) / 2 for w in words if inside(w[0]) and w[4] in ("0.0", "0.2") and w[0] < x0 + 70)
        scale = 0.2 / (ticks[1] - ticks[0])               # tick-label spacing per 0.2 (labels 0.2 above 0.0)
        y = lambda py: (zero - np.asarray(py)) * scale
        marks = sorted(((d["rect"].x0 + d["rect"].x1) / 2, (d["rect"].y0 + d["rect"].y1) / 2) for d in draws
                       if d["type"] == "fs" and len(d["items"]) == 8 and inside(d["rect"].x0))
        bars = {round(d["rect"].x0, 1): d["rect"].height / 2 for d in draws
                if d["type"] == "s" and d.get("width") == 1.5 and not d.get("dashes", "").startswith("[ 5") and inside(d["rect"].x0)}
        marks = [m for m in marks if round(m[0], 1) in bars and not legend.contains(pymupdf.Point(*m))]
        mx, my = np.array(marks).T
        curves = {}
        for d in draws:
            if d["type"] == "s" and d["color"] and d["color"][0] == 1 and len(d["items"]) > 5 and inside(d["rect"].x0):
                pts = np.array([(it[1].x, it[1].y) for it in d["items"]] + [(d["items"][-1][2].x, d["items"][-1][2].y)])
                key = "fit" if d["color"][1] > 0.5 else "sys"
                curves[key] = (theta(pts[:, 0]), y(pts[:, 1]))
        panels.append(dict(theta=theta(mx), y=y(my), err=np.array([bars[round(x, 1)] for x in mx]) * scale, **curves))
    return panels


def main():
    setup()
    plt.rcParams.update({"font.size": 40, "xtick.major.size": 10, "ytick.major.size": 10,
                         "xtick.major.width": 2.5, "ytick.major.width": 2.5, "axes.linewidth": 2.5})
    p3 = paper3_arrays()
    eb = np.load(P2)
    th = eb["theta"]
    n = len(th)
    cov = eb["cov_pure_eb"]
    sig = lambda k: np.sqrt(np.diag(cov[k * n:(k + 1) * n, k * n:(k + 1) * n]))
    bmodes = [(eb["xip_B"], sig(2)), (eb["xim_B"], sig(3))]

    fig, axes = plt.subplots(1, 2, figsize=(24, 9.6), dpi=DPI)
    for i, (ax, p, (xb, sb), name) in enumerate(zip(axes, p3, bmodes, [r"$\xi_+$", r"$\xi_-$"])):
        print(f"{name}: P3 theta vs P2 theta max rel diff {np.max(np.abs(p['theta'] / th - 1)):.4f}")
        tot = eb["xip_total" if i == 0 else "xim_total"] * th * 1e4
        print(f"  P3 data - P2 total (theta xi 1e4): max |diff| {np.max(np.abs(p['y'] - tot)):.3f}")
        ax.axvspan(0.5, CUT[0], color="0.9", lw=0, zorder=0)
        ax.axvspan(CUT[1], 400, color="0.9", lw=0, zorder=0)
        ax.axhline(0, color=MUTED, ls="--", lw=2, zorder=1)
        ax.plot(*p["fit"], color="orange", lw=4, zorder=3, label=r"best fit $\xi_\pm$ (Goh+2026)")
        ax.plot(*p["sys"], color="red", lw=3, zorder=3, label=r"best-fit $\xi^{\rm sys}_\pm$ (PSF leakage)")
        ax.errorbar(p["theta"] * 0.97, p["y"], p["err"], fmt="o", color=INK, ms=9, lw=2.5, zorder=4,
                    label="UNIONS-3500 data")
        ax.errorbar(th * 1.03, th * xb * 1e4, th * sb * 1e4, fmt="D", color=B_COLOR, ms=9, lw=2.5, zorder=5,
                    label=r"B-modes $\xi^B_\pm$ (Daley+2026)")
        ax.set_xscale("log")
        ax.set_xlim(0.9, 275)
        ax.set_xlabel(r"$\theta$ [arcmin]")
        ax.text(0.04, 0.95, name, transform=ax.transAxes, va="top", fontsize=52)
    axes[0].set_ylabel(r"$\theta\,\xi\ \times 10^4$")
    axes[0].set_ylim(-0.3, 1.3)
    axes[1].set_ylim(-0.3, 1.15)
    fig.tight_layout(w_pad=2, rect=(0, 0, 1, 0.88))
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=4, frameon=False,
               fontsize=32, handletextpad=0.4, columnspacing=1.6)
    out = IMAGES / "paper3_xipm_bmodes.png"
    fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main()
