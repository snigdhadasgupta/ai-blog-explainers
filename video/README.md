# Launch video

A 64-second launch film for **AI Blog Explainers**, rendered from HTML — no video editor, no external footage. The product shots are real screenshots of the live pages, and the share cards in the montage are the actual PNGs from `share-cards/`.

**Output:** `ai-blog-explainers-launch.mp4` — 1920×1080, 30 fps, H.264 + AAC, ~15 MB.
**Poster frame:** `poster.png`.

## Storyboard

| Time | Scene |
|---|---|
| 0:00 | Logo + wordmark cold open |
| 0:06 | The problem — a live stream of real headlines, "Nobody has time to read it all" |
| 0:15 | The pipeline — scan → explain → share |
| 0:23 | The homepage, scrolling, with callouts |
| 0:32 | An explainer page, scrolling |
| 0:41 | The share-card grid |
| 0:50 | Stats — 23 explainers, 7 sources, 0 manual steps, 24h cycle |
| 0:56 | Call to action + URL |

## How it works

`launch.html` is a 1920×1080 stage that exposes `window.seek(t)`. Every element's position and
opacity is a pure function of `t`, so there are no CSS transitions or `requestAnimationFrame`
timing — a frame renders identically no matter how fast the machine is.

`render.mjs` drives it: it steps `seek(t)` one frame at a time in headless Chromium, pipes each
screenshot straight into ffmpeg's stdin, and gets a deterministic MP4 out. Nothing is recorded in
real time, so a slow machine produces the same file as a fast one — just later.

Opened in a normal browser, `launch.html` plays itself on a loop for previewing.

## Music

`score.py` synthesizes the soundtrack from scratch — oscillators, envelopes and a
Schroeder reverb, no samples and no library tracks — so there is nothing to license and no
attribution to carry. Warm editorial ambient in F major at 82 BPM, arranged against the same
scene boundaries as the film: sparse under the cold open, tense under "nobody has time to read
it all", a pulse when the pipeline appears, a lift into the share-card grid, and a resolve on the
end card.

It masters to about −16 dBFS RMS with ~1 dB of true headroom, because AAC reconstructs
inter-sample peaks above the source level — mastering hot here comes back clipping.

## Re-rendering

```bash
node video/capture.mjs     # refresh the product screenshots from the current site
python3 video/score.py     # ~20 s → video/score.wav  (needs numpy)
node video/render.mjs      # ~4 min → video/ai-blog-explainers-launch.mp4
```

`render.mjs` picks up `score.wav` automatically when it exists, and falls back to a silent
track otherwise. To re-score without re-rendering 1,920 frames, just remux:

```bash
ffmpeg -i video/ai-blog-explainers-launch.mp4 -i video/score.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -shortest out.mp4
```

Useful flags:

```bash
node video/render.mjs --probe 6,23,41     # dump stills to video/probe/ for design review
node video/render.mjs --start 41 --end 50 # render one section while iterating
node video/render.mjs --fps 24 --crf 24   # faster, smaller
```

Requirements: Playwright (`npm i -D playwright`) and an ffmpeg built with libx264
(`pip install imageio-ffmpeg`, or set `FFMPEG=/path/to/ffmpeg`). The Playwright-bundled ffmpeg
will **not** work — it only ships the VP8/WebM encoder.

## Updating the copy

Facts shown on screen live at the top of the `<script>` in `launch.html`: `HEADLINES` (the
streaming titles), `CARDS` (which share cards appear in the grid), and the stat numbers in the
`#s7` markup. When the site's post count changes, update the `23` in `#s7` and re-render.

## Files

- `launch.html` — the film. Timeline, scenes, and copy.
- `score.py` — the soundtrack. Arrangement, voices, and mix.
- `render.mjs` — frame-stepper + encoder.
- `capture.mjs` — screenshots the live pages into `assets/`.
- `pw.mjs` — resolves Playwright from a local or global install.
- `fonts/`, `fonts.css` — Inter + Source Serif 4 (latin subset), vendored so renders are
  reproducible on any machine.
- `assets/`, `probe/`, `score.wav` — generated, git-ignored. Recreate with the commands above.
