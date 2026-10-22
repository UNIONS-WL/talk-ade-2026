#!/usr/bin/env node
// House deck build: a deck directory (deck.json + slides/*.html + figures) becomes
// one self-contained index.html (reveal, fonts, figures and math inlined) and a
// report.html that lays the same slides out as a scrolling document with their notes.
//
//   node house/build.mjs <deck-dir>... [--out _site]   build named decks
//   node house/build.mjs --all [--out _site]           build every deck with a deck.json
//   node house/build.mjs --listing <file.yml>          write Quarto listing items for house decks

import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parseHTML } from 'linkedom';
import { imageSize } from 'image-size';

const HOUSE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.dirname(HOUSE);
const NM = path.join(REPO, 'node_modules');
const CACHE = path.join(NM, '.cache', 'house');

export const LAYOUTS = [
  'title', 'section', 'statement', 'points', 'figure', 'figure-text',
  'compare', 'grid', 'number', 'bleed', 'table', 'quote', 'closing', 'people',
];

const MIME = {
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.svg': 'image/svg+xml', '.webp': 'image/webp', '.avif': 'image/avif',
};

export class BuildError extends Error {
  constructor(problems) {
    super(problems.map(p => `  ${p}`).join('\n'));
    this.problems = problems;
  }
}

const read = p => fs.readFileSync(p, 'utf8');
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// ── Deck index ────────────────────────────────────────────────────────────

export function loadDeck(dir) {
  dir = path.resolve(dir);
  const file = path.join(dir, 'deck.json');
  if (!fs.existsSync(file)) throw new BuildError([`${dir}: no deck.json`]);
  let meta;
  try { meta = JSON.parse(read(file)); }
  catch (e) { throw new BuildError([`deck.json: ${e.message}`]); }
  const problems = [];
  for (const k of ['title', 'author', 'date', 'footer', 'sections'])
    if (meta[k] === undefined) problems.push(`deck.json: missing "${k}"`);
  if (!Array.isArray(meta.sections)) problems.push('deck.json: "sections" must be a list');
  const slides = [];
  const seen = new Set();
  for (const [i, sec] of (meta.sections ?? []).entries()) {
    if (!sec.title) problems.push(`deck.json: section ${i + 1} has no "title"`);
    if (!sec.outline) problems.push(`deck.json: section "${sec.title ?? i + 1}" has no one-sentence "outline"`);
    if (!Array.isArray(sec.slides) || !sec.slides.length) { problems.push(`deck.json: section "${sec.title ?? i + 1}" lists no slides`); continue; }
    for (const name of sec.slides) {
      if (seen.has(name)) problems.push(`deck.json: slide "${name}" listed twice`);
      seen.add(name);
      const src = path.join(dir, 'slides', `${name}.html`);
      if (!fs.existsSync(src)) problems.push(`deck.json: slides/${name}.html does not exist`);
      slides.push({ name, src, section: sec });
    }
  }
  const slideDir = path.join(dir, 'slides');
  if (fs.existsSync(slideDir))
    for (const f of fs.readdirSync(slideDir))
      if (f.endsWith('.html') && !seen.has(f.slice(0, -5)))
        problems.push(`slides/${f} is not listed in deck.json (list it, e.g. in a Backup section, or delete it)`);
  if (problems.length) throw new BuildError(problems);
  return { dir, name: path.basename(dir), meta, slides };
}

// ── Assets ────────────────────────────────────────────────────────────────

function pdfToPng(pdf) {
  const st = fs.statSync(pdf);
  const key = crypto.createHash('sha1').update(`${path.resolve(pdf)}:${st.size}:${st.mtimeMs}`).digest('hex').slice(0, 16);
  fs.mkdirSync(CACHE, { recursive: true });
  const base = path.join(CACHE, key);
  if (!fs.existsSync(`${base}.png`))
    execFileSync('pdftocairo', ['-png', '-singlefile', '-scale-to', '3200', '-f', '1', '-l', '1', pdf, base]);
  return `${base}.png`;
}

function loadImage(file) {
  let ext = path.extname(file).toLowerCase();
  if (ext === '.pdf') { file = pdfToPng(file); ext = '.png'; }
  const mime = MIME[ext];
  if (!mime) throw new Error(`unsupported image type ${ext}`);
  const buf = fs.readFileSync(file);
  let w, h;
  try { ({ width: w, height: h } = imageSize(buf)); } catch { /* sizes unknown */ }
  return { buf, mime, w, h, uri: () => `data:${mime};base64,${buf.toString('base64')}` };
}

// White plot backgrounds disappear into the ground by multiplying the pixels by
// the theme's ground colour at build time (white × ground = ground), so the
// result is identical on screen, in a PDF export and in any browser.
async function multiplied(im, ground) {
  const { default: sharp } = await import('sharp');
  const key = crypto.createHash('sha1').update(im.buf).update(ground.join(',')).digest('hex').slice(0, 16);
  const ext = im.mime === 'image/jpeg' ? 'jpg' : 'png';
  const out = path.join(CACHE, `${key}.x.${ext}`);
  if (!fs.existsSync(out)) {
    fs.mkdirSync(CACHE, { recursive: true });
    const rgb = await sharp(im.buf).toColourspace('srgb').png().toBuffer();
    const { channels } = await sharp(rgb).metadata();
    const k = ground.map(c => c / 255);
    let img = sharp(rgb).linear(channels === 4 ? [...k, 1] : k, channels === 4 ? [0, 0, 0, 0] : [0, 0, 0]);
    img = ext === 'jpg' ? img.jpeg({ quality: 95, chromaSubsampling: '4:4:4' }) : img.png();
    await img.toFile(out);
  }
  return `data:${im.mime};base64,${fs.readFileSync(out).toString('base64')}`;
}

function fontFaces() {
  const g = path.join(NM, '@fontsource-variable/eb-garamond/files');
  const m = path.join(NM, '@fontsource/ibm-plex-mono/files');
  const face = (family, file, weight, style, range) => {
    const b64 = fs.readFileSync(file).toString('base64');
    return `@font-face{font-family:'${family}';font-style:${style};font-weight:${weight};font-display:block;src:url(data:font/woff2;base64,${b64}) format('woff2');unicode-range:${range};}`;
  };
  const LATIN = 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
  const LATIN_EXT = 'U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF';
  const GREEK = 'U+0370-0377,U+037A-037F,U+0384-038A,U+038C,U+038E-03A1,U+03A3-03FF';
  const out = [];
  for (const style of ['normal', 'italic']) {
    out.push(face('EB Garamond', `${g}/eb-garamond-latin-wght-${style}.woff2`, '400 800', style, LATIN));
    out.push(face('EB Garamond', `${g}/eb-garamond-latin-ext-wght-${style}.woff2`, '400 800', style, LATIN_EXT));
    out.push(face('EB Garamond', `${g}/eb-garamond-greek-wght-${style}.woff2`, '400 800', style, GREEK));
  }
  for (const w of [400, 500])
    out.push(face('IBM Plex Mono', `${m}/ibm-plex-mono-latin-${w}-normal.woff2`, w, 'normal', LATIN));
  return out.join('\n');
}

// ── Math: TeX pre-rendered to SVG at build time ───────────────────────────

let MJ;
async function loadMathJax() {
  if (MJ) return MJ;
  const { mathjax } = await import('mathjax-full/js/mathjax.js');
  const { TeX } = await import('mathjax-full/js/input/tex.js');
  const { SVG } = await import('mathjax-full/js/output/svg.js');
  const { liteAdaptor } = await import('mathjax-full/js/adaptors/liteAdaptor.js');
  const { RegisterHTMLHandler } = await import('mathjax-full/js/handlers/html.js');
  const { AllPackages } = await import('mathjax-full/js/input/tex/AllPackages.js');
  const adaptor = liteAdaptor();
  RegisterHTMLHandler(adaptor);
  MJ = { mathjax, TeX, SVG, adaptor, AllPackages };
  return MJ;
}

// One TeX expression at a time, straight into the slide's DOM: nothing else
// in the authored HTML is reparsed or reserialized by MathJax.
export async function makeTypesetter(macros = {}) {
  const { mathjax, TeX, SVG, adaptor, AllPackages } = await loadMathJax();
  const tex = new TeX({
    packages: AllPackages.filter(p => !['bussproofs', 'autoload', 'require', 'noundefined'].includes(p)),
    macros,
    formatError: (jax, err) => { throw new Error(err.message); },
  });
  const svg = new SVG({ fontCache: 'local' });
  const doc = mathjax.document('', { InputJax: tex, OutputJax: svg });
  let used = false;
  return {
    render(src, display) { used = true; return adaptor.outerHTML(doc.convert(src, { display, em: 16, ex: 8, containerWidth: 1712 })); },
    css() { return used ? adaptor.textContent(svg.styleSheet(doc)) : ''; },
  };
}

const MATH = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|(?<!\\)\$((?:[^$\\]|\\.)+?)\$/g;
const SKIP_TEXT = 'code, pre, script, style, svg, mjx-container, textarea';

// Text pass over a slide: typeset TeX, then make hyphens next to digits
// (SPT-3G, DR1-KP, KP2-3) non-breaking so names never split across lines.
function textPass(root, typeset, problems, where) {
  const doc = root.ownerDocument;
  const walker = doc.createTreeWalker(root, 4);
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (!n.parentElement?.closest(SKIP_TEXT)) nodes.push(n);
  for (const n of nodes) {
    const text = n.textContent;
    const nb = t => t.replace(/(?<=\w)-(?=\d)|(?<=\d)-(?=\w)/g, '‑').replace(/\\\$/g, '$');
    if (!/[$\\]/.test(text)) { if (/\w-\d|\d-\w/.test(text)) n.textContent = nb(text); continue; }
    const frag = doc.createElement('span');
    let last = 0, html = '';
    const escText = t => nb(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    for (const m of text.matchAll(MATH)) {
      html += escText(text.slice(last, m.index));
      const display = m[1] !== undefined || m[2] !== undefined;
      const src = m[1] ?? m[2] ?? m[3] ?? m[4];
      try { html += typeset.render(src, display); }
      catch (e) { problems.push(`${where}: TeX error in ${m[0].slice(0, 60)}: ${e.message}`); html += escText(m[0]); }
      last = m.index + m[0].length;
    }
    html += escText(text.slice(last));
    frag.innerHTML = html;
    n.replaceWith(...frag.childNodes);
  }
}

// ── Slides ────────────────────────────────────────────────────────────────

function parseFragment(html) {
  const { document } = parseHTML(`<!doctype html><html><head></head><body>${html}</body></html>`);
  return document;
}

export function parseSlide(src) {
  const document = parseFragment(read(src));
  const top = [...document.body.children];
  const stray = [...document.body.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ').trim();
  return { document, top, stray, section: top.length === 1 && top[0].localName === 'section' ? top[0] : null };
}

function wrapInFrame(fig, el, ar) {
  const doc = fig.ownerDocument;
  const box = doc.createElement('span');
  box.className = 'frame';
  if (ar) box.setAttribute('style', `--ar:${ar.toFixed(5)}`);
  const cell = doc.createElement('div');
  cell.className = 'cell';
  fig.insertBefore(cell, el);
  // caption, frame and source travel together inside the cell
  const cap = fig.querySelector(':scope > figcaption');
  if (cap) cell.appendChild(cap);
  cell.appendChild(box);
  box.appendChild(el);
  const src = fig.querySelector(':scope > .source');
  if (src) cell.appendChild(src);
  return box;
}

function moveMarks(fig, box, problems, where) {
  for (const mark of [...fig.querySelectorAll(':scope > mark')]) {
    const nums = (mark.getAttribute('data-box') || '').trim().split(/[\s,]+/).map(Number);
    if (nums.length !== 4 || nums.some(n => !Number.isFinite(n) || n < 0) || nums[2] <= 0 || nums[3] <= 0 || nums[0] + nums[2] > 100.01 || nums[1] + nums[3] > 100.01)
      problems.push(`${where}: <mark> needs data-box="x y w h" in percent of the image, inside it (got "${mark.getAttribute('data-box') || ''}")`);
    else mark.setAttribute('style', `--x:${nums[0]};--y:${nums[1]};--w:${nums[2]};--h:${nums[3]}`);
    box.appendChild(mark);
  }
}

// Images are stored once per deck and referenced by key, so a figure shown
// on several slides (or cropped several ways) is inlined a single time.
function addAsset(assets, im, blend) {
  const key = crypto.createHash('sha1').update(im.buf).update(blend ? 'x' : '').digest('hex').slice(0, 12);
  assets.set(key, { im, blend });
  return key;
}

async function resolveAssets(assets, ground) {
  const out = new Map();
  for (const [key, { im, blend }] of assets)
    out.set(key, blend && ground && im.mime !== 'image/svg+xml' ? await multiplied(im, ground) : im.uri());
  return out;
}

function assetScript(assets) {
  const dict = JSON.stringify(Object.fromEntries(assets));
  return `<script>(function(){var A=${dict};document.querySelectorAll('img[data-asset]').forEach(function(i){i.src=A[i.getAttribute('data-asset')];});})();</script>`;
}

function frameFigures(frame, deckDir, problems, where, assets) {
  // inline SVG schematics: sized by their viewBox, coloured by theme tokens
  for (const svg of [...frame.querySelectorAll('figure > svg')]) {
    const vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || !(vb[2] > 0 && vb[3] > 0)) { problems.push(`${where}: an inline <svg> in a figure needs a viewBox`); continue; }
    svg.removeAttribute('width'); svg.removeAttribute('height');
    const fig = svg.parentElement;
    moveMarks(fig, wrapInFrame(fig, svg, vb[2] / vb[3]), problems, where);
  }
  for (const img of [...frame.querySelectorAll('img')]) {
    const src = img.getAttribute('src') || '';
    if (/^(data:|https?:)/.test(src)) { if (src.startsWith('http')) problems.push(`${where}: remote image ${src} (copy it into images/)`); continue; }
    const file = path.resolve(deckDir, src);
    if (!fs.existsSync(file)) { problems.push(`${where}: missing image ${src}`); continue; }
    let im;
    try { im = loadImage(file); } catch (e) { problems.push(`${where}: ${src}: ${e.message}`); continue; }
    img.removeAttribute('src');
    const fig0 = img.parentElement?.localName === 'figure' ? img.parentElement : null;
    // portraits are photographs and keep their own backgrounds
    const portrait = !!img.closest('.people');
    const blend = !!fig0 && !fig0.classList.contains('plain') && !portrait && frame.getAttribute('data-layout') !== 'bleed';
    img.setAttribute('data-asset', addAsset(assets, im, blend));
    if (blend && im.mime === 'image/svg+xml') img.setAttribute('data-blend', '');
    img.setAttribute('data-src-path', src);
    if (!img.hasAttribute('alt')) img.setAttribute('alt', '');
    const fig = img.parentElement;
    if (fig?.localName !== 'figure' || portrait) continue;
    // data-crop="x y w h": show only that region, in percent of the image
    let crop = null;
    if (img.hasAttribute('data-crop')) {
      crop = img.getAttribute('data-crop').trim().split(/[\s,]+/).map(Number);
      if (crop.length !== 4 || crop.some(n => !Number.isFinite(n) || n < 0 || n > 100) || crop[2] <= 0 || crop[3] <= 0 || crop[0] + crop[2] > 100.01 || crop[1] + crop[3] > 100.01) {
        problems.push(`${where}: ${src}: data-crop needs "x y w h" in percent of the image, inside it`);
        crop = null;
      }
    }
    const ar = im.w && im.h ? (im.w / im.h) * (crop ? crop[2] / crop[3] : 1) : null;
    const box = wrapInFrame(fig, img, ar);
    if (crop) {
      box.classList.add('crop');
      box.setAttribute('style', `${box.getAttribute('style') || ''};--cx:${crop[0] / 100};--cy:${crop[1] / 100};--cw:${crop[2] / 100};--ch:${crop[3] / 100}`);
    }
    moveMarks(fig, box, problems, where);
  }
}

// people: the build gathers the portrait blocks into .roster (the size
// container) and chooses the rows that give the largest portraits in the
// nominal roster box: the body, less the text column (60 % of the width, or
// half the height under data-stack) and the source line. The memoriam block is extra columns on the right. The CSS
// sizes the portraits from the real roster with the same arithmetic.
const PEOPLE = { W: 1712, H: 771, col: 64, gap: 32, rowGap: 16, caption: 72, sep: 64, label: 40, source: 48, max: 240 };
function peopleGrid(frame, body) {
  const blocks = [...body.querySelectorAll(':scope > .people')];
  if (!blocks.length) return;
  const roster = body.ownerDocument.createElement('div');
  roster.className = 'roster';
  body.insertBefore(roster, blocks[0]);
  for (const b of blocks) roster.appendChild(b);
  const main = blocks.find(b => !b.classList.contains('memoriam'));
  const n = main ? main.querySelectorAll(':scope > figure').length : 0;
  const m = roster.querySelectorAll(':scope > .memoriam > figure').length;
  const P = PEOPLE;
  const text = !!body.querySelector(':scope > .text');
  const stack = text && frame.hasAttribute('data-stack');
  const W = text && !stack ? (P.W - P.col) * 0.6 : P.W;
  // stacked under the text, the portraits are planned for half the body
  const H = (P.H - (body.querySelector(':scope > .source') ? P.source : 0)) * (stack ? 0.5 : 1);
  const lab = main?.hasAttribute('data-label') ? P.label : 0;
  let best = null;
  for (let rows = 1; rows <= Math.max(n, 1); rows++) {
    const cols = Math.ceil(n / rows);
    const mrows = m ? Math.min(rows, m) : 0;
    const mcols = m ? Math.ceil(m / mrows) : 0;
    const d = Math.min(
      (W - (m ? P.sep : 0)) / (cols + mcols) - P.gap,
      (H - lab - (rows - 1) * P.rowGap) / rows - P.caption,
      m ? (H - P.label - (mrows - 1) * P.rowGap) / mrows - P.caption : Infinity);
    // past the size cap, the fewest rows win
    const score = Math.min(d, P.max);
    if (!best || score > best.score + 0.5) best = { score, rows, cols, mrows, mcols };
  }
  const { rows, cols, mrows, mcols } = best;
  frame.setAttribute('style', `${frame.getAttribute('style') ? frame.getAttribute('style') + ';' : ''}--cols:${cols};--rows:${rows};--mcols:${mcols};--mrows:${mrows}`);
}

// Build one .slide frame from an authored element (a <section> or an <aside class="detail">).
function makeFrame(el, { deckDir, problems, where, footer, number, isDetail, assets, typeset }) {
  const doc = el.ownerDocument;
  const layout = el.getAttribute('data-layout');
  const frame = doc.createElement('div');
  frame.className = isDetail ? 'slide detail' : 'slide';
  if (layout) frame.setAttribute('data-layout', layout);
  for (const a of ['data-split', 'data-flip', 'data-cols', 'data-stack']) if (el.hasAttribute(a)) frame.setAttribute(a, el.getAttribute(a));
  for (const c of el.classList) if (c !== 'detail') frame.classList.add(c);
  const style = el.getAttribute('style');
  if (style && !isDetail) frame.setAttribute('style', style);

  const kids = [...el.childNodes].filter(n => !(n.nodeType === 1 && n.localName === 'aside' && (n.classList.contains('notes') || n.classList.contains('detail'))));
  const head = kids.find(n => n.nodeType === 1);
  const body = doc.createElement('div');
  body.className = 'body';
  if (head && /^h[12]$/.test(head.localName) && layout !== 'title') frame.appendChild(head);
  for (const n of kids) if (n !== head || layout === 'title' || !/^h[12]$/.test(head.localName)) body.appendChild(n);
  frame.appendChild(body);
  if (layout === 'grid') frame.setAttribute('data-count', String(body.querySelectorAll(':scope > figure').length));
  if (layout === 'people') peopleGrid(frame, body);

  frameFigures(frame, deckDir, problems, where, assets);
  textPass(frame, typeset, problems, where);
  // a detail is shown whole: it has no fragment sequence of its own
  if (isDetail) for (const f of frame.querySelectorAll('.fragment')) f.classList.remove('fragment');

  if (layout !== 'title') {
    const foot = doc.createElement('div');
    foot.className = 'foot';
    foot.innerHTML = isDetail
      ? `<span>${esc(el.getAttribute('data-label') || 'Detail')}</span><button class="close" type="button">back to slide ${number}</button>`
      : `<span>${footer}</span><span class="num">${number}</span>`;
    frame.appendChild(foot);
  }
  return frame;
}

// linkedom escapes only quotes in attribute values; escape ampersands too, so
// an authored "&amp;lt;" stays literal text rather than becoming "<".
function serialize(el, inner = false) {
  const touched = [];
  for (const e of [el, ...el.querySelectorAll('*')])
    for (const a of [...e.attributes])
      if (a.value.includes('&')) { touched.push([e, a.name, a.value]); e.setAttribute(a.name, a.value.replace(/&/g, '\uE000')); }
  const html = (inner ? el.innerHTML : el.outerHTML).replace(/\uE000/g, '&amp;');
  for (const [e, n, v] of touched) e.setAttribute(n, v);
  return html;
}

function buildSlides(deck, typeset) {
  const problems = [];
  const out = [];
  const assets = new Map();
  out.assets = assets;
  deck.slides.forEach((s, i) => {
    const where = `slides/${s.name}.html`;
    const { section, stray } = parseSlide(s.src);
    if (!section) { problems.push(`${where}: must hold exactly one top-level <section>`); return; }
    if (stray) problems.push(`${where}: text outside the <section> ("${stray.slice(0, 40)}") would be lost`);
    const number = i + 1;
    const footer = esc(deck.meta.footer);
    const frame = makeFrame(section, { deckDir: deck.dir, problems, where, footer, number, assets, typeset });
    const notes = [...section.querySelectorAll(':scope > aside.notes')];
    for (const n of notes) textPass(n, typeset, problems, `${where} notes`);
    const details = [...section.querySelectorAll(':scope > aside.detail')].map((d, k) => {
      const f = makeFrame(d, { deckDir: deck.dir, problems, where: `${where} detail ${k + 1}`, footer, number, isDetail: true, assets, typeset });
      f.setAttribute('data-detail', String(k));
      return { frame: f, label: d.getAttribute('data-label') || `Detail ${k + 1}` };
    });
    if (details.length) {
      const chips = section.ownerDocument.createElement('div');
      chips.className = 'chips';
      chips.innerHTML = details.map((d, k) => `<button class="chip" type="button" data-open="${k}">${esc(d.label)}</button>`).join('');
      frame.appendChild(chips);
    }
    const attrs = [...section.attributes]
      .filter(a => !['data-layout', 'data-split', 'data-flip', 'data-stack', 'class', 'style', 'id'].includes(a.name))
      .map(a => ` ${a.name}="${esc(a.value)}"`).join('');
    out.push({
      ...s, number,
      sectionAttrs: `id="${esc(s.name)}" data-house-slide="${esc(s.name)}"${attrs}`,
      frame: serialize(frame),
      notes: notes.map(n => serialize(n, true)).join('\n'),
      details: details.map(d => ({ label: d.label, frame: serialize(d.frame) })),
    });
  });
  if (problems.length) throw new BuildError(problems);
  return out;
}

// ── Output ────────────────────────────────────────────────────────────────

// A theme is a token set (plus any furniture, such as a logo) in themes/<name>.css;
// url(...) references in it are inlined relative to the themes directory.
export function themeNames() {
  return fs.readdirSync(path.join(HOUSE, 'themes')).filter(f => f.endsWith('.css')).map(f => f.slice(0, -4));
}

function themeCss(deck) {
  const name = deck.meta.theme || 'house';
  const file = path.join(HOUSE, 'themes', `${name}.css`);
  if (!fs.existsSync(file)) throw new BuildError([`deck.json: unknown theme "${name}" (one of ${themeNames().join(', ')})`]);
  return read(file).replace(/url\(\s*["']?([^"')]+?)["']?\s*\)/g, (m, ref) => {
    ref = ref.trim();
    if (/^(data:|https?:|#)/.test(ref)) return m;
    const im = loadImage(path.resolve(path.dirname(file), ref));
    return `url("${im.uri()}")`;
  });
}

// The ground figures multiply into, or null when the theme does not blend figures.
function themeGround(css) {
  if (!/--figure-blend:\s*multiply/.test(css)) return null;
  const m = css.match(/--ground:\s*#([0-9a-fA-F]{6})/);
  return m ? [0, 2, 4].map(i => parseInt(m[1].slice(i, i + 2), 16)) : null;
}

function deckCss(deck) {
  const extra = deck.meta.css ? path.join(deck.dir, deck.meta.css) : null;
  return extra && fs.existsSync(extra) ? read(extra) : '';
}

function deckHTML(deck, slides, mathCss, theme) {
  const sections = slides.map(s => `<section ${s.sectionAttrs}>
${s.frame}
${s.details.map(d => d.frame).join('\n')}
${s.notes.trim() ? `<aside class="notes">${s.notes}</aside>` : ''}
</section>`).join('\n');
  return `<!doctype html>
<html lang="en" class="theme-${esc(deck.meta.theme || 'house')}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(deck.meta.title)}</title>
<meta name="description" content="${esc(deck.meta.description || '')}">
<style>${fontFaces()}</style>
<style>${read(path.join(NM, 'reveal.js/dist/reveal.css'))}</style>
<style>${read(path.join(HOUSE, 'house.css'))}</style>
<style>${theme}</style>
<style>${mathCss}</style>
${deckCss(deck) ? `<style>${deckCss(deck)}</style>` : ''}
</head>
<body>
<div class="reveal"><div class="slides">
${sections}
</div></div>
${assetScript(slides.assets)}
<script>${read(path.join(NM, 'reveal.js/dist/reveal.js'))}</script>
<script>${read(path.join(NM, 'reveal.js/dist/plugin/notes.js'))}</script>
<script>${read(path.join(HOUSE, 'runtime.js'))}</script>
</body>
</html>
`;
}

function reportHTML(deck, slides, mathCss, theme) {
  const m = deck.meta;
  const toc = m.sections.map((sec, i) => `<li><a href="#part-${i + 1}">${esc(sec.title)}</a> <span class="outline">— ${esc(sec.outline)}</span></li>`).join('');
  let body = '';
  let current = null;
  m.sections.forEach((sec, i) => { sec._id = `part-${i + 1}`; });
  for (const s of slides) {
    if (s.section !== current) {
      current = s.section;
      body += `<h2 class="part" id="${current._id}">${esc(current.title)}</h2><p class="part-outline">${esc(current.outline)}</p>`;
    }
    body += `<article id="${esc(s.name)}">
<div class="viewport">${s.frame}</div>
${s.notes.trim() ? `<div class="prose">${s.notes}</div>` : ''}
${s.details.map(d => `<div class="detail-copy"><p class="label">${esc(d.label)}</p><div class="viewport">${d.frame.replace('class="slide detail"', 'class="slide detail open"')}</div></div>`).join('\n')}
</article>`;
  }
  return `<!doctype html>
<html lang="en" class="theme-${esc(m.theme || 'house')}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(m.title)} — report</title>
<style>${fontFaces()}</style>
<style>${read(path.join(HOUSE, 'house.css'))}</style>
<style>${theme}</style>
<style>${mathCss}</style>
${deckCss(deck) ? `<style>${deckCss(deck)}</style>` : ''}
</head>
<body class="report">
<main>
<header class="deck">
<h1>${esc(m.title)}</h1>
<p>${esc(m.author)}${m.venue ? ` · ${esc(m.venue)}` : ''} · ${esc(m.date)}</p>
<nav class="toc"><ol>${toc}</ol></nav>
</header>
${body}
</main>
${assetScript(slides.assets)}
<script>
(function () {
  function fit() {
    document.querySelectorAll('.viewport').forEach(function (v) {
      var s = v.clientWidth / 1920;
      v.firstElementChild.style.transform = 'scale(' + s + ')';
    });
  }
  window.addEventListener('resize', fit);
  fit();
})();
</script>
</body>
</html>
`;
}

export async function buildDeck(dir, outRoot, { theme: themeOverride } = {}) {
  const deck = loadDeck(dir);
  if (themeOverride) deck.meta.theme = themeOverride;
  const typeset = await makeTypesetter(deck.meta.macros || {});
  const slides = buildSlides(deck, typeset);
  const theme = themeCss(deck);
  slides.assets = await resolveAssets(slides.assets, themeGround(theme));
  const mathCss = typeset.css();
  const out = path.join(outRoot, deck.name);
  fs.mkdirSync(out, { recursive: true });
  const index = path.join(out, 'index.html');
  const report = path.join(out, 'report.html');
  fs.writeFileSync(index, deckHTML(deck, slides, mathCss, theme));
  fs.writeFileSync(report, reportHTML(deck, slides, mathCss, theme));
  return { deck, slides, index, report };
}

export function houseDecks() {
  return fs.readdirSync(REPO)
    .filter(d => fs.existsSync(path.join(REPO, d, 'deck.json')))
    .map(d => path.join(REPO, d));
}

function listing(file) {
  const items = houseDecks().map(dir => {
    const m = JSON.parse(read(path.join(dir, 'deck.json')));
    if (m.draft) return null;
    const name = path.basename(dir);
    return [
      `- title: ${JSON.stringify(m.title)}`,
      `  path: ${name}/index.html`,
      `  date: ${JSON.stringify(m.date)}`,
      `  description: ${JSON.stringify(m.description || m.venue || '')}`,
    ].join('\n');
  }).filter(Boolean);
  fs.writeFileSync(file, items.length ? items.join('\n') + '\n' : '[]\n');
  console.log(`wrote ${file} (${items.length} decks)`);
}

async function main(argv) {
  const args = [...argv];
  let out = path.join(REPO, '_site');
  const oi = args.indexOf('--out');
  if (oi >= 0) { out = path.resolve(args[oi + 1]); args.splice(oi, 2); }
  const li = args.indexOf('--listing');
  if (li >= 0) { listing(path.resolve(args[li + 1])); return 0; }
  const all = args.includes('--all');
  const dirs = all ? houseDecks() : args.filter(a => !a.startsWith('--'));
  if (all && !dirs.length) { console.log('no house decks to build'); return 0; }
  if (!dirs.length) { console.error('usage: node house/build.mjs <deck-dir>... | --all [--out DIR] | --listing FILE'); return 2; }
  let failed = 0;
  for (const d of dirs) {
    try {
      const r = await buildDeck(d, out);
      const kb = f => `${Math.round(fs.statSync(f).size / 1024)} kB`;
      console.log(`${r.deck.name}: ${r.slides.length} slides → ${path.relative(process.cwd(), r.index)} (${kb(r.index)}), report.html (${kb(r.report)})`);
    } catch (e) {
      failed++;
      console.error(`${path.basename(path.resolve(d))}: build failed\n${e instanceof BuildError ? e.message : e.stack}`);
    }
  }
  return failed ? 1 : 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  main(process.argv.slice(2)).then(code => process.exit(code));
