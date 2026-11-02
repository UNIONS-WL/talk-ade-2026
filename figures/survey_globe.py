# /// script
# dependencies = ["numpy", "pillow", "matplotlib", "astropy", "mocpy", "imageio-ffmpeg", "fonttools", "brotli"]
# ///
"""Looping orthographic survey globes with the Stage III S8 comparison.

Run in the project container on a compute allocation after footprints.py.
The camera looks from declination +40 degrees; RA increases to the left.
"""
import argparse
import multiprocessing as mp
from pathlib import Path
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from astropy.coordinates import SkyCoord
from astropy import units as u

from footprints import RA, DEC, load_masks, PURPLE
from _style import COBALT, TEAL, ORANGE, YELLOW, MUTED, ROOT, setup

W, H, FPS, N = 2000, 860, 30, 720
CX, CY, R, ELEV = 1020, 425, 395, np.radians(40)
GROUND = '#F7F2E8'
G = {}


def rgb(color):
    return np.array(Image.new('RGB', (1, 1), color).getpixel((0, 0)), dtype=float)


def unit(ra, dec):
    a, d = np.radians(ra), np.radians(dec)
    return np.stack([np.cos(d)*np.cos(a), np.cos(d)*np.sin(a), np.sin(d)], -1)


def basis(phi):
    p = np.radians(phi)
    return (np.array([np.cos(ELEV)*np.cos(p), np.cos(ELEV)*np.sin(p), np.sin(ELEV)]),
            np.array([np.sin(p), -np.cos(p), 0]),
            np.array([-np.sin(ELEV)*np.cos(p), -np.sin(ELEV)*np.sin(p), np.cos(ELEV)]))


def init(masks):
    G['masks'] = masks
    fpath = ROOT/'figures/.cache/EBGaramond.ttf'
    G['font'] = ImageFont.truetype(str(fpath), 40)
    G['small'] = ImageFont.truetype(str(fpath), 34)
    yy, xx = np.mgrid[-R:R+1, -R:R+1].astype(np.float32)
    x, y = xx/R, -yy/R
    G['inside'] = x*x+y*y <= 1
    G['grid'] = (x[G['inside']], y[G['inside']], np.sqrt(np.clip(1-x*x-y*y, 0, 1))[G['inside']])
    G['gal'] = np.abs(SkyCoord(RA*u.deg, DEC*u.deg).galactic.b.deg) < 10
    # Contours retain disconnected fields and holes without triangulating the globe.
    import matplotlib.pyplot as plt
    G['lines'] = {}
    for name in ['lsst', 'euclid_wide', 'euclid_dr1']:
        fig, ax = plt.subplots()
        contour = ax.contour(RA, DEC, masks[name], levels=[.5])
        G['lines'][name] = [unit(p[:,0], p[:,1]) for p in contour.allsegs[0] if len(p)>1]
        plt.close(fig)
    G['grat'] = [unit(np.arange(361), np.full(361, d)) for d in [-60,-30,0,30,60]]
    G['grat'] += [unit(np.full(179, a), np.arange(-89,90)) for a in range(0,360,30)]
    whisker = Image.open(ROOT/'images/s8_stage3.png').convert('RGB').resize((575,820), Image.Resampling.LANCZOS)
    G['whisker'] = Image.fromarray((np.asarray(whisker)*rgb(GROUND)/255).astype(np.uint8))


def lines(draw, vectors, c, r, up, color, width, dashed=False):
    for v in vectors:
        visible = v@c > .003
        xy = np.column_stack([CX+R*(v@r), CY-R*(v@up)])
        for j in range(len(v)-1):
            if visible[j] and visible[j+1] and (not dashed or j%12 < 8):
                draw.line([tuple(xy[j]), tuple(xy[j+1])], fill=color, width=width)


def render(i):
    c, r, up = basis(195 + 360*i/N)
    x, y, z = G['grid']
    v = x[:,None]*r + y[:,None]*up + z[:,None]*c
    ra = np.degrees(np.arctan2(v[:,1],v[:,0]))%360
    dec = np.degrees(np.arcsin(np.clip(v[:,2],-1,1)))
    rows = np.clip(np.rint((dec+90)*4).astype(int),0,720)
    cols = np.rint((360-ra)*4).astype(int)%1440
    tex = np.tile(rgb('#F0E7D6'), (len(rows),1))
    tex[G['gal'][rows,cols]] = rgb('#DDD6C9')
    # Final surveys are translucent so the Stage III fills stay in front.
    for name, color in [('lsst',MUTED), ('euclid_wide',YELLOW)]:
        sel = G['masks'][name][rows,cols]
        tex[sel] = .87*tex[sel]+.13*rgb(color)
    sel = G['masks']['euclid_dr1'][rows,cols]
    tex[sel] = .60*tex[sel]+.40*rgb(ORANGE)
    base = tex.copy()
    frames = []
    for unions in [False, True]:
        tex = base.copy()
        for name,color in [('des',COBALT),('kids',TEAL),('hsc_y3',ORANGE)]+([('unions',PURPLE)] if unions else []):
            sel = G['masks'][name][rows,cols]
            tex[sel] = .16*tex[sel]+.84*rgb(color)
        tex *= (.88+.12*z[:,None])
        disc = np.full((2*R+1,2*R+1,3),rgb(GROUND),np.uint8)
        disc[G['inside']] = np.clip(tex,0,255).astype(np.uint8)
        im = Image.new('RGB',(W,H),GROUND)
        im.paste(G['whisker'],(0,15))
        im.paste(Image.fromarray(disc),(CX-R,CY-R))
        d = ImageDraw.Draw(im)
        lines(d,G['grat'],c,r,up,'#CFC4AF',1)
        for name,color,width in [('lsst',MUTED,3),('euclid_wide',YELLOW,4),('euclid_dr1',ORANGE,2)]:
            lines(d,G['lines'][name],c,r,up,color,width,name!='euclid_dr1')
        d.ellipse((CX-R,CY-R,CX+R,CY+R),outline=MUTED,width=2)
        d.text((CX,CY-R*np.cos(ELEV)-27),'N',font=G['small'],fill=MUTED,anchor='mm')
        entries = [('DES',COBALT,'fill'),('KiDS-1000',TEAL,'fill'),('HSC Y3',ORANGE,'fill'),
                   ('UNIONS DR6',PURPLE,'fill'),('LSST WFD (final)',MUTED,'line'),
                   ('Euclid Wide (final)',YELLOW,'line'),('Euclid DR1',ORANGE,'line')]
        for k,(name,color,kind) in enumerate(entries):
            if name=='UNIONS DR6' and not unions:
                continue
            yy = 185+k*70
            if kind=='fill':
                d.rectangle((1475,yy+5,1515,yy+30),fill=color)
            elif name == 'Euclid DR1':
                d.line((1475,yy+17,1515,yy+17),fill=color,width=4)
            else:
                for xx in range(1475,1515,15):
                    d.line((xx,yy+17,xx+9,yy+17),fill=color,width=4)
            d.text((1535,yy),name,font=G['font'],fill='#15171A')
        frames.append(im.tobytes())
    return i, frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', help='Comma-separated preview frames')
    ap.add_argument('--jobs',type=int,default=4)
    a=ap.parse_args()
    setup()
    masks=load_masks(ROOT/'figures/.cache/euclid_dr1_observed_wide_moc.fits')
    out=ROOT/'figures/.cache/globe'
    out.mkdir(exist_ok=True)
    indices=[int(x) for x in a.frames.split(',')] if a.frames else range(N)
    ff=[]
    if not a.frames:
        for name in ['consensus','north']:
            ff.append(subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(out/f'{name}.mp4')],stdin=subprocess.PIPE))
    with mp.Pool(a.jobs,initializer=init,initargs=(masks,)) as pool:
        for i,frames in pool.imap(render,indices,chunksize=1):
            for j,raw in enumerate(frames):
                if a.frames:
                    Image.frombytes('RGB',(W,H),raw).save(out/f'{["consensus","north"][j]}_{i:04d}.jpg',quality=95)
                else:
                    ff[j].stdin.write(raw)
            if i%60==0: print(f'frame {i}/{N}',flush=True)
    for p in ff:
        p.stdin.close()
        assert p.wait()==0


if __name__=='__main__':
    main()
