#!/usr/bin/env python3
"""Digitize the RSD_2021A wide footprint from Scaramella et al. Fig. 46.

The source is a published reference realization, not an as-built final mask.
The resulting regular-grid mask is for a talk outline only, not science cuts.
Requires Ghostscript and ImageMagick's `convert`; no Python packages are used.
"""
from collections import deque
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile

SOURCE = "https://doi.org/10.1051/0004-6361/202141938"
PAPER = "Euclid Collaboration: Scaramella et al. 2022, A&A 662, A112, Fig. 46"
PUBLISHED_AREA = 14514.0
WIDTH, HEIGHT = 1323, 1871  # page 35 rendered at 160 dpi by Ghostscript
FRAME = (669.4, 456.0, 536.0, 266.0)  # centre x/y, half-width/height in that render
PALETTE = ((85,196,147),(243,104,109),(85,153,204),(248,172,106),(146,115,182),(255,246,85))
TOLERANCE = 32  # RGB distance, retaining blended survey-color pixels
CLOSING_RADIUS = 2  # source-raster pixels; closes sub-degree seams between patches


def ppm_pixels(path):
    data = Path(path).read_bytes()
    pos = 0
    def token():
        nonlocal pos
        while True:
            while data[pos] in b" \t\r\n": pos += 1
            if data[pos] == 35:
                while data[pos] not in (10,13): pos += 1
            else: break
        start = pos
        while data[pos] not in b" \t\r\n": pos += 1
        return data[start:pos]
    assert token() == b"P6", "expected raw PPM"
    width, height, maximum = map(int, (token(), token(), token()))
    while data[pos] in b" \t\r\n": pos += 1
    pixels = data[pos:]
    assert maximum == 255 and len(pixels) == width * height * 3
    return width, height, pixels


def mollweide_pixel(ra, dec):
    cx, cy, rx, ry = FRAME
    lam, phi = math.radians(180.0 - ra), math.radians(dec)
    if abs(abs(phi) - math.pi/2) < 1e-12:
        theta = math.copysign(math.pi/2, phi)
    else:
        theta = phi
        for _ in range(12):
            derivative = 2 + 2*math.cos(2*theta)
            if abs(derivative) < 1e-10: break
            delta = (2*theta + math.sin(2*theta) - math.pi*math.sin(phi)) / derivative
            theta -= delta
            if abs(delta) < 1e-12: break
    x = (2*math.sqrt(2)/math.pi) * lam * math.cos(theta)
    y = math.sqrt(2) * math.sin(theta)
    return round(cx + rx*x/(2*math.sqrt(2))), round(cy - ry*y/math.sqrt(2))


def fill_enclosed(mask, nrow, ncol):
    """Fill enclosed holes on the periodic-RA grid for a presentation outline."""
    visited = bytearray(len(mask))
    queue = deque()
    def seed(index):
        if not mask[index] and not visited[index]:
            visited[index] = 1
            queue.append(index)
    for x in range(ncol):
        seed(x); seed((nrow-1)*ncol+x)
    for y in range(nrow):
        seed(y*ncol); seed(y*ncol+ncol-1)
    while queue:
        i = queue.popleft(); y, x = divmod(i, ncol)
        for yy, xx in ((y-1,x),(y+1,x),(y,(x-1)%ncol),(y,(x+1)%ncol)):
            if 0 <= yy < nrow:
                j = yy*ncol+xx
                if not mask[j] and not visited[j]:
                    visited[j] = 1; queue.append(j)
    filled = bytearray(mask)
    for i, value in enumerate(filled):
        if not value and not visited[i]: filled[i] = 1
    return filled


def area_deg2(mask, nrow, ncol):
    total = 0.0
    for iy in range(nrow):
        dec = -90 + iy*.25
        lo, hi = max(-90,dec-.125), min(90,dec+.125)
        pixel_area = math.radians(.25)*math.radians(hi-lo)*math.cos(math.radians(dec))*(180/math.pi)**2
        total += sum(mask[iy*ncol:(iy+1)*ncol])*pixel_area
    return total


def main(pdf):
    outdir = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="euclid-rsd-") as temp:
        page = Path(temp)/"page.ppm"
        raw_mask = Path(temp)/"mask.pgm"
        closed_mask = Path(temp)/"closed.pgm"
        subprocess.run(["gs","-q","-dNOPAUSE","-dBATCH","-sDEVICE=ppmraw","-r160","-dFirstPage=35","-dLastPage=35",f"-sOutputFile={page}",str(pdf)],check=True)
        width,height,pixels = ppm_pixels(page)
        assert (width,height)==(WIDTH,HEIGHT), (width,height)
        raw = bytearray(width*height)
        tol2 = TOLERANCE*TOLERANCE
        for j in range(width*height):
            q = pixels[3*j:3*j+3]
            distance = min(sum((q[k]-color[k])**2 for k in range(3)) for color in PALETTE)
            raw[j] = 255 if distance <= tol2 else 0
        raw_mask.write_bytes(f"P5\n{width} {height}\n255\n".encode()+raw)
        subprocess.run(["convert",str(raw_mask),"-morphology",f"Close",f"Disk:{CLOSING_RADIUS}",str(closed_mask)],check=True)
        pgm = closed_mask.read_bytes(); pos = pgm.index(b"\n255\n")+5
        # The source page is sampled onto the talk renderer's 0.25-degree grid.
        nrow,ncol = 721,1441
        initial = bytearray(nrow*ncol)
        raster = pgm[pos:]
        for iy in range(nrow):
            dec = -90 + iy*.25
            for ix in range(ncol):
                ra = 360 - ix*.25
                x,y = mollweide_pixel(ra,dec)
                if 0 <= x < width and 0 <= y < height and raster[y*width+x] > 0:
                    initial[iy*ncol+ix] = 1
        # A one-degree close on the final grid joins sub-degree field seams.
        grid_raw = Path(temp)/"grid.pgm"
        grid_closed = Path(temp)/"grid-closed.pgm"
        grid_raw.write_bytes(f"P5\n{ncol} {nrow}\n255\n".encode()+bytes(255 if v else 0 for v in initial))
        subprocess.run(["convert",str(grid_raw),"-morphology","Close","Disk:4",str(grid_closed)],check=True)
        grid_data = grid_closed.read_bytes(); grid_pos = grid_data.index(b"\n255\n")+5
        initial = bytearray(1 if value else 0 for value in grid_data[grid_pos:])
        # RA=0 and RA=360 are the same meridian.
        for iy in range(nrow): initial[iy*ncol+ncol-1] = initial[iy*ncol]
        before = area_deg2(initial,nrow,ncol)
        mask = fill_enclosed(initial,nrow,ncol)
        after = area_deg2(mask,nrow,ncol)

    # NumPy-compatible boolean NPY inside NPZ, built with the standard library.
    header = f"{{'descr': '|b1', 'fortran_order': False, 'shape': ({nrow}, {ncol}), }}".encode('latin1')
    header += b' '*((16-((10+len(header)+1)%16))%16)+b'\n'
    npy = b'\x93NUMPY'+bytes([1,0])+struct.pack('<H',len(header))+header+mask
    with zipfile.ZipFile(outdir/'euclid_wide.npz','w',zipfile.ZIP_DEFLATED,6) as archive:
        archive.writestr('mask.npy',npy)
    metadata = {
        'source':PAPER,'source_url':SOURCE,
        'reference_definition':'RSD_2021A, 14,514 deg2; paper describes it as a good proxy for the final solution, not an as-built final mask.',
        'digitization':'Figure 46 page 35, Mollweide equatorial map. Six year-fill colors segmented at RGB distance <=32, closed with a 2-pixel disk in source raster and a 1-degree disk on the 0.25-degree sky grid, then sampled by inverse Mollweide.',
        'hole_treatment':'Enclosed holes are filled for an outer survey outline; this is presentation geometry, not a science mask.',
        'sampled_area_before_hole_fill_deg2':round(before,1),
        'sampled_area_after_hole_fill_deg2':round(after,1),
        'published_reference_area_deg2':PUBLISHED_AREA,
        'grid':'RA 360 to 0 deg and Dec -90 to +90 deg, 0.25 deg spacing; shape (721, 1441).',
        'frame_pixels_at_160dpi':{'center_x':FRAME[0],'center_y':FRAME[1],'half_width':FRAME[2],'half_height':FRAME[3]},
    }
    (outdir/'euclid_wide_source.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))

if __name__ == '__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: euclid_wide_digitize.py RSD_2021A_paper.pdf')
    main(sys.argv[1])
