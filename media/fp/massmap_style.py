"""One look for the DR6 mass map, shared by the demo video and the proposal figure.

The palette is sampled from the July 2026 press globe (the Waterloo / Globe and
Mail image of the v1 map): pale cyan for underdense sky, deep blue for the
peaks. The map shown is `massmap_display.py`'s: the delivered 30′ KS map smoothed
to 60′ and rescaled to unit σ inside the footprint. No colorbar numbers are
shown: the catalogue is blinded.

    from massmap_style import colorize      # κ array (+ σ) → RGB floats in [0, 1]
"""
import numpy as np

SMOOTH_FWHM_ARCMIN = 30.0          # Gaussian smoothing of the delivered KS map
DISPLAY_FWHM_ARCMIN = 60.0         # total smoothing of the map shown (massmap_display.py)
NSIDE = 1024                       # HEALPix RING; the series and the figure use the same
LO, HI = -1.5, 3.5                 # display range in units of the shown map's σ

# low κ → high κ (pale → deep), sampled from the press globe
STOPS = ["#c7fbff", "#a4defa", "#67b1d5", "#2d8ab4", "#0d4885", "#08204f"]


def _rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)]) / 255.0


_STOPS = np.stack([_rgb(h) for h in STOPS])


def colorize(kappa, sigma_final):
    """Map κ to RGB with the shared palette; NaN stays NaN."""
    x = np.clip((np.asarray(kappa) / sigma_final - LO) / (HI - LO), 0, 1) * (len(STOPS) - 1)
    i = np.minimum(np.floor(np.nan_to_num(x)).astype(int), len(STOPS) - 2)
    f = (np.nan_to_num(x) - i)[..., None]
    rgb = _STOPS[i] * (1 - f) + _STOPS[i + 1] * f
    rgb[~np.isfinite(kappa)] = np.nan
    return rgb


def cmap():
    """The palette as a matplotlib colormap, for the proposal figure."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("unions_press", STOPS)
