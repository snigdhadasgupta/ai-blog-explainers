// Renders launch.html into an MP4 by stepping the timeline frame by frame.
// Deterministic: every frame is a pure seek(t), so output never depends on wall-clock speed.
//
//   node video/render.mjs                          # full 1080p render
//   node video/render.mjs --fps 24 --crf 24        # lighter/faster
//   node video/render.mjs --probe 0.8,7,17,26      # dump still PNGs to video/probe/
//   node video/render.mjs --start 41 --end 50      # render one section only
//
import { chromium } from './pw.mjs';
import { writeStats } from './stats.mjs';
import { spawn } from 'node:child_process';
import { mkdirSync, existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import { createRequire } from 'node:module';

const here = dirname(fileURLToPath(import.meta.url));

/* ---------- args ---------- */
const argv = process.argv.slice(2);
const arg = (name, def) => {
  const i = argv.indexOf('--' + name);
  return i === -1 ? def : argv[i + 1];
};
const has = (name) => argv.includes('--' + name);

const FPS = +arg('fps', 30);
const WIDTH = +arg('width', 1920);
const HEIGHT = +arg('height', 1080);
const CRF = +arg('crf', 20);
const OUT = resolve(here, arg('out', 'ai-blog-explainers-launch.mp4'));
const PROBE = arg('probe', null);
const QUIET = has('quiet');

/* ---------- locate ffmpeg (full build with libx264) ---------- */
function findFfmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const require = createRequire(import.meta.url);
  for (const id of ['ffmpeg-static', '@ffmpeg-installer/ffmpeg']) {
    try {
      const m = require(id);
      const p = typeof m === 'string' ? m : m.path;
      if (p && existsSync(p)) return p;
    } catch {
      /* next */
    }
  }
  // imageio-ffmpeg ships a full static build; pip install imageio-ffmpeg
  const candidates = [
    '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2',
    '/usr/bin/ffmpeg',
    '/usr/local/bin/ffmpeg',
  ];
  for (const p of candidates) if (existsSync(p)) return p;
  throw new Error('No ffmpeg with libx264 found. Set FFMPEG=/path/to/ffmpeg.');
}

/* ---------- refresh on-screen numbers from the live site ---------- */
const stats = writeStats();
if (!QUIET) console.log(`stats: ${stats.posts} posts -> "${stats.bucket}+", ${stats.sources} sources`);

/* ---------- browser ---------- */
const browser = await chromium.launch({
  args: ['--force-color-profile=srgb', '--disable-lcd-text', '--hide-scrollbars'],
});
const page = await browser.newPage({
  viewport: { width: WIDTH, height: HEIGHT },
  deviceScaleFactor: 1,
});
await page.goto(pathToFileURL(resolve(here, 'launch.html')).href + '?render=1', {
  waitUntil: 'load',
});
await page.evaluate(() => window.__ready);

const DURATION = await page.evaluate(() => window.DURATION);
const START = +arg('start', 0);
const END = Math.min(+arg('end', DURATION), DURATION);

/* ---------- probe mode: stills for design review ---------- */
if (PROBE) {
  const dir = resolve(here, 'probe');
  mkdirSync(dir, { recursive: true });
  for (const raw of PROBE.split(',')) {
    const t = +raw;
    await page.evaluate((tt) => window.seek(tt), t);
    const name = `t${String(t).replace('.', '_')}.png`;
    await page.screenshot({ path: resolve(dir, name) });
    console.log('probe', name);
  }
  await browser.close();
  process.exit(0);
}

/* ---------- encode ---------- */
const FFMPEG = findFfmpeg();
const total = Math.round((END - START) * FPS);

// Use the generated score if it is present; otherwise lay down a silent track,
// since some platforms mishandle a video with no audio stream at all.
const SCORE = resolve(here, 'score.wav');
const audioIn = existsSync(SCORE)
  ? ['-i', SCORE]
  : ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000'];
if (!QUIET) console.log(existsSync(SCORE) ? 'audio: score.wav' : 'audio: silent');

const args = [
  '-y',
  '-f', 'image2pipe',
  '-framerate', String(FPS),
  '-c:v', 'mjpeg',
  '-i', '-',
  ...audioIn,
  '-map', '0:v:0',
  '-map', '1:a:0',
  '-shortest',
  '-c:v', 'libx264',
  '-preset', 'slow',
  '-crf', String(CRF),
  '-profile:v', 'high',
  '-level', '4.1',
  '-pix_fmt', 'yuv420p',
  '-c:a', 'aac',
  '-b:a', '192k',
  '-r', String(FPS),
  '-movflags', '+faststart',
  OUT,
];

const ff = spawn(FFMPEG, args, { stdio: ['pipe', 'ignore', 'pipe'] });
let ffErr = '';
ff.stderr.on('data', (d) => (ffErr += d.toString()));
const done = new Promise((res, rej) =>
  ff.on('close', (code) => (code === 0 ? res() : rej(new Error('ffmpeg failed:\n' + ffErr.slice(-2500)))))
);

const write = (buf) =>
  ff.stdin.write(buf) ? Promise.resolve() : new Promise((r) => ff.stdin.once('drain', r));

const t0 = Date.now();
for (let i = 0; i < total; i++) {
  const t = START + i / FPS;
  await page.evaluate((tt) => window.seek(tt), t);
  const buf = await page.screenshot({ type: 'jpeg', quality: 95 });
  await write(buf);
  if (!QUIET && (i % 60 === 0 || i === total - 1)) {
    const pct = (((i + 1) / total) * 100).toFixed(1);
    const rate = (i + 1) / ((Date.now() - t0) / 1000);
    process.stdout.write(
      `\r  frame ${i + 1}/${total}  ${pct}%  ${rate.toFixed(1)} fps  eta ${Math.round((total - i - 1) / rate)}s   `
    );
  }
}
ff.stdin.end();
await done;
process.stdout.write('\n');

/* ---------- poster frame ---------- */
await page.evaluate(() => window.seek(4.0));   // title card makes the better poster
// poster.jpg is what the landing-page player loads — keep it in step with the
// film automatically, or it quietly drifts from whatever was rendered by hand.
await page.screenshot({ path: resolve(here, 'poster.jpg'), type: 'jpeg', quality: 82 });

await browser.close();
console.log(`\n✓ ${OUT}`);
console.log(`  ${WIDTH}x${HEIGHT} · ${FPS}fps · ${(END - START).toFixed(1)}s · crf ${CRF}`);
