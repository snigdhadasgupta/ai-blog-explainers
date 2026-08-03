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

`score.py` synthesizes the soundtrack from scratch — oscillators, envelopes, drum synthesis
and a Schroeder reverb, no samples and no library tracks — so there is nothing to license and no
attribution to carry.

A driving major-key anthem at ~117 BPM: four-on-the-floor, claps on 2 and 4, octave bass in
eighths, 16th-note arps, and a sidechain pump against the kick. Strictly major harmony
(F / Bb / C) voiced high and open — the minor sevenths and low pads are what made an earlier
pass sound wistful.

The beat runs from the logo hit (`DRUM_IN`, ~0.6s) to the last downbeat (`DRUM_OUT`, ~62.4s),
so the film opens and closes hot; sections differentiate by density via `section_gain()`, not by
dropping the drums. Everything cuts out for half a beat before the share-card grid (`GAP`) —
including the riser and the reverse crash — so the drop reads as −9 dB of silence followed by a
+12 dB slam.

The tempo is not arbitrary. `BAR` is derived so the bar grid — anchored at the drum entry —
lands within ~0.15s of the two cuts that matter most: the drop at 41.6s and the end card at
56.2s. Change a scene boundary in `launch.html` and the grid follows.

Mastering notes, both learned the hard way:

- **Master to true peak, not sample peak.** AAC reconstructs inter-sample peaks well above the
  source; this mix reads 0.46 sample / 0.61 true, a 2.5 dB gap. `true_peak()` oversamples 4× and
  the master normalizes against that, which is why the encoded file lands at 0.88 with no
  clipped samples instead of 1.10 with clipping.
- **Roll off above ~13 kHz.** The noise voices are tilted bright by repeated `diff()`, which
  piles energy exactly where AAC quantizes coarsest — that was most of the overshoot, and the
  hats sound better for it.
- **Watch the band balance.** A heavier kick plus a bass sitting at F1 once put 93% of the total
  energy below 140 Hz, which would have played as a muffled thud on laptop and phone speakers.
  The bass register moved up an octave and the kick's sub tail came down; it now sits at ~75%,
  with the melodic band roughly tripled.

Sits at about −14.2 dBFS RMS, peaking at 0.90 after encode with no clipped samples.

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
