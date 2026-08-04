// Captures product screenshots of the live site pages into video/assets/.
// These are the "real UI" shots used by launch.html.
//   node video/capture.mjs
import { chromium } from './pw.mjs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const site = resolve(here, '..');
const out = resolve(here, 'assets');

// [file, output name, viewport height, full page?]
const SHOTS = [
  ['index.html', 'home-full.png', 900, true],
  ['index.html', 'home-top.png', 900, false],
  ['explainers/claude-opus-5.html', 'explainer-full.png', 900, true],
  ['share.html', 'share-full.png', 900, true],
  ['this-week.html', 'week-full.png', 900, true],
];

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();

for (const [file, name, height, full] of SHOTS) {
  await page.setViewportSize({ width: 1440, height });
  await page.goto(pathToFileURL(resolve(site, file)).href, { waitUntil: 'networkidle' });
  // Open every collapsed group so full-page shots show real content, not chevrons.
  await page.evaluate(() => document.querySelectorAll('details').forEach((d) => (d.open = true)));
  await page.waitForTimeout(400);
  await page.screenshot({ path: resolve(out, name), fullPage: full });
  const dims = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    document.documentElement.scrollHeight,
  ]);
  console.log(name, full ? `full ${dims[0]}x${dims[1]}` : `viewport 1440x${height}`);
}

await browser.close();
