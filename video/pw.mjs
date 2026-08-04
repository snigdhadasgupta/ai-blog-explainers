// Resolves Playwright whether it is installed locally or globally.
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CANDIDATES = ['playwright', '/opt/node22/lib/node_modules/playwright'];

let pw = null;
for (const id of CANDIDATES) {
  try {
    pw = require(id);
    break;
  } catch {
    /* try next */
  }
}
if (!pw) {
  throw new Error(
    'Playwright not found. Install it with `npm i -D playwright` (browsers: `npx playwright install chromium`).'
  );
}

export const { chromium } = pw;
