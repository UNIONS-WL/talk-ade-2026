// Flag on-slide text smaller than readable sizes, headlessly.
// node tools/fontcheck.mjs "$PWD/index.html"   (needs puppeteer and PUPPETEER_EXECUTABLE_PATH)
// Body text (p, li, span in lists) must be >= BODY px; captions, labels, kickers and credits >= SMALL px.
// Backup slides and speaker notes are skipped. Exits 1 when anything is too small.
import puppeteer from 'puppeteer';
const BODY = 24, SMALL = 16;
const SMALL_CLASSES = ['caption', 'figcap', 'label', 'kicker', 'who', 'arx', 'sub', 'contact', 'stat-label', 'credit', 'small'];
const b = await puppeteer.launch({ executablePath: process.env.PUPPETEER_EXECUTABLE_PATH, args: ['--no-sandbox'] });
const p = await b.newPage(); await p.setViewport({ width: 1280, height: 720 });
await p.goto('file://' + process.argv[2], { waitUntil: 'networkidle0' });
await p.waitForFunction(() => window.Reveal && Reveal.isReady());
const bad = await p.evaluate((BODY, SMALL, SMALL_CLASSES) => {
  const out = [];
  const slides = Reveal.getSlides();
  let backup = false;
  slides.forEach((s, i) => {
    if (s.dataset.section === 'Backup') backup = true;
    if (backup) return;
    const scale = Reveal.getScale ? 1 : 1;
    for (const el of s.querySelectorAll('p, li, span, strong, div')) {
      if (el.closest('.katex')) continue;
      if (el.closest('aside.notes') || el.closest('.slide-footer') || el.closest('footer')) continue;
      const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
      if (!own) continue;
      if (/^\d+ \/ \d+$/.test(el.textContent.trim()) || el.closest('.pageno, .slide-number')) continue;
      const px = parseFloat(getComputedStyle(el).fontSize);
      const small = SMALL_CLASSES.some(c => el.closest('.' + c));
      const min = small ? SMALL : BODY;
      if (px < min) out.push(`${i + 1}\t${px}px < ${min}\t${(s.querySelector('h2')?.textContent || '').trim().slice(0, 40)}\t${el.textContent.trim().slice(0, 60)}`);
    }
  });
  return out;
}, BODY, SMALL, SMALL_CLASSES);
await b.close();
console.log(bad.length ? bad.join('\n') : 'fonts ok');
process.exit(bad.length ? 1 : 0);
