"""Shared figure style for this deck: EB Garamond, the unions theme palette, slide sizes.

Figures are drawn at 2x the slide body box (1712 x 771 px -> 3424 x 1542) with
fonts >= 64 px in the PNG, so they display at >= 32 px.
"""
from pathlib import Path
import matplotlib as mpl
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMAGES = ROOT / "images"

INK, MUTED, RULE = "#15171A", "#5D625F", "#D3C9B5"
ORANGE, TEAL, YELLOW, COBALT = "#A9461A", "#2F7465", "#C89A1E", "#2B4C7E"
BINS = [COBALT, TEAL, YELLOW, ORANGE]
DPI = 100
BODY = (34.24, 15.42)  # inches at DPI=100 -> 3424 x 1542 px


def setup():
    woff = ROOT / "node_modules/@fontsource-variable/eb-garamond/files/eb-garamond-latin-wght-normal.woff2"
    ttf = HERE / ".cache" / "EBGaramond.ttf"
    if not ttf.exists():
        from fontTools.ttLib import TTFont
        ttf.parent.mkdir(exist_ok=True)
        f = TTFont(str(woff)); f.flavor = None; f.save(str(ttf))
    font_manager.fontManager.addfont(str(ttf))
    name = font_manager.FontProperties(fname=str(ttf)).get_name()
    mpl.rcParams.update({
        "font.family": name, "mathtext.fontset": "custom",
        "mathtext.rm": name, "mathtext.it": f"{name}:italic", "mathtext.bf": f"{name}:bold",
        "font.size": 64, "axes.linewidth": 3, "axes.edgecolor": INK, "axes.labelcolor": INK,
        "xtick.color": INK, "ytick.color": INK, "text.color": INK,
        "xtick.major.width": 3, "ytick.major.width": 3, "xtick.major.size": 14, "ytick.major.size": 14,
        "xtick.minor.size": 7, "ytick.minor.size": 7, "xtick.minor.width": 2, "ytick.minor.width": 2,
        "axes.spines.top": False, "axes.spines.right": False,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })
    return name
