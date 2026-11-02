#!/usr/bin/env python3
# /// script
# dependencies = ["numpy", "pillow", "scipy", "astropy"]
# ///
"""Reproduce the public ESA Euclid Wide Galactic reference-survey mask.

The published PNG places a Galactic Mollweide sky image inside a black oval.
This script fits that frame, samples the blue overlay in Galactic coordinates,
transforms it to a regular ICRS grid, and reports area/latitude checks.
The output is a talk-map proxy, not a science mask.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from PIL import Image
from scipy.optimize import least_squares
from astropy.coordinates import SkyCoord
from astropy import units as u

OUT = Path(__file__).resolve().parent / 'euclid_wide'
PUBLISHED_AREA = 13345.0
ENVELOPE_RADIUS_DEG = .5


def dilate(mask, dec_deg, radius_deg):
    """Great-circle dilation on a periodic RA grid without a duplicate seam."""
    dec = np.radians(dec_deg)
    nrow, ncol = mask.shape
    out = np.zeros_like(mask)
    reach = int(np.ceil(radius_deg/.25))
    sin_dec, cos_dec = np.sin(dec), np.cos(dec)
    cos_radius = np.cos(np.radians(radius_deg))
    for j in range(nrow):
        for i in range(max(0,j-reach), min(nrow,j+reach+1)):
            denominator = cos_dec[j]*cos_dec[i]
            if denominator < 1e-14:
                dx = ncol//2
            else:
                cosine = (cos_radius-sin_dec[j]*sin_dec[i])/denominator
                dx = int(np.floor(np.arccos(np.clip(cosine,-1,1))/np.radians(.25)+1e-10))
                dx = min(dx,ncol//2)
            if dx == ncol//2:
                out[j] |= np.any(mask[i])
            else:
                for shift in range(-dx,dx+1):
                    out[j] |= np.roll(mask[i],shift)
    return out


def presentation_envelope(raw, dec_deg):
    """Close photographic pinholes then remove isolated color detections."""
    def grow(mask):
        return dilate(mask, dec_deg, ENVELOPE_RADIUS_DEG)
    mask = raw[:,:-1]
    closed = ~grow(~grow(mask))
    opened = grow(~grow(~closed))
    return np.column_stack([opened,opened[:,0]])


def fit_mollweide_frame(image):
    height, width = image.shape[:2]
    points = []
    for y in range(30, 1700):
        x = np.flatnonzero(np.all(image[y] < 20, axis=1))
        left, right = x[x < width // 2], x[x >= width // 2]
        if len(left) and len(right) and left[0] < 500 and right[-1] > 2800:
            points.extend(((float(left[0]), float(y), -1.),
                           (float(right[-1]), float(y), 1.)))
    points = np.asarray(points)
    def residual(params):
        cx, cy, rx, ry = params
        x, y, side = points.T
        yy = (y - cy) / ry
        return x - (cx + side * rx * np.sqrt(np.clip(1 - yy * yy, 0, 1)))
    fit = least_squares(residual, (1680, 866, 1580, 790),
                        loss='soft_l1', f_scale=1.)
    return fit.x, float(np.sqrt(np.mean(residual(fit.x) ** 2))), len(points)


def mollweide_theta(latitude_deg):
    phi = np.deg2rad(latitude_deg)
    theta = phi.copy()
    for _ in range(12):
        denominator = 2 + 2 * np.cos(2 * theta)
        delta = np.divide(2 * theta + np.sin(2 * theta) - np.pi * np.sin(phi),
                          denominator, out=np.zeros_like(theta),
                          where=np.abs(denominator) > 1e-10)
        theta -= delta
    return theta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='ESA ReferenceSurveyGAL PNG downloaded from the source URL in the metadata')
    args = parser.parse_args()
    image = np.asarray(Image.open(args.source).convert('RGB')).astype(np.int16)
    (cx, cy, rx, ry), frame_rms, nframe = fit_mollweide_frame(image)
    ra, dec = np.meshgrid(360 - np.arange(1441) * .25,
                          np.linspace(-90, 90, 721))
    coords = SkyCoord(ra * u.deg, dec * u.deg, frame='icrs')
    galactic = coords.galactic
    longitude = galactic.l.to_value(u.deg)
    latitude = galactic.b.to_value(u.deg)
    # The central bulge is at image center (l=0); Galactic longitude increases
    # toward image-left.
    lam = (longitude + 180) % 360 - 180
    theta = mollweide_theta(latitude)
    x = cx - rx * (lam / 180) * np.cos(theta)
    y = cy - ry * np.sin(theta)
    xi = np.clip(np.rint(x).astype(int), 0, image.shape[1] - 1)
    yi = np.clip(np.rint(y).astype(int), 0, image.shape[0] - 1)
    rgb = image[yi, xi]
    red, green, blue = (rgb[..., i] for i in range(3))
    # The ESA overlay's blue-white color has a large B-G contrast. Requiring
    # low R/G rejects the photographic Milky Way and stars with similar blue hue.
    raw_mask = ((red < 55) & (red < .70 * green) & (blue - green > 18) &
            (blue > 1.2 * green) & (green > 24))
    mask = presentation_envelope(raw_mask,dec[:,0])

    weights = np.cos(np.deg2rad(dec[:, :-1])) * .25 ** 2
    wide = mask[:, :-1]
    area = float(np.sum(wide * weights))
    low15 = float(np.sum(wide * (np.abs(latitude[:, :-1]) < 15) * weights))

    np.savez_compressed(str(OUT) + '.npz', mask=mask, raw_mask=raw_mask,
                        ra_deg=ra[0], dec_deg=dec[:, 0])
    result = {
        'source': 'ESA Euclid Wide and Deep Survey, Galactic Mollweide reference-survey graphic, version 65',
        'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
        'source_url': 'https://www.cosmos.esa.int/documents/10647/2199742/EuclidWideRegionOfInterest.65.MollweideReferenceSurveyGAL.MOL.Logos.png',
        'interpretation': 'Digitized public reference-survey graphic for visualization; not an as-built science mask.',
        'published_reference_area_deg2': PUBLISHED_AREA,
        'digitized_area_deg2': round(area, 1),
        'raw_color_selection_area_deg2': round(float(np.sum(raw_mask[:,:-1]*weights)),1),
        'presentation_envelope': 'Great-circle binary close then open at fixed radius 0.5 deg; periodic RA; photographic pinholes and isolated detections suppressed, broad gaps retained.',
        'fraction_of_published_area': round(area / PUBLISHED_AREA, 5),
        'galactic_abs_b_lt_15_area_deg2': round(low15, 2),
        'frame_fit': {
            'method': 'robust least-squares ellipse fit to the outer black oval scanline endpoints',
            'center_x_px': round(float(cx), 3), 'center_y_px': round(float(cy), 3),
            'semi_major_x_px': round(float(rx), 3), 'semi_minor_y_px': round(float(ry), 3),
            'ellipse_ratio': round(float(rx / ry), 6),
            'rms_edge_residual_px': round(frame_rms, 3),
            'fitted_edge_points': nframe,
            'longitude_center_deg': 0.0,
            'longitude_increases': 'toward image-left',
            'latitude_positive': 'toward image-top',
        },
        'pixel_selection': {
            'rule': 'R<55, R<0.70*G, B-G>18, B>1.2*G, G>24',
            'reason': 'blue/teal survey fill versus photographic sky; threshold remains image-calibrated and area is reported without rescaling',
            'grid': 'ICRS RA 360..0 deg and Dec -90..+90 deg at 0.25 deg; shape 721x1441, with duplicate RA seam column',
        },
    }
    (OUT.parent/'euclid_wide_source.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
