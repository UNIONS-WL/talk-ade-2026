#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "healpy", "astropy", "scipy"]
# ///
"""Euclid Wide footprint from ESA's planned-survey pointing list (RSD_2026A).

ESA publishes the full mission timeline as `rsd2026a.txt`
(https://www.cosmos.esa.int/web/euclid/where-is-euclid-observing). Each POINTING
record carries the four corners of the field in *ecliptic* longitude/latitude
(J2000): read that way, no Wide field lies within 15 deg of the Galactic plane or
10 deg of the ecliptic, as the survey design requires.

The Wide footprint is every pointing tagged WIDE, INFILL-*, NORTH-CAP-* or
SOUTH-CAP-*, rasterised in ecliptic HEALPix and sampled onto the ICRS grid of
footprints.py. Holes under 5 deg² (seams between adjacent pointings) are filled
so the outline traces the survey, not its tiling. Writes euclid_wide.npz and euclid_wide_source.json beside this file.
"""
import hashlib, json, urllib.request
from pathlib import Path

import astropy.units as u
import healpy as hp
import numpy as np
from astropy.coordinates import SkyCoord
from scipy.ndimage import label

URL = "https://www.cosmos.esa.int/documents/10647/20498717/rsd2026a.txt"
HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / ".cache" / "rsd2026a.txt"
NSIDE = 1024
TAGS = ("WIDE", "INFILL", "NORTH-CAP", "SOUTH-CAP")

if not CACHE.exists():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, CACHE)

ecl = np.zeros(hp.nside2npix(NSIDE), bool)
fields = area = 0.0
for line in open(CACHE):
    f = line.split()
    if not line.startswith("POINTING") or not f[1].startswith(TAGS):
        continue
    corners = np.array(f[18:26], float).reshape(4, 2)
    ecl[hp.query_polygon(NSIDE, hp.ang2vec(corners[:, 0], corners[:, 1], lonlat=True), inclusive=True)] = True
    if f[7] == "0":
        fields += 1
        area += float(f[26])

ra, dec = np.linspace(360, 0, 1441), np.linspace(-90, 90, 721)
RA, DEC = np.meshgrid(ra, dec)
e = SkyCoord(RA * u.deg, DEC * u.deg, frame="icrs").barycentricmeanecliptic
mask = ecl[hp.ang2pix(NSIDE, e.lon.deg, e.lat.deg, lonlat=True)]
holes, n = label(~mask)
pix_area = np.cos(np.radians(DEC)) * 0.25**2
hole_area = np.bincount(holes.ravel(), pix_area.ravel(), n + 1)
mask |= (holes > 0) & (hole_area[holes] < 5)
np.savez_compressed(HERE / "euclid_wide.npz", ra_deg=ra, dec_deg=dec, mask=mask)

(HERE / "euclid_wide_source.json").write_text(json.dumps({
    "source": "ESA Euclid reference survey RSD_2026A pointing list (rsd2026a.txt)",
    "source_url": URL,
    "source_sha256": hashlib.sha256(CACHE.read_bytes()).hexdigest(),
    "frame": "corner coordinates are ecliptic J2000 longitude/latitude",
    "tags": list(TAGS),
    "fields": int(fields),
    "published_reference_area_deg2": round(area, 1),
    "interpretation": "Planned Wide-survey pointings for visualization; not an as-built science mask.",
}, indent=2) + "\n")
print(f"{int(fields)} fields, {area:.0f} deg2 from the file's per-field areas")
