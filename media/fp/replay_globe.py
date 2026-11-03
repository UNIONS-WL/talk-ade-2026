# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "scipy", "healpy", "imageio-ffmpeg"]
# ///
"""UNIONS DR6 shear-catalogue production filling in on a turning globe.

Draws its own frames in the palette and type of the production status page:
an orthographic celestial sphere textured with the Gaia EDR3 all-sky map
(galactic, transformed to equatorial). The camera faces the main footprint cap's centroid,
swings to the other cap (RA outside `MAIN_RA`) while its tiles finish, and swings back. Every DR6 tile is a pale veil until its
batch is processed and teal after. A pale line outlines the footprint throughout.
Overlays: catalogue objects so far, the date, and cumulative completed area
(deg²) against time.

Inputs (live): production/status.json (tile universe, batch timeline, latest
build) and production/tile_history.json (processed_at per tile). Tiles that
status.json counts as done but the history export lacks are timed from the
status timeline (see `time_missing`).

With `--massmap FILE` (the final full-area Kaiser–Squires κ_E map, HEALPix, in
units of its noise σ unless a `series.json` beside it gives `sigma_final`), each
tile's patch of that map replaces the bare Gaia sky as the tile finishes,
coloured with the shared press palette (`massmap_style.py`); there is no veil,
and where the map is masked the sky shows through. The outlined footprint is
then the tiles the map covers, so the last frame is the whole map filling it.

Inputs beside the script: assets/gaia_edr3_colour_equirectangular.png (ESA/Gaia/DPAC,
CC BY-SA 3.0 IGO) and assets/EBGaramond-{Regular,Medium}.otf.

    uv run replay_globe.py [--jobs 8] [--frames 0,300,600] [--massmap assets/display.fits]
    GLOBE_LAYOUT=deck uv run replay_globe.py ...   # 1200×1100 slide layout: globe over the chart, white page
    → shots/replay/dr6_globe.mp4, shots/replay/dr6_globe_sheet.jpg
"""
import argparse
import sys
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import pathlib
import subprocess
import urllib.request

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.spatial import cKDTree

BASE = "https://unions-wl.github.io/production/"
HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from massmap_style import colorize  # noqa: E402
OUT = HERE / "shots" / "replay"
ASSETS = HERE / "assets"
GAIA = ASSETS / "gaia_edr3_colour_equirectangular.png"

W, H, SS = 1920, 1080, 2           # output size, supersampling factor
FPS = 30
INTRO_S, SIM_S, HOLD_S = 0.7, 30.0, 5.0
MAIN_RA = (85.0, 295.0)            # RA span of the main cap; the tiles outside it form the other cap (deg)
SWING_S = 1.2                      # seconds for each swing between the two caps
WARP = 3.0                         # sim-clock slowdown while the other cap fills
CX, CY, R = 640, 540, 430          # globe centre and radius (output px)
PX0, PX1 = 1220, 1800              # the text column to the globe's right (output px)
CHART = (PX0, PX1, 500, 720)       # completed-area chart: x0, x1, y_top, y_bottom (output px)
DECK = os.environ.get("GLOBE_LAYOUT") == "deck"   # slide layout: globe over the chart on a white page, no text column
if DECK:
    W, H = 1200, 1100
    CX, CY, R = 600, 380, 360
    CHART = (90, 1110, 850, 1010)
TAU_H = 4.0                        # remaining→processed ease per tile (sim hours)
TILE = 0.5                         # tile side (deg)

# status-page palette
PARCH = (237, 226, 206)
PAGE = (255, 255, 255) if DECK else PARCH   # what the globe sits on
RAG = (251, 246, 233)
INK = (27, 22, 17)
MUTED = (122, 111, 92)
RULE = (197, 184, 158)
GRID = (226, 215, 192)
TEAL = (63, 130, 120)
OCHRE = (196, 147, 51)
COBALT = (61, 91, 160)
CINNABAR = (188, 69, 56)
MAP_SWATCH = (45, 138, 180)          # mid stop of the press palette (massmap_style.STOPS)
V1_AREA = 2894.0                   # first-release (v1) footprint, deg² (cat_config cov_th.A)
V1_LABEL = "first release"
CORE_YEARS = 32                    # the run's total compute, Cail's final count (status.json's corehours stop at 27 Oct)
PREVIOUS = "previous runs  >  1 year"
A_TODO, A_DONE = 0.50, 0.92        # tile opacity over the sky

OUTLINE = RAG                      # footprint outline colour
A_OUTLINE = 0.8

FONTS = {"serif": ASSETS / "EBGaramond-Regular.otf", "serif-medium": ASSETS / "EBGaramond-Medium.otf"}

# J2000 equatorial → galactic rotation
EQ2GAL = np.array([[-0.0548755604, -0.8734370902, -0.4838350155],
                   [0.4941094279, -0.4448296300, 0.7469822445],
                   [-0.8676661490, -0.1980763734, 0.4559837762]])


def font(name, px):
    return ImageFont.truetype(str(FONTS[name]), int(px * SS))


def get(name):
    return json.loads(urllib.request.urlopen(BASE + name).read())


def ts(s):
    s = s.replace("Z", "+00:00")
    if len(s) == 16:  # 'YYYY-MM-DDTHH:MM' timeline stamps, Nibi local (EDT)
        return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone(dt.timedelta(hours=-4)))
    return dt.datetime.fromisoformat(s)


def tile_radec(ids):
    """UNIONS tile ids 'xxx.yyy' → (RA, Dec) arrays in degrees."""
    xy = np.array([[int(v) for v in t.split(".")] for t in ids], float)
    dec = xy[:, 1] / 2 - 90
    return xy[:, 0] / (2 * np.cos(np.radians(dec))), dec


def unit(ra, dec):
    ra, dec = np.radians(ra), np.radians(dec)
    return np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], -1)


def cluster_of(batch):
    return batch.split("-")[0]


def time_missing(miss, hist_ids, hist_t, hist_c, timeline):
    """Processed times for done tiles absent from the history export.

    Per stream (cluster), the timeline's cumulative count minus the history's
    gives how many tiles the history lacks at each batch completion. Missing
    tiles are shared between streams in proportion to those deficits, each
    going to the nearest stream's processed area that still has room; within a
    stream they are cut into compact 25-tile patches ordered outward from the
    processed area, and each patch takes the timeline stamp at which the
    stream's deficit reaches it. Returns epoch seconds per tile.
    """
    if not miss:
        return np.zeros(0)
    pm = unit(*tile_radec(miss))
    ph = unit(*tile_radec(hist_ids))
    ev_t = np.array([ts(e[0]).timestamp() for e in timeline])
    ev_n = np.diff([0] + [e[1] for e in timeline])
    ev_c = np.array([cluster_of(e[2]) for e in timeline])
    streams = sorted(set(hist_c) & set(ev_c))
    deficits, dist = {}, {}
    for c in streams:
        tl = np.cumsum(np.where(ev_c == c, ev_n, 0))
        hs = np.sort(hist_t[hist_c == c])
        deficits[c] = np.maximum.accumulate(np.clip(tl - np.searchsorted(hs, ev_t, side="right"), 0, None))
        dist[c] = cKDTree(ph[hist_c == c]).query(pm)[0]
    total = sum(d[-1] for d in deficits.values())
    if total <= 0:  # the timeline shows nothing the history lacks: put them at its end
        return np.full(len(miss), ev_t[-1])
    quota = {c: round(len(miss) * deficits[c][-1] / total) for c in streams}
    quota[max(streams, key=lambda c: quota[c])] += len(miss) - sum(quota.values())
    # greedy: closest (tile, stream) pairs first, while the stream has room
    pairs = sorted((dist[c][k], k, c) for c in streams for k in range(len(miss)))
    stream = np.full(len(miss), "", object)
    for _, k, c in pairs:
        if not stream[k] and quota[c] > 0:
            stream[k] = c
            quota[c] -= 1
    out = np.zeros(len(miss))
    for c in streams:
        sel = np.flatnonzero(stream == c)
        if not len(sel):
            continue
        deficit = deficits[c]
        print(f"  {c}: {len(sel)} tiles timed against a timeline deficit of {deficit[-1]}")
        dsel = dist[c]
        # compact patches grown outward from the processed area
        order = sel[np.argsort(dsel[sel])]
        local = cKDTree(pm[order])
        free = np.ones(len(order), bool)
        patches = []
        for i in range(len(order)):
            if not free[i]:
                continue
            k = min(len(order), 120)
            while True:
                _, nb = local.query(pm[order[i]], k=k)
                nb = np.atleast_1d(nb)
                nb = nb[free[nb]][:25]
                if len(nb) == 25 or k == len(order) or free.sum() <= len(nb):
                    break
                k = min(len(order), k * 4)
            free[nb] = False
            patches.append(order[nb])
        done = 0
        scale = deficit[-1] / len(sel)
        for p in patches:
            done += len(p)
            j = min(np.searchsorted(deficit, done * scale - 1e-9), len(ev_t) - 1)
            out[p] = ev_t[j]
    return out


def load():
    cur, hist = get("status.json"), get("tile_history.json")
    universe = list(dict.fromkeys(x for k in cur["tiles"] for x in cur["tiles"][k]))
    assert len(universe) == cur["dr6_tiles"], (len(universe), cur["dr6_tiles"])
    done = set(cur["tiles"]["published"]) | set(cur["tiles"]["processed"])
    assert len(done) == cur["processed_tiles"], (len(done), cur["processed_tiles"])
    rows = [r for r in hist["rows"] if r[0] in done]
    hist_ids = [r[0] for r in rows]
    hist_t = np.array([ts(r[3]).timestamp() for r in rows])
    hist_c = np.array([cluster_of(r[1]) for r in rows])
    miss = sorted(done - set(hist_ids))
    miss_t = time_missing(miss, hist_ids, hist_t, hist_c, cur["timeline"])
    when = dict(zip(hist_ids, hist_t)) | dict(zip(miss, miss_t))
    t_done = np.array([when.get(t, np.inf) for t in universe])
    print(f"{len(universe)} tiles, {len(done)} done: {len(hist_ids)} from history, {len(miss)} timed from the timeline")
    return cur, universe, t_done




# ---------------------------------------------------------------- geometry

def tile_geometry(ids):
    ra, dec = tile_radec(ids)
    hw = TILE / 2 / np.cos(np.radians(dec))
    hd = TILE / 2
    # exact spherical area of each RA×Dec tile, deg²
    area = np.radians(2 * hw) * (np.sin(np.radians(dec + hd)) - np.sin(np.radians(dec - hd))) * (180 / math.pi) ** 2
    g = 1.14  # slight overlap so neighbours leave no seams
    cra = ra[:, None] + g * hw[:, None] * np.array([-1, 1, 1, -1])
    cdec = dec[:, None] + g * hd * np.array([-1, -1, 1, 1])
    return unit(ra, dec), unit(cra, cdec), area


def basis(phi, elev):
    """View direction c, screen-right r and screen-up u for the camera facing RA phi from latitude elev.

    Sky convention, as on the status page: seen from inside, RA increases to the left.
    """
    p, e = math.radians(phi), math.radians(elev)
    c = np.array([math.cos(e) * math.cos(p), math.cos(e) * math.sin(p), math.sin(e)])
    r = np.array([math.sin(p), -math.cos(p), 0.0])
    u = np.array([-math.sin(e) * math.cos(p), -math.sin(e) * math.sin(p), math.cos(e)])
    return c, r, u


def project(v, r, u):
    return (CX + R * (v @ r)) * SS, (CY - R * (v @ u)) * SS


def graticule_lines():
    lines = []
    for dec in (-60, -30, 0, 30, 60):
        ra = np.linspace(0, 360, 361)
        lines.append(unit(ra, np.full_like(ra, dec)))
    for ra in range(0, 360, 30):
        dec = np.linspace(-89, 89, 179)
        lines.append(unit(np.full_like(dec, ra), dec))
    return lines


# ---------------------------------------------------------------- static layers

def static_layers():
    """Parchment page with the globe's soft shadow, the antialiased disc mask, and the
    disc's pixel grid (output resolution) for sampling the sky."""
    w, h = W * SS, H * SS
    bg = Image.new("RGB", (w, h), PAGE)
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).ellipse(((CX - R * 0.96) * SS, (CY - R * 0.9 + 26) * SS,
                                (CX + R * 0.96) * SS, (CY + R * 1.0 + 26) * SS), fill=70)
    sh = sh.filter(ImageFilter.GaussianBlur(40 * SS))
    if not DECK:
        bg = Image.composite(Image.new("RGB", (w, h), (120, 100, 75)), bg, sh)
    big = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(big).ellipse(((CX - R) * SS * 2, (CY - R) * SS * 2, (CX + R) * SS * 2, (CY + R) * SS * 2), fill=255)
    mask = big.resize((w, h), Image.LANCZOS)
    yy, xx = np.mgrid[CY - R:CY + R + 1, CX - R:CX + R + 1].astype(np.float64)
    a, b = (xx + 0.5 - CX) / R, (CY - yy - 0.5) / R
    mu = np.sqrt(np.clip(1 - a * a - b * b, 0, 1))
    return bg, mask, (a.ravel(), b.ravel(), mu.ravel())


def load_gaia():
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(GAIA).convert("RGB")
    tex = np.asarray(im.resize((1600, 800), Image.LANCZOS), np.float32)
    grey = tex.mean(-1, keepdims=True)
    return (grey + 0.8 * (tex - grey)) * np.array([0.92, 0.89, 0.84], np.float32)   # a little warmer, a little quieter


def sky(c, r, u, t_eval=None):
    """Gaia all-sky map on the visible hemisphere: (2R+1)² RGB at output resolution, and the
    DR6 footprint there as a (2R+1)² boolean mask.

    The map is galactic plate carrée with l = 0 at the centre, increasing to the left.
    """
    a, b, mu = G["grid"]
    v = a[:, None] * r + b[:, None] * u + mu[:, None] * c
    tile = tile_of(v)
    g = v @ EQ2GAL.T
    l = np.degrees(np.arctan2(g[:, 1], g[:, 0]))
    lat = np.degrees(np.arcsin(np.clip(g[:, 2], -1, 1)))
    tex = G["gaia"]
    th, tw = tex.shape[:2]
    x = ((0.5 - l / 360) % 1) * tw - 0.5
    y = np.clip((90 - lat) / 180 * th - 0.5, 0, th - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0 %= tw
    x1 = (x0 + 1) % tw
    y1 = np.minimum(y0 + 1, th - 1)
    s = (tex[y0, x0] * (1 - fx) * (1 - fy) + tex[y0, x1] * fx * (1 - fy)
         + tex[y1, x0] * (1 - fx) * fy + tex[y1, x1] * fx * fy)
    s = (np.array([20, 20, 22], np.float32) + 0.92 * s) * (0.8 + 0.2 * mu)[:, None]   # blacks lifted to slate
    if "kappa" in G and t_eval is not None:
        rgb, alpha = massmap(v, tile, t_eval)
        alpha *= np.clip(mu / 0.08, 0, 1)
        s = s * (1 - alpha[:, None]) + 255 * rgb * (0.86 + 0.14 * mu)[:, None] * alpha[:, None]
    n = 2 * R + 1
    return np.clip(s, 0, 255).astype(np.uint8).reshape(n, n, 3), (tile >= 0).reshape(n, n)


def tile_of(v):
    """Index of the DR6 tile holding each unit vector, −1 outside the footprint.

    Tile ids are 'a.b' with Dec = b/2 − 90, RA = a / (2 cos Dec).
    """
    dec = np.degrees(np.arcsin(np.clip(v[:, 2], -1, 1)))
    ra = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 360
    b = np.clip(np.round(2 * (dec + 90)).astype(int), 0, 360)
    a = np.round(2 * ra * np.cos(np.radians(b / 2 - 90))).astype(int) % 721
    return G["tile_lut"][b, a]


def massmap(v, tile, t_eval):
    """Mass-map colour and opacity per sky pixel at time t_eval: the final map, shown where its tile
    is done; transparent where the map is masked, so the sky shows through."""
    import healpy as hp
    k = G["kappa"]
    cur = k["map"][k["lut"][hp.vec2pix(k["nside"], v[:, 0], v[:, 1], v[:, 2])]]
    p = np.where(tile >= 0, ease((t_eval - G["t_done"][np.maximum(tile, 0)]) / (TAU_H * 3600)), 0.0)
    rgb = colorize(cur, k["sigma"])
    ok = np.isfinite(rgb[:, 0])
    alpha = np.where(ok, 0.96 * p, 0.0)
    return np.nan_to_num(rgb), alpha


# ---------------------------------------------------------------- frame

def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def fmt_objects(n):
    m = n / 1e6
    return ("0" if m == 0 else f"{m:.1f}" if m < 10 else f"{m:,.0f}"), "million objects measured"


G = {}


def outline(foot):
    """Opacity of the footprint outline over the full supersampled frame: an antialiased line about
    5 px wide along the boundary of the footprint mask, with holes of a tile or so closed so
    single unmapped tiles don't get rings, fading towards the limb like the tiles."""
    n, S = 2 * R + 1, SS
    m = Image.fromarray((foot * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.MinFilter(7))
    m = np.asarray(m.resize((n * S, n * S), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2.4 * S)), np.float32) / 255
    line = np.clip(3.0 - 7.0 * np.abs(m - 0.5), 0, 1)
    mu = np.asarray(Image.fromarray(G["grid"][2].reshape(n, n).astype(np.float32)).resize((n * S, n * S), Image.BILINEAR))
    a = Image.fromarray((255 * A_OUTLINE * line * np.clip(mu / 0.08, 0, 1)).astype(np.uint8))
    full = Image.new("L", (W * S, H * S), 0)
    full.paste(a, ((CX - R) * S, (CY - R) * S))
    return full


def init(state):
    G.update(state)
    G["bg"], G["mask"], G["grid"] = static_layers()
    G["gaia"] = load_gaia()
    G["fonts"] = dict(big=font("serif", 120), unit=font("serif", 30), date=font("serif", 48),
                      tick=font("serif", 22), head=font("serif", 26), pay=font("serif-medium", 50))
    if DECK:   # drawn at twice slide size
        G["fonts"].update(date=font("serif", 36), tick=font("serif", 34), head=font("serif-medium", 38))


def render(job):
    i, t_disp, t_eval, view = job
    g, S = G, SS
    c, r, u = basis(*view)

    # sky on the sphere
    rgb, foot = sky(c, r, u, t_eval)
    disc = Image.fromarray(rgb).resize(((2 * R + 1) * S, (2 * R + 1) * S), Image.BILINEAR)
    img = g["bg"].copy()
    layer = Image.new("RGB", img.size, PAGE)
    layer.paste(disc, ((CX - R) * S, (CY - R) * S))
    img = Image.composite(layer, img, g["mask"])

    # graticule and tiles, drawn into one translucent overlay
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for line in g["grat"]:
        mu = line @ c
        x, y = project(line, r, u)
        for a in range(len(line) - 1):
            if mu[a] > 0 and mu[a + 1] > 0:
                k = min(1.0, (mu[a] + mu[a + 1]) * 2)
                d.line([(x[a], y[a]), (x[a + 1], y[a + 1])], fill=RULE + (int(70 * k),), width=S)

    p = ease((t_eval - g["t_done"]) / (TAU_H * 3600))
    mu = g["centre"] @ c
    vis = np.flatnonzero(mu > 0)
    m = mu[vis]
    pv = p[vis][:, None]
    if "kappa" not in g:   # without a map, tiles carry the progress: a veil, ochre while running, teal when done
        run = np.sin(np.pi * pv) ** 2
        col = np.array(PARCH) * (1 - pv) + np.array(TEAL) * pv
        col += (np.array(OCHRE) - col) * (0.85 * run)
        alpha = (A_TODO + (A_DONE - A_TODO) * pv[:, 0]) * np.clip(m / 0.08, 0, 1)
        col *= (0.82 + 0.18 * m)[:, None]
        rgba = np.concatenate([col, 255 * alpha[:, None]], 1).astype(int)
        xs, ys = project(g["corner"][vis], r, u)
        for k in range(len(vis)):
            d.polygon(list(zip(xs[k], ys[k])), fill=tuple(rgba[k]))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    img.paste(Image.new("RGB", img.size, OUTLINE), (0, 0), outline(foot))
    d = ImageDraw.Draw(img)
    d.ellipse(((CX - R) * S, (CY - R) * S, (CX + R) * S, (CY + R) * S), outline=MUTED, width=int(1.3 * S))

    f = g["fonts"]
    x0, x1 = PX0 * S, PX1 * S
    tl = dt.datetime.fromtimestamp(t_disp, dt.timezone.utc)
    if not DECK:
        d.text((x0, 230 * S), tl.strftime("%-d %B %Y"), font=f["date"], fill=INK, anchor="ls")
        num, unit_ = fmt_objects(g["per_tile"] * p.sum())
        d.text((x0 - 4 * S, 372 * S), num, font=f["big"], fill=INK, anchor="ls")
        d.text((x0, 414 * S), unit_, font=f["unit"], fill=MUTED, anchor="ls")

    # completed area against time: the full footprint dashed above, the first release dashed in cobalt
    cx0, cx1, cy0, cy1 = (v * S for v in CHART)
    T0, T1, A = g["t0"], g["t1"], g["area_total"]
    X = lambda t: cx0 + (cx1 - cx0) * (t - T0) / (T1 - T0)
    Y = lambda v: cy1 - (cy1 - cy0) * v / A
    if not DECK:   # the full footprint, dashed along the top
        for x in range(int(cx0), int(cx1), 9 * S):
            d.line([(x, Y(A)), (x + 3 * S, Y(A))], fill=MUTED, width=S)
    d.line([(cx0, cy1), (cx1, cy1)], fill=RULE, width=S)
    for tday, anc in ((T0, "la"), (T1, "ra")):
        d.text((X(tday), cy1 + 12 * S), dt.datetime.fromtimestamp(tday, dt.timezone.utc).strftime("%-d %b"),
               font=f["tick"], fill=MUTED, anchor=anc)
    ct, ca = g["curve_t"], g["curve_a"]
    keep = ct <= t_eval
    a_now = float((g["area"] * p).sum())
    pts = [(X(t), Y(v)) for t, v in zip(ct[keep], ca[keep])]
    pts.append((X(min(t_disp, T1)), Y(a_now)))
    if len(pts) > 1:
        fill = tuple(int(0.8 * PAGE[j] + 0.2 * TEAL[j]) for j in range(3))
        d.polygon(pts + [(pts[-1][0], cy1), (pts[0][0], cy1)], fill=fill)
        d.line(pts, fill=TEAL, width=3 * S, joint="curve")
    if not DECK:   # the first release, dashed in cobalt
        yv = Y(V1_AREA)
        for x in range(int(cx0), int(cx1), 12 * S):
            d.line([(x, yv), (x + 6 * S, yv)], fill=COBALT, width=2 * S)
        d.text((cx0, yv - 8 * S), V1_LABEL, font=f["tick"], fill=COBALT, anchor="ls")
    hx, hy = pts[-1]
    d.ellipse((hx - 8 * S, hy - 8 * S, hx + 8 * S, hy + 8 * S), fill=RAG)
    d.ellipse((hx - 5 * S, hy - 5 * S, hx + 5 * S, hy + 5 * S), fill=TEAL)
    label = f"{a_now:,.0f} deg²"
    xy, anchor = ((hx + 14 * S, hy - 10 * S), "ls") if hx < cx1 - 150 * S else ((hx, Y(A) - 12 * S), "rs")
    x0b, y0b, x1b, y1b = d.textbbox(xy, label, font=f["head"], anchor=anchor)
    d.rectangle((x0b - 4 * S, y0b - 2 * S, x1b + 4 * S, y1b + 4 * S), fill=PAGE)
    d.text(xy, label, font=f["head"], fill=INK, anchor=anchor)
    if DECK:   # the date rides above the chart's left end
        d.text((cx0, cy0 - 34 * S), tl.strftime("%-d %B %Y"), font=f["date"], fill=MUTED, anchor="ls")

    # once the run is done: what it cost, against what the last one took
    k = float(np.clip((i - g["i_end"] - 0.4 * FPS) / (0.9 * FPS), 0, 1))
    if k > 0 and not DECK:
        top = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dt_ = ImageDraw.Draw(top)
        a8 = int(255 * ease(k))
        dt_.text((x0, 850 * S), f"{CORE_YEARS} core-years  ·  {g['days']} days", font=f["pay"], fill=INK + (a8,), anchor="ls")
        dt_.text((x0, 912 * S), PREVIOUS, font=f["unit"], fill=MUTED + (a8,), anchor="ls")
        img = Image.alpha_composite(img.convert("RGBA"), top).convert("RGB")

    return i, img.resize((W, H), Image.LANCZOS).tobytes()


def tile_lut(ids, keep):
    """(b, a) → tile index, for the tiles `keep` of ids 'a.b'; −1 where there is no such tile."""
    lut = np.full((361, 721), -1, np.int32)
    for k in keep:
        a, b = (int(x) for x in ids[k].split("."))
        lut[b, a % 721] = k
    return lut


def mapped(ids, kappa):
    """Whether the map has any unmasked pixel in each tile (sampled on a 6×6 grid per tile)."""
    import healpy as hp
    ra, dec = tile_radec(ids)
    f = (np.arange(6) + 0.5) / 6 - 0.5
    d = dec[:, None, None] + TILE * f[:, None]
    r = ra[:, None, None] + TILE * f[None, :] / np.cos(np.radians(dec))[:, None, None]
    v = unit(*np.broadcast_arrays(r, d)).reshape(-1, 3)
    vals = kappa["map"][kappa["lut"][hp.vec2pix(kappa["nside"], v[:, 0], v[:, 1], v[:, 2])]]
    return np.isfinite(vals.reshape(len(ids), -1)).any(1)


def load_massmap(f):
    """The final map, compacted to its footprint (nside ≤ 512 keeps workers light)."""
    import healpy as hp
    side = f.parent / "series.json"
    sigma = json.loads(side.read_text())["sigma_final"] if side.exists() else 1.0
    m = hp.read_map(f, dtype=np.float32)
    nside = min(512, hp.get_nside(m))
    if hp.get_nside(m) != nside:
        m = hp.ud_grade(m, nside)
    m[m == hp.UNSEEN] = np.nan
    keep = np.flatnonzero(np.isfinite(m))
    lut = np.full(hp.nside2npix(nside), len(keep), np.int64)   # out-of-footprint → the NaN slot
    lut[keep] = np.arange(len(keep))
    print(f"mass map: {f.name}, nside {nside}, σ {sigma:.3g}")
    return dict(nside=nside, map=np.append(m[keep], np.nan).astype(np.float32), lut=lut, sigma=sigma)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=max(1, mp.cpu_count() - 2))
    ap.add_argument("--frames", type=str, default="", help="comma-separated frame indices to write as PNG only")
    ap.add_argument("--massmap", type=pathlib.Path, help="final κ_E HEALPix map (FITS)")
    a = ap.parse_args()

    cur, universe, t_done = load()
    centre, corner, area = tile_geometry(universe)
    t0 = ts(cur["timeline"][0][0]).timestamp() - 3 * 3600
    finite = t_done[np.isfinite(t_done)]
    t1 = finite.max()                                  # the last tile's finish ends the clock
    n_done, a_done = int((t_done <= t1).sum()), float(area[t_done <= t1].sum())
    assert n_done == cur["processed_tiles"], (n_done, cur["processed_tiles"])
    per_tile = cur["latest"]["objects"] / cur["latest"]["tiles"]

    # completion curve, one point per 15 min, eased like the tiles
    curve_t = np.arange(t0, t1 + 1, 900.0)
    curve_a = np.array([(area * ease((t - t_done) / (TAU_H * 3600))).sum() for t in curve_t])
    A = float(area.sum())
    day0 = dt.datetime.fromtimestamp(t0, dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    xticks = [(day0 + dt.timedelta(days=k)).timestamp() for k in range(0, 60, 2)]
    xticks = [x for x in xticks if t0 <= x <= t1]
    days = round((finite.max() - ts(cur["timeline"][0][0]).timestamp()) / 86400)
    state = dict(days=days, t_done=t_done, centre=centre, corner=corner, area=area, per_tile=per_tile,
                 t0=t0, t1=t1, area_total=A, yticks=[0, 2000, 4000], xticks=xticks,
                 curve_t=curve_t, curve_a=curve_a, grat=graticule_lines())
    shown = np.isfinite(t_done)
    if a.massmap:
        state["kappa"] = load_massmap(a.massmap)
        shown &= mapped(universe, state["kappa"])
    state["tile_lut"] = tile_lut(universe, np.flatnonzero(shown))
    print(f"footprint shown: {shown.sum()} tiles, {area[shown].sum():,.0f} deg²")

    n_in, n_sim, n_hold = round(INTRO_S * FPS), round(SIM_S * FPS), round(HOLD_S * FPS)
    N = n_in + n_sim + n_hold
    state["i_end"] = n_in + n_sim
    # camera: faces the main cap, swings to the other cap while it fills, swings back
    # each cap is seen face-on: the camera looks at its area-weighted centroid
    ra, _ = tile_radec(universe)   # swing out as the other cap starts filling, back as it finishes
    other = shown & ((ra < MAIN_RA[0]) | (ra > MAIN_RA[1]))
    def centroid(sel):
        v = (centre[sel] * area[sel, None]).sum(0)
        return math.degrees(math.atan2(v[1], v[0])), math.degrees(math.asin(v[2] / np.linalg.norm(v)))
    (phi_main, el_main), (phi_other, el_other) = centroid(shown & ~other), centroid(other)
    turn = (phi_other - phi_main + 180) % 360 - 180
    fa, fb = np.quantile((t_done[other] - t0) / (t1 - t0), [0.02, 0.98])
    # the sim clock slows by WARP across that window, so the other cap fills slowly enough to watch
    fg = np.linspace(0, 1, 20001)
    dens = 1 + (WARP - 1) * (ease((fg - fa + 0.01) / 0.01) - ease((fg - fb) / 0.01))
    gg = np.concatenate([[0], np.cumsum((dens[1:] + dens[:-1]) / 2)])
    gg /= gg[-1]                                       # fraction of sim frames elapsed at run fraction fg
    sw = SWING_S * FPS
    ia = n_in + np.interp(fa, fg, gg) * n_sim - sw / 2   # half-way round as the first tiles land
    ib = n_in + np.interp(fb, fg, gg) * n_sim            # back once its last tiles have landed
    print(f"main cap at (RA {phi_main % 360:.0f}, Dec {el_main:.0f}); other cap: {other.sum()} tiles at (RA {phi_other % 360:.0f}, Dec {el_other:.0f}), filling {fa:.0%}–{fb:.0%} of the run; swings at frames {ia:.0f}, {ib:.0f}")
    jobs = []
    for i in range(N):
        w = ease((i - ia) / sw) - ease((i - ib) / sw)
        view = (phi_main + turn * w, el_main + (el_other - el_main) * w)
        if i < n_in:
            t = te = t0
        elif i < n_in + n_sim:
            t = te = t0 + (t1 - t0) * np.interp((i - n_in + 1) / n_sim, gg, fg)
        else:  # hold on the live state; let the last tiles finish their ease
            t = t1
            te = t1 + TAU_H * 3600 * min(1.0, (i - n_in - n_sim + 1) / FPS)
        jobs.append((i, t, te, view))
    sel = [int(x) for x in a.frames.split(",")] if a.frames else None

    # the last frame shows the live state
    p_end = ease((jobs[-1][2] - t_done) / (TAU_H * 3600))
    assert abs(p_end.sum() - cur["processed_tiles"]) < 1e-6
    assert abs((p_end * area).sum() - a_done) < 1e-6
    print(f"{N} frames ({N / FPS:.1f} s), {(t1 - t0) / n_sim / 60:.0f} min sim per frame; "
          f"end: {n_done} tiles, {a_done:,.0f} of {A:,.0f} deg², {per_tile * n_done / 1e6:,.0f} M objects")

    OUT.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("spawn")
    with ctx.Pool(a.jobs, initializer=init, initargs=(state,)) as pool:
        if sel is not None:
            for i, raw in pool.imap(render, [jobs[k] for k in sel]):
                Image.frombytes("RGB", (W, H), raw).save(OUT / f"globe_{i:04d}.png")
            return
        mp4 = OUT / "dr6_globe.mp4"
        ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                               "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
                               "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
        sheet_at = set(np.linspace(0, N - 1, 12).round().astype(int))
        thumbs = {}
        for i, raw in pool.imap(render, jobs, chunksize=4):
            ff.stdin.write(raw)
            if i in sheet_at:
                thumbs[i] = Image.frombytes("RGB", (W, H), raw).resize((640, 360), Image.LANCZOS)
        ff.stdin.close()
        assert ff.wait() == 0
    sheet = Image.new("RGB", (640 * 3 + 40, 360 * 4 + 50), PARCH)
    for k, i in enumerate(sorted(thumbs)):
        sheet.paste(thumbs[i], (10 + (k % 3) * 650, 10 + (k // 3) * 370))
    sheet.save(OUT / "dr6_globe_sheet.jpg", quality=90)
    print("→", mp4, OUT / "dr6_globe_sheet.jpg")


if __name__ == "__main__":
    main()
