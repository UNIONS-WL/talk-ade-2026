#!/usr/bin/env node
// Tests for the checker itself: the demo deck must pass, and every slide of the
// broken fixture must fail for the reason it was written to exhibit.
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHECK = path.join(HERE, '..', 'check.mjs');
const run = dir => spawnSync(process.execPath, [CHECK, dir], { encoding: 'utf8' });

const EXPECT = {
  overflow: 'clipped by the canvas (bottom',
  tiny: 'is set at 18.0px',
  unknown: 'class "sparkle" is not in the design system',
  contrast: 'has contrast 1.36:1',
  layoutless: 'unknown layout "carousel"',
  toomany: 'allows at most 2 figure',
  overlap: 'overlaps div.text',
  offcanvas: 'p.wide "wide" is clipped by the canvas (right',
  stepfade: 'at step 0 of 2: p.fragment.fade-out "gone later" is clipped by the canvas',
  svgtext: 'text.fill-ground "same colour as its box" has contrast 1.00:1',
  faint: 'p "barely there" has contrast',
  headline: 'overlaps the headline',
  nested: 'p "first paragraph here" overlaps p "second paragraph"',
  shrunk: 'the slide frame is scaled or transformed',
  emptyfig: 'a <figure> holds exactly one',
  widemath: 'leaves the content box (right',
  cssurl: 'loads a file through url() in a style',
  longname: 'does not fit under its portrait in two lines',
  noface: 'a portrait is <figure><img',
  stackless: 'data-stack goes on a people slide with a div.text',
};
const SVG_OFF = 'text "far right" is clipped by the canvas';

let failed = 0;
const ok = (cond, msg) => { console.log(`${cond ? '✓' : '✗'} ${msg}`); if (!cond) failed++; };

const demo = run(path.join(HERE, '..', 'demo'));
ok(demo.status === 0, `demo deck passes (${demo.stdout.trim().split('\n').pop()})`);

const broken = run(path.join(HERE, 'broken'));
ok(broken.status === 1, 'broken fixture exits 1');
const blocks = {};
let cur = null;
for (const line of broken.stdout.split('\n')) {
  const m = line.match(/^[✗!✓] \d+ (\S+)/);
  if (m) { cur = m[1]; blocks[cur] = []; continue; }
  if (cur && line.startsWith('    error:')) blocks[cur].push(line);
}
for (const [slide, needle] of Object.entries(EXPECT))
  ok((blocks[slide] || []).some(l => l.includes(needle)), `${slide}: reports "${needle}"`);

ok((blocks.svgtext || []).some(l => l.includes(SVG_OFF)), `svgtext: reports "${SVG_OFF}"`);
ok(broken.stdout.includes('failed to load file:///tmp/missing.png'), 'a failed file load is reported');

const fail = run(path.join(HERE, 'buildfail'));
ok(fail.status === 1, 'build-failure fixture exits 1');
for (const needle of [
  'slides/missing.html: missing image images/does_not_exist.png',
  'slides/badbox.html: <mark> needs data-box="x y w h" in percent of the image, inside it',
  'slides/stray.html: text outside the <section> ("LOST TEXT")',
  'slides/badtex.html: TeX error in $\\frac{1}{$',
]) ok(fail.stderr.includes(needle), `build refuses: ${needle}`);

const only = spawnSync(process.execPath, [CHECK, path.join(HERE, '..', 'demo'), '--only', 'nope'], { encoding: 'utf8' });
ok(only.status === 2 && only.stderr.includes('no slide named nope'), '--only with an unknown slide fails');

console.log(failed ? `\n${failed} failed` : '\nall passed');
process.exit(failed ? 1 : 0);
