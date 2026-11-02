"""Cail's house slides (slides/*.html) as Lectern sections on the deck's 1280×720 canvas.

The house layouts (figure, figure-text, bleed, points, section, number, people, closing) are
placed with absolute positions computed from each figure's aspect ratio; text, maths ($…$),
fragments, highlight boxes (data-box, % of the image) and speaker notes carry over. PDF figures
are read as the PNGs rasterised next to them (pdftocairo -r 220). Run once for the merge:

  python tools/house_to_lectern.py > /tmp/cail_sections.html
"""
import re
import sys
from html import escape
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
X0, W, TOP, BOT = 40, 1200, 112, 652          # body box below the headline, above the footer
PDF_PNG = {'images/paper2_cosebis_full.pdf': 'images/paper2_cosebis_bn.png'}


def img_path(src):
    if src.endswith('.pdf'):
        return PDF_PNG.get(src, src[:-4] + '.png')
    return src


def size(src):
    with Image.open(ROOT / src) as im:
        return im.size


def inner(tag, html):
    m = re.search(rf'<{tag}\b[^>]*>(.*?)</{tag}>', html, re.S)
    return m.group(1).strip() if m else None


def attrs(tag_html):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag_html))


def notes(html):
    m = re.search(r'<aside class="notes">(.*?)</aside>', html, re.S)
    return f'<aside class="notes">{m.group(1).strip()}</aside>' if m else ''


def fit(iw, ih, bw, bh):
    s = min(bw / iw, bh / ih)
    return round(iw * s), round(ih * s)


def figure(fig, x, y, w, h):
    """A house <figure> (figcaption above, image, marks, source below) in the box (x, y, w, h)."""
    out = []
    cap = inner('figcaption', fig)
    src_line = re.search(r'<span class="source">(.*?)</span>', fig, re.S)
    top, avail = y, h
    if cap:
        out.append(f'<p class="figcap" style="position:absolute;left:{x}px;top:{top}px;width:{w}px;margin:0;">{cap}</p>')
        top += 34; avail -= 34
    if src_line:
        avail -= 28
    im = re.search(r'<img\b[^>]*>', fig)
    vid = re.search(r'<video\b[^>]*>', fig)
    if im:
        a = attrs(im.group(0)); src = img_path(a['src'])
        iw, ih = size(src)
        dw, dh = fit(iw, ih, w, avail)
        ix = x + (w - dw) // 2
        cls = ' class="plot"' if 'plain' not in a.get('class', '') else ''
        out.append(f'<img{cls} src="{src}" alt="{a.get("alt", "")}" style="position:absolute;left:{ix}px;top:{top}px;width:{dw}px;height:{dh}px;">')
        for mk in re.finditer(r'<mark\b[^>]*></mark>', fig):
            ma = attrs(mk.group(0))
            bx, by, bw_, bh_ = map(float, ma['data-box'].split())
            mx, my = ix + dw * bx / 100, top + dh * by / 100
            frag = ' fragment' if 'fragment' in ma.get('class', '') else ''
            lab = ma.get('data-label')
            box = f'<div class="hl-box" style="position:absolute;left:{mx:.0f}px;top:{my:.0f}px;width:{dw * bw_ / 100:.0f}px;height:{dh * bh_ / 100:.0f}px;"></div>'
            if lab:
                box += f'<p class="hl-label" style="position:absolute;left:{mx:.0f}px;top:{my + dh * bh_ / 100 + 6:.0f}px;width:{dw * bw_ / 100:.0f}px;margin:0;">{lab}</p>'
            out.append(f'<div class="{frag.strip()}">{box}</div>' if frag else box)
        bottom = top + dh
    else:
        a = attrs(vid.group(0)); src = a['src']
        iw, ih = size(a['poster'])
        dw, dh = fit(iw, ih, w, avail)
        ix = x + (w - dw) // 2
        loop = '' if 'data-once' in vid.group(0) else ' loop=""'
        out.append(f'<video src="{src}" poster="{a["poster"]}" muted=""{loop} playsinline="" data-autoplay="" style="position:absolute;left:{ix}px;top:{top}px;width:{dw}px;height:{dh}px;"></video>')
        bottom = top + dh
    if src_line:
        out.append(f'<p class="caption" style="position:absolute;left:{x}px;top:{bottom + 6}px;width:{w}px;margin:0;">{src_line.group(1).strip()}</p>')
    return out


def text_block(div, x, y, w):
    """div.text: kickers, numbers, small/accent/muted paragraphs and lists, stacked from y."""
    body = re.sub(r'^\s*<div class="text">|</div>\s*$', '', div.strip())
    return [f'<div class="textcol" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;">{body.strip()}</div>']


def head(h2):
    return f'<h2>{h2}</h2>'


def convert(name, html):
    sec = re.search(r'<section\b([^>]*)>', html).group(1)
    layout = attrs(sec + ' ').get('data-layout') or re.search(r'data-layout="([^"]+)"', sec).group(1)
    h2 = inner('h2', html)
    parts = []
    extra = ''
    fig = re.search(r'<figure\b[^>]*>.*?</figure>', html, re.S)
    if layout == 'figure':
        parts += [head(h2)] + figure(fig.group(0), X0, TOP, W, BOT - TOP)
    elif layout == 'figure-text':
        text = re.search(r'<div class="text">.*?</div>(?=\s*<aside)', html, re.S).group(0)
        if 'data-stack' in sec:
            parts += [head(h2)] + figure(fig.group(0), X0, TOP, W, 300) + text_block(text, X0 + 40, TOP + 330, W - 80)
        else:
            split = int(attrs(sec + ' ').get('data-split', 60))
            fw = round(W * split / 100) - 20
            parts += [head(h2)] + figure(fig.group(0), X0, TOP, fw, BOT - TOP) + text_block(text, X0 + fw + 40, TOP + 40, W - fw - 40)
    elif layout == 'bleed':
        im = re.search(r'<(img|video)\b[^>]*>', fig.group(0)).group(0)
        a = attrs(im)
        if im.startswith('<video'):
            media = f'<video src="{a["src"]}" poster="{a["poster"]}" muted="" loop="" playsinline="" data-autoplay="" style="position:absolute;left:0;top:0;width:1280px;height:720px;object-fit:cover;object-position:50% 0;"></video>'
        else:
            media = f'<img src="{a["src"]}" alt="{a.get("alt", "")}" style="position:absolute;left:0;top:0;width:1280px;height:720px;object-fit:cover;">'
        parts += [media, f'<h2 class="on-veil">{h2}</h2>']
        extra = ' class="bleed"'
    elif layout == 'section':
        p = inner('p', html)
        parts += [f'<h2>{h2}</h2>', f'<p class="divider-sub">{p}</p>']
        extra = ' class="divider" data-background-color="#22574B"'
    elif layout == 'points':
        uls = re.findall(r'<ul\b[^>]*>.*?</ul>', re.sub(r'<aside.*?</aside>', '', html, flags=re.S), re.S)
        parts.append(head(h2))
        y = TOP + 10
        for ul in uls:
            if 'class="plain"' in ul:
                parts.append(f'<ul class="people-list" style="position:absolute;left:{X0 + 20}px;top:{y}px;width:{W - 40}px;margin:0;">{inner("ul", ul)}</ul>')
            else:
                n = ul.count('<li')
                parts.append(f'<ul style="position:absolute;left:{X0 + 29}px;top:{y}px;width:{W - 60}px;margin:0;">{inner("ul", ul)}</ul>')
                y += 44 * n + 40
    elif layout == 'number':
        stats = re.findall(r'<div class="stat"><span class="value">(.*?)</span><span class="label">(.*?)</span></div>', html)
        parts.append(head(h2))
        cw = W // len(stats)
        for k, (v, l) in enumerate(stats):
            parts.append(f'<p class="stat-value" style="position:absolute;left:{X0 + k * cw}px;top:280px;width:{cw - 30}px;margin:0;">{v}</p>')
            parts.append(f'<p class="stat-label" style="position:absolute;left:{X0 + k * cw}px;top:372px;width:{cw - 30}px;margin:0;">{l}</p>')
    elif layout == 'people':
        text = re.search(r'<div class="text">.*?</div>', html, re.S).group(0)
        ppl = re.search(r'<div class="people"([^>]*)>(.*?)</div>', html, re.S)
        lab = attrs(ppl.group(1) + ' ').get('data-label', '')
        pim = attrs(re.search(r'<img\b[^>]*>', ppl.group(2)).group(0))
        pcap = inner('figcaption', ppl.group(2))
        parts += [head(h2)] + text_block(text, X0, TOP + 40, 600)
        parts += [f'<p class="label" style="position:absolute;left:760px;top:200px;width:360px;margin:0;text-align:center;">{lab}</p>',
                  f'<img src="{pim["src"]}" alt="{pim["alt"]}" style="position:absolute;left:840px;top:236px;width:200px;height:200px;border-radius:50%;object-fit:cover;object-position:50% 35%;">',
                  f'<p class="caption" style="position:absolute;left:760px;top:448px;width:360px;margin:0;">{pcap}</p>']
    elif layout == 'closing':
        ol = re.search(r'<ol>.*?</ol>', html, re.S).group(0)
        contact = inner('p', html.split('</ol>')[1])
        parts += [head(h2), f'<ol class="closing" style="position:absolute;left:{X0 + 29}px;top:{TOP + 10}px;width:{W - 60}px;margin:0;">{inner("ol", ol)}</ol>',
                  f'<p class="contact" style="position:absolute;left:{X0}px;top:560px;margin:0;">{contact}</p>']
    else:
        raise ValueError(layout)
    body = '\n        '.join(parts)
    return f'''      <!-- Cail · {name} -->
      <section{extra}>
        {body}
        {notes(html)}
      </section>
'''


if __name__ == '__main__':
    for name in sys.argv[1:]:
        sys.stdout.write(convert(name, (ROOT / 'slides' / f'{name}.html').read_text()))
