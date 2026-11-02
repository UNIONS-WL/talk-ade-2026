# /// script
# dependencies = ["matplotlib", "numpy", "mocpy", "astropy", "pillow", "fonttools", "brotli"]
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


def load_masks(dr1=None):
    """Shared equatorial geometry and physical gates for maps and globes."""
    masks = {name:moc_mask(name) for name in ["des", "kids", "lsst"]}
    if dr1:
        masks["euclid_dr1"] = MOC.from_fits(dr1).contains_lonlat(RA.ravel()*u.deg, DEC.ravel()*u.deg).reshape(RA.shape)
    wide_product = np.load(DATA / "euclid_wide.npz")
    assert np.array_equal(wide_product['ra_deg'],RA[0]), 'Euclid RA axis must run 360→0'
    assert np.array_equal(wide_product['dec_deg'],DEC[:,0]), 'Euclid Dec axis must run −90→+90'
    masks.update(unions=unions_mask(), hsc_y3=hsc_mask(), euclid_wide=wide_product['mask'])
    weights = np.cos(Y[:,:-1])*.25**2
    wide = masks['euclid_wide'][:,:-1]
    area = np.sum(wide*weights)
    reference_area = json.loads((DATA/'euclid_wide_source.json').read_text())['published_reference_area_deg2']
    assert abs(area/reference_area-1) < .05, ('Euclid Wide area',area,reference_area)
    b = SkyCoord(RA*u.deg,DEC*u.deg).galactic.b.deg[:,:-1]
    low_lat_area = np.sum(wide*(np.abs(b)<15)*weights)
    assert low_lat_area < 5, ('Euclid Wide Galactic-plane coverage',low_lat_area)
    if dr1:
        observed = masks['euclid_dr1'][:,:-1]
        contained = np.sum(observed*wide*weights)/np.sum(observed*weights)
        # Observed VIS mosaics include non-Wide/calibration tiles; the public
        # reference and observed footprint need not have identical boundaries.
        assert contained >= .95, ('DR1 contained in Wide',contained)
        print(f'Euclid DR1 containment: {contained:.4%}')
    print(f'Euclid Wide: {area:.1f} deg2; |b|<15: {low_lat_area:.2f} deg2')
    return masks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dr1", type=Path, help="Authorized observed DR1 MOC, kept outside tracked data")
    parser.add_argument("--output-dir", type=Path, default=IMAGES)
    parser.add_argument("--projection", choices=['mollweide','mercator'], default='mollweide')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    setup()
    plt.rcParams.update({"font.size":48, "axes.linewidth":1.4})
    coords = SkyCoord(RA*u.deg, DEC*u.deg, frame="icrs")
    galactic = np.abs(coords.galactic.b.deg) < 10
    masks = load_masks(args.dr1)
    # These broad coverage checks reject a planned HSC map or an intermediate-year
    # Stage IV map substituted for the products documented beside the inputs.
    area_ranges = {"des":(4800,5500), "kids":(800,1000), "hsc_y3":(350,650),
                   "lsst":(17000,19000), "euclid_wide":(12500,16000),
                   "euclid_dr1":(2300,2400), "unions":(5000,6500)}
    for name, mask in masks.items():
        assert mask.shape == RA.shape, (name, mask.shape)
        area = np.sum(mask[:,:-1]*np.cos(Y[:,:-1]))*.25**2
        low, high = area_ranges[name]
        assert low < area < high, (name, area, area_ranges[name])
        print(f"{name}: raster coverage {area:.1f} deg2")
    for unions in [False, True]:
        fig = plt.figure(figsize=(23.62,15.42), dpi=100)
        mercator = args.projection == 'mercator'
        if mercator:
            ax = fig.add_axes([.055,.32,.90,.66])
            px = X
            py = np.log(np.tan(np.pi/4+np.radians(np.clip(DEC,-85,85))/2))
            ax.set_ylim(-2.44,2.44)  # Declinations −80° to +80°.
            ax.set_xlim(-np.pi,np.pi)
        else:
            ax = fig.add_axes([.055,.32,.90,.66], projection="mollweide")
            px,py = X,Y
        ax.contourf(px,py,galactic.astype(float),levels=[.5,1.5],colors=["#EAE6DE"],antialiased=False)
        for name, color in [("des",COBALT),("kids",TEAL),("hsc_y3",ORANGE)]+([("unions",PURPLE)] if unions else []):
            if name in masks:
                ax.contourf(px,py,masks[name].astype(float),levels=[.5,1.5],colors=[color],alpha=.78,antialiased=False)
        for name,color,lw in [("lsst",MUTED,3.8),("euclid_wide",YELLOW,4.5),("euclid_dr1",ORANGE,3.2)]:
            if name in masks:
                ax.contour(px,py,masks[name].astype(float),levels=[.5],colors=[color],linewidths=lw,linestyles="--")
        ax.set_xticks(np.radians([-120,-60,0,60,120]),["300°","240°","180°","120°","60°"])
        lat_ticks = np.radians([-60,-30,0,30,60])
        ax.set_yticks(np.log(np.tan(np.pi/4+lat_ticks/2)) if mercator else lat_ticks,["−60°","−30°","0°","30°","60°"])
        ax.tick_params(axis="both",labelsize=48,pad=16,length=0)
        ax.grid(color="#B8B1A3",alpha=.4,lw=1.2)
        for spine in ax.spines.values():
            spine.set_color("#B8B1A3")
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
        if mercator:
            stem += '_mercator'
        fig.savefig(args.output_dir / (stem + ("" if args.dr1 else "_nodr1") + ".png"),dpi=100)
        plt.close(fig)

if __name__ == "__main__":
    main()
