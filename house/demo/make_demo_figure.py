# /// script
# dependencies = ["matplotlib", "numpy"]
# ///
"""Synthetic spectrum for the house demo deck: images/house_demo_spectrum.pdf (illustrative, not data)."""
import matplotlib.pyplot as plt
import numpy as np

if __name__ == "__main__":
    rng = np.random.default_rng(3)
    ell = np.geomspace(30, 2000, 18)
    model = 2e-6 * (ell / 100) ** -0.9 * np.exp(-ell / 3000)
    err = model * (0.12 + 0.25 * (ell / 2000))
    data = model + rng.normal(0, err)
    plt.rcParams.update({"font.size": 22, "axes.linewidth": 1.8, "font.family": "serif"})
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(ell, ell * model, color="#1B1611", lw=3, label="model")
    ax.errorbar(ell, ell * data, ell * err, fmt="o", ms=10, lw=2.5, capsize=0, color="#B03E32", label="mock bandpowers")
    ax.set_xscale("log")
    ax.set_xlabel(r"multipole $\ell$")
    ax.set_ylabel(r"$\ell\, C_\ell$")
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig("../../images/house_demo_spectrum.pdf")
