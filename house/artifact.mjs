// Prepare the built deck for publishing as a claude.ai Artifact.
//
// The built index.html inlines every asset, videos included, which puts it
// over the Artifact page limit (16 MB). This copies the deck to _artifact/
// with each inlined video written to media/<key>.<ext> and referenced by
// relative path; images, fonts and math stay inlined.
//
//   node house/build.mjs . && node house/artifact.mjs .
//
// Publish _artifact/index.html with every file under _artifact/media/ in
// `files`.
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || '.');
const name = path.basename(root);
const src = path.join(root, '_site', name, 'index.html');
const out = path.join(root, '_artifact');
const EXT = { 'video/mp4': 'mp4', 'video/webm': 'webm' };

let html = fs.readFileSync(src, 'utf8');
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(path.join(out, 'media'), { recursive: true });

const written = [];
html = html.replace(/"([0-9a-f]{12})":"data:(video\/[a-z0-9]+);base64,([A-Za-z0-9+/=]+)"/g, (_, key, mime, b64) => {
  const rel = `media/${key}.${EXT[mime] || 'bin'}`;
  fs.writeFileSync(path.join(out, rel), Buffer.from(b64, 'base64'));
  written.push(rel);
  return `"${key}":"${rel}"`;
});

fs.writeFileSync(path.join(out, 'index.html'), html);
const mb = (n) => (n / 1e6).toFixed(1) + ' MB';
console.log(`index.html ${mb(Buffer.byteLength(html))}`);
for (const rel of written) console.log(`${rel} ${mb(fs.statSync(path.join(out, rel)).size)}`);
