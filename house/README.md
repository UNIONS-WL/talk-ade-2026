# House deck system

Talks are hand-authored HTML on reveal.js, written against one design system and verified by a checker that renders every slide. There is no Markdown layer: one file per slide, a small index, and a build that inlines everything into a single offline HTML file.

```
node house/build.mjs <deck-dir>        # → _site/<deck>/index.html and report.html
node house/check.mjs <deck-dir>        # lint + render; screenshots in <deck-dir>/_check/
node house/check.mjs <deck-dir> --steps          # also one screenshot per fragment step
node house/check.mjs <deck-dir> --only a,b       # just these slides
node house/check.mjs <deck-dir> --theme euclid   # try the deck in another theme
node house/check.mjs --all             # every top-level directory holding a deck.json
npm test                               # the checker's own tests (demo passes, fixtures fail)
```

First time on a machine: `npm install` at the repo root (reveal, MathJax, fonts, sharp, puppeteer). PDF figures need `pdftocairo` (poppler).

## A deck

```
2610_Napoli_CMBX/
├── deck.json
├── slides/
│   ├── title.html
│   ├── footprint.html
│   └── …
└── images -> ../images        # the shared figure pool; add new figures there
```

`deck.json` is the index: metadata, theme, and the sections in order, each with a one-sentence outline and its slides (file names without `.html`). Every file in `slides/` must be listed; spare slides go in a `Backup` section.

```json
{
  "title": "Euclid × CMB lensing",
  "author": "Cail Daley",
  "venue": "OU-SHE × WLSWG, Napoli",
  "date": "2026-10-13",
  "description": "One line for the talks index.",
  "footer": "Cail Daley · Euclid CMBX · Napoli · October 2026",
  "theme": "euclid",
  "draft": false,
  "macros": { "Ckk": "C_\\ell^{\\kappa\\kappa}" },
  "sections": [
    { "title": "Data", "outline": "RR2 overlaps ACT and SPT lensing over 385 deg².",
      "slides": ["title", "footprint", "nz"] }
  ]
}
```

`theme` is one of the files in `house/themes/` (default `house`). `macros` are TeX macros for every slide. `css` names an optional deck stylesheet for rare one-offs; classes it defines join the vocabulary the linter accepts. `draft: true` keeps the deck off the talks index but still publishes it at its URL.

A slide file holds exactly one `<section>` with a `data-layout`, a headline, its content, and speaker notes:

```html
<section data-layout="figure">
  <h2>Mock bandpowers follow the model to $\ell \approx 2000$</h2>
  <figure>
    <img src="images/house_demo_spectrum.pdf" alt="Mock bandpowers against a model spectrum">
    <mark class="box fragment" data-box="63 38 33 46" data-label="small scales"></mark>
    <span class="source">Synthetic spectrum made by house/demo/make_demo_figure.py.</span>
  </figure>
  <aside class="notes">
    <p>The paragraph a reader needs: what is plotted, what to see, why it matters.</p>
  </aside>
</section>
```

The headline is a claim, one line. The notes are prose: the report variant prints them under each slide, so they are written for a reader, not as a script fragment. Math is TeX between `$…$`, `\(…\)`, `$$…$$` or `\[…\]`, typeset to SVG at build time; a TeX error fails the build and names the slide. An expression must sit in one run of text (no tags inside it); write a literal dollar as `\$`. Put punctuation that follows inline math inside it (`$b_i,$`), or the line may break before it.

## The canvas and its budget

Every slide is a fixed 1920×1080 frame. The content box is x 104–1816, y 72–968 (1712 × 896 px); the footer sits below it. With a one-line headline the body box is **1712 × 771 px** (y 197–968). Space is arithmetic: count before you write, and when content does not fit, **split the slide — nothing shrinks**. The checker rejects inline type sizes and anything below 24 px.

The type scale has five sizes, shared by every theme. Emphasis is weight (`<strong>`) or colour (`.accent`, `.muted`), never another size. Every theme sets prose in EB Garamond; measured average characters per line:

| token | px | used for | line pitch | full 1712 | points 1560 | text column 659 | half 824 | third 544 |
|---|---|---|---|---|---|---|---|---|
| `--t-display` | 104 | title, section divider, big numbers | 108 | 41 | — | 16 | 20 | 13 |
| `--t-head` | 60 | headlines, statements, quotes | 67 | 72 | 65 | 27 | 34 | 22 |
| `--t-body` | 44 | body text, bullets | 59 | 101 | 92 | 39 | 48 | 32 |
| `--t-small` | 32 | captions, table cells, stat labels, nested bullets | 43 | 139 | 127 | 53 | 67 | 44 |
| `--t-fine` | 24 | sources, kickers, footer — the floor | 32 | 185 | 169 | 71 | 89 | 59 |

Characters per line are measured averages for prose in EB Garamond; plan on about 85 % of them, since words wrap whole. Rules of thumb for the 771 px body:

- a one-line bullet costs 79 px (line plus gap), a two-line bullet 139 px: at most **nine one-line bullets**, about five two-line ones;
- a headline that wraps to two lines costs 67 px of body; three lines is an error. In euclid the headline stops 240 px short of the right edge to clear the logo, so it holds about 50 characters;
- a figure caption (`figcaption`) costs 54 px and a `.source` line 48 px off the figure's height; both are one line and must fit the figure's width;
- a figure fills its cell at its own aspect ratio: in the `figure` layout a 16:9 plot is 1371 × 771, a 4:3 plot 1028 × 771; each half of `compare` is 824 wide and a `grid` cell 544 (three columns) or 836 (two), so landscape plots there are width-limited. Wide figures want a 2 × 2 grid (`data-cols="2"`).

Above 60 words of on-screen text the checker warns: the audience reads instead of listening.

## Layouts

`data-layout` on the `<section>`; the checker enforces what each may hold at its top level, after the headline.

| layout | holds | for |
|---|---|---|
| `title` | `<h1>`, `p.subtitle`, `p.byline`, `p.affil`, `p.venue`, `p.date`, `div.logos` | the opening slide; no footer |
| `section` | `<h2>`, one `<p>` | a divider: section title and its outline |
| `statement` | `<h2>`, up to two `<p>` | one claim, vertically centred |
| `points` | `<h2>`, lists, `<p>`, `div.eq`, `div.cols`, `<pre>`, `.source` | a text slide |
| `figure` | `<h2>`, one `<figure>` | one figure filling the body |
| `figure-text` | `<h2>`, one `<figure>`, one `div.text` | figure beside labels or key numbers; `data-split="50|60|70"` is the figure's share (default 60), `data-flip` puts the text left |
| `compare` | `<h2>`, two `<figure>` | side by side, each with a `figcaption` label |
| `grid` | `<h2>`, three to six `<figure>` | three columns; four make a 2 × 2; `data-cols="2\|3"` sets the columns |
| `number` | `<h2>`, one to three `div.stat` | key numbers: `<div class="stat"><span class="value">385</span><span class="label">deg² …</span></div>` |
| `bleed` | optional `<h2>`, one `<figure>` | a photograph filling the canvas; headline on a band |
| `table` | `<h2>`, one `<table>`, `.source` | `th`/`td`; `td.r` right-aligns, `tr.hl` highlights a row; `table.large` sets a short table at body size with its first column unwrapped |
| `quote` | one `<blockquote>`, `.source` | a quotation |
| `closing` | `<h2>`, an `<ol>` of takeaways, `p.contact` | stays on screen for questions |
| `people` | `<h2>`, one `div.people`, optional `div.people.memoriam`, optional `div.text`, `.source` | portraits with names, for a team or a project's leads; see below |

A `people` slide holds up to 24 portraits, each `<figure><img src="images/collaborators/…" alt="Name"><figcaption>Name</figcaption></figure>`, or `<span class="initials">AB</span>` in place of the image for someone without a photo:

```html
<section data-layout="people">
  <h2>The Euclid CMBX working group</h2>
  <div class="text"> <span class="kicker">…</span> <p>…</p> <ul>…</ul> </div>        <!-- optional -->
  <div class="people" data-label="SWG leads"> <figure>…</figure> … </div>
  <div class="people memoriam" data-label="In memoriam"> <figure>…</figure> </div>   <!-- optional -->
  <p class="source">…</p>                                                            <!-- optional -->
  <aside class="notes">…</aside>
</section>
```

The build picks the number of rows that gives the largest portraits in the space they have: the whole body, or 60 % of its width beside a `div.text` (text left; `data-flip` puts it right), or the full width under it with `data-stack` on the section (text at the top, portraits and any memoriam block in a row anchored to the bottom of the body; rows are planned for half the body's height), less a `.source` line under both. Portraits are capped at 240 px, and once a group reaches the cap the fewest rows win. Every portrait is the same round crop (`object-fit: cover`, centred a little above the middle, where faces sit), with its name at the fine size, which may wrap to two lines; initials sit in a disc of the same size at the headline size. `data-label` on a block puts a small-caps heading above its portraits. The memoriam block sits to the right of the others behind a thin rule, in the same portrait style. Portraits keep their own backgrounds: images in a `people` block are never multiplied into the ground.

## Figures

A `<figure>` holds an optional `<figcaption>` (a one-line label above), one image, optional `<mark>` highlights, and an optional `.source` line under it. Caption, image and source stay together, centred in the space the layout gives the figure (top-aligned in `compare` and `grid`, so captions line up).

- **Pre-rendered figures are the normal case.** PNG, JPEG, SVG and PDF work as `<img src="images/…">`; a PDF's first page is rasterised to 3200 px on its long side at build time (cached in `node_modules/.cache/house`). The image takes the largest box of its aspect ratio that fits its cell. The build multiplies figure pixels by the theme's ground colour, so a plot's white background becomes the ground and the plot sits on the paper without a white rectangle, identically on screen, in a PDF and in any browser; a figure whose background is content (a photograph, a map with a cream ground) takes `class="plain"`. SVG images blend in CSS instead.
- **Text in figures** must be legible on screen too, and the checker cannot read pixels: make axis labels and legends at least 24 px *as displayed*. A plot shown 1371 px wide from a 12-inch matplotlib figure at 100 dpi is scaled by 1.14, so 22 pt labels are about 35 px. Look at the screenshots.
- **Crops**: `<img src="…" data-crop="x y w h">` shows only that region (percent of the image, from its top left), so one tall composite can feed several slides without cropped copies in the pool. Each image file is inlined once per deck however many times it is shown or cropped. There is no scrolling: a figure too tall for a slide is cropped into panels.
- **Highlights** are the one emphasis device for data figures: `<mark class="box fragment" data-box="x y w h">` outlines a region given in percent of the image (from its top left); `data-label="…"` adds a tag above it (`class="below"` puts it under). `<mark class="spot fragment" data-box="…">` dims everything outside the region instead. Add `fade-in-then-out` to a box that should disappear at the next step.
- **Schematics are inline SVG**, for diagrams with no plot behind them. Put the `<svg viewBox="…">` directly in the `<figure>`; it scales like an image. Colour it with theme classes so it recolours with the theme — `fill-ink`, `fill-muted`, `fill-accent`, `fill-teal`, `fill-cobalt`, `fill-ochre`, `fill-rule`, `fill-panel`, `fill-ground`, `fill-none`, and `stroke-…` for each colour — and leave text unstyled (it takes the deck's face and ink). Give `font-size` in viewBox units; the checker measures it on screen against the 24 px floor. `<g class="fragment">` reveals parts in order. Ids must be unique across the whole deck (prefix them with the slide name).
- `<div class="placeholder">figure to come</div>` in place of the image marks a figure not made yet; the checker warns while one remains.

## Components

- `<div class="eq"><span class="kicker">Label</span>$$…$$</div>` — a labelled display equation.
- `.kicker` — small-caps label above a block. `.source` — attribution in the fine size. `.num` — a key number inline. `.tag` — a pill.
- Hyphens next to a digit (SPT-3G, DR1-KP, KP2-3) are made non-breaking by the build, so names never split across lines.
- `.accent`, `.muted`, `.teal`, `.cobalt` — colour emphasis. `.small`, `.fine` — the two smaller sizes, for secondary lines.
- `<div class="cols">` — two or more equal columns inside a `points` body.
- `<pre><code>` — code in the mono face at the fine size.
- Fragments are reveal's: `class="fragment"` on any element, with reveal's variants (`fade-in-then-out`, `semi-fade-out`, …).

## Depth on demand

A detail is a slide outside the linear order: a null test, the per-bin version of a plot. Write it inside the slide's `<section>` as

```html
<aside class="detail" data-label="Per-bin fits" data-layout="grid">
  <h2>Each bin fits on its own</h2>
  <figure>…</figure> …
</aside>
```

with any layout. A detail is shown whole: fragments inside it appear at once. A chip labelled with `data-label` appears above the footer; clicking it (or pressing `D`) opens the detail over the slide, and Escape returns to the same slide and fragment. The checker renders and measures every detail; the report prints each one after its slide. There are no vertical slides.

## The checker

`node house/check.mjs <deck>` measures every fragment state of every slide (a problem seen only before the last step is reported with its step), exits 1 on any error and writes `<deck>/_check/`: one screenshot per slide with all fragments shown (`NN-name.png`), one per detail, `contact.png` (every frame on one sheet, errors outlined red, warnings amber) and `check.txt`. Look at the contact sheet before calling a deck done; a passing check says nothing about whether a figure's own labels are legible.

Errors:

- structure: an unknown layout or a class outside the vocabulary (house.css, the themes, the deck's css); content a layout does not allow, or too many of it; a figure without exactly one image, inline SVG or placeholder (a portrait: one image or one `span.initials`, and a name); an id used on two slides; elements the build cannot inline (`<script>`, `<iframe>`, `<video>`, SVG `<image>`, `url()` in a style); an inline type size or scale; build failures (missing image, TeX error, text outside the `<section>`, a highlight or crop outside its image);
- geometry: text ink or a box outside the content box, anything off the canvas (footer, logos and themed bands may leave the content box but not the canvas); an element clipping its content; the headline overlapping the body, or sibling blocks overlapping anywhere in the body; a caption or source wider than its figure (a portrait's name may take two lines within its column); more than 24 portraits on a `people` slide; a scaled or transformed slide frame; a three-line headline;
- legibility: text set below 24 px, SVG text as displayed included; contrast below 4.5:1 for text against its background, with opacity, and for SVG text against the filled shape under its centre;
- the page: a script error, a file that fails to load, any network request (decks work offline).

Warnings: a two-line headline (not on `statement`); more than 60 words on screen; a `points` slide filling less than 40 % of its body (make it a `statement`, or merge); an image drawn under 240 px tall and under 900 px wide (check its labels, or give it room; portraits and logos are exempt); missing speaker notes; a placeholder; inline styles; images without alt text.

## Themes

A theme is a token set in `house/themes/<name>.css` over the same layouts; `deck.json` names it.

- `house` — warm paper (`#F7F0E1`), ink, one cinnabar accent, EB Garamond.
- `house-dark` — the same palette on a dark ground; figures sit on white cards instead of multiplying.
- `euclid` — for talks given as a Euclid member, inside the Euclid Consortium frame taken from the official "Euclid Slide Theme" master: Euclid blue `#435AA1`, a blue band down the left edge carrying the footer line, the consortium logo top right (`images/euclid_logo.png`), bold EB Garamond headlines in black, a blue subtitle band on the title slide and a blue band behind section titles. The ground is a pale cool off-white (`#F3F5F8`) that sits with the blue; plots multiply into it.

A theme sets `--face` and `--face-head` (EB Garamond and IBM Plex Mono are inlined in every deck), `--ground`, `--ground-deep`, `--ink`, `--muted`, `--accent`, `--teal`, `--cobalt`, `--ochre`, `--rule`, `--panel`, `--veil`, `--figure-card` and `--figure-blend` (`multiply` makes the build multiply figures into `--ground`, which must then be a six-digit hex; `normal` leaves them as they are) and may add furniture (a logo, a band) with ordinary CSS; `url(…)` paths in a theme are resolved relative to `house/themes/` and inlined. Contrast is checked per deck, so a new theme is tested with `node house/check.mjs house/demo --theme <name>`.

## Output

`_site/<deck>/index.html` is the deck: one self-contained file (fonts, reveal, figures and typeset math inlined), works offline and from `file://`. `S` opens reveal's speaker view with the notes. For a PDF, `decktape reveal --size 1920x1080 file://$PWD/_site/<deck>/index.html out.pdf`.

`_site/<deck>/report.html` is the same slides scaled into a scrolling document, each followed by its notes and details: the written version of the talk, from the same source.

Publishing: pushing to `main` runs `.github/workflows/publish.yml`, which runs `npm test` and `node house/check.mjs --all` (a failing deck stops the deploy), renders the Quarto site, builds every directory holding a `deck.json` into `_site/`, and lists non-draft house decks on the index (via `house-decks.yml`, generated with `node house/build.mjs --listing house-decks.yml`). The public URL is `https://cailmdaley.github.io/talks/<deck-dir>/`. Older Quarto decks build as before.
