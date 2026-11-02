// Screenshot slides of index.html headlessly, every fragment shown.
// node tools/shot.mjs "$PWD/index.html" <outdir> "<headline prefix>" ...   (needs puppeteer and PUPPETEER_EXECUTABLE_PATH)
import puppeteer from 'puppeteer';
const [,, file, outdir, ...heads] = process.argv;
const b = await puppeteer.launch({ executablePath: process.env.PUPPETEER_EXECUTABLE_PATH, args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
const p = await b.newPage(); await p.setViewport({ width: 1280, height: 720 });
await p.goto('file://' + file, { waitUntil: 'networkidle0' });
await p.waitForFunction(() => window.Reveal && Reveal.isReady());
const titles = await p.evaluate(() => Reveal.getSlides().map(s => (s.querySelector('h2')?.textContent || '').trim()));
for (const h of heads) {
  const i = titles.findIndex(t => t.startsWith(h));
  if (i < 0) { console.log('missing', h); continue; }
  await p.evaluate(i => { Reveal.slide(i); const f = Reveal.getCurrentSlide().querySelectorAll('.fragment').length; for (let k=0;k<f;k++) Reveal.nextFragment(); }, i);
  await new Promise(r => setTimeout(r, 2500));
  await p.screenshot({ path: `${outdir}/${String(i+1).padStart(2,'0')}.png` });
  console.log(i+1, h);
}
await b.close();
