import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 800 });

const errors = [];
page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
page.on('pageerror', e => errors.push('[PAGEERROR] ' + e.message));

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });
const btns = await page.$$('button');
for (const b of btns) {
  const t = await b.textContent();
  if (t && t.includes('비교')) { await b.click(); break; }
}

// Wait 8 seconds — at frame ~64 (beginning of squat motion)
await page.waitForTimeout(8000);
await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_v2_skelutils.png' });

// Wait 20 more seconds — at frame ~224 (deep squat)
await page.waitForTimeout(16000);
await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_v2_skelutils_deep.png' });

if (errors.length) console.log('Errors:', errors.slice(0,5).join('\n'));
else console.log('No errors');
await browser.close();
