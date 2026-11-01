# First Principles demo-video animations

Copied from Cail's mac, 1 Nov 2026. sha256 sums of the mac originals: `SHA256SUMS.mac` (all verified OK on candide).

## Paris mass map (Eiffel Tower at dusk, κ_E over Paris)
Both: 2500x1636, 30 fps, 12.0 s, H.264. Origin: `~/Downloads/unions-eiffel-composites/24h_reflect_4min/`.
- `eiffel_unions_24h_roof_reflection_4min_30fps_gold.mp4` (61 MB) — the "gold" variant used in the demo cut.
- `eiffel_unions_24h_roof_reflection_4min_30fps.mp4` (63 MB) — the earlier smooth render.
- Regenerate: `render_smooth_30fps.py` (built on `render_roof_reflection.py`); κ-plate method in `METHOD_exact_kappa_northern_v2.md` / `render_exact_kappa_v2.py`. No standalone map FITS/PNG sits beside the videos; the render scripts and the Gaia-colour/κ plates they read stay on the mac.

## DR6 mass map filling in (globe replay)
Origin: `first-principles-foundation/shots/replay/` in the loom. Regenerate: `replay_globe.py` (needs `--massmap` κ_E FITS).
- `dr6_globe.mp4` (8.9 MB) — 1920x1080, 30 fps, 22.7 s, full frame: globe on the left, date / object counter / area curve on the right.
- `dr6_globe_nostats_crop.mp4` (9.8 MB) — same clip cropped to x 0–1160, 1160x1080: globe only, no stats column (made with ffmpeg `crop=1160:1080:0:0`, re-encoded crf 14; not a native render).
- `dr6_globe_sheet.jpg` — contact sheet of the clip.
