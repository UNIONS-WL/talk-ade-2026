# /// script
# dependencies = ["matplotlib", "numpy", "mocpy", "astropy", "pillow", "fonttools", "brotli", "scipy"]
# ///
"""Survey coverage on the equatorial sky; provenance in data/footprints/README.md."""
import json
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from astropy.coordinates import SkyCoord
from astropy import units as u
from mocpy import MOC
from scipy.ndimage import label
from _style import setup, IMAGES, COBALT, TEAL, ORANGE, YELLOW, MUTED

DATA = Path(__file__).parent / "data" / "footprints"
PURPLE = "#76519A"
# A regular grid preserves the same sampling and canvas in both variants.
RA, DEC = np.meshgrid(np.linspace(360, 0, 1441), np.linspace(-90, 90, 721))
X, Y = np.radians(180 - RA), np.radians(DEC)


def moc_mask(name):
    return MOC.from_fits(DATA / f"{name}.fits").contains_lonlat(RA.ravel()*u.deg, DEC.ravel()*u.deg).reshape(RA.shape)


def unions_mask():
    """Union of half-degree DR6 tile rectangles using ShapePipe's tile convention."""
    status = json.loads((DATA / "unions_dr6_status.json").read_text())
    ids = sorted({t for group in status["tiles"].values() for t in group})
    assert len(ids) == status["dr6_tiles"]
    mask = np.zeros(RA.shape, bool)
    area = 0.
    for tile in ids:
        a, b = map(int, tile.split("."))
        dec = b/2 - 90
        ra = a/(2*np.cos(np.radians(dec)))
        hw = .25/np.cos(np.radians(dec))
        rows = np.flatnonzero(np.abs(DEC[:,0]-dec) <= .25)
        cols = np.flatnonzero(np.abs((RA[0]-ra+180)%360-180) <= hw)
        mask[np.ix_(rows,cols)] = True
        area += np.radians(2*hw)*(np.sin(np.radians(dec+.25))-np.sin(np.radians(dec-.25)))*(180/np.pi)**2
    print(f"UNIONS: {len(ids)} tiles; summed tile area {area:.1f} deg2")
    return mask


def hsc_mask():
    return np.load(DATA / "hsc_y3.npz")["mask"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dr1", type=Path, help="Authorized observed DR1 MOC, kept outside tracked data")
    parser.add_argument("--output-dir", type=Path, default=IMAGES)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    setup()
    plt.rcParams.update({"font.size":48, "axes.linewidth":1.4})
    coords = SkyCoord(RA*u.deg, DEC*u.deg, frame="icrs")
    galactic = np.abs(coords.galactic.b.deg) < 10
    masks = {name:moc_mask(name) for name in ["des", "kids", "lsst"]}
    if args.dr1:
        masks["euclid_dr1"] = MOC.from_fits(args.dr1).contains_lonlat(RA.ravel()*u.deg, DEC.ravel()*u.deg).reshape(RA.shape)
    masks["unions"] = unions_mask()
    masks["hsc_y3"] = hsc_mask()
    masks["euclid_wide"] = np.load(DATA / "euclid_wide.npz")["mask"]
    # Remove isolated raster specks from the published background image.
    components, count = label(masks["euclid_wide"])
    areas = np.bincount(components.ravel(), weights=np.cos(Y).ravel())*.25**2
    keep = areas > 25
    keep[0] = False
    masks["euclid_wide"] = keep[components]
    # These broad coverage checks reject a planned HSC map or an intermediate-year
    # Stage IV map substituted for the products documented beside the inputs.
    area_ranges = {"des":(4800,5500), "kids":(800,1000), "hsc_y3":(350,650),
                   "lsst":(17000,19000), "euclid_wide":(14000,16000),
                   "euclid_dr1":(2300,2400), "unions":(5000,6500)}
    for name, mask in masks.items():
        assert mask.shape == RA.shape, (name, mask.shape)
        area = np.sum(mask[:,:-1]*np.cos(Y[:,:-1]))*.25**2
        low, high = area_ranges[name]
        assert low < area < high, (name, area, area_ranges[name])
        print(f"{name}: raster coverage {area:.1f} deg2")
    for unions in [False, True]:
        fig = plt.figure(figsize=(23.62,15.42), dpi=100)
        ax = fig.add_axes([.055,.32,.90,.66], projection="mollweide")
        ax.contourf(X,Y,galactic.astype(float),levels=[.5,1.5],colors=["#EAE6DE"],antialiased=False)
        for name, color in [("des",COBALT),("kids",TEAL),("hsc_y3",ORANGE)]+([("unions",PURPLE)] if unions else []):
            if name in masks:
                ax.contourf(X,Y,masks[name].astype(float),levels=[.5,1.5],colors=[color],alpha=.78,antialiased=False)
        for name,color,lw in [("lsst",MUTED,3.8),("euclid_wide",YELLOW,4.5),("euclid_dr1",ORANGE,3.2)]:
            if name in masks:
                ax.contour(X,Y,masks[name].astype(float),levels=[.5],colors=[color],linewidths=lw,linestyles="--")
        ax.set_xticks(np.radians([-120,-60,0,60,120]),["300°","240°","180°","120°","60°"])
        ax.set_yticks(np.radians([-60,-30,0,30,60]),["−60°","−30°","0°","30°","60°"])
        ax.tick_params(axis="both",labelsize=48,pad=16,length=0)
        ax.grid(color="#B8B1A3",alpha=.4,lw=1.2)
        ax.spines["geo"].set_color("#B8B1A3")
        handles = [Patch(facecolor=c,alpha=.78,label=n) for n,c in [("DES",COBALT),("KiDS-1000",TEAL),("HSC Y3",ORANGE)]]
        if unions:
            handles.append(Patch(facecolor=PURPLE,alpha=.78,label="UNIONS DR6"))
        else:
            handles.append(Patch(facecolor="white",edgecolor="white",label=""))
        handles += [Line2D([0],[0],color=c,lw=4,ls="--",label=n) for n,c in [("LSST WFD (final)",MUTED),("Euclid Wide (final)",YELLOW)]]
        if args.dr1:
            handles.append(Line2D([0],[0],color=ORANGE,lw=4,ls="--",label="Euclid DR1"))
        fig.legend(handles=handles,loc="lower center",bbox_to_anchor=(.52,.005),ncol=2,frameon=False,fontsize=46,handlelength=1.5,columnspacing=1.5,labelspacing=.1)
        stem = "footprints_unions" if unions else "footprints"
        fig.savefig(args.output_dir / (stem + ("" if args.dr1 else "_nodr1") + ".png"),dpi=100)
        plt.close(fig)

if __name__ == "__main__":
    main()
